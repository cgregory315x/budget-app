import asyncio
import hashlib
import os
import tempfile
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, BinaryIO, cast

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.db.models import AccountType, ImportStatus, StatementImport, Transaction
from app.imports.types import UnsupportedStatementError
from app.main import create_app
from app.schemas.accounts import AccountCreate
from app.schemas.imports import StatementImportConfirm, StatementImportPreview
from app.schemas.transactions import TransactionCreate
from app.services import accounts, statement_imports, transactions
from tests.fixtures.pdfs import selectable_text_pdf


def create_test_account(
    session: Session, *, account_type: AccountType = AccountType.CHECKING, archived: bool = False
) -> uuid.UUID:
    account = accounts.create_account(
        session,
        AccountCreate(
            name="Synthetic account",
            institution="Synthetic institution",
            account_type=account_type,
        ),
    )
    if archived:
        accounts.archive_account(session, account.id)
    return account.id


def upload(data: bytes, *, content_type: str = "application/pdf") -> UploadFile:
    file = tempfile.SpooledTemporaryFile()  # noqa: SIM115 - UploadFile owns and closes it.
    file.write(data)
    file.seek(0)
    return UploadFile(
        filename="synthetic-statement.pdf",
        file=cast(BinaryIO, file),
        size=len(data),
        headers=Headers({"content-type": content_type}),
    )


def preview(
    session: Session, account_id: uuid.UUID, file: UploadFile, **kwargs: Any
) -> StatementImportPreview:
    return asyncio.run(
        statement_imports.preview_statement_import(session, account_id, file, **kwargs)
    )


def test_import_preview_api_contract_is_registered() -> None:
    paths = create_app().openapi()["paths"]
    operation = paths["/api/v1/imports/preview"]["post"]

    assert operation["requestBody"]["content"].keys() == {"multipart/form-data"}
    assert operation["responses"].keys() >= {"200", "422"}
    assert set(paths["/api/v1/imports/confirm"]) == {"post"}


def confirmation(
    account_id: uuid.UUID,
    *,
    file_sha256: str = "c" * 64,
    candidates: list[dict[str, object]] | None = None,
) -> StatementImportConfirm:
    return StatementImportConfirm.model_validate(
        {
            "account_id": account_id,
            "adapter": "navy_federal_checking_v1",
            "file_sha256": file_sha256,
            "statement_start": "2026-08-01",
            "statement_end": "2026-08-31",
            "warnings": ["Synthetic statement warning"],
            "candidates": candidates
            or [
                {
                    "posted_date": "2026-08-02",
                    "description": "Synthetic Market Purchase",
                    "amount": "-45.67",
                    "confidence": "0.900",
                }
            ],
        }
    )


def test_confirms_statement_and_transactions_atomically(db_session: Session) -> None:
    account_id = create_test_account(db_session)

    result = statement_imports.confirm_statement_import(
        db_session,
        confirmation(
            account_id,
            candidates=[
                {
                    "posted_date": "2026-08-02",
                    "description": "Synthetic Market Purchase",
                    "amount": "-45.67",
                    "confidence": "0.900",
                },
                {
                    "posted_date": "2026-08-05",
                    "description": "Synthetic Payroll",
                    "amount": "1250.00",
                    "confidence": "1.000",
                },
            ],
        ),
    )

    imported = db_session.get(StatementImport, result.import_id)
    stored = list(
        db_session.scalars(
            select(Transaction).where(Transaction.statement_import_id == result.import_id)
        )
    )
    assert imported is not None
    assert imported.status == ImportStatus.CONFIRMED
    assert imported.warnings == '["Synthetic statement warning"]'
    assert result.transaction_count == 2
    assert {transaction.id for transaction in stored} == set(result.transaction_ids)
    assert all(transaction.statement_import_id == result.import_id for transaction in stored)


def test_rejects_statement_replay(db_session: Session) -> None:
    account_id = create_test_account(db_session)
    data = confirmation(account_id)
    statement_imports.confirm_statement_import(db_session, data)

    with pytest.raises(
        statement_imports.ImportConfirmationConflictError,
        match="already imported",
    ):
        statement_imports.confirm_statement_import(db_session, data)

    assert len(list(db_session.scalars(select(StatementImport)))) == 1


