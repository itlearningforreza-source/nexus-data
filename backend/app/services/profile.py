from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.services.datastore import dtype_to_str

logger = logging.getLogger("nexus")


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _is_numeric_type(dtype_str: str) -> bool:
    return dtype_str in ("integer", "float")


def profile_column(name: str, series: pd.Series) -> dict[str, Any]:
    total = len(series)
    filled = series.notna()
    null_count = int(series.isna().sum())
    null_pct = round(null_count / total * 100, 2) if total else 0.0
    unique = int(series.dropna().nunique(dropna=True)) if filled.any() else 0
    cardinality_ratio = round(unique / total, 4) if total else 0.0

    dtype = series.dtype
    dtype_str = dtype_to_str(dtype)
    numeric = dtype_str in ("integer", "float")
    coerced = None

    if dtype_str in ("integer", "float"):
        coerced = series
    else:
        try:
            attempted = pd.to_numeric(series, errors="coerce")
            convert_ratio = attempted.notna().sum() / max(filled.sum(), 1)
            if convert_ratio >= 0.9:
                dtype_str = "float"
                numeric = True
                coerced = attempted
        except Exception as e:
            logger.debug("Failed to coerce numeric: %s", e)

    sample = []
    if filled.any():
        vals = series.dropna()
        sample = [_j(vals.iloc[i]) for i in range(min(5, len(vals)))]

    return {
        "name": name,
        "dtype": dtype_str,
        "pandas_dtype": str(dtype),
        "numeric": numeric,
        "null_count": null_count,
        "null_pct": null_pct,
        "unique_count": unique,
        "cardinality_ratio": cardinality_ratio,
        "total": total,
        "sample": sample,
        "stats": _column_stats(coerced if numeric else series, numeric),
        "top_values": _top_values(series),
    }


def _column_stats(series: pd.Series, numeric: bool) -> dict[str, Any]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return {}
    vals = np.asarray(s, dtype="float64")
    stats: dict[str, Any] = {
        "count": int(len(vals)),
        "min": _j(float(vals.min())),
        "max": _j(float(vals.max())),
        "range": _j(float(vals.max() - vals.min())),
        "mean": _j(float(vals.mean())),
        "median": _j(float(np.median(vals))),
        "sum": _j(float(vals.sum())),
        "std": _j(float(vals.std())),
        "var": _j(float(vals.var())),
        "first_quartile": _j(float(np.percentile(vals, 25))),
        "third_quartile": _j(float(np.percentile(vals, 75))),
        "iqr": _j(float(np.percentile(vals, 75) - np.percentile(vals, 25))),
    }
    for p in (5, 10, 25, 50, 75, 90, 95, 99):
        stats[f"p{p}"] = _j(float(np.percentile(vals, p)))
    if len(vals) > 1:
        mu = vals.mean()
        sd = vals.std()
        if sd > 0:
            stats["skewness"] = _j(float(pd.Series(vals).skew()))
            stats["kurtosis"] = _j(float(pd.Series(vals).kurt()))
        else:
            stats["skewness"] = _j(0.0)
            stats["kurtosis"] = _j(0.0)
    mode = pd.Series(vals).mode()
    if len(mode) > 0:
        stats["mode"] = _j(float(mode.iloc[0]))
    return stats


def _top_values(series: pd.Series, limit: int = 10) -> list[dict[str, Any]]:
    s = series.dropna()
    if len(s) == 0:
        return []
    vc = s.value_counts().head(limit)
    out = []
    for label, count in vc.items():
        out.append({
            "value": _j(label),
            "count": int(count),
            "pct": round(float(count) / len(s) * 100, 2),
        })
    return out


def _j(v: Any) -> Any:
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v)
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return str(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    columns = []
    for col in df.columns:
        columns.append(profile_column(str(col), df[col]))
    total_rows = len(df)
    total_cells = total_rows * len(df.columns)
    null_cells = int(df.isna().sum().sum())
    return {
        "row_count": total_rows,
        "column_count": len(df.columns),
        "null_cells": null_cells,
        "null_pct": round(null_cells / total_cells * 100, 2) if total_cells else 0.0,
        "columns": columns,
    }