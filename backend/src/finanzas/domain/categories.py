"""Categorías: clases y reglas puras (RF-6, plan §2.2)."""

from enum import StrEnum


class CategoryKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
