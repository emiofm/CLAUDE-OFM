"""Models/Accs: models -> Threads accounts -> per-account profile lists."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Creator, ManagedAccount, Talent, TargetProfile
from ..serializers import creator_out
from ..usernames import normalize, parse_many
from ..utils import to_aware

router = APIRouter(prefix="/api", tags=["models-accounts"])


# ----------------------------------------------------------------- schemas
class TalentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class TalentPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    notes: str | None = Field(None, max_length=2000)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class AccountIn(BaseModel):
    username: str
    label: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)


class AccountPatch(BaseModel):
    username: str | None = None
    label: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=2000)
    position: int | None = None


class ProfilesIn(BaseModel):
    # Either free text ("@a, @b\nhttps://threads.net/@c") or a list.
    usernames: str | list[str]
    selected: bool = False
    source: str = Field("manual", pattern="^(manual|search)$")


class ProfilePatch(BaseModel):
    selected: bool | None = None
    note: str | None = Field(None, max_length=1000)


class BulkSelect(BaseModel):
    selected: bool
    ids: list[int] | None = None  # None = all profiles of the account


# ------------------------------------------------------------- serializers
def _profile_out(p: TargetProfile, creators: dict[str, Creator]) -> dict:
    c = creators.get(p.username)
    return {
        "id": p.id,
        "account_id": p.account_id,
        "username": p.username,
        "selected": p.selected,
        "note": p.note,
        "source": p.source,
        "created_at": to_aware(p.created_at),
        "profile_url": f"https://www.threads.net/@{p.username}",
        # Enrichment from the Profile Search Engine, when we have seen them.
        "creator": creator_out(c).model_dump() if c else None,
    }


def _creators_for(db: Session, usernames: list[str]) -> dict[str, Creator]:
    if not usernames:
        return {}
    rows = db.scalars(select(Creator).where(Creator.username.in_(usernames))).all()
    return {c.username: c for c in rows}


def _account_out(a: ManagedAccount, with_profiles: bool, db: Session) -> dict:
    out = {
        "id": a.id,
        "talent_id": a.talent_id,
        "username": a.username,
        "label": a.label,
        "notes": a.notes,
        "position": a.position,
        "created_at": to_aware(a.created_at),
        "profile_url": f"https://www.threads.net/@{a.username}",
        "profiles_total": len(a.profiles),
        "profiles_selected": sum(1 for p in a.profiles if p.selected),
    }
    if with_profiles:
        creators = _creators_for(db, [p.username for p in a.profiles])
        out["profiles"] = [_profile_out(p, creators) for p in a.profiles]
    return out


def _talent_out(t: Talent, db: Session, with_profiles: bool = False) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "notes": t.notes,
        "color": t.color,
        "created_at": to_aware(t.created_at),
        "accounts": [_account_out(a, with_profiles, db) for a in t.accounts],
    }


def _get(db: Session, cls, obj_id: int, what: str):
    obj = db.get(cls, obj_id)
    if obj is None:
        raise HTTPException(404, f"{what} not found")
    return obj


def _username_or_400(raw: str) -> str:
    u = normalize(raw)
    if u is None:
        raise HTTPException(400, f"'{raw}' is not a valid Threads username")
    return u


# ------------------------------------------------------------------ models
@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    talents = db.scalars(
        select(Talent)
        .options(selectinload(Talent.accounts).selectinload(ManagedAccount.profiles))
        .order_by(Talent.name)
    ).all()
    return [_talent_out(t, db) for t in talents]


@router.post("/models", status_code=201)
def create_model(body: TalentIn, db: Session = Depends(get_db)):
    t = Talent(name=body.name.strip(), notes=body.notes, color=body.color)
    db.add(t)
    db.commit()
    return _talent_out(t, db)


@router.get("/models/{talent_id}")
def get_model(talent_id: int, db: Session = Depends(get_db)):
    return _talent_out(_get(db, Talent, talent_id, "Model"), db, with_profiles=True)


@router.patch("/models/{talent_id}")
def update_model(talent_id: int, body: TalentPatch, db: Session = Depends(get_db)):
    t = _get(db, Talent, talent_id, "Model")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(t, k, v.strip() if isinstance(v, str) and k == "name" else v)
    db.commit()
    return _talent_out(t, db)


@router.delete("/models/{talent_id}")
def delete_model(talent_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, Talent, talent_id, "Model"))
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------- accounts
@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    """Flat list (used by the 'Add to list' picker in the search engine)."""
    rows = db.scalars(
        select(ManagedAccount)
        .options(selectinload(ManagedAccount.talent), selectinload(ManagedAccount.profiles))
        .order_by(ManagedAccount.talent_id, ManagedAccount.position, ManagedAccount.id)
    ).all()
    return [{**_account_out(a, False, db), "talent_name": a.talent.name} for a in rows]


@router.post("/models/{talent_id}/accounts", status_code=201)
def create_account(talent_id: int, body: AccountIn, db: Session = Depends(get_db)):
    t = _get(db, Talent, talent_id, "Model")
    username = _username_or_400(body.username)
    pos = db.scalar(select(func.coalesce(func.max(ManagedAccount.position), -1)).where(
        ManagedAccount.talent_id == talent_id)) + 1
    a = ManagedAccount(talent=t, username=username, label=body.label, notes=body.notes, position=pos)
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"@{username} is already an account of this model") from None
    return _account_out(a, True, db)


@router.get("/accounts/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    return _account_out(_get(db, ManagedAccount, account_id, "Account"), True, db)


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, body: AccountPatch, db: Session = Depends(get_db)):
    a = _get(db, ManagedAccount, account_id, "Account")
    data = body.model_dump(exclude_unset=True)
    if "username" in data:
        data["username"] = _username_or_400(data["username"] or "")
    for k, v in data.items():
        setattr(a, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Another account of this model already uses that username") from None
    return _account_out(a, True, db)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, ManagedAccount, account_id, "Account"))
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------- profiles
@router.post("/accounts/{account_id}/profiles")
def add_profiles(account_id: int, body: ProfilesIn, db: Session = Depends(get_db)):
    a = _get(db, ManagedAccount, account_id, "Account")
    valid, invalid = parse_many(body.usernames)
    if not valid and not invalid:
        raise HTTPException(400, "Enter at least one username")
    existing = {p.username for p in a.profiles}
    added, duplicates = [], []
    for u in valid:
        if u in existing:
            duplicates.append(u)
            continue
        a.profiles.append(TargetProfile(username=u, selected=body.selected, source=body.source))
        added.append(u)
    db.commit()
    return {
        "added": added,
        "duplicates": duplicates,
        "invalid": invalid,
        "account": _account_out(a, True, db),
    }


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: int, body: ProfilePatch, db: Session = Depends(get_db)):
    p = _get(db, TargetProfile, profile_id, "Profile")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return _profile_out(p, _creators_for(db, [p.username]))


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, TargetProfile, profile_id, "Profile"))
    db.commit()
    return {"deleted": True}


@router.post("/accounts/{account_id}/profiles/select")
def bulk_select(account_id: int, body: BulkSelect, db: Session = Depends(get_db)):
    a = _get(db, ManagedAccount, account_id, "Account")
    ids = set(body.ids) if body.ids is not None else None
    for p in a.profiles:
        if ids is None or p.id in ids:
            p.selected = body.selected
    db.commit()
    return _account_out(a, True, db)
