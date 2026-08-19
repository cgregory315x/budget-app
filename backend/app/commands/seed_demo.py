import argparse
from datetime import date

from app.db.session import SessionLocal
from app.services.demo_data import DemoDataNotEmptyError, seed_demo_data


def _month(value: str) -> date:
    try:
        return date.fromisoformat(f"{value}-01")
    except ValueError as error:
        raise argparse.ArgumentTypeError("use YYYY-MM format") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Load fictional portfolio demonstration data.")
    parser.add_argument(
        "--end-month", type=_month, required=True, help="final demo month (YYYY-MM)"
    )
    parser.add_argument(
        "--confirm-empty-database",
        action="store_true",
        help="confirm that this command may seed a verified-empty database",
    )
    arguments = parser.parse_args()
    if not arguments.confirm_empty_database:
        parser.error("--confirm-empty-database is required")

    with SessionLocal() as session:
        try:
            seed_demo_data(session, arguments.end_month)
            session.commit()
        except DemoDataNotEmptyError as error:
            session.rollback()
            parser.exit(2, f"Refusing to seed demo data: {error}.\n")
    print("Synthetic demo data added successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
