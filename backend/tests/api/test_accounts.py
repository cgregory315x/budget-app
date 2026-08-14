import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.main import create_app
from app.schemas.accounts import AccountCreate, AccountResponse, AccountUpdate
from app.services import accounts


def create_account(
    session: Session,
    *,
    name: str = "Synthetic Checking",
    institution: str = "Example Credit Union",
    account_type: str = "checking",
    current_balance: str | None = "1250.25",
) -> AccountResponse:
    data = AccountCreate.model_validate(
        {
            "name": name,
            "institution": institution,
            "account_type": account_type,
            "currency": "usd",
            "current_balance": current_balance,
        }
    )
    return AccountResponse.model_validate(accounts.create_account(session, data))


def test_account_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]

    assert set(paths["/api/v1/accounts"]) == {"get", "post"}
    assert set(paths["/api/v1/accounts/{account_id}"]) == {"get", "patch", "delete"}
    assert paths["/api/v1/accounts"]["post"]["responses"].keys() >= {"201", "422"}


def test_create_get_and_list_account(db_session: Session) -> None:
    created = create_account(db_session)

    stored = AccountResponse.model_validate(accounts.get_account(db_session, created.id))
    assert stored == created
    assert created.name == "Synthetic Checking"
    assert created.institution == "Example Credit Union"
    assert created.account_type.value == "checking"
    assert created.currency == "USD"
    assert created.current_balance == Decimal("1250.25")

    create_account(db_session, name="Alpha Savings", current_balance=None)
    listed = accounts.list_accounts(db_session)
    assert [item.name for item in listed] == ["Alpha Savings", "Synthetic Checking"]


def test_update_account_and_clear_balance(db_session: Session) -> None:
    created = create_account(db_session)
    update = AccountUpdate.model_validate(
        {"name": "  Primary Checking  ", "currency": "usd", "current_balance": None}
    )

    updated = accounts.update_account(db_session, created.id, update)
    assert updated.name == "Primary Checking"
    assert updated.currency == "USD"
    assert updated.current_balance is None

    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"institution": None})


def test_archive_is_idempotent_and_filtered_by_default(db_session: Session) -> None:
    created = create_account(db_session)

    accounts.archive_account(db_session, created.id)
    accounts.archive_account(db_session, created.id)
    assert accounts.list_accounts(db_session) == []
    assert accounts.list_accounts(db_session, include_archived=True)[0].archived is True


@pytest.mark.parametrize(
    "payload",
    [
        {"name": " ", "institution": "Example", "account_type": "checking"},
        {"name": "Example", "institution": " ", "account_type": "checking"},
        {"name": "Example", "institution": "Example", "account_type": "unknown"},
        {
            "name": "Example",
            "institution": "Example",
            "account_type": "checking",
            "currency": "US1",
        },
        {
            "name": "Example",
            "institution": "Example",
            "account_type": "checking",
            "current_balance": "1.234",
        },
    ],
)
def test_invalid_account_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AccountCreate.model_validate(payload)


def test_unknown_account_is_rejected(db_session: Session) -> None:
    missing_id = uuid.uuid4()

    with pytest.raises(accounts.AccountNotFoundError):
        accounts.get_account(db_session, missing_id)
    with pytest.raises(accounts.AccountNotFoundError):
        accounts.update_account(
            db_session,
            missing_id,
            AccountUpdate.model_validate({"name": "Missing"}),
        )
    with pytest.raises(accounts.AccountNotFoundError):
        accounts.archive_account(db_session, missing_id)
