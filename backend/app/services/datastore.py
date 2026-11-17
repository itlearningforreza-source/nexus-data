from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.core.errors import DataProcessingError, ValidationError

logger = logging.getLogger("nexus")

SAFE_EXTENSIONS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".jsonl",
                   ".parquet", ".feather"}
MAGIC_BLOCKS = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
}


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    base = re.sub(r"[^\w.\- ]", "_", base)
    return base[:200] or "dataset"


def validate_upload(filename: str, content: bytes) -> tuple[str, str, str]:
    """Validate extension, size and basic content. Returns (safe_name, ext, store_id)."""
    safe_name = _safe_filename(filename)
    ext = Path(safe_name).suffix.lower()
    if ext not in SAFE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext or 'unknown'}'. Supported: csv, tsv, txt, xlsx, xls, json, jsonl, parquet, feather."
        )
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationError(
            f"File is too large. Maximum allowed size is {settings.MAX_UPLOAD_MB} MB."
        )
    if len(content) == 0:
        raise ValidationError("The uploaded file is empty.")
    head = content[:64]
    for magic, kind in MAGIC_BLOCKS.items():
        if head.startswith(magic) and kind not in ("png", "gif"):
            pass
    if ext in (".xlsx", ".parquet", ".feather") and not (
        content[:2] == b"PK" and ext == ".xlsx"
    ) and ext == ".xlsx":
        if not content[:2] == b"PK":
            raise ValidationError("Invalid XLSX file: missing zip signature.")
    if ext == ".feather" and not (content[:4] == b"FEA1"):
        raise ValidationError("Invalid Feather file: missing signature.")
    store_id = uuid.uuid4().hex + ext
    return safe_name, ext, store_id


def store_incoming(content: bytes, store_id: str) -> Path:
    incoming = settings.storage_dir / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    path = incoming / store_id
    path.write_bytes(content)
    return path


def canonical_path(file_id: str) -> Path:
    canonical = settings.storage_dir / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    return canonical / f"{file_id}.parquet"


def original_path(store_id: str) -> Path:
    incoming = settings.storage_dir / "incoming"
    return incoming / store_id


def save_canonical(df: pd.DataFrame, file_id: str) -> Path:
    path = canonical_path(file_id)
    df.to_parquet(path, index=False)
    return path


def load_canonical(file_id: str) -> pd.DataFrame:
    path = canonical_path(file_id)
    if not path.exists():
        raise DataProcessingError("Stored dataset file is missing. Please re-upload.")
    return pd.read_parquet(path)


def dataframe_hash(df: pd.DataFrame) -> str:
    sample = df.sample(min(2000, len(df)), random_state=42)
    h = hashlib.sha256()
    h.update(sample.to_csv(index=False).encode("utf-8", errors="replace")[:4_000_000])
    return h.hexdigest()[:16]


def parse_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize common empty markers to NaN."""
    df = df.replace(
        {"": None, "NA": None, "N/A": None, "n/a": None, "NULL": None,
         "null": None, "#N/A": None, "NaN": None, "nan": None},
    )
    return df


def parse_file(path: Path, ext: str, **options: Any) -> pd.DataFrame:
    """Parse a stored file into a DataFrame using pandas. Raises DataProcessingError."""
    try:
        if ext in (".csv", ".txt"):
            delimiter = options.get("delimiter")
            if not delimiter:
                delimiter = "\t" if ext == ".txt" else ","
            df = pd.read_csv(
                path,
                delimiter=delimiter,
                encoding=options.get("encoding") or "utf-8-sig",
                on_bad_lines="warn",
                low_memory=False,
            )
        elif ext == ".tsv":
            df = pd.read_csv(path, delimiter="\t", encoding="utf-8-sig", on_bad_lines="warn")
        elif ext == ".xlsx":
            df = pd.read_excel(path, engine="openpyxl", sheet_name=options.get("sheet") or 0)
        elif ext == ".xls":
            df = pd.read_excel(path, engine="xlrd", sheet_name=options.get("sheet") or 0)
        elif ext == ".json":
            df = pd.read_json(path)
        elif ext == ".jsonl":
            df = pd.read_json(path, lines=True)
        elif ext == ".parquet":
            df = pd.read_parquet(path)
        elif ext == ".feather":
            df = pd.read_feather(path)
        else:
            raise DataProcessingError(f"Unsupported format '{ext}'.")
    except DataProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataProcessingError(
            f"Unable to parse file as {ext}. The file may be malformed or have an unexpected structure.",
            detail={"error": str(exc)},
        ) from exc

    if df is None or df.empty:
        raise DataProcessingError("The dataset contains no rows after parsing.")
    df.columns = [str(c).strip() if isinstance(c, str) else str(c) for c in df.columns]
    if df.columns.duplicated().any():
        seen: dict[str, int] = {}
        new_cols = []
        for c in df.columns:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        df.columns = new_cols
    df = parse_nulls(df)
    return df


def data_profile_cache_key(dataset_id: str, version: int) -> Path:
    cache = settings.cache_dir
    cache.mkdir(parents=True, exist_ok=True)
    return cache / f"profile_{dataset_id}_v{version}.json"


def write_cache(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, default=str))


def read_cache(path: Path) -> Any | None:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.warning("Failed to read cache %s: %s", path, e)
            return None
    return None


def dtype_to_str(dtype: Any) -> str:
    s = str(dtype)
    if s.startswith("int"):
        return "integer"
    if s.startswith("float"):
        return "float"
    if s.startswith("bool"):
        return "boolean"
    if s.startswith("datetime") or s.startswith("timestamp"):
        return "datetime"
    if s.startswith("category"):
        return "categorical"
    if s.startswith("object"):
        return "object"
    if s.startswith("string"):
        return "string"
    return "object"