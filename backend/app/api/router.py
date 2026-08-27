from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.employees import router as employees_router
from app.api.routes.health import router as health_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.menus import router as menus_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(invitations_router)
api_router.include_router(employees_router)
api_router.include_router(menus_router)
