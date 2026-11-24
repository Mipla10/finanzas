"""Comercios usados, para autocompletar en la web y WhatsApp (RF-13, plan §5.3)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from finanzas.db.repositories import movements as movements_repo
from finanzas.domain.errors import InvalidData
from finanzas.services.movements import MAX_LIMIT

DEFAULT_MERCHANTS_LIMIT = 20  # plan §4.2


@dataclass(frozen=True)
class MerchantUse:
    merchant: str  # forma más reciente que se escribió
    uses: int


def list_merchants(
    session: Session, owner_id: uuid.UUID, limit: int = DEFAULT_MERCHANTS_LIMIT
) -> list[MerchantUse]:
    """Los comercios del dueño (nunca los de otros), los más usados primero."""
    if limit < 1:
        raise InvalidData("ge", field="limit", limit=1)
    if limit > MAX_LIMIT:  # mismos límites que el listado (plan §5.1)
        raise InvalidData("le", field="limit", limit=MAX_LIMIT)
    return [
        MerchantUse(merchant, uses)
        for merchant, uses in movements_repo.merchant_uses(session, owner_id, limit)
    ]
