import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.main import create_app
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import categories


def create_category(
    session: Session,
    *,
    name: str = "Synthetic Groceries",
    kind: str = "expense",
    color: str = "#12abef",
) -> CategoryResponse:
    data = CategoryCreate.model_validate({"name": name, "kind": kind, "color": color})
    return CategoryResponse.model_validate(categories.create_category(session, data))


def test_category_api_contract_is_registered() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    assert set(paths["/api/v1/categories"]) == {"get", "post"}
    assert set(paths["/api/v1/categories/{category_id}"]) == {"get", "patch", "delete"}
    assert paths["/api/v1/categories"]["post"]["responses"].keys() >= {"201", "422"}
    assert paths["/api/v1/categories/{category_id}"]["delete"]["responses"].keys() >= {
        "204",
        "422",
    }


def test_create_get_and_list_category(db_session: Session) -> None:
    created = create_category(db_session)

    stored = CategoryResponse.model_validate(
        categories.get_category(db_session, created.id)
    )
    assert stored == created
    assert created.name == "Synthetic Groceries"
    assert created.kind.value == "expense"
    assert created.color == "#12ABEF"
    assert created.archived is False

    create_category(db_session, name="Alpha", kind="income")
    listed = categories.list_categories(db_session)
    assert [item.name for item in listed] == ["Alpha", "Synthetic Groceries"]


def test_update_category_and_reject_empty_patch(db_session: Session) -> None:
    created = create_category(db_session)
    update = CategoryUpdate.model_validate(
        {"name": "  Updated Category  ", "color": "#abcdef"}
    )

    updated = categories.update_category(db_session, created.id, update)
    assert updated.name == "Updated Category"
    assert updated.color == "#ABCDEF"
    assert updated.kind.value == "expense"

    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate({})
    with pytest.raises(ValidationError):
        CategoryUpdate.model_validate({"name": None})


def test_archive_is_idempotent_and_filtered_by_default(db_session: Session) -> None:
    created = create_category(db_session)

    categories.archive_category(db_session, created.id)
    categories.archive_category(db_session, created.id)
    assert categories.list_categories(db_session) == []
    assert categories.list_categories(db_session, include_archived=True)[0].archived is True


def test_duplicate_normalized_name_is_rejected(db_session: Session) -> None:
    create_category(db_session, name="Example")
    duplicate = CategoryCreate.model_validate({"name": " example ", "kind": "expense"})

    with pytest.raises(categories.CategoryNameConflictError):
        categories.create_category(db_session, duplicate)


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "   ", "kind": "expense"},
        {"name": "x" * 81, "kind": "expense"},
        {"name": "Example", "kind": "unknown"},
        {"name": "Example", "kind": "expense", "color": "blue"},
    ],
)
def test_invalid_category_is_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CategoryCreate.model_validate(payload)


def test_unknown_category_is_rejected(db_session: Session) -> None:
    missing_id = uuid.uuid4()

    with pytest.raises(categories.CategoryNotFoundError):
        categories.get_category(db_session, missing_id)
    with pytest.raises(categories.CategoryNotFoundError):
        categories.update_category(
            db_session, missing_id, CategoryUpdate.model_validate({"name": "Missing"})
        )
    with pytest.raises(categories.CategoryNotFoundError):
        categories.archive_category(db_session, missing_id)
