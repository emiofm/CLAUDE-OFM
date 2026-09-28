# Creator Finder

An internal tool for finding **Threads** accounts that:

1. look visually similar (overall aesthetic, not identity) to a reference model,
2. have posted recently,
3. have a meaningful audience, **when the official API reports one**,
4. show creator / *possible* monetization signals,
5. are ranked by a configurable score.

It has a FastAPI backend, a Next.js frontend, SQLite for development and PostgreSQL for production, and a CLIP/SigLIP image-embedding pipeline. All data comes from the **official Threads API**. It does no scraping, never tries to get around rate limits, never fills in metrics that are missing, and does no face recognition.

```
Upload 3-20 reference images → embeddings → centroid
Keywords → GET /keyword_search (paginated) → collect posts → dedupe creators
→ GET /profile_lookup (profile, follower_count if returned) → GET /profile_posts (activity)
→ download post images in memory → embeddings → similarity vs. centroid
→ activity score → creator/monetization signals → engagement (if real counts exist)
→ weighted ranking → results UI (save / ignore / open Threads)
```

---

## Repository layout

```
backend/
  app/
    main.py                FastAPI app, CORS, error handler
    config.py              env settings (secrets only server-side)
    db.py, models.py       SQLAlchemy models (Creator, Post, ReferenceSet, ReferenceImage,
                           SearchJob, SearchResult, ThreadsConnection, CacheEntry, AppSetting)
    schemas.py, serializers.py
    logging_conf.py        [TAG] key=value logs + secret redaction
    data_availability.py   what the official API does / doesn't provide
    deps.py                runtime wiring (overridable in tests)
    threads/
      client.py            Threads Graph API client (pagination, budgets, 429 handling)
      errors.py            typed errors + user-facing messages (401/403/429/5xx)
      oauth.py             OAuth code exchange, long-lived token, refresh, debug_token
    services/
      pipeline.py          the search pipeline
      audience.py          AudienceProvider / OfficialThreadsAudienceProvider
      embeddings.py        CLIP/SigLIP (transformers) + debug colour-histogram embedder
      similarity.py        centroid, cosine → 0-100, 70% best + 30% top-5 aggregation
      scoring.py           activity, signals, keyword relevance, engagement, ranking, filters
      dedup.py, cache.py, images.py, app_config.py
    routers/               auth, references, search, creators, settings
  tests/                   pytest suite (78 tests)
  requirements.txt, requirements-ml.txt, requirements-dev.txt, Dockerfile
frontend/
  app/page.tsx             search + results
  app/saved/page.tsx       saved / ignored creators
  app/settings/page.tsx    Threads connection, scopes, tests, weights, TTLs, data availability
  components/, lib/        UI components, typed API client
docker-compose.yml         postgres + backend + frontend
.env.example
```

---

## 1. Install

Requirements: Python 3.11+, Node 20+ (22 recommended). Docker is optional.

```bash
cp .env.example .env            # then fill in THREADS_APP_ID / THREADS_APP_SECRET

# backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
# real image embeddings (CLIP / SigLIP). CPU wheels:
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ml.txt

# frontend
cd ../frontend
npm install
```

If you can't install torch yet, set `EMBEDDING_MODEL=debug-color-histogram` in `.env`. That fallback needs no extra dependencies but only compares colour and layout, so it is **not** meaningful for real searches.

## 2. Run locally

```bash
# terminal 1
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000       # API docs: http://localhost:8000/docs

# terminal 2
cd frontend
npm run dev                                     # http://localhost:3000
```

SQLite is used by default (`backend/data/creator_finder.db`) and the tables are created on startup.

With Docker (PostgreSQL):

```bash
docker compose up --build        # frontend :3000, backend :8000, postgres :5432
```

Tests:

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

## 3. Create a Meta / Threads app