def test_exact_duplicate_rolls_back_and_can_be_explicitly_allowed(
    db_session: Session,
) -> None:
    account_id = create_test_account(db_session)
    existing = transactions.create_transaction(
        db_session,
        TransactionCreate(
            account_id=account_id,
            posted_date=date(2026, 8, 2),
            description="Synthetic Market Purchase",
            amount=Decimal("-45.67"),
        ),
    )

    with pytest.raises(
        statement_imports.ImportConfirmationConflictError,
        match="exactly matches",
    ):
        statement_imports.confirm_statement_import(
            db_session, confirmation(account_id, file_sha256="d" * 64)
        )
    assert list(db_session.scalars(select(StatementImport))) == []
    assert len(list(db_session.scalars(select(Transaction)))) == 1

    allowed = confirmation(
        account_id,
        file_sha256="e" * 64,
        candidates=[
            {
                "posted_date": "2026-08-02",
                "description": "Synthetic Market Purchase",
                "amount": "-45.67",
                "confidence": "0.900",
                "allow_duplicate": True,
            }
        ],
    )
    result = statement_imports.confirm_statement_import(db_session, allowed)
    duplicate = db_session.get(Transaction, result.transaction_ids[0])
    assert duplicate is not None
    assert (existing.occurrence_index, duplicate.occurrence_index) == (1, 2)


def test_extracts_selectable_text_and_identifies_adapter(db_session: Session) -> None:
    account_id = create_test_account(db_session)
    pdf = selectable_text_pdf(
        """NAVY FEDERAL CREDIT UNION
Checking Account XXXX 1234
Statement Period: 08/01/2026 - 08/31/2026
Transactions
08/02/2026 SYNTHETIC MARKET PURCHASE -$45.67
Ending Balance $1,000.00"""
    )

    result = preview(db_session, account_id, upload(pdf))

    assert result.account_id == account_id
    assert result.adapter == "navy_federal_checking_v1"
    assert "SYNTHETIC MARKET PURCHASE" in result.extracted_text
    assert result.statement.filename == "synthetic-statement.pdf"
    assert result.statement.size_bytes == len(pdf)
    assert result.statement.page_count == 1
    assert result.statement.text_character_count == len(result.extracted_text)
    assert result.parsed_statement.account_hint == "…1234"
    assert result.parsed_statement.period_start == date(2026, 8, 1)
    assert result.parsed_statement.transactions[0].amount == Decimal("-45.67")
    assert result.statement.duplicate.is_duplicate is False
    assert result.parsed_statement.transactions[0].duplicate_status is None


def test_marks_duplicate_statement_and_candidate_transactions(db_session: Session) -> None:
    account_id = create_test_account(db_session)
    pdf = selectable_text_pdf(
        """NAVY FEDERAL CREDIT UNION
Checking Account XXXX 1234
Statement Period: 08/01/2026 - 08/31/2026
Transactions
08/02/2026 SYNTHETIC MARKET PURCHASE -$45.67
08/02/2026 DIFFERENT SYNTHETIC SHOP -$45.67
Ending Balance $1,000.00"""
    )
    existing_import = StatementImport(
        account_id=account_id,
        adapter="navy_federal_checking_v1",
        file_sha256=hashlib.sha256(pdf).hexdigest(),
        statement_start=date(2026, 8, 1),
        statement_end=date(2026, 8, 31),
        status=ImportStatus.CONFIRMED,
    )
    db_session.add(existing_import)
    db_session.commit()
    existing_transaction = transactions.create_transaction(
        db_session,
        TransactionCreate(
            account_id=account_id,
            posted_date=date(2026, 8, 2),
            description="Synthetic Market Purchase",
            amount=Decimal("-45.67"),
        ),
    )

    result = preview(db_session, account_id, upload(pdf))

    assert result.statement.duplicate.is_duplicate is True
    assert result.statement.duplicate.existing_import_id == existing_import.id
    exact, possible = result.parsed_statement.transactions
    assert exact.duplicate_status == "exact"
    assert exact.matched_transaction_id == existing_transaction.id
    assert "Exact duplicate" in exact.warnings[-1]
    assert possible.duplicate_status == "possible"
    assert possible.matched_transaction_id == existing_transaction.id


def test_returns_extracted_text_when_transaction_layout_is_not_supported(
    db_session: Session,
) -> None:
    account_id = create_test_account(db_session)
    pdf = selectable_text_pdf(
        "NAVY FEDERAL CREDIT UNION\nChecking\nSynthetic statement layout not yet supported"
    )

    result = preview(db_session, account_id, upload(pdf))

    assert "Synthetic statement layout" in result.extracted_text
    assert result.parsed_statement.transactions == []
    assert result.parsed_statement.warnings == [
        "Transaction parser needs review: No supported transaction rows were found"
    ]


