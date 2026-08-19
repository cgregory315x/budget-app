from fastapi import APIRouter

from app.api.routes.accounts import router as accounts_router
from app.api.routes.categories import router as categories_router
from app.api.routes.health import router as health_router
from app.api.routes.monthly_planning import budget_router, income_router
from app.api.routes.monthly_summary import router as summary_router
from app.api.routes.transactions import router as transactions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(categories_router, prefix="/categories", tags=["categories"])
api_router.include_router(
    transactions_router, prefix="/transactions", tags=["transactions"]
)
api_router.include_router(budget_router, prefix="/budgets", tags=["budgets"])
api_router.include_router(income_router, prefix="/income", tags=["income"])
api_router.include_router(summary_router, prefix="/summary", tags=["summary"])
