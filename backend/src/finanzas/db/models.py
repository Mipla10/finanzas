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
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from finanzas.db.base import Base
from finanzas.domain.accounts import AccountType


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