def test_previews_credit_card_statement_for_active_credit_card_account(
    db_session: Session,
) -> None:
    account_id = create_test_account(db_session, account_type=AccountType.CREDIT_CARD)
    pdf = selectable_text_pdf(
        """NAVY FEDERAL CREDIT UNION
CREDIT CARD xxxx xxxx xxxx 1234
TRANSACTIONS
Trans Date Post Date Reference No. Description Amount
08/02/26 08/03/26 12345678901234567890123 SYNTHETIC MARKET $45.67
TOTAL New Activity $45.67"""
    )

    result = preview(db_session, account_id, upload(pdf))

    assert result.adapter == "navy_federal_credit_card_v1"
    assert result.parsed_statement.account_hint == "…1234"
    assert result.parsed_statement.transactions[0].amount == Decimal("-45.67")


def test_rejects_credit_card_statement_for_checking_account(db_session: Session) -> None:
    account_id = create_test_account(db_session)
    pdf = selectable_text_pdf(
        """NAVY FEDERAL CREDIT UNION
Trans Date Post Date Reference No. Description Amount
08/02/26 08/03/26 123456789012 SYNTHETIC MARKET $45.67"""
    )

    with pytest.raises(statement_imports.IneligibleAccountError, match="credit card account"):
        preview(db_session, account_id, upload(pdf))


def test_temporary_pdf_is_deleted_even_when_adapter_is_unsupported(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    account_id = create_test_account(db_session)
    temporary_pdf = tmp_path / "temporary.pdf"

    def controlled_mkstemp(*, suffix: str) -> tuple[int, str]:
        descriptor = os.open(temporary_pdf, os.O_RDWR | os.O_CREAT | os.O_EXCL)
        return descriptor, str(temporary_pdf)

    monkeypatch.setattr(tempfile, "mkstemp", controlled_mkstemp)
    with pytest.raises(UnsupportedStatementError):
        preview(
            db_session, account_id, upload(selectable_text_pdf("Unknown synthetic bank"))
        )
    assert not temporary_pdf.exists()


@pytest.mark.parametrize(
    ("data", "content_type", "error_type"),
    [
        (b"%PDF-1.4 fake", "text/plain", statement_imports.InvalidPdfError),
        (b"not a pdf", "application/pdf", statement_imports.InvalidPdfError),
        (selectable_text_pdf("   "), "application/pdf", statement_imports.EmptyStatementTextError),
    ],
)
def test_rejects_invalid_pdf_inputs(
    db_session: Session, data: bytes, content_type: str, error_type: type[Exception]
) -> None:
    account_id = create_test_account(db_session)
    with pytest.raises(error_type):
        preview(
            db_session, account_id, upload(data, content_type=content_type)
        )


def test_rejects_oversized_pdf(db_session: Session) -> None:
    account_id = create_test_account(db_session)
    with pytest.raises(statement_imports.PdfTooLargeError):
        preview(
            db_session, account_id, upload(b"%PDF-" + b"x" * 20), max_bytes=10
        )


@pytest.mark.parametrize("account_type", [AccountType.CREDIT_CARD, AccountType.LOAN])
def test_requires_active_checking_account(
    db_session: Session, account_type: AccountType
) -> None:
    account_id = create_test_account(db_session, account_type=account_type)
    with pytest.raises(statement_imports.IneligibleAccountError):
        preview(
            db_session,
            account_id,
            upload(
                selectable_text_pdf(
                    """NAVY FEDERAL CREDIT UNION
Checking
Transactions
08/02/2026 SYNTHETIC PURCHASE -1.00"""
                )
            ),
        )


def test_rejects_archived_and_unknown_accounts(db_session: Session) -> None:
    archived_id = create_test_account(db_session, archived=True)
    valid_pdf = selectable_text_pdf("NAVY FEDERAL CREDIT UNION")
    with pytest.raises(statement_imports.IneligibleAccountError):
        preview(db_session, archived_id, upload(valid_pdf))
    with pytest.raises(statement_imports.AccountNotFoundError):
        preview(db_session, uuid.uuid4(), upload(valid_pdf))
