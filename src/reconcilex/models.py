"""Immutable records shared by ingestion and reconciliation."""

from dataclasses import dataclass
from datetime import date


class ReconcileError(ValueError):
    """An actionable input, configuration, or reconciliation failure."""


@dataclass(frozen=True)
class Transaction:
    id: str
    date: date
    amount_minor: int
    currency: str
    reference: str
    description: str
    row: int
    duplicate_content: bool = False


@dataclass(frozen=True)
class Dataset:
    transactions: tuple[Transaction, ...]
    filename: str
    sha256: str
    warnings: tuple[str, ...] = ()
