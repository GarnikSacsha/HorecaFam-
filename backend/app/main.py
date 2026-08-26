from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.request_id import RequestIDMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(title="HoReCa Training Platform API")
    application.state.settings = resolved_settings
    application.add_middleware(RequestIDMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)
    return application
