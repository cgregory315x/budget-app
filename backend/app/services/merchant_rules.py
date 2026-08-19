import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.categorization.merchant import normalize_merchant, normalize_regex_pattern
from app.db.models import (
    CategorizationSource,
    Category,
    MerchantRule,
    RuleMatchType,
    Transaction,
)
from app.schemas.merchant_rules import (
    MerchantRuleCreate,
    MerchantRuleUpdate,
    RuleApplyDecision,
)


class MerchantRuleNotFoundError(Exception):
    pass


class MerchantRuleConflictError(Exception):
    pass


class MerchantRuleReferenceError(Exception):
    pass


class MerchantRulePatternError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Match:
    transaction: Transaction
    rule: MerchantRule
    competing_rule_ids: tuple[uuid.UUID, ...]


def _active_category(session: Session, category_id: uuid.UUID) -> None:
    category = session.get(Category, category_id)
    if category is None or category.archived:
        raise MerchantRuleReferenceError("Category is unavailable")


def _normalized_pattern(pattern: str, match_type: RuleMatchType) -> str:
    normalized = (
        normalize_regex_pattern(pattern)
        if match_type == RuleMatchType.REGEX
        else normalize_merchant(pattern)
    )
    if match_type == RuleMatchType.REGEX:
        try:
            re.compile(normalized)
        except re.error as error:
            raise MerchantRulePatternError("Regular expression is invalid") from error
    return normalized


def list_rules(session: Session) -> list[MerchantRule]:
    statement = (
        select(MerchantRule)
        .options(joinedload(MerchantRule.category))
        .order_by(MerchantRule.priority, MerchantRule.created_at, MerchantRule.id)
    )
    return list(session.scalars(statement))


def get_rule(session: Session, rule_id: uuid.UUID) -> MerchantRule:
    rule = session.get(MerchantRule, rule_id)
    if rule is None:
        raise MerchantRuleNotFoundError
    return rule


def _commit(session: Session, rule: MerchantRule) -> MerchantRule:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise MerchantRuleConflictError from error
    session.refresh(rule)
    return rule


def create_rule(session: Session, data: MerchantRuleCreate) -> MerchantRule:
    _active_category(session, data.category_id)
    values = data.model_dump()
    values["pattern_normalized"] = _normalized_pattern(data.pattern, data.match_type)
    rule = MerchantRule(**values)
    session.add(rule)
    return _commit(session, rule)


def update_rule(session: Session, rule_id: uuid.UUID, data: MerchantRuleUpdate) -> MerchantRule:
    rule = get_rule(session, rule_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _active_category(session, changes["category_id"])
    for field, value in changes.items():
        setattr(rule, field, value)
    if "pattern" in changes or "match_type" in changes:
        rule.pattern_normalized = _normalized_pattern(rule.pattern, rule.match_type)
    return _commit(session, rule)


def disable_rule(session: Session, rule_id: uuid.UUID) -> MerchantRule:
    rule = get_rule(session, rule_id)
    if rule.enabled:
        rule.enabled = False
        session.commit()
        session.refresh(rule)
    return rule


def delete_rule(session: Session, rule_id: uuid.UUID) -> None:
    rule = get_rule(session, rule_id)
    session.delete(rule)
    session.commit()


def _matches(rule: MerchantRule, merchant: str) -> bool:
    if rule.match_type == RuleMatchType.EXACT:
        return merchant == rule.pattern_normalized
    if rule.match_type == RuleMatchType.CONTAINS:
        return rule.pattern_normalized in merchant
    try:
        return re.search(rule.pattern_normalized, merchant) is not None
    except re.error:
        return False


def _specificity(rule: MerchantRule) -> tuple[int, int]:
    match_rank = {
        RuleMatchType.EXACT: 0,
        RuleMatchType.CONTAINS: 1,
        RuleMatchType.REGEX: 2,
    }
    return (match_rank[rule.match_type], -len(rule.pattern_normalized))


def preview_matches(session: Session) -> tuple[list[Match], int]:
    rules = [rule for rule in list_rules(session) if rule.enabled and not rule.category.archived]
    transactions = list(
        session.scalars(
            select(Transaction)
            .where(Transaction.category_id.is_(None))
            .order_by(Transaction.posted_date.desc(), Transaction.id)
        )
    )
    matches: list[Match] = []
    unmatched = 0
    for transaction in transactions:
        merchant = transaction.merchant_normalized or normalize_merchant(transaction.description)
        candidates = [rule for rule in rules if _matches(rule, merchant)]
        if not candidates:
            unmatched += 1
            continue
        candidates.sort(
            key=lambda rule: (
                rule.priority,
                *_specificity(rule),
                rule.created_at,
                str(rule.id),
            )
        )
        matches.append(Match(transaction, candidates[0], tuple(rule.id for rule in candidates[1:])))
    return matches, unmatched


def _learn_exact_rule(
    session: Session, merchant: str, category_id: uuid.UUID
) -> bool:
    existing = session.scalar(
        select(MerchantRule).where(
            MerchantRule.pattern_normalized == merchant,
            MerchantRule.match_type == RuleMatchType.EXACT,
        )
    )
    if existing is not None:
        changed = existing.category_id != category_id or not existing.enabled
        existing.category_id = category_id
        existing.enabled = True
        return changed
    session.add(
        MerchantRule(
            pattern=merchant,
            pattern_normalized=merchant,
            match_type=RuleMatchType.EXACT,
            category_id=category_id,
            priority=100,
            enabled=True,
        )
    )
    return True


def apply_matches(
    session: Session, decisions: list[RuleApplyDecision]
) -> tuple[int, int, int]:
    preview, _ = preview_matches(session)
    winners = {match.transaction.id: match for match in preview}
    applied = 0
    learned = 0
    active_categories = set(
        session.scalars(select(Category.id).where(Category.archived.is_(False)))
    )
    for decision in decisions:
        match = winners.get(decision.transaction_id)
        if match is None or match.transaction.category_id is not None:
            continue
        if decision.category_id not in active_categories:
            continue
        match.transaction.category_id = decision.category_id
        match.transaction.categorization_confidence = None
        if decision.category_id == match.rule.category_id:
            match.transaction.categorization_source = CategorizationSource.MERCHANT_RULE
            match.transaction.categorization_rule_id = match.rule.id
        else:
            match.transaction.categorization_source = CategorizationSource.MANUAL
            match.transaction.categorization_rule_id = None
        if decision.save_exact_rule:
            merchant = match.transaction.merchant_normalized or normalize_merchant(
                match.transaction.description
            )
            learned += _learn_exact_rule(session, merchant, decision.category_id)
        applied += 1
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise MerchantRuleConflictError from error
    return applied, len(decisions) - applied, learned