1. Go to <https://developers.facebook.com/apps> → **Create app**.
2. Choose the use case **"Access the Threads API"**.
3. In **Use cases → Access the Threads API → Customize**, add these permissions:
   - `threads_basic` (required for every call)
   - `threads_keyword_search` (the `keyword_search` endpoint)
   - `threads_profile_discovery` (the `profile_lookup` and `profile_posts` endpoints)
4. In **App roles → Roles**, add your Threads account as a **Threads Tester** and accept the invite in the Threads app (Settings → Account → Website permissions → Invites).
5. For production use on other people's public content, submit the permissions for **App Review**. Until `threads_keyword_search` is approved, keyword search only returns posts **owned by the authenticated user**.

## 4. Configure OAuth

Under **Use cases → Threads API → Settings**, set:

- **Redirect Callback URLs**: the value of `THREADS_REDIRECT_URI`, e.g. `https://<your-host>/auth/threads/callback`
- **Uninstall / Delete callback URLs**: any URL you control (required by Meta)

Meta requires HTTPS redirect URIs. For local development, expose the backend through an HTTPS tunnel (for example `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`). Then set:

```
THREADS_REDIRECT_URI=https://<tunnel-host>/auth/threads/callback
```

It must match the Meta setting **exactly**.

The backend implements:

| Route | Purpose |
|---|---|
| `GET /auth/threads` | Redirects to `https://threads.net/oauth/authorize` with `client_id`, `redirect_uri`, `scope`, `response_type=code` and a CSRF `state` stored in an httpOnly cookie |
| `GET /auth/threads/callback` | Checks `state`, then `POST /oauth/access_token` (code → short-lived token), then `GET /access_token?grant_type=th_exchange_token` (→ 60-day long-lived token), then `debug_token` (granted scopes) and `/me`, and stores the token server-side |
| `POST /auth/threads/refresh` | `GET /refresh_access_token?grant_type=th_refresh_token`. This also runs automatically before a search when fewer than 7 days remain and the token is at least 24 h old |
| `POST /auth/threads/disconnect` | Deletes the stored token |

Tokens are stored only in the database. Set `TOKEN_ENCRYPTION_KEY` to Fernet-encrypt them at rest. They are never sent to the browser, never put in URLs (API calls use `Authorization: Bearer`), and are redacted from logs.

## 5. Add `THREADS_APP_ID`

Copy the **Threads App ID** from **Use cases → Threads API → Settings**. It is not the same as the Facebook App ID shown in the dashboard header. Put it in `.env`:

```
THREADS_APP_ID=1234567890
```

## 6. Add `THREADS_APP_SECRET`

On the same page, click **Show** next to **Threads App Secret** and put it in `.env`:

```
THREADS_APP_SECRET=abcdef...
```

Only the backend reads this file. Never put it in `NEXT_PUBLIC_*` variables or in frontend code.

## 7. Get the access token through OAuth

