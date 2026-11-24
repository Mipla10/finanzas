"""Tablas de la BD (plan §2.2). Toda tabla de negocio tiene owner_id."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.naming import conv

from finanzas.db.base import Base
from finanzas.domain.accounts import AccountType
from finanzas.domain.categories import CategoryKind
from finanzas.domain.movements import AdjustmentDirection, MovementType


def pg_enum(enum_class: type, name: str) -> SAEnum:
    """ENUM de PostgreSQL que guarda los valores ('bank'), no los nombres."""
    return SAEnum(enum_class, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(60))
    name_key: Mapped[str] = mapped_column(String(60))
    type: Mapped[AccountType] = mapped_column(pg_enum(AccountType, "account_type"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    initial_balance_cents: Mapped[int] = mapped_column(BigInteger)
    start_date: Mapped[date] = mapped_column(Date)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Destino de las FK compuestas: garantiza «mismo dueño» (plan §2.1).
        UniqueConstraint("id", "owner_id"),
        # Nombre único por usuario (RF-4).
        UniqueConstraint("owner_id", "name_key"),
        # Un bolsillo solo puede colgar de una cuenta del MISMO dueño.
        ForeignKeyConstraint(
            ["parent_id", "owner_id"],
            ["accounts.id", "accounts.owner_id"],
            name="fk_accounts_parent_owner",
        ),
        # Solo los bolsillos tienen padre, y todo bolsillo lo tiene.
        CheckConstraint(
            "(type = 'pocket') = (parent_id IS NOT NULL)", name="pocket_has_parent"
        ),
        CheckConstraint("parent_id <> id", name="not_own_parent"),
        Index(None, "owner_id"),
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(40))
    name_key: Mapped[str] = mapped_column(String(40))
    # La clase no se puede cambiar una vez creada (RF-6); lo controla el servicio.
    kind: Mapped[CategoryKind] = mapped_column(pg_enum(CategoryKind, "category_kind"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Destino de las FK compuestas desde movements (plan §2.1).
        UniqueConstraint("id", "owner_id"),
        # Nombre único por usuario y clase (RF-6); también sirve de índice por dueño.
        UniqueConstraint("owner_id", "kind", "name_key"),
    )


# Forma de cada tipo (tabla de plan §2.2). Si el código se equivoca, la BD lo frena.
# COALESCE(..., FALSE): en SQL una comparación con NULL da «desconocido» y un
# CHECK «desconocido» se acepta; así lo desconocido cuenta como falso.
MOVEMENT_SHAPE = """
COALESCE((
(type = 'expense' AND from_account_id IS NOT NULL AND to_account_id IS NULL
    AND category_id IS NOT NULL AND adjustment_direction IS NULL)
OR (type = 'income' AND from_account_id IS NULL AND to_account_id IS NOT NULL
    AND category_id IS NOT NULL AND adjustment_direction IS NULL)
OR (type = 'transfer' AND from_account_id IS NOT NULL AND to_account_id IS NOT NULL
    AND from_account_id <> to_account_id
    AND category_id IS NULL AND adjustment_direction IS NULL)
OR (type = 'yield' AND from_account_id IS NULL AND to_account_id IS NOT NULL
    AND category_id IS NULL AND adjustment_direction IS NULL)
OR (type = 'adjustment' AND category_id IS NULL AND (
    (adjustment_direction = 'in' AND from_account_id IS NULL
        AND to_account_id IS NOT NULL)
    OR (adjustment_direction = 'out' AND from_account_id IS NOT NULL
        AND to_account_id IS NULL)))
), FALSE)
"""


class Movement(Base):
    """Estado ACTUAL de cada movimiento; sus versiones van en movement_versions."""

    __tablename__ = "movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    type: Mapped[MovementType] = mapped_column(pg_enum(MovementType, "movement_type"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[date] = mapped_column(Date)
    from_account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    to_account_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    adjustment_direction: Mapped[AdjustmentDirection | None] = mapped_column(
        pg_enum(AdjustmentDirection, "adjustment_direction")
    )
    merchant: Mapped[str | None] = mapped_column(String(80))
    merchant_key: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(String(500))
    # Momento de registro: nunca cambia, ni al corregir (RF-2).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_version: Mapped[int] = mapped_column(Integer)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        # Destino de la FK compuesta desde movement_versions (plan §2.2).
        UniqueConstraint("id", "owner_id"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(MOVEMENT_SHAPE, name=conv("ck_movement_shape")),
        # Cuentas y categoría deben ser del MISMO dueño (RNF-5, plan §2.1).
        ForeignKeyConstraint(
            ["from_account_id", "owner_id"],
            ["accounts.id", "accounts.owner_id"],
            name="fk_movements_from_account_owner",
        ),
        ForeignKeyConstraint(
            ["to_account_id", "owner_id"],
            ["accounts.id", "accounts.owner_id"],
            name="fk_movements_to_account_owner",
        ),
        ForeignKeyConstraint(
            ["category_id", "owner_id"],
            ["categories.id", "categories.owner_id"],
            name="fk_movements_category_owner",
        ),
    )


# Índices de plan §2.2: listado con su orden exacto, saldos, filtros y comercios.
Index(
    "ix_movements_listing",
    Movement.owner_id,
    Movement.date.desc(),
    Movement.created_at.desc(),
    Movement.id.desc(),
)
Index(
    "ix_movements_from_active",
    Movement.owner_id,
    Movement.from_account_id,
    postgresql_where=Movement.voided_at.is_(None),
)
Index(
    "ix_movements_to_active",
    Movement.owner_id,
    Movement.to_account_id,
    postgresql_where=Movement.voided_at.is_(None),
)
Index("ix_movements_category", Movement.owner_id, Movement.category_id)
Index("ix_movements_merchant", Movement.owner_id, Movement.merchant_key)
