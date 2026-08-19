from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountType,
    Category,
    CategoryKind,
    MerchantRule,
    RuleMatchType,
    Transaction,
)
from app.main import create_app
from app.schemas.merchant_rules import (
    MerchantRuleCreate,
    MerchantRuleUpdate,
    RuleApplyDecision,
)
from app.services import merchant_rules


def seed(session: Session) -> tuple[Category, Category, Transaction, Transaction]:
    account = Account(
        name="Test checking",
        institution="Synthetic",
        account_type=AccountType.CHECKING,
        currency="USD",
        archived=False,
    )
    groceries = Category(
        name="Groceries", kind=CategoryKind.EXPENSE, color="#123456", archived=False
    )
    coffee = Category(name="Coffee", kind=CategoryKind.EXPENSE, color="#654321", archived=False)
    session.add_all([account, groceries, coffee])
    session.flush()
    uncategorized = Transaction(
        account_id=account.id,
        posted_date=date(2026, 8, 1),
        description="ACME-MARKET #42",
        merchant_normalized="ACME MARKET 42",
        amount=Decimal("-12.50"),
        fingerprint="a" * 64,
        occurrence_index=1,
        excluded_from_budget=False,
    )
    assigned = Transaction(
        account_id=account.id,
        category_id=coffee.id,
        posted_date=date(2026, 8, 2),
        description="ACME MARKET",
        merchant_normalized="ACME MARKET",
        amount=Decimal("-5.00"),
        fingerprint="b" * 64,
        occurrence_index=1,
        excluded_from_budget=False,
    )
    session.add_all([uncategorized, assigned])
    session.commit()
    return groceries, coffee, uncategorized, assigned


def make_rule(
    session: Session, category: Category, **changes: object
) -> MerchantRule:
    values: dict[str, object] = {
        "pattern": "Acme Market",
        "match_type": "contains",
        "category_id": category.id,
        "priority": 100,
        "enabled": True,
    }
    values.update(changes)
    return merchant_rules.create_rule(session, MerchantRuleCreate.model_validate(values))


def test_rule_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]
    assert set(paths["/api/v1/merchant-rules"]) == {"get", "post"}
    assert set(paths["/api/v1/merchant-rules/{rule_id}"]) == {"patch", "delete"}
    assert "/api/v1/merchant-rules/matches/preview" in paths
    assert "/api/v1/merchant-rules/matches/apply" in paths


def test_rule_crud_normalizes_and_requires_active_category(db_session: Session) -> None:
    groceries, _, _, _ = seed(db_session)
    rule = make_rule(db_session, groceries)
    assert rule.pattern == "Acme Market"
    assert rule.pattern_normalized == "ACME MARKET"
    updated = merchant_rules.update_rule(
        db_session, rule.id, MerchantRuleUpdate.model_validate({"priority": 10})
    )
    assert updated.priority == 10
    assert merchant_rules.disable_rule(db_session, rule.id).enabled is False
    groceries.archived = True
    db_session.commit()
    with pytest.raises(merchant_rules.MerchantRuleReferenceError):
        make_rule(db_session, groceries, pattern="Other")
    merchant_rules.delete_rule(db_session, rule.id)
    with pytest.raises(merchant_rules.MerchantRuleNotFoundError):
        merchant_rules.get_rule(db_session, rule.id)


def test_preview_precedence_and_apply_never_overwrite(db_session: Session) -> None:
    groceries, coffee, uncategorized, assigned = seed(db_session)
    broad = make_rule(db_session, coffee, pattern="Acme", priority=100)
    winner = make_rule(
        db_session,
        groceries,
        match_type="exact",
        pattern="ACME MARKET 42",
        priority=100,
    )
    matches, unmatched = merchant_rules.preview_matches(db_session)
    assert unmatched == 0
    assert len(matches) == 1
    assert matches[0].transaction.id == uncategorized.id
    assert matches[0].rule.id == winner.id
    assert matches[0].competing_rule_ids == (broad.id,)

    applied, skipped, learned = merchant_rules.apply_matches(
        db_session,
        [
            RuleApplyDecision(
                transaction_id=uncategorized.id,
                category_id=groceries.id,
            ),
            RuleApplyDecision(
                transaction_id=assigned.id,
                category_id=groceries.id,
            ),
        ],
    )
    assert (applied, skipped, learned) == (1, 1, 0)
    db_session.refresh(uncategorized)
    db_session.refresh(assigned)
    assert uncategorized.category_id == groceries.id
    assert assigned.category_id == coffee.id


def test_lower_priority_number_wins_conflict(db_session: Session) -> None:
    groceries, coffee, _, _ = seed(db_session)
    make_rule(db_session, groceries, pattern="Acme", priority=20)
    preferred = make_rule(db_session, coffee, pattern="Market", priority=10)
    matches, _ = merchant_rules.preview_matches(db_session)
    assert matches[0].rule.id == preferred.id


def test_correction_can_learn_and_refine_exact_rule(db_session: Session) -> None:
    groceries, coffee, uncategorized, _ = seed(db_session)
    make_rule(db_session, groceries, pattern="Acme", priority=100)

    result = merchant_rules.apply_matches(
        db_session,
        [
            RuleApplyDecision(
                transaction_id=uncategorized.id,
                category_id=coffee.id,
                save_exact_rule=True,
            )
        ],
    )

    assert result == (1, 0, 1)
    db_session.refresh(uncategorized)
    assert uncategorized.category_id == coffee.id
    exact = db_session.query(MerchantRule).filter_by(
        pattern_normalized="ACME MARKET 42",
        match_type=RuleMatchType.EXACT,
    ).one()
    assert exact.category_id == coffee.id
    assert exact.enabled is True


def test_apply_skips_archived_correction_category(db_session: Session) -> None:
    groceries, coffee, uncategorized, _ = seed(db_session)
    make_rule(db_session, groceries)
    coffee.archived = True
    db_session.commit()

    result = merchant_rules.apply_matches(
        db_session,
        [
            RuleApplyDecision(
                transaction_id=uncategorized.id,
                category_id=coffee.id,
                save_exact_rule=True,
            )
        ],
    )

    assert result == (0, 1, 0)
    db_session.refresh(uncategorized)
    assert uncategorized.category_id is None
