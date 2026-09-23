from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.schemas.menu import EmployeeMenuSourceNote


class SourceItem(BaseModel):
    name: str
    description: str | None
    note: EmployeeMenuSourceNote


class SourceCatalog(BaseModel):
    source_reference: str
    items: dict[str, SourceItem]


@lru_cache(maxsize=1)
def _catalog() -> SourceCatalog:
    return SourceCatalog.model_validate_json(Path(__file__).with_suffix(".json").read_bytes())


def menu_source_note(
    *,
    source_kind: str,
    source_reference: str | None,
    source_item_key: str | None,
    name: str,
    description: str | None,
    locale: str,
) -> EmployeeMenuSourceNote | None:
    # Старі редакційні нотатки не можна переносити на змінену або іншу позицію.
    if source_kind != "json_import" or locale != "uk" or not source_item_key:
        return None
    catalog = _catalog()
    if source_reference != catalog.source_reference:
        return None
    item = catalog.items.get(source_item_key)
    if item is None or item.name != name or (item.description or "") != (description or ""):
        return None
    return item.note.model_copy(deep=True)
