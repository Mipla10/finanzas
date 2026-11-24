"""Esquemas de saldos y comercios (RF-13, RF-16, plan §4.3)."""

import uuid

from pydantic import BaseModel

from finanzas.domain.accounts import AccountType


class AccountBalanceOut(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    parent_id: uuid.UUID | None
    archived: bool  # solo aparecen archivadas con saldo distinto de cero
    balance_cents: int


class BankGroupOut(BaseModel):
    """Subtotal «banco + bolsillos»."""

    bank_id: uuid.UUID
    name: str
    subtotal_cents: int


class BalancesOut(BaseModel):
    accounts: list[AccountBalanceOut]
    groups: list[BankGroupOut]
    total_cents: int  # cada cuenta una sola vez, incluidas las archivadas


class MerchantOut(BaseModel):
    merchant: str  # la forma escrita más reciente
    uses: int


class MerchantList(BaseModel):
    items: list[MerchantOut]
