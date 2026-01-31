"""Seed data for capabilities table."""

# Capabilities define what actions users can perform
# Format: (cap_name, description)
CAPABILITIES = [
    ("accounts:read", "View accounts and account types"),
    ("accounts:write", "Create, update, delete accounts"),
    ("contacts:read", "View contacts"),
    ("contacts:write", "Create, update, delete contacts"),
    ("contacts:passwords", "View encrypted passwords"),
    ("transactions:read", "View transactions"),
    ("transactions:write", "Create, update, delete transactions"),
    ("journals:read", "View journals"),
    ("journals:write", "Create, update, delete journals"),
    ("reports:read", "View reports"),
    ("admin:roles", "Manage roles and capabilities"),
    ("admin:users", "Manage users"),
]


async def seed_capabilities(conn) -> None:
    """Insert capabilities if not exists."""
    async with conn.cursor() as cur:
        for cap_name, description in CAPABILITIES:
            # Check if capability already exists
            await cur.execute(
                "SELECT id FROM capabilities WHERE cap_name = %(cap_name)s",
                {"cap_name": cap_name},
            )
            if await cur.fetchone():
                print(f"Capability already exists: {cap_name}")
                continue

            # Insert capability
            await cur.execute(
                """
                INSERT INTO capabilities (cap_name, description)
                VALUES (%(cap_name)s, %(description)s)
                """,
                {"cap_name": cap_name, "description": description},
            )
            print(f"Created capability: {cap_name}")


async def clear_capabilities(conn) -> None:
    """Remove all seeded capabilities."""
    async with conn.cursor() as cur:
        # First remove role-capability mappings
        await cur.execute("DELETE FROM rolecapabilities")
        print("Cleared role-capability mappings")

        # Then remove capabilities
        await cur.execute("DELETE FROM capabilities")
        print("Cleared capabilities")
