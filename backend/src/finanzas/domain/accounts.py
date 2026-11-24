"""Cuentas: tipos y reglas puras (RF-4, plan §2.2)."""

from enum import StrEnum


class AccountType(StrEnum):
    BANK = "bank"
    POCKET = "pocket"  # bolsillo: siempre cuelga de un banco
    DIGITAL_WALLET = "digital_wallet"
    CASH = "cash"
