import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.imports.types import UnsupportedStatementError
from app.schemas.imports import (
    StatementImportConfirm,
    StatementImportConfirmResponse,
    StatementImportPreview,
)
from app.services import statement_imports

router = APIRouter()
SessionDependency = Annotated[Session, Depends(get_db_session)]


@router.post("/preview", response_model=StatementImportPreview)
async def preview(
    session: SessionDependency,
    account_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> StatementImportPreview:
    try:
        return await statement_imports.preview_statement_import(session, account_id, file)
    except statement_imports.AccountNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except statement_imports.PdfTooLargeError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error
    except (
        statement_imports.IneligibleAccountError,
        statement_imports.InvalidPdfError,
        statement_imports.EmptyStatementTextError,
        UnsupportedStatementError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.post("/confirm", response_model=StatementImportConfirmResponse)
def confirm(
    data: StatementImportConfirm, session: SessionDependency
) -> StatementImportConfirmResponse:
    try:
        return statement_imports.confirm_statement_import(session, data)
    except statement_imports.AccountNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except statement_imports.ImportConfirmationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except (
        statement_imports.IneligibleAccountError,
        statement_imports.ImportConfirmationError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
