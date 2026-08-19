from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.monthly_planning import validate_month
from app.schemas.monthly_summary import MonthlySummaryResponse
from app.services.monthly_summary import build_monthly_summary

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get("", response_model=MonthlySummaryResponse)
def monthly_summary(
    session: SessionDependency,
    month: Annotated[date, Query()],
) -> MonthlySummaryResponse:
    try:
        normalized_month = validate_month(month)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return build_monthly_summary(session, normalized_month)
