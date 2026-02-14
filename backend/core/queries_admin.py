"""Shared SQL queries for admin/auth operations."""


def sql_select_user_capabilities() -> str:
    """Get all capabilities for a user through their roles."""
    return """
        SELECT DISTINCT c.cap_name
        FROM capabilities c
        JOIN rolecapabilities rc ON rc.capabilityid = c.id
        JOIN userroles ur ON ur.roleid = rc.roleid
        WHERE ur.userid = %(user_id)s
    """
