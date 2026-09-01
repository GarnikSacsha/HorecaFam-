from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.clock import utc_now
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.observability import configure_observability
from app.core.request_id import RequestIDMiddleware
from app.db.session import create_engine, create_session_factory
from app.security.passwords import PasswordManager


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_observability(resolved_settings)
    application = FastAPI(title="HoReCa Training Platform API")
    application.state.settings = resolved_settings
    application.state.clock = utc_now
    application.state.password_manager = PasswordManager()
    application.state.private_storage = None
    application.state.engine = create_engine(resolved_settings)
    application.state.session_factory = create_session_factory(application.state.engine)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Request-ID"],
    )
    application.add_middleware(RequestIDMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)
    return application
