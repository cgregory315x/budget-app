import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.categorization.merchant import normalize_merchant
from app.db.session import get_db_session
from app.schemas.merchant_rules import (
    MerchantRuleCreate,
    MerchantRuleResponse,
    MerchantRuleUpdate,
    RuleApplyRequest,
    RuleApplyResponse,
    RuleMatchPreview,
    RulePreviewResponse,
)
from app.services import merchant_rules

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Merchant rule not found")


def _save_error(error: Exception) -> HTTPException:
    if isinstance(
        error,
        (
            merchant_rules.MerchantRuleReferenceError,
            merchant_rules.MerchantRulePatternError,
        ),
    ):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=409, detail="A rule already uses that pattern and match type")


@router.get("", response_model=list[MerchantRuleResponse])
def list_all(session: SessionDependency) -> list[MerchantRuleResponse]:
    return [
        MerchantRuleResponse.model_validate(rule) for rule in merchant_rules.list_rules(session)
    ]


@router.post("", response_model=MerchantRuleResponse, status_code=status.HTTP_201_CREATED)
def create(data: MerchantRuleCreate, session: SessionDependency) -> MerchantRuleResponse:
    try:
        rule = merchant_rules.create_rule(session, data)
    except (
        merchant_rules.MerchantRuleReferenceError,
        merchant_rules.MerchantRulePatternError,
        merchant_rules.MerchantRuleConflictError,
    ) as error:
        raise _save_error(error) from error
    return MerchantRuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=MerchantRuleResponse)
def update(
    rule_id: uuid.UUID, data: MerchantRuleUpdate, session: SessionDependency
) -> MerchantRuleResponse:
    try:
        rule = merchant_rules.update_rule(session, rule_id, data)
    except merchant_rules.MerchantRuleNotFoundError as error:
        raise _not_found() from error
    except (
        merchant_rules.MerchantRuleReferenceError,
        merchant_rules.MerchantRulePatternError,
        merchant_rules.MerchantRuleConflictError,
    ) as error:
        raise _save_error(error) from error
    return MerchantRuleResponse.model_validate(rule)


@router.post("/{rule_id}/disable", response_model=MerchantRuleResponse)
def disable(rule_id: uuid.UUID, session: SessionDependency) -> MerchantRuleResponse:
    try:
        rule = merchant_rules.disable_rule(session, rule_id)
    except merchant_rules.MerchantRuleNotFoundError as error:
        raise _not_found() from error
    return MerchantRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(rule_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        merchant_rules.delete_rule(session, rule_id)
    except merchant_rules.MerchantRuleNotFoundError as error:
        raise _not_found() from error
    return Response(status_code=204)


@router.post("/matches/preview", response_model=RulePreviewResponse)
def preview(session: SessionDependency) -> RulePreviewResponse:
    matches, unmatched = merchant_rules.preview_matches(session)
    return RulePreviewResponse(
        matches=[
            RuleMatchPreview(
                transaction_id=match.transaction.id,
                description=match.transaction.description,
                merchant_normalized=match.transaction.merchant_normalized
                or normalize_merchant(match.transaction.description),
                posted_date=match.transaction.posted_date.isoformat(),
                amount=str(match.transaction.amount),
                rule_id=match.rule.id,
                rule_pattern=match.rule.pattern,
                category_id=match.rule.category_id,
                category_name=match.rule.category.name,
                competing_rule_ids=list(match.competing_rule_ids),
            )
            for match in matches
        ],
        unmatched_count=unmatched,
    )


@router.post("/matches/apply", response_model=RuleApplyResponse)
def apply(data: RuleApplyRequest, session: SessionDependency) -> RuleApplyResponse:
    applied, skipped = merchant_rules.apply_matches(session, data.transaction_ids)
    return RuleApplyResponse(applied_count=applied, skipped_count=skipped)
