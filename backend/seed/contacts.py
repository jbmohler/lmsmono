"""Seed data for contacts - personas and bits."""

from seed.users import DEV_USER_ID

# Sample personas with their bits
SEED_PERSONAS = [
    # Individual contacts
    {
        "is_corporate": False,
        "first_name": "Alice",
        "last_name": "Johnson",
        "title": "Ms.",
        "organization": "TechStart Inc",
        "memo": "Primary vendor contact for software licenses",
        "birthday": "1988-06-12",
        "bits": [
            {"bit_type": "email", "email": "alice.johnson@techstart.io", "name": "Work", "is_primary": True},
            {"bit_type": "email", "email": "alice.j@gmail.com", "name": "Personal", "is_primary": False},
            {"bit_type": "phone", "number": "555-0101", "name": "Office", "is_primary": True},
            {"bit_type": "phone", "number": "555-0102", "name": "Mobile", "is_primary": False},
            {"bit_type": "address", "address1": "123 Tech Park Dr", "address2": "Suite 400", "city": "San Jose", "state": "CA", "zip": "95110", "country": "USA", "name": "Office", "is_primary": True},
        ],
    },
    {
        "is_corporate": False,
        "first_name": "Bob",
        "last_name": "Williams",
        "title": "Mr.",
        "organization": "Consulting Group LLC",
        "memo": None,
        "bits": [
            {"bit_type": "email", "email": "bob.williams@consultinggroup.com", "name": "Work", "is_primary": True},
            {"bit_type": "phone", "number": "555-0201", "name": "Mobile", "is_primary": True},
        ],
    },
    {
        "is_corporate": False,
        "first_name": "Carol",
        "last_name": "Martinez",
        "title": "Dr.",
        "organization": None,
        "memo": "Family physician - annual checkups",
        "birthday": "1975-02-28",
        "bits": [
            {"bit_type": "phone", "number": "555-0301", "name": "Office", "is_primary": True},
            {"bit_type": "address", "address1": "456 Medical Center Blvd", "city": "Palo Alto", "state": "CA", "zip": "94301", "country": "USA", "name": "Clinic", "is_primary": True},
            {"bit_type": "url", "url": "https://paltomedical.com/dr-martinez", "name": "Website", "is_primary": True},
        ],
    },
    {
        "is_corporate": False,
        "first_name": "David",
        "last_name": "Chen",
        "title": None,
        "organization": "Self-employed",
        "memo": "Freelance graphic designer",
        "bits": [
            {"bit_type": "email", "email": "david@chendesign.co", "name": "Work", "is_primary": True},
            {"bit_type": "phone", "number": "555-0401", "name": "Mobile", "is_primary": True},
            {"bit_type": "url", "url": "https://chendesign.co", "name": "Portfolio", "is_primary": True},
            {"bit_type": "url", "url": "https://linkedin.com/in/davidchen", "username": "davidchen", "name": "LinkedIn", "is_primary": False},
        ],
    },
    {
        "is_corporate": False,
        "first_name": "Emma",
        "last_name": "Thompson",
        "title": "Ms.",
        "organization": "First National Bank",
        "memo": "Account manager",
        "bits": [
            {"bit_type": "email", "email": "ethompson@firstnational.com", "name": "Work", "is_primary": True},
            {"bit_type": "phone", "number": "555-0501", "name": "Direct", "is_primary": True},
            {"bit_type": "phone", "number": "800-555-1234", "name": "Bank Main", "is_primary": False},
        ],
    },

    # Corporate contacts
    {
        "is_corporate": True,
        "first_name": None,
        "last_name": "Acme Corporation",
        "title": None,
        "organization": None,
        "memo": "Main supplier for office equipment",
        "bits": [
            {"bit_type": "phone", "number": "800-555-ACME", "name": "Main", "is_primary": True},
            {"bit_type": "phone", "number": "800-555-2264", "name": "Support", "is_primary": False},
            {"bit_type": "email", "email": "orders@acme.com", "name": "Orders", "is_primary": True},
            {"bit_type": "email", "email": "support@acme.com", "name": "Support", "is_primary": False},
            {"bit_type": "url", "url": "https://acme.com", "name": "Website", "is_primary": True},
            {"bit_type": "url", "url": "https://portal.acme.com", "username": "customer123", "name": "Portal", "is_primary": False},
            {"bit_type": "address", "address1": "1 Industrial Way", "city": "Commerce", "state": "CA", "zip": "90040", "country": "USA", "name": "HQ", "is_primary": True},
        ],
    },
    {
        "is_corporate": True,
        "first_name": None,
        "last_name": "City Electric Utility",
        "title": None,
        "organization": None,
        "memo": "Monthly utility bill - account #12345",
        "bits": [
            {"bit_type": "phone", "number": "800-555-ELEC", "name": "Customer Service", "is_primary": True},
            {"bit_type": "url", "url": "https://cityelectric.gov/pay", "username": "user@example.com", "name": "Bill Pay", "is_primary": True},
            {"bit_type": "address", "address1": "PO Box 9999", "city": "Sacramento", "state": "CA", "zip": "95814", "country": "USA", "name": "Payment", "is_primary": True},
        ],
    },
    {
        "is_corporate": True,
        "first_name": None,
        "last_name": "Mountain View Insurance",
        "title": None,
        "organization": None,
        "memo": "Auto and home insurance - Policy #INS-789",
        "bits": [
            {"bit_type": "phone", "number": "888-555-INSURE", "name": "Claims", "is_primary": True},
            {"bit_type": "phone", "number": "888-555-4678", "name": "Billing", "is_primary": False},
            {"bit_type": "email", "email": "claims@mvinsurance.com", "name": "Claims", "is_primary": True},
            {"bit_type": "url", "url": "https://mvinsurance.com/portal", "username": "policyholder", "name": "Portal", "is_primary": True},
        ],
    },
]


