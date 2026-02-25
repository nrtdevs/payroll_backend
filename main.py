from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controllers.auth_controller import router as auth_router
from app.controllers.attendance_controller import router as attendance_router
from app.controllers.master_controller import router as master_router
from app.controllers.owner_controller import router as owner_router
from app.controllers.user_controller import router as user_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
    )
    register_exception_handlers(app)

    app.include_router(auth_router)
    app.include_router(attendance_router)
    app.include_router(master_router)
    app.include_router(owner_router)
    app.include_router(user_router)
    return app


app = create_app()
