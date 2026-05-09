"""JSONL-backed golden dataset with strict schema validation.

Datasets are append-only files of UTF-8 JSON lines, one per row, validated
against :class:`evalkit.config.DatasetRow`. Versioning is delegated to git -
that's a deliberate choice over rolling our own version metadata. ``git log
golden.jsonl`` is a perfectly good audit trail.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from evalkit.config import DatasetRow
from evalkit.exceptions import DatasetError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping
    from typing import Any


class GoldenDataset:
    """A JSONL-backed dataset of :class:`DatasetRow` instances."""

    def __init__(self, rows: list[DatasetRow], path: Path | None = None) -> None:
        self._rows = rows
        self._path = path

    # ---------- loaders -------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> GoldenDataset:
        """Load all rows from a JSONL file, validating each."""
        p = Path(path)
        if not p.exists():
            raise DatasetError(f"dataset not found: {p}")
        rows: list[DatasetRow] = []
        seen_ids: set[str] = set()
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{p}:{lineno}: invalid JSON: {exc}") from exc
            try:
                row = DatasetRow.model_validate(obj)
            except ValidationError as exc:
                raise DatasetError(f"{p}:{lineno}: schema error:\n{exc}") from exc
            if row.id in seen_ids:
                raise DatasetError(f"{p}:{lineno}: duplicate id {row.id!r}")
            seen_ids.add(row.id)
            rows.append(row)
        return cls(rows, path=p)

    @classmethod
    def from_rows(
        cls,
        rows: Iterable[Mapping[str, Any] | DatasetRow],
    ) -> GoldenDataset:
        """Build an in-memory dataset (no file)."""
        out: list[DatasetRow] = []
        for r in rows:
            if isinstance(r, DatasetRow):
                out.append(r)
                continue
            try:
                out.append(DatasetRow.model_validate(r))
            except ValidationError as exc:
                raise DatasetError(f"row schema error:\n{exc}") from exc
        return cls(out)

    # ---------- iteration / access -------------------------------------

    def __iter__(self) -> Iterator[DatasetRow]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int) -> DatasetRow:
        return self._rows[index]

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def ids(self) -> list[str]:
        return [r.id for r in self._rows]

    # ---------- mutation (in-memory) -----------------------------------

    def add(self, row: Mapping[str, Any] | DatasetRow) -> None:
        validated = row if isinstance(row, DatasetRow) else DatasetRow.model_validate(row)
        if validated.id in self.ids:
            raise DatasetError(f"id {validated.id!r} already in dataset")
        self._rows.append(validated)

    # ---------- persistence --------------------------------------------

    def save(self, path: str | Path | None = None) -> Path:
        """Atomically write the dataset to a JSONL file.

        We write to a temp file in the same directory, fsync, then rename, so
        a crash mid-write can never corrupt the existing dataset.
        """
        target = Path(path) if path is not None else self._path
        if target is None:
            raise DatasetError("no path provided and dataset was loaded in-memory")
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_path = Path(f.name)
            for row in self._rows:
                f.write(row.model_dump_json())
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        shutil.move(str(tmp_path), str(target))
        self._path = target
        return target

    # ---------- validation entrypoint ----------------------------------

    @staticmethod
    def validate_file(path: str | Path) -> int:
        """Validate a file in place, return the number of rows.

        Raises:
            DatasetError: on the first invalid row.
        """
        ds = GoldenDataset.load(path)
        return len(ds)