async def seed_contacts(conn) -> None:
    """Insert seed contacts and their bits."""
    async with conn.cursor() as cur:
        for persona_data in SEED_PERSONAS:
            bits = persona_data.pop("bits", [])

            # Check if persona already exists by name
            if persona_data["is_corporate"]:
                await cur.execute(
                    """
                    SELECT id FROM contacts.personas
                    WHERE l_name = %(last_name)s AND corporate_entity = true AND owner_id = %(owner_id)s
                    """,
                    {"last_name": persona_data["last_name"], "owner_id": DEV_USER_ID},
                )
            else:
                await cur.execute(
                    """
                    SELECT id FROM contacts.personas
                    WHERE l_name = %(last_name)s AND f_name = %(first_name)s AND owner_id = %(owner_id)s
                    """,
                    {
                        "last_name": persona_data["last_name"],
                        "first_name": persona_data["first_name"],
                        "owner_id": DEV_USER_ID,
                    },
                )

            existing = await cur.fetchone()
            if existing:
                name = persona_data["last_name"]
                if persona_data.get("first_name"):
                    name = f"{persona_data['first_name']} {name}"
                print(f"Contact already exists: {name}")
                persona_data["bits"] = bits  # Restore for next iteration
                continue

            # Begin transaction for persona + persona_shares
            await cur.execute("BEGIN")
            try:
                # Insert persona
                await cur.execute(
                    """
                    INSERT INTO contacts.personas (
                        corporate_entity, l_name, f_name, title,
                        organization, memo, birthday, owner_id
                    )
                    VALUES (
                        %(is_corporate)s, %(last_name)s, %(first_name)s, %(title)s,
                        %(organization)s, %(memo)s, %(birthday)s, %(owner_id)s
                    )
                    RETURNING id
                    """,
                    {
                        "is_corporate": persona_data["is_corporate"],
                        "last_name": persona_data["last_name"],
                        "first_name": persona_data.get("first_name"),
                        "title": persona_data.get("title"),
                        "organization": persona_data.get("organization"),
                        "memo": persona_data.get("memo"),
                        "birthday": persona_data.get("birthday"),
                        "owner_id": DEV_USER_ID,
                    },
                )
                row = await cur.fetchone()
                persona_id = row[0]

                # Insert persona_shares for owner
                await cur.execute(
                    """
                    INSERT INTO contacts.persona_shares (persona_id, user_id)
                    VALUES (%(persona_id)s, %(user_id)s)
                    """,
                    {"persona_id": persona_id, "user_id": DEV_USER_ID},
                )

                await cur.execute("COMMIT")

                name = persona_data["last_name"]
                if persona_data.get("first_name"):
                    name = f"{persona_data['first_name']} {name}"
                print(f"Created contact: {name}")

                # Insert bits
                for seq, bit in enumerate(bits):
                    bit_type = bit["bit_type"]
                    bit["bit_sequence"] = seq

                    if bit_type == "email":
                        await cur.execute(
                            """
                            INSERT INTO contacts.email_addresses
                                (persona_id, email, name, memo, is_primary, bit_sequence)
                            VALUES
                                (%(persona_id)s, %(email)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                            """,
                            {
                                "persona_id": persona_id,
                                "email": bit["email"],
                                "name": bit.get("name"),
                                "memo": bit.get("memo"),
                                "is_primary": bit.get("is_primary", False),
                                "bit_sequence": bit["bit_sequence"],
                            },
                        )
                    elif bit_type == "phone":
                        await cur.execute(
                            """
                            INSERT INTO contacts.phone_numbers
                                (persona_id, number, name, memo, is_primary, bit_sequence)
                            VALUES
                                (%(persona_id)s, %(number)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                            """,
                            {
                                "persona_id": persona_id,
                                "number": bit["number"],
                                "name": bit.get("name"),
                                "memo": bit.get("memo"),
                                "is_primary": bit.get("is_primary", False),
                                "bit_sequence": bit["bit_sequence"],
                            },
                        )
                    elif bit_type == "address":
                        await cur.execute(
                            """
                            INSERT INTO contacts.street_addresses
                                (persona_id, address1, address2, city, state, zip, country,
                                 name, memo, is_primary, bit_sequence)
                            VALUES
                                (%(persona_id)s, %(address1)s, %(address2)s, %(city)s, %(state)s,
                                 %(zip)s, %(country)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                            """,
                            {
                                "persona_id": persona_id,
                                "address1": bit.get("address1"),
                                "address2": bit.get("address2"),
                                "city": bit.get("city"),
                                "state": bit.get("state"),
                                "zip": bit.get("zip"),
                                "country": bit.get("country"),
                                "name": bit.get("name"),
                                "memo": bit.get("memo"),
                                "is_primary": bit.get("is_primary", False),
                                "bit_sequence": bit["bit_sequence"],
                            },
                        )
                    elif bit_type == "url":
                        await cur.execute(
                            """
                            INSERT INTO contacts.urls
                                (persona_id, url, username, name, memo, is_primary, bit_sequence)
                            VALUES
                                (%(persona_id)s, %(url)s, %(username)s, %(name)s, %(memo)s, %(is_primary)s, %(bit_sequence)s)
                            """,
                            {
                                "persona_id": persona_id,
                                "url": bit["url"],
                                "username": bit.get("username"),
                                "name": bit.get("name"),
                                "memo": bit.get("memo"),
                                "is_primary": bit.get("is_primary", False),
                                "bit_sequence": bit["bit_sequence"],
                            },
                        )

                print(f"  Added {len(bits)} contact bits")

            except Exception as e:
                await cur.execute("ROLLBACK")
                print(f"Error creating contact: {e}")
                raise

            # Restore bits for potential re-run
            persona_data["bits"] = bits


