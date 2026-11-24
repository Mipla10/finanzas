"""Categorías precargadas para cada usuario nuevo (RF-3, plan §5.4).

Se pueden editar, archivar y borrar como cualquier otra.
"""

from finanzas.domain.categories import CategoryKind

_E, _I = CategoryKind.EXPENSE, CategoryKind.INCOME

DEFAULT_CATEGORIES: tuple[tuple[str, CategoryKind], ...] = (
    ("Alimentación", _E),
    ("Domicilios", _E),
    ("Transporte", _E),
    ("Vivienda", _E),
    ("Servicios", _E),
    ("Salud", _E),
    ("Educación", _E),
    ("Entretenimiento", _E),
    ("Ropa", _E),
    ("Suscripciones", _E),
    ("Comisiones bancarias", _E),
    ("Otros", _E),
    ("Salario", _I),
    ("Freelance", _I),
    ("Regalos", _I),
    ("Otros", _I),
)
