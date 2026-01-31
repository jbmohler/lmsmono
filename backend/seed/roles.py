"""Seed data for roles table with predefined roles and capabilities."""

# Roles with sort order
ROLES = [
    ("Administrator", 1),
    ("Manager", 2),
    ("Staff", 3),
    ("Viewer", 4),
]

# Role capabilities mapping
ROLE_CAPABILITIES = {
    "Administrator": [
        "accounts:read",
        "accounts:write",
        "contacts:read",
        "contacts:write",
        "contacts:passwords",
        "transactions:read",
        "transactions:write",
        "journals:read",
        "journals:write",
        "reports:read",
        "admin:roles",
        "admin:users",
    ],
    "Manager": [
        "accounts:read",
        "accounts:write",
        "contacts:read",
        "contacts:write",
        "transactions:read",
        "transactions:write",
        "journals:read",
        "journals:write",
        "reports:read",
    ],
    "Staff": [
        "accounts:read",
        "contacts:read",
        "contacts:write",
        "transactions:read",
        "transactions:write",
        "journals:read",
        "reports:read",
    ],
    "Viewer": [
        "accounts:read",
        "contacts:read",
        "transactions:read",
        "journals:read",
        "reports:read",
    ],
}


async def seed_roles(conn) -> None:
    """Insert roles and their capabilities if not exists."""
    async with conn.cursor() as cur:
        for role_name, sort in ROLES:
            # Check if role already exists
            await cur.execute(
                "SELECT id FROM roles WHERE role_name = %(role_name)s",
                {"role_name": role_name},
            )
            existing = await cur.fetchone()

            if existing:
                role_id = existing[0]
                print(f"Role already exists: {role_name}")
            else:
                # Insert role
                await cur.execute(
                    """
                    INSERT INTO roles (role_name, sort)
                    VALUES (%(role_name)s, %(sort)s)
                    RETURNING id
                    """,
                    {"role_name": role_name, "sort": sort},
                )
                result = await cur.fetchone()
                role_id = result[0]
                print(f"Created role: {role_name}")

            # Assign capabilities to role
            caps = ROLE_CAPABILITIES.get(role_name, [])
            for cap_name in caps:
                # Get capability ID
                await cur.execute(
                    "SELECT id FROM capabilities WHERE cap_name = %(cap_name)s",
                    {"cap_name": cap_name},
                )
                cap_row = await cur.fetchone()
                if not cap_row:
                    print(f"  Warning: Capability not found: {cap_name}")
                    continue

                cap_id = cap_row[0]

                # Insert role-capability mapping if not exists
                await cur.execute(
                    """
                    INSERT INTO rolecapabilities (roleid, capabilityid)
                    VALUES (%(role_id)s, %(cap_id)s)
                    ON CONFLICT (roleid, capabilityid) DO NOTHING
                    """,
                    {"role_id": role_id, "cap_id": cap_id},
                )


async def clear_roles(conn) -> None:
    """Remove all seeded roles."""
    async with conn.cursor() as cur:
        # First remove user-role mappings
        await cur.execute("DELETE FROM userroles")
        print("Cleared user-role mappings")

        # Remove role-capability mappings
        await cur.execute("DELETE FROM rolecapabilities")
        print("Cleared role-capability mappings")

        # Then remove roles
        await cur.execute("DELETE FROM roles")
        print("Cleared roles")
