"""Collapse keyword-search posts into unique creators."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CandidateCreator:
    username: str
    posts: dict[str, dict] = field(default_factory=dict)  # threads_post_id -> post
    keywords: set[str] = field(default_factory=set)
    post_keywords: dict[str, set[str]] = field(default_factory=dict)

    @property
    def hit_count(self) -> int:
        return len(self.posts)


def normalize_username(username: str | None) -> str | None:
    if not username:
        return None
    u = username.strip().lstrip("@").lower()
    return u or None


def dedupe_creators(results_by_keyword: dict[str, list[dict]]) -> dict[str, CandidateCreator]:
    """One entry per creator, however many of their posts matched.

    Posts are also de-duplicated by id across keywords, and each post keeps the
    set of keywords that surfaced it.
    """
    creators: dict[str, CandidateCreator] = {}
    for keyword, posts in results_by_keyword.items():
        for post in posts:
            username = normalize_username(post.get("username"))
            post_id = post.get("id")
            if not username or not post_id:
                continue
            c = creators.setdefault(username, CandidateCreator(username=username))
            c.posts.setdefault(str(post_id), post)
            c.keywords.add(keyword)
            c.post_keywords.setdefault(str(post_id), set()).add(keyword)
    return creators


def rank_candidates(creators: dict[str, CandidateCreator], limit: int) -> list[CandidateCreator]:
    """Pre-select candidates to analyse (most keyword hits first)."""
    return sorted(
        creators.values(), key=lambda c: (len(c.keywords), c.hit_count), reverse=True
    )[:limit]
