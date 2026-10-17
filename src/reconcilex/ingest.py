"""Strict CSV input with row provenance and duplicate-content warnings."""

import csv
import hashlib
import io
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .config import Mapping, Settings, money_minor
from .models import Dataset, ReconcileError, Transaction


def load_csv(path: Path | str, mapping: Mapping | None = None,
             settings: Settings | None = None) -> Dataset:
    settings = settings or Settings()
    mapping = mapping or Mapping()
    path = Path(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(settings.max_bytes + 1)
        if len(raw) > settings.max_bytes:
            raise ReconcileError(f"{path.name}: exceeds {settings.max_bytes} byte input limit")
        text = raw.decode(mapping.encoding)
        if "\x00" in text:
            raise ReconcileError(f"{path.name}: NUL characters are not supported")
        reader = csv.reader(io.StringIO(text, newline=""),
                            delimiter=mapping.delimiter, strict=True)
        header = next(reader, None)
        if not header or any(not h.strip() for h in header) or len(set(header)) != len(header):
            raise ReconcileError(f"{path.name}: missing, blank, or duplicate CSV headers")
        required = [mapping.id, mapping.date, mapping.amount, mapping.currency]
        missing = [h for h in required if h not in header]
        if missing:
            raise ReconcileError(f"{path.name}: missing mapped columns: {', '.join(missing)}")
        records, seen_ids = [], set()
        for values in reader:
            row = reader.line_num
            if len(records) >= settings.max_rows:
                raise ReconcileError(f"{path.name}: exceeds {settings.max_rows} data row limit")
            if len(values) != len(header):
                raise ReconcileError(f"{path.name}: row {row}: incorrect number of CSV fields")
            data = dict(zip(header, values))
            if any(not data[h].strip() for h in required):
                raise ReconcileError(f"{path.name}: row {row}: required value is missing")
            tid = data[mapping.id].strip()
            if tid in seen_ids:
                raise ReconcileError(f"{path.name}: row {row}: duplicate transaction id {tid!r}")
            seen_ids.add(tid)
            code = data[mapping.currency].strip().upper()
            if code not in settings.currency_precision:
                raise ReconcileError(f"{path.name}: row {row}: unsupported currency {code!r}; configure its precision")
            try:
                date_text = data[mapping.date].strip()
                date = datetime.strptime(date_text, mapping.date_format).date()
                if date.strftime(mapping.date_format) != date_text:
                    raise ValueError("date does not match the explicit format")
                amount = money_minor(data[mapping.amount].strip(), settings.currency_precision[code]) * mapping.sign
            except ValueError as exc:
                raise ReconcileError(f"{path.name}: row {row}: {exc}") from exc
            records.append(Transaction(tid, date, amount, code,
                                       data.get(mapping.reference, "").strip(),
                                       data.get(mapping.description, "").strip(), row))
        if not records:
            raise ReconcileError(f"{path.name}: CSV contains no transactions")
    except (OSError, UnicodeError, LookupError, csv.Error) as exc:
        raise ReconcileError(f"{path.name}: cannot read CSV: {exc}") from exc
    fingerprints = [(t.date, t.amount_minor, t.currency, t.reference.casefold(), t.description.casefold())
                    for t in records]
    counts = Counter(fingerprints)
    warnings = []
    for index, fingerprint in enumerate(fingerprints):
        if counts[fingerprint] > 1:
            records[index] = replace(records[index], duplicate_content=True)
            warnings.append(f"row {records[index].row}: duplicate content retained for review ({records[index].id})")
    return Dataset(tuple(records), path.name, hashlib.sha256(raw).hexdigest(), tuple(warnings))
