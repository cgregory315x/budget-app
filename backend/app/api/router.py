from fastapi import APIRouter

from app.api.routes.accounts import router as accounts_router
from app.api.routes.categories import router as categories_router
from app.api.routes.health import router as health_router
from app.api.routes.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(
    transactions_router, prefix="/transactions", tags=["transactions"]
)
