from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User
from app.models.menu import MenuVersion
from app.models.menu_history import MenuChangeEvent
from app.schemas.menu import MenuItemWrite
from app.schemas.menu_history import (
    MenuBusinessValues,
    MenuChangeEventResponse,
    MenuChangeHistoryResponse,
    MenuHistoryComponent,
)
from app.services.audit_queries import _decode_cursor, _encode_cursor


def business_values(payload: MenuItemWrite | None) -> MenuBusinessValues | None:
    if payload is None:
        return None
    # Явний перелік не дозволяє джерелам імпорту або службовим полям потрапити в історію.
    return MenuBusinessValues(
        name=payload.name_uk,
        description=payload.description_uk,
        price_minor=payload.price_minor,
        currency=payload.currency,
        availability=payload.availability,
        component_data_status=payload.component_data_status,
        components=[
            MenuHistoryComponent(name=item.name_uk, optional=item.optional)
            for item in payload.components
        ],
        allergen_data_status=payload.allergen_data_status,
        allergen_codes=sorted(payload.allergen_codes),
    )


async def record_menu_change(
    db: AsyncSession,
    *,
    version: MenuVersion,
    item_id: UUID,
    actor_user_id: UUID,
    before: MenuItemWrite | None,
    after: MenuItemWrite | None,
) -> None:
    old_values, new_values = business_values(before), business_values(after)
    if old_values == new_values:
        return
    actor = await db.get(User, actor_user_id)
    if actor is None:
        raise RuntimeError("Menu change actor does not exist")
    values = new_values or old_values
    assert values is not None
    # Запис входить у транзакцію зміни меню; окремий commit тут заборонений.
    db.add(
        MenuChangeEvent(
            organization_id=version.organization_id,
            location_id=version.location_id,
            menu_version_id=version.id,
            menu_item_id=item_id,
            actor_user_id=actor_user_id,
            actor_email=actor.email_normalized,
            item_name=values.name,
            action="created" if before is None else "removed" if after is None else "updated",
            old_values=old_values.model_dump(mode="json") if old_values else None,
            new_values=new_values.model_dump(mode="json") if new_values else None,
        )
    )


async def list_menu_changes(
    db: AsyncSession,
    *,
    organization_id: UUID,
    limit: int,
    cursor: str | None,
) -> MenuChangeHistoryResponse:
    query = select(MenuChangeEvent).where(MenuChangeEvent.organization_id == organization_id)
    if cursor is not None:
        created_at, event_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(MenuChangeEvent.created_at, MenuChangeEvent.id) < (created_at, event_id)
        )
    rows = list(
        await db.scalars(
            query.order_by(
                MenuChangeEvent.created_at.desc(),
                MenuChangeEvent.id.desc(),
            ).limit(limit + 1)
        )
    )
    visible = rows[:limit]
    return MenuChangeHistoryResponse(
        items=[MenuChangeEventResponse.model_validate(row) for row in visible],
        next_cursor=_encode_cursor(visible[-1].created_at, visible[-1].id)
        if len(rows) > limit
        else None,
    )
