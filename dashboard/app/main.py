"""Application entrypoint: FastAPI + REST API + NiceGUI UI in one process."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.presentation.api.v1.errors import register_exception_handlers
from app.presentation.api.v1.router import api_router
from app.presentation.ui.router import register_pages

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger("main")

app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="AI Software Factory — Dashboard REST API (Phase 1 foundation)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


# -- Mount the NiceGUI UI onto the same FastAPI app -------------------------
from nicegui import ui  # noqa: E402

register_pages()
ui.run_with(
    app,
    title=settings.app_name,
    storage_secret=settings.supabase_jwt_secret or "dev-storage-secret",
    dark=True,
)


def main() -> None:
    import uvicorn

    log.info("starting", host=settings.app_host, port=settings.app_port)
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=not settings.is_production,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
