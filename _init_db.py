"""Safely apply database migrations.

This replaces the old destructive initializer, which dropped every table.
Run with: python _init_db.py
"""
import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


if __name__ == "__main__":
    main()
