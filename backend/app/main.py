from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.db.init_db import init_db
from app.services.storage import ensure_data_directories


def create_app() -> FastAPI:
    """
    Application factory for the Hoffmann Lab cow monitoring API.
    """
    ensure_data_directories()
    init_db()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Data ingestion and storage API for cow uterine contraction and bolus data.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {
            "message": "Hoffmann Lab Cow Monitoring API",
            "docs": "/docs",
            "health": "/api/health",
        }

    app.include_router(router, prefix=settings.API_PREFIX)

    return app


app = create_app()