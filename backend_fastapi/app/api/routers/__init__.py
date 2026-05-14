from .auth import router as auth_router
from .books import router as books_router
from .borrow import router as borrow_router
from .health import router as health_router
from .users import router as users_router

__all__ = ["auth_router", "books_router", "borrow_router", "health_router", "users_router"]
