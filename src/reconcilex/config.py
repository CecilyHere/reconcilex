"""Explicit configuration and exact decimal-string money conversion."""

import codecs
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .models import ReconcileError

DEFAULT_PRECISION = {"SGD": 2, "USD": 2, "EUR": 2, "GBP": 2,
                     "AUD": 2, "CAD": 2, "JPY": 0, "KWD": 3}
MONEY = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")


def money_minor(value: str, precision: int) -> int:
    """Parse plain decimal text into an integer, without rounding or floats."""
    if not isinstance(value, str) or not MONEY.fullmatch(value) or len(value) > 26:
        raise ReconcileError("amount must be plain decimal text, e.g. -1234.50; no separators or exponents")
    whole, _, fraction = value.lstrip("+-").partition(".")
    if len(whole) > 18 or len(fraction) > precision:
        raise ReconcileError(f"amount exceeds 18 whole digits or {precision} decimal places")
    minor = int(whole) * 10**precision + int(fraction.ljust(precision, "0") or "0")
    return -minor if value.startswith("-") else minor


def money_text(minor: int, precision: int) -> str:
    sign = "-" if minor < 0 else ""
    whole, fraction = divmod(abs(minor), 10**precision)
    return f"{sign}{whole}.{fraction:0{precision}d}" if precision else f"{sign}{whole}"


@dataclass(frozen=True)
class Mapping:
    id: str = "id"
    date: str = "date"
    amount: str = "amount"
    currency: str = "currency"
    reference: str = "reference"
    description: str = "description"
    date_format: str = "%Y-%m-%d"
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    sign: int = 1


@dataclass(frozen=True)
class Settings:
    ledger: Mapping = field(default_factory=Mapping)
    bank: Mapping = field(default_factory=Mapping)
    date_window_days: int = 3
    amount_tolerance: str = "0"
    currency_precision: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_PRECISION))
    max_rows: int = 50_000
    max_bytes: int = 10 * 1024 * 1024
    max_candidates: int = 100_000
    max_comparisons: int = 2_000_000

    def normalized(self) -> dict:
        return asdict(self)


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ReconcileError(f"{label} must be an object")
    return value


def _mapping(data: object, label: str) -> Mapping:
    data = _object(data, label)
    if set(data) - set(Mapping.__dataclass_fields__):
        raise ReconcileError(f"unknown {label} configuration field")
    values = asdict(Mapping()) | data
    for key, value in values.items():
        if key == "sign":
            if type(value) is not int or value not in (-1, 1):
                raise ReconcileError(f"{label}.sign must be 1 or -1")
        elif not isinstance(value, str) or not value or "\x00" in value:
            raise ReconcileError(f"{label}.{key} must be nonempty text")
    names = [values[key] for key in ("id", "date", "amount", "currency", "reference", "description")]
    if len(set(names)) != len(names):
        raise ReconcileError(f"{label} column mappings must be distinct")
    if len(values["delimiter"]) != 1 or values["delimiter"] in '\r\n"':
        raise ReconcileError(f"{label}.delimiter must be one character, excluding newline or quote")
    try:
        codecs.lookup(values["encoding"])
    except LookupError as exc:
        raise ReconcileError(f"unknown {label}.encoding") from exc
    return Mapping(**values)


def settings_from_dict(data: object) -> Settings:
    data = _object(data, "configuration")
    if set(data) - set(Settings.__dataclass_fields__):
        raise ReconcileError("unknown top-level configuration field")
    values = Settings().normalized() | data
    for key in ("date_window_days", "max_rows", "max_bytes", "max_candidates", "max_comparisons"):
        minimum = 0 if key == "date_window_days" else 1
        if type(values[key]) is not int or not minimum <= values[key] <= 100_000_000:
            raise ReconcileError(f"{key} must be an integer between {minimum} and 100000000")
    if values["date_window_days"] > 366:
        raise ReconcileError("date_window_days must be at most 366")
    precision = _object(values["currency_precision"], "currency_precision")
    for code, scale in precision.items():
        if not re.fullmatch(r"[A-Z]{3}", code) or type(scale) is not int or not 0 <= scale <= 6:
            raise ReconcileError("currency_precision requires three-letter uppercase codes and integer scales 0–6")
    if not precision:
        raise ReconcileError("currency_precision cannot be empty")
    tolerance = values["amount_tolerance"]
    if not isinstance(tolerance, str) or money_minor(tolerance, 6) < 0:
        raise ReconcileError("amount_tolerance must be a nonnegative decimal string")
    return Settings(**(values | {"ledger": _mapping(values["ledger"], "ledger"),
                                 "bank": _mapping(values["bank"], "bank"),
                                 "currency_precision": dict(precision)}))


def load_settings(path: Path | str | None = None) -> Settings:
    if path is None:
        return Settings()
    try:
        # A duplicate key almost always indicates a configuration mistake.
        def unique_keys(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ReconcileError(f"duplicate configuration key: {key}")
                result[key] = value
            return result
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReconcileError(f"cannot read JSON configuration: {exc}") from exc
    return settings_from_dict(data)
