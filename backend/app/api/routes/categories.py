import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.categories import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import categories

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


def _conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "A category with that name already exists, including archived categories. "
            "Restore the archived category instead."
        ),
    )


@router.get("", response_model=list[CategoryResponse])
def list_all(
    session: SessionDependency,
    include_archived: Annotated[bool, Query()] = False,
) -> list[CategoryResponse]:
    return [
        CategoryResponse.model_validate(category)
        for category in categories.list_categories(
            session, include_archived=include_archived
        )
    ]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create(data: CategoryCreate, session: SessionDependency) -> CategoryResponse:
    try:
        category = categories.create_category(session, data)
    except categories.CategoryNameConflictError as error:
        raise _conflict() from error
    return CategoryResponse.model_validate(category)


@router.get("/{category_id}", response_model=CategoryResponse)
def get(category_id: uuid.UUID, session: SessionDependency) -> CategoryResponse:
    try:
        category = categories.get_category(session, category_id)
    except categories.CategoryNotFoundError as error:
        raise _not_found() from error
    return CategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update(
    category_id: uuid.UUID, data: CategoryUpdate, session: SessionDependency
) -> CategoryResponse:
    try:
        category = categories.update_category(session, category_id, data)
    except categories.CategoryNotFoundError as error:
        raise _not_found() from error
    except categories.CategoryNameConflictError as error:
        raise _conflict() from error
    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a category",
)
def archive(category_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        categories.archive_category(session, category_id)
    except categories.CategoryNotFoundError as error:
        raise _not_found() from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{category_id}/restore",
    response_model=CategoryResponse,
    summary="Restore an archived category",
)
def restore(category_id: uuid.UUID, session: SessionDependency) -> CategoryResponse:
    try:
        category = categories.restore_category(session, category_id)
    except categories.CategoryNotFoundError as error:
        raise _not_found() from error
    return CategoryResponse.model_validate(category)
