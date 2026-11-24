"""Movimientos: tipos y reglas puras (RF-7 a RF-12, plan §2.2).

Regla clave: el dinero SALE de from_account_id y ENTRA a to_account_id,
para todos los tipos. Así el saldo se calcula con una sola fórmula.
"""

from enum import StrEnum


class MovementType(StrEnum):
    EXPENSE = "expense"  # gasto: sale de una cuenta, con categoría de gasto
    INCOME = "income"  # ingreso: entra a una cuenta, con categoría de ingreso
    TRANSFER = "transfer"  # entre cuentas propias: no es gasto ni ingreso
    YIELD = "yield"  # rendimiento: entra a una cuenta, cuenta como ingreso
    ADJUSTMENT = "adjustment"  # ajuste al saldo real del banco


class AdjustmentDirection(StrEnum):
    IN = "in"  # el saldo real es mayor: entra dinero
    OUT = "out"  # el saldo real es menor: sale dinero
