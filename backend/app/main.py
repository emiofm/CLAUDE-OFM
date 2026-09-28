from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import init_db
from .deps import default_client_factory, default_deps_factory, default_embedder_factory
from .logging_conf import setup_logging
from .routers import auth, creators, models_accounts, references, search, settings as settings_router
from .threads.errors import ThreadsAPIError


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    s.reference_upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Threads Purge API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Overridable factories (tests swap these for fakes).
    app.state.deps_factory = default_deps_factory
    app.state.client_factory = default_client_factory
    app.state.embedder_factory = default_embedder_factory
    app.state.oauth_transport = None

    @app.exception_handler(ThreadsAPIError)
    async def _threads_error(_: Request, exc: ThreadsAPIError):
        return JSONResponse(status_code=exc.status_code or 502, content=exc.to_dict())

    @app.get("/health")
    def health():
        return {"ok": True}

    for r in (
        auth.router,
        references.router,
        search.router,
        creators.router,
        models_accounts.router,
        settings_router.router,
    ):
        app.include_router(r)
    return app


app = create_app()