async def clear_contacts(conn) -> None:
    """Remove all seeded contacts for dev user."""
    async with conn.cursor() as cur:
        # Get all persona IDs for dev user
        await cur.execute(
            "SELECT id FROM contacts.personas WHERE owner_id = %(owner_id)s",
            {"owner_id": DEV_USER_ID},
        )
        personas = await cur.fetchall()
        persona_ids = [p[0] for p in personas]

        if not persona_ids:
            print("No contacts to clear")
            return

        # Use a transaction to handle circular FK constraints
        # The owner_shares_fkey is DEFERRABLE INITIALLY DEFERRED
        await cur.execute("BEGIN")
        try:
            for persona_id in persona_ids:
                # Delete bits first
                await cur.execute(
                    "DELETE FROM contacts.email_addresses WHERE persona_id = %(id)s",
                    {"id": persona_id},
                )
                await cur.execute(
                    "DELETE FROM contacts.phone_numbers WHERE persona_id = %(id)s",
                    {"id": persona_id},
                )
                await cur.execute(
                    "DELETE FROM contacts.street_addresses WHERE persona_id = %(id)s",
                    {"id": persona_id},
                )
                await cur.execute(
                    "DELETE FROM contacts.urls WHERE persona_id = %(id)s",
                    {"id": persona_id},
                )

            # Delete persona_shares first (regular FK from persona_shares to personas)
            for persona_id in persona_ids:
                await cur.execute(
                    "DELETE FROM contacts.persona_shares WHERE persona_id = %(id)s",
                    {"id": persona_id},
                )

            # Then delete personas (deferred FK to persona_shares checked at commit)
            for persona_id in persona_ids:
                await cur.execute(
                    "DELETE FROM contacts.personas WHERE id = %(id)s",
                    {"id": persona_id},
                )

            await cur.execute("COMMIT")
            print(f"Cleared {len(persona_ids)} contacts")
        except Exception:
            await cur.execute("ROLLBACK")
            raise
