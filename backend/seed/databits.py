"""Seed data for databits - legacy credential/notes store."""

SEED_BITS = [
    {
        "caption": "Gmail",
        "website": "https://mail.google.com",
        "uname": "joel@gmail.com",
        "pword": "hunter2",
        "data": None,
    },
    {
        "caption": "GitHub",
        "website": "https://github.com",
        "uname": "joelbmohler",
        "pword": "gh_p@ssw0rd",
        "data": "Personal account. Work account is separate.",
    },
    {
        "caption": "AWS Console",
        "website": "https://console.aws.amazon.com",
        "uname": "joel@integro212.com",
        "pword": "Aws!Dev99",
        "data": "Dev account only. MFA enabled.\nAccount ID: 123456789012",
    },
    {
        "caption": "Namecheap",
        "website": "https://www.namecheap.com",
        "uname": "joelmohler",
        "pword": "Nc$Domains1",
        "data": "Domain registrar. Renewal reminders go to joel@integro212.com",
    },
    {
        "caption": "Cloudflare",
        "website": "https://dash.cloudflare.com",
        "uname": "joel@integro212.com",
        "pword": "Cf!Zone22",
        "data": None,
    },
    {
        "caption": "DockerHub",
        "website": "https://hub.docker.com",
        "uname": "joelbmohler",
        "pword": "Dkr#Hub77",
        "data": "Free tier. 200 pulls/6hr limit for public images.",
    },
    {
        "caption": "Postgres Admin (prod)",
        "website": None,
        "uname": "lms_owner",
        "pword": "prod!Pg#99",
        "data": "Production database owner role.\nHost: db.example.com:5432\nDo not use for app connections — use lms_server.",
    },
    {
        "caption": "Fly.io",
        "website": "https://fly.io",
        "uname": "joel@integro212.com",
        "pword": "Fly!2024$x",
        "data": "Hosting for LMS production. App: lms-prod",
    },
    {
        "caption": "Router Admin",
        "website": "http://192.168.1.1",
        "uname": "admin",
        "pword": "r0uter!99",
        "data": "Home office router. Reset procedure: hold button 10s.",
    },
    {
        "caption": "Wi-Fi password",
        "website": None,
        "uname": None,
        "pword": "homenet2024",
        "data": "SSID: HomeOffice-5G\nGuest network: HomeGuest / guest2024",
    },
]


SEED_DATABIT_TAGS = ["Admin", "Cloud", "Dev", "Home", "Network"]

# caption → tag names
SEED_DATABIT_TAG_ASSIGNMENTS = {
    "Gmail":                ["Dev"],
    "GitHub":               ["Dev", "Admin"],
    "AWS Console":          ["Dev", "Cloud", "Admin"],
    "Namecheap":            ["Dev", "Cloud"],
    "Cloudflare":           ["Dev", "Cloud"],
    "DockerHub":            ["Dev", "Cloud"],
    "Postgres Admin (prod)": ["Dev", "Admin"],
    "Fly.io":               ["Dev", "Cloud"],
    "Router Admin":         ["Network", "Admin", "Home"],
    "Wi-Fi password":       ["Network", "Home"],
}


async def seed_databits(conn) -> None:
    """Insert databits if table is empty."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM databits.bits")
        row = await cur.fetchone()
        if row and row[0] > 0:
            print(f"Databits already seeded ({row[0]} rows), skipping")
            return

        for bit in SEED_BITS:
            await cur.execute(
                """
                INSERT INTO databits.bits (caption, website, uname, pword, data)
                VALUES (%(caption)s, %(website)s, %(uname)s, %(pword)s, %(data)s)
                """,
                bit,
            )
            print(f"  Created: {bit['caption']}")

    print(f"Seeded {len(SEED_BITS)} data bits")


async def seed_databit_tags(conn) -> None:
    """Insert databit tags and assign them to seeded bits."""
    async with conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM databits.tags")
        row = await cur.fetchone()
        if row and row[0] > 0:
            print(f"Databit tags already seeded ({row[0]} rows), skipping")
            return

        tag_ids: dict[str, object] = {}
        for tag_name in SEED_DATABIT_TAGS:
            await cur.execute(
                "INSERT INTO databits.tags (name) VALUES (%(name)s) RETURNING id",
                {"name": tag_name},
            )
            row = await cur.fetchone()
            tag_ids[tag_name] = row[0]
            print(f"  Created tag: {tag_name}")

        for caption, tag_names in SEED_DATABIT_TAG_ASSIGNMENTS.items():
            await cur.execute(
                "SELECT id FROM databits.bits WHERE caption = %(caption)s",
                {"caption": caption},
            )
            bit_row = await cur.fetchone()
            if not bit_row:
                print(f"  Bit not found: {caption}, skipping tags")
                continue
            bit_id = bit_row[0]
            for tag_name in tag_names:
                tag_id = tag_ids.get(tag_name)
                if not tag_id:
                    continue
                await cur.execute(
                    "INSERT INTO databits.tagbits (tag_id, bit_id) VALUES (%(tag_id)s, %(bit_id)s) ON CONFLICT DO NOTHING",
                    {"tag_id": tag_id, "bit_id": bit_id},
                )
            print(f"  Tagged '{caption}': {', '.join(tag_names)}")

    print(f"Seeded {len(SEED_DATABIT_TAGS)} databit tags")


async def clear_databits(conn) -> None:
    """Remove all databits seed data."""
    async with conn.cursor() as cur:
        await cur.execute("DELETE FROM databits.tagbits")
        await cur.execute("DELETE FROM databits.bits")
        await cur.execute("DELETE FROM databits.tags")
    print("Cleared databits")
