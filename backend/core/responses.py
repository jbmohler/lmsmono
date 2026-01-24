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
    data: dict[str, Any]


@dataclass
class MultiRowResponse:
    """Response containing multiple rows with column metadata."""

    columns: list[ColumnMeta]
    data: list[dict[str, Any]]