1. Start the backend and frontend.
2. Open **Settings** (<http://localhost:3000/settings>) and click **Connect Threads**.
3. Log in to Threads and approve the permissions.
4. You are sent back to Settings, which should show **Connected** with your username, the granted scopes and the token expiry.
5. Click **Test API connection**. This calls `GET /me`.

Alternative: paste a long-lived token generated in Meta's dashboard into `THREADS_ACCESS_TOKEN`. A token stored through OAuth takes precedence over it.

## 8. Test keyword search

- **UI:** Settings → *Test keyword search*. This runs one page of `keyword_search`, which counts as one query against the 24 h limit.
- **API:**
  ```bash
  curl -X POST localhost:8000/api/settings/test-keyword-search \
       -H 'content-type: application/json' -d '{"q":"coffee"}'
  ```
- **Full search:**
  ```bash
  curl -X POST localhost:8000/api/search -H 'content-type: application/json' \
       -d '{"keywords":["brunette","lifestyle creator"],"filters":{"min_posts_30d":5}}'
  curl localhost:8000/api/search/1            # job status / progress / warnings
  curl 'localhost:8000/api/search/1/results?sort=best'
  ```

## 9. How image embeddings work

- Reference images (3–20 JPG/PNG/WEBP) are embedded with `EMBEDDING_MODEL`, by default `openai/clip-vit-base-patch32`. Any Hugging Face CLIP or SigLIP checkpoint works, for example `google/siglip-base-patch16-224`. Only the image tower (`get_image_features`) is used.
- The embeddings are L2-normalised and averaged into a **centroid**, which is stored on the `ReferenceSet`.
- For each candidate creator, up to `max_images_per_creator` image posts are used (the `media_url` of images, the `thumbnail_url` of videos). Posts that matched the search come first, then the most recent. Each image is downloaded **into memory**, embedded and discarded. Only the vector is cached on `Post.image_embedding`, and it is deleted after the embedding TTL.
- The per-image cosine to the centroid is mapped to 0–100 through a configurable window (`cosine_floor` → 0 %, `cosine_ceiling` → 100 %; defaults 0.5 / 0.95, which suit CLIP image–image similarity).
- Creator similarity = **70 % best image + 30 % mean of the top 5 images**. Both weights and *k* are configurable.
- This compares visual and content aesthetic: palette, lighting, hair colour, makeup and clothing style, setting, composition and photographic style. **No face detection, face recognition or biometric identification is performed.**
- Reference uploads are the user's own files and stay under `backend/data/references/` until the set is deleted. Third-party images are never written to disk.

## Scoring

Default weights (editable in Settings):

| Component | Weight |
|---|---|
| visual_similarity | 45 |
| activity | 25 |
| engagement | 15 |
| creator_signal | 10 |
| keyword_relevance | 5 |
| audience | 0 (applies only when a real follower count exists) |

Every component is either 0–100 or **unavailable (`null`)**. Unavailable components are **left out**, and the remaining weights are re-normalised. Missing data is never counted as zero or estimated. Each result's `score_breakdown` shows the effective weights and which components were unavailable.

**Activity** = 35 % posts in 7 d + 40 % posts in 30 d + 15 % posts in 90 d + 10 % recency. Recency decays with a 14-day half-life. Each count saturates at a target (5 / 20 / 50), so extra posts add nothing beyond it. Accounts averaging more than `spam_posts_per_day` are damped, so spam isn't rewarded.

**Creator signal** matches terms in the bio and post text: onlyfans, OF (case-sensitive), fansly, link in bio, linktree, beacons, allmylinks, exclusive, VIP, subscribe, fans, content creator, creator, model, and so on. Monetization terms are only ever shown as **"Possible monetization signal"**. They do not claim that someone has any account.

**Filters.** A known value below a minimum excludes the creator. An unknown value lets the creator through with a flag such as "Followers unknown", unless *"Exclude creators whose filtered metrics are unavailable"* is ticked. Activity counted only from keyword-search hits is a lower bound: reaching the minimum is conclusive, falling short is flagged "unverified".

## 10. Current API limitations

- `keyword_search` searches **posts only**. There is no people search, and no search by image or appearance. Results depend on Meta's ranking (`TOP` or `RECENT`).
- Without App Review approval of `threads_keyword_search`, only **your own** posts are returned.
- Meta documents **2,200 keyword-search queries per user per rolling 24 h**. Each *page* counts as a query. The app keeps its own sliding-window budget (`THREADS_KEYWORD_SEARCH_DAILY_BUDGET`, default 500) and a budget for profile-discovery calls (`THREADS_PROFILE_DAILY_BUDGET`). On HTTP 429 or Meta throttling codes it waits only if Meta sends a short `Retry-After`. Otherwise it stops and reports the limit.
- `profile_lookup` needs an **exact username** and `threads_profile_discovery`. Meta returns only profiles it makes discoverable, so some creators will have no profile data.
- `media_url` values are temporary CDN links and expire, so the UI hot-links them and caches nothing permanently.
- Carousel children are not expanded (that would cost one extra call per post). The parent `media_url` is used when present.
- The official endpoints and fields were checked against Meta's Threads API reference as mirrored in maintained client libraries. developers.facebook.com could not be reached from the build environment, so re-check the linked docs if Meta changes the API.

## 11. Metrics NOT available through the official Threads API

| Metric | What the app does |
|---|---|
| Follower / following **lists** of third parties | Not implemented. No endpoint exists |
| Per-post likes / replies / reposts of **other people's** posts | `Post.likes` / `Post.replies` stay `NULL`. Insights exist only for your own media |
| Follower count when `profile_lookup` isn't permitted or omits it | Shown as **"Follower count unavailable from official Threads API"** and excluded from the score |
| Profile-level likes / replies when not returned | "Unavailable" |
| Exact 7/30/90-day activity without `threads_profile_discovery` | Shown as a lower bound from keyword-search hits and marked as such |
| Link-in-bio destinations / monetisation platforms | Only a *possible* signal from text |

What **is** used, and only when Meta returns it: the `follower_count`, `likes_count`, `replies_count`, `reposts_count`, `quotes_count` and `views_count` fields of `profile_lookup`. These are labelled with their source in the UI and the API (`followers.source = "threads_profile_lookup"`).

## 12. Adding a future AudienceProvider

`backend/app/services/audience.py`:

```python
class AudienceProvider(ABC):
    name: str
    @abstractmethod
    async def get_follower_count(self, username: str) -> int | None: ...
```

`OfficialThreadsAudienceProvider` reads `follower_count` from `profile_lookup` and returns `None` when the field is missing, not permitted or not found.

To add a compliant third-party source:

```python
class AcmeAudienceProvider(AudienceProvider):
    name = "acme"                          # stored in Creator.follower_source
    def __init__(self, api_key: str): ...
    async def get_follower_count(self, username: str) -> int | None:
        # call the provider's documented API; return None when unknown
        ...
```

Then return it from `default_deps_factory` in `backend/app/deps.py`, for example as a fallback chain (official first, then Acme). The pipeline, database (`follower_count`, `follower_source`, `follower_last_checked`), filters, `audience` score weight and UI already handle it. Only use providers whose terms allow this data use.

---

## API overview

| Method | Path | |
|---|---|---|
| POST | `/api/reference-sets` | multipart `files` (3–20) + `name` |
| GET | `/api/reference-sets[/{id}]` | list / detail |
| POST | `/api/search` | `{reference_set_id?, keywords[], filters{}}` → job |
| GET | `/api/search/{id}` | status, progress, warnings, error |
| GET | `/api/search/{id}/results?sort=best\|active\|engagement\|newest` | ranked results |
| POST | `/api/creators/{id}/save\|ignore\|reset` | |
| GET | `/api/creators?status=saved\|ignored` | saved-creators page |
| GET/PUT | `/api/settings` | config, connection, scopes, data availability |
| POST | `/api/settings/test-connection`, `/api/settings/test-keyword-search` | |

## Logging

```
[THREADS] keyword search started keyword=brunette search_type=TOP
[THREADS] keyword search finished keyword=brunette results_received=50
[THREADS] deduplicated posts=120 unique_creators=37 analysing=37
[EMBEDDING] processing images count=8
[SCORING] creator=@example similarity=0.91 activity=74.2 total=81.3 passes=True
```

Access tokens, `client_secret`, `input_token`, Bearer headers and `TH|…` app tokens are redacted by the log formatter.

## Compliance notes

- Official endpoints only. Pagination follows Meta's cursors with page and item caps. No scraping, no CAPTCHA or authentication bypass, no evasion of rate limits.
- Nothing is fabricated: unknown values are stored as `NULL` and shown as unavailable.
- Visual similarity only. No biometric processing.
- Third-party data is cached only as long as needed, with configurable TTLs for profiles, posts and embeddings. Expired rows are purged after each search.
