from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.repositories import get_repository
from app.repositories.memory import InMemoryRepository
from app.services.demo_data import seed_demo_data


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Apply Postgres migrations if using postgres repository
    if settings.repository_type == "postgres" and settings.database_url:
        from app.db.migrate import apply_migrations

        apply_migrations(settings.database_url)

    app.include_router(api_router, prefix=settings.api_prefix)

    repo = get_repository()
    if settings.seed_demo_data and isinstance(repo, InMemoryRepository):
        seed_demo_data(repo)

    frontend_dist = settings.frontend_dist or Path(__file__).resolve().parents[2] / "static"
    index_html = frontend_dist / "index.html"
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if index_html.exists():

        @app.get("/")
        def serve_index() -> FileResponse:
            return FileResponse(index_html)

        @app.get("/{path:path}")
        def serve_spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                return FileResponse(index_html, status_code=404)
            return FileResponse(index_html)

    else:

        @app.get("/")
        def api_root() -> dict[str, str]:
            return {"service": settings.app_name, "docs": "/docs", "health": f"{settings.api_prefix}/health"}

    return app


app = create_app()


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
