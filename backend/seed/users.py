"""Seed data for users table - minimal dev user."""

# Dev user ID - must match TEST_OWNER_ID in api/contacts.py
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
DEV_USERNAME = "dev"
DEV_FULL_NAME = "Dev User"


async def seed_users(conn) -> None:
    """Insert the dev user if not exists."""
    async with conn.cursor() as cur:
        # Check if dev user already exists
        await cur.execute(
            "SELECT id FROM users WHERE id = %(id)s",
            {"id": DEV_USER_ID},
        )
        if await cur.fetchone():
            print(f"Dev user already exists: {DEV_USERNAME}")
            return

        # Insert dev user (no password - auth not implemented yet)
        await cur.execute(
            """
            INSERT INTO users (id, username, full_name, descr)
            VALUES (%(id)s, %(username)s, %(full_name)s, %(descr)s)
            """,
            {
                "id": DEV_USER_ID,
                "username": DEV_USERNAME,
                "full_name": DEV_FULL_NAME,
                "descr": "Development user for testing",
            },
        )
        print(f"Created dev user: {DEV_USERNAME} (id: {DEV_USER_ID})")


async def clear_users(conn) -> None:
    """Remove all seeded users. Use with caution."""
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM users WHERE id = %(id)s",
            {"id": DEV_USER_ID},
        )
        print("Cleared dev user")
