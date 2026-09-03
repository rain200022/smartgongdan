from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    app_settings = get_settings()
    application = FastAPI(title=app_settings.app_name, version=__version__)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    register_exception_handlers(application)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
