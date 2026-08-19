import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Category
from app.schemas.categories import CategoryCreate, CategoryUpdate


class CategoryNotFoundError(Exception):
    pass


class CategoryNameConflictError(Exception):
    pass


def list_categories(session: Session, *, include_archived: bool = False) -> list[Category]:
    statement = select(Category)
    if not include_archived:
        statement = statement.where(Category.archived.is_(False))
    statement = statement.order_by(func.lower(Category.name), Category.id)
    return list(session.scalars(statement))


def get_category(session: Session, category_id: uuid.UUID) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError
    return category


def _name_exists(session: Session, name: str, *, excluding: uuid.UUID | None = None) -> bool:
    statement = select(Category.id).where(func.lower(Category.name) == name.casefold())
    if excluding is not None:
        statement = statement.where(Category.id != excluding)
    return session.scalar(statement) is not None


def _commit(session: Session, category: Category) -> Category:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise CategoryNameConflictError from error
    session.refresh(category)
    return category


def create_category(session: Session, data: CategoryCreate) -> Category:
    if _name_exists(session, data.name):
        raise CategoryNameConflictError
    category = Category(**data.model_dump())
    session.add(category)
    return _commit(session, category)


def update_category(
    session: Session, category_id: uuid.UUID, data: CategoryUpdate
) -> Category:
    category = get_category(session, category_id)
    changes = data.model_dump(exclude_unset=True)
    name = changes.get("name")
    if isinstance(name, str) and _name_exists(session, name, excluding=category.id):
        raise CategoryNameConflictError
    for field, value in changes.items():
        setattr(category, field, value)
    return _commit(session, category)


def archive_category(session: Session, category_id: uuid.UUID) -> None:
    category = get_category(session, category_id)
    if not category.archived:
        category.archived = True
        session.commit()


def restore_category(session: Session, category_id: uuid.UUID) -> Category:
    category = get_category(session, category_id)
    if category.archived:
        category.archived = False
        session.commit()
        session.refresh(category)
    return category
