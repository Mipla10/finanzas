"""Esquemas de cuentas (RF-4, RF-5, plan §4.3)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from finanzas.api.schemas.common import BogotaDatetime, Cents, RequestModel
from finanzas.db.models import Account
from finanzas.domain.accounts import AccountType


class AccountCreate(RequestModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Ahorro",
                    "type": "pocket",
                    "parent_id": "00000000-0000-4000-8000-0000000000a1",
                    "initial_balance_cents": 300000000,
                    "start_date": "2026-11-01",
                }
            ]
        }
    )

    name: str
    type: AccountType
    parent_id: uuid.UUID | None = None  # obligatoria solo en los bolsillos
    initial_balance_cents: Cents
    start_date: date | None = None  # por defecto, hoy


class AccountUpdate(RequestModel):
    """Lo que no se envía no cambia. El tipo y la cuenta padre no se editan."""

    name: str | None = None
    initial_balance_cents: Cents | None = None
    start_date: date | None = None


class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    parent_id: uuid.UUID | None
    initial_balance_cents: int
    start_date: date
    archived: bool
    created_at: BogotaDatetime

    @classmethod
    def of(cls, account: Account) -> "AccountOut":
        return cls(
            id=account.id,
            name=account.name,
            type=account.type,
            parent_id=account.parent_id,
            initial_balance_cents=account.initial_balance_cents,
            start_date=account.start_date,
            archived=account.archived_at is not None,
            created_at=account.created_at,
        )


class AccountList(BaseModel):
    items: list[AccountOut]
