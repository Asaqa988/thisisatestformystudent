"""Excel files for automation exports."""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# The columns each kind of export offers, in their default order.
COLUMN_SETS: dict[str, list[str]] = {
    "customers": [
        "Name",
        "Phone",
        "Email",
        "Channels",
        "City",
        "Country",
        "Company",
        "Conversations",
        "Open conversations",
        "Last message",
        "First contact",
    ],
    "conversations": [
        "Customer",
        "Channel",
        "Inbox",
        "Status",
        "Last message",
        "Last message from",
        "Last message at",
        "AI",
    ],
}

HEADER_FILL = PatternFill("solid", start_color="1F4E5A")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def build_workbook(
    rows: list[dict],
    *,
    kind: str,
    columns: list[str] | None = None,
    sheet_name: str | None = None,
) -> tuple[bytes, list[str]]:
    """Write rows to an .xlsx file. Unknown column names are ignored; none left means all."""
    available = COLUMN_SETS.get(kind, list(rows[0].keys()) if rows else [])
    chosen = [c for c in (columns or []) if c in available] or available

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _sheet_title(sheet_name or kind.capitalize())
    sheet.append(chosen)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        sheet.append([_cell(row.get(column)) for column in chosen])

    for index, column in enumerate(chosen, start=1):
        values = [str(column)] + [str(row.get(column) or "") for row in rows[:500]]
        width = min(max(len(v) for v in values) + 2, 60)
        sheet.column_dimensions[get_column_letter(index)].width = max(width, 10)
        if any(isinstance(row.get(column), datetime) for row in rows[:50]):
            for cell in sheet[get_column_letter(index)][1:]:
                cell.number_format = "yyyy-mm-dd hh:mm"

    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = sheet.dimensions

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), chosen


def _cell(value):
    # Excel cannot store time zones; show the time in UTC without the offset.
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return value


def _sheet_title(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch not in "[]:*?/\\").strip()
    return (cleaned or "Sheet")[:31]
