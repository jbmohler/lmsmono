from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnMeta:
    """Metadata for a column in a table response."""

    key: str
    label: str
    type: str  # "string", "number", "currency", "date", "datetime", "boolean", "uuid", "ref"


@dataclass
class SingleRowResponse:
    """Response containing a single row with column metadata."""

    columns: list[ColumnMeta]
    data: dict[str, Any] | None


@dataclass
class MultiRowResponse:
    """Response containing multiple rows with column metadata."""

    columns: list[ColumnMeta]
    data: list[dict[str, Any]]


def make_ref(id: str, name: str) -> dict[str, str]:
    """Create a standard {id, name} reference struct for foreign keys."""
    return {"id": id, "name": name}
