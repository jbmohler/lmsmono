#!/usr/bin/env python3
"""Run seed scripts to populate the database with development data.

Usage:
    python -m seed.run [--clear]

Options:
    --clear     Remove all seed data before inserting
"""

import argparse
import asyncio
import sys

import psycopg

from core.config import AppConfig
from seed.users import seed_users, clear_users
from seed.contacts import seed_contacts, clear_contacts


async def main(clear: bool = False) -> int:
    """Run all seed scripts."""
    config = AppConfig.load()

    if not config.database.host:
        print("Error: No database configured")
        return 1

    print(f"Connecting to database: {config.database.host}/{config.database.name}")

    async with await psycopg.AsyncConnection.connect(
        config.database.conninfo
    ) as conn:
        # Disable autocommit for transaction control in seed scripts
        await conn.set_autocommit(True)

        if clear:
            print("\n=== Clearing seed data ===")
            await clear_contacts(conn)
            await clear_users(conn)

        print("\n=== Seeding users ===")
        await seed_users(conn)

        print("\n=== Seeding contacts ===")
        await seed_contacts(conn)

        print("\n=== Seed complete ===")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with development data")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing seed data before inserting",
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main(clear=args.clear)))
