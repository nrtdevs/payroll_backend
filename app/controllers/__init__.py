from app.controllers.auth_controller import router as auth_router
from app.controllers.attendance_controller import router as attendance_router
from app.controllers.master_controller import router as master_router
from app.controllers.owner_controller import router as owner_router
from app.controllers.user_controller import router as user_router

__all__ = ["auth_router", "attendance_router", "master_router", "owner_router", "user_router"]
