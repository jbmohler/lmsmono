"""Seed data for users table with sample users."""

# Dev user ID - must match TEST_OWNER_ID in api/contacts.py
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"

# Sample users with their roles
SAMPLE_USERS = [
    {
        "id": DEV_USER_ID,
        "username": "admin",
        "full_name": "System Administrator",
        "descr": "Full system access",
        "roles": ["Administrator"],
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "username": "jsmith",
        "full_name": "John Smith",
        "descr": "Department manager",
        "roles": ["Manager"],
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "username": "mjones",
        "full_name": "Mary Jones",
        "descr": "Staff member",
        "roles": ["Staff"],
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "username": "viewer",
        "full_name": "Report Viewer",
        "descr": "Read-only access to reports",
        "roles": ["Viewer"],
    },
]


async def seed_users(conn) -> None:
    """Insert sample users with role assignments."""
    async with conn.cursor() as cur:
        for user in SAMPLE_USERS:
            # Check if user already exists
            await cur.execute(
                "SELECT id FROM users WHERE id = %(id)s",
                {"id": user["id"]},
            )
            if await cur.fetchone():
                print(f"User already exists: {user['username']}")
                user_id = user["id"]
            else:
                # Insert user (no password - auth not implemented yet)
                await cur.execute(
                    """
                    INSERT INTO users (id, username, full_name, descr)
                    VALUES (%(id)s, %(username)s, %(full_name)s, %(descr)s)
                    """,
                    {
                        "id": user["id"],
                        "username": user["username"],
                        "full_name": user["full_name"],
                        "descr": user["descr"],
                    },
                )
                print(f"Created user: {user['username']} (id: {user['id']})")
                user_id = user["id"]

            # Assign roles to user
            for role_name in user.get("roles", []):
                # Get role ID
                await cur.execute(
                    "SELECT id FROM roles WHERE role_name = %(role_name)s",
                    {"role_name": role_name},
                )
                role_row = await cur.fetchone()
                if not role_row:
                    print(f"  Warning: Role not found: {role_name}")
                    continue

                role_id = role_row[0]

                # Insert user-role mapping if not exists
                await cur.execute(
                    """
                    INSERT INTO userroles (userid, roleid)
                    VALUES (%(user_id)s, %(role_id)s)
                    ON CONFLICT (userid, roleid) DO NOTHING
                    """,
                    {"user_id": user_id, "role_id": role_id},
                )


async def clear_users(conn) -> None:
    """Remove all seeded users."""
    async with conn.cursor() as cur:
        # First remove user-role mappings for seeded users
        user_ids = [user["id"] for user in SAMPLE_USERS]
        await cur.execute(
            "DELETE FROM userroles WHERE userid = ANY(%(ids)s)",
            {"ids": user_ids},
        )
        print("Cleared user-role mappings for seeded users")

        # Then remove users
        await cur.execute(
            "DELETE FROM users WHERE id = ANY(%(ids)s)",
            {"ids": user_ids},
        )
        print("Cleared seeded users")
