"""GET /merchants: comercios usados, para autocompletar (RF-13, plan §5.3)."""

from typing import Annotated

from fastapi import APIRouter, Query

from finanzas.api.deps import OwnerDep, SessionDep
from finanzas.api.schemas.balances import MerchantList, MerchantOut
from finanzas.services.merchants import DEFAULT_MERCHANTS_LIMIT, list_merchants
from finanzas.services.movements import MAX_LIMIT

router = APIRouter(tags=["comercios"])


@router.get("/merchants", summary="Comercios usados, los más frecuentes primero")
def merchants(
    session: SessionDep,
    owner_id: OwnerDep,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_MERCHANTS_LIMIT,
) -> MerchantList:
    return MerchantList(
        items=[
            MerchantOut(merchant=m.merchant, uses=m.uses)
            for m in list_merchants(session, owner_id, limit)
        ]
    )
