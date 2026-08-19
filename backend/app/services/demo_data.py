import hashlib
from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Account,
    AccountType,
    CategorizationSource,
    Category,
    CategoryKind,
    MerchantRule,
    MonthlyBudget,
    MonthlyIncome,
    StatementImport,
    Transaction,
)


class DemoDataNotEmptyError(RuntimeError):
    pass


USER_DATA_MODELS = (
    Account,
    Category,
    Transaction,
    MonthlyBudget,
    MonthlyIncome,
    MerchantRule,
    StatementImport,
)


def _shift_month(month: date, offset: int) -> date:
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _posted_date(month: date, day: int) -> date:
    return date(month.year, month.month, min(day, monthrange(month.year, month.month)[1]))


def _fingerprint(month: date, description: str, sequence: int) -> str:
    value = f"budget-app-demo|{month.isoformat()}|{description}|{sequence}"
    return hashlib.sha256(value.encode()).hexdigest()


def database_has_user_data(session: Session) -> bool:
    return any(
        session.scalar(select(func.count()).select_from(model)) != 0
        for model in USER_DATA_MODELS
    )


def seed_demo_data(session: Session, end_month: date) -> None:
    if end_month.day != 1:
        raise ValueError("end_month must be the first day of a month")
    if database_has_user_data(session):
        raise DemoDataNotEmptyError(
            "demo data can only be added to a completely empty database"
        )

    checking = Account(
        name="Demo Everyday Checking",
        institution="Example Community Bank",
        account_type=AccountType.CHECKING,
        currency="USD",
        current_balance=Decimal("6240.18"),
    )
    credit = Account(
        name="Demo Rewards Card",
        institution="Example Card Company",
        account_type=AccountType.CREDIT_CARD,
        currency="USD",
        current_balance=Decimal("-842.67"),
    )
    categories = {
        "income": Category(name="Demo Income", kind=CategoryKind.INCOME, color="#397D72"),
        "housing": Category(name="Demo Housing", kind=CategoryKind.EXPENSE, color="#6783BA"),
        "groceries": Category(name="Demo Groceries", kind=CategoryKind.EXPENSE, color="#D18A48"),
        "dining": Category(name="Demo Dining", kind=CategoryKind.EXPENSE, color="#A66C9B"),
        "utilities": Category(name="Demo Utilities", kind=CategoryKind.EXPENSE, color="#507F94"),
        "transport": Category(
            name="Demo Transportation", kind=CategoryKind.EXPENSE, color="#A77745"
        ),
        "transfer": Category(name="Demo Transfers", kind=CategoryKind.TRANSFER, color="#8D9793"),
    }
    session.add_all((checking, credit, *categories.values()))
    session.flush()

    budget_limits = {
        "housing": Decimal("1500.00"),
        "groceries": Decimal("650.00"),
        "dining": Decimal("250.00"),
        "utilities": Decimal("300.00"),
        "transport": Decimal("275.00"),
    }
    expense_variation = (
        ("510.24", "168.35", "214.18", "132.40"),
        ("548.91", "201.62", "226.07", "154.75"),
        ("472.66", "189.14", "219.83", "121.30"),
        ("601.42", "278.19", "241.55", "176.88"),
        ("536.77", "223.48", "232.09", "143.26"),
        ("684.13", "294.72", "257.61", "188.94"),
    )

    for month_offset, values in enumerate(expense_variation, start=-5):
        month = _shift_month(end_month, month_offset)
        session.add(
            MonthlyIncome(
                month=month,
                description="Demo monthly take-home pay",
                amount=Decimal("4800.00"),
            )
        )
        session.add_all(
            MonthlyBudget(
                month=month,
                category_id=categories[key].id,
                limit_amount=limit,
            )
            for key, limit in budget_limits.items()
        )
        transaction_specs = (
            (checking, 1, "DEMO EMPLOYER PAYROLL", "4600.00", "income", False),
            (checking, 3, "DEMO APARTMENTS RENT", "-1450.00", "housing", False),
            (credit, 8, "EXAMPLE MARKET", f"-{values[0]}", "groceries", False),
            (credit, 12, "SAMPLE CAFE", f"-{values[1]}", "dining", False),
            (checking, 16, "EXAMPLE ELECTRIC AND INTERNET", f"-{values[2]}", "utilities", False),
            (credit, 21, "DEMO TRANSIT AND FUEL", f"-{values[3]}", "transport", False),
            (checking, 24, "DEMO CARD PAYMENT", "-900.00", "transfer", False),
            (credit, 24, "DEMO CARD PAYMENT", "900.00", "transfer", False),
            (checking, 26, "SYNTHETIC REIMBURSABLE PURCHASE", "-45.00", "dining", True),
        )
        for sequence, (account, day, description, amount, category_key, excluded) in enumerate(
            transaction_specs, start=1
        ):
            session.add(
                Transaction(
                    account_id=account.id,
                    category_id=categories[category_key].id,
                    posted_date=_posted_date(month, day),
                    description=description,
                    amount=Decimal(amount),
                    fingerprint=_fingerprint(month, description, sequence),
                    occurrence_index=1,
                    excluded_from_budget=excluded,
                    categorization_source=CategorizationSource.MANUAL,
                )
            )
