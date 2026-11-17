from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import ValidationError

CLEAN_OPS = [
    "remove_duplicates",
    "fill_missing",
    "drop_missing",
    "ffill",
    "bfill",
    "interpolate",
    "replace_values",
    "regex_replace",
    "trim",
    "lowercase",
    "uppercase",
    "titlecase",
    "parse_dates",
    "fix_dtype",
    "normalize_categories",
    "detect_outliers",
    "remove_outliers",
    "winsorize",
    "clip",
    "drop_column",
]


def apply_clean_operation(df: pd.DataFrame, op: str, params: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    columns = params.get("columns") or [params.get("column")]
    columns = [c for c in columns if c]
    if op in ("fill_missing", "ffill", "bfill", "interpolate", "replace_values", "regex_replace", "trim", "lowercase", "uppercase", "titlecase", "parse_dates", "fix_dtype", "normalize_categories", "detect_outliers", "remove_outliers", "winsorize", "clip", "drop_column", "replace_values"):
        if not columns:
            raise ValidationError(f"Operation '{op}' requires at least one column.")
        missing = [c for c in columns if c not in out.columns]
        if missing:
            raise ValidationError(f"Unknown column(s): {', '.join(missing)}")

    if op == "remove_duplicates":
        subset = params.get("subset") or columns or None
        out = out.drop_duplicates(subset=subset, keep="first")
    elif op == "fill_missing":
        value = params.get("value")
        method = params.get("method", "constant")
        for c in columns:
            if method == "constant":
                out[c] = out[c].fillna(value)
            elif method == "mean":
                out[c] = out[c].fillna(pd.to_numeric(out[c], errors="coerce").mean())
            elif method == "median":
                out[c] = out[c].fillna(pd.to_numeric(out[c], errors="coerce").median())
            elif method == "mode":
                m = out[c].mode()
                out[c] = out[c].fillna(m.iloc[0] if len(m) else None)
    elif op == "drop_missing":
        how = params.get("how", "any")
        out = out.dropna(subset=columns or None, how=how)
    elif op == "ffill":
        for c in columns:
            out[c] = out[c].ffill()
    elif op == "bfill":
        for c in columns:
            out[c] = out[c].bfill()
    elif op == "interpolate":
        for c in columns:
            if pd.api.types.is_numeric_dtype(out[c]) or pd.api.types.is_datetime64_any_dtype(out[c]):
                out[c] = out[c].interpolate(method=params.get("method", "linear"))
            else:
                out[c] = out[c].ffill().bfill()
    elif op == "replace_values":
        find = params.get("find")
        replace = params.get("replace")
        for c in columns:
            out[c] = out[c].replace({find: replace})
    elif op == "regex_replace":
        pattern = params.get("pattern", "")
        replace = params.get("replace", "")
        flags = re.IGNORECASE if params.get("ignore_case") else 0
        for c in columns:
            out[c] = out[c].astype("string").str.replace(pattern, replace, regex=True, flags=flags)
    elif op == "trim":
        for c in columns:
            out[c] = out[c].astype("string").str.strip()
    elif op == "lowercase":
        for c in columns:
            out[c] = out[c].astype("string").str.lower()
    elif op == "uppercase":
        for c in columns:
            out[c] = out[c].astype("string").str.upper()
    elif op == "titlecase":
        for c in columns:
            out[c] = out[c].astype("string").str.title()
    elif op == "parse_dates":
        fmt = params.get("format")
        for c in columns:
            out[c] = pd.to_datetime(out[c], format=fmt, errors="coerce")
    elif op == "fix_dtype":
        target = params.get("dtype", "string")
        for c in columns:
            out[c] = _convert_dtype(out[c], target)
    elif op == "normalize_categories":
        for c in columns:
            out[c] = out[c].astype("string").str.strip().str.lower()
    elif op == "detect_outliers":
        out[c] = pd.to_numeric(out[c], errors="coerce")
    elif op == "remove_outliers":
        method = params.get("method", "iqr")
        threshold = float(params.get("threshold", 3.0))
        mask = pd.Series(True, index=out.index)
        for c in columns:
            s = pd.to_numeric(out[c], errors="coerce")
            if method == "iqr":
                q1, q3 = s.quantile(0.25), s.quantile(0.75)
                lo, hi = q1 - threshold * (q3 - q1), q3 + threshold * (q3 - q1)
            elif method == "zscore":
                mu, sd = s.mean(), s.std()
                lo, hi = mu - threshold * sd, mu + threshold * sd
            else:
                raise ValidationError(f"Unknown outlier method '{method}'")
            mask = mask & s.between(lo, hi)
        out = out[mask]
    elif op == "winsorize":
        lower_q = float(params.get("lower", 0.01))
        upper_q = float(params.get("upper", 0.99))
        for c in columns:
            s = pd.to_numeric(out[c], errors="coerce")
            out[c] = s.clip(s.quantile(lower_q), s.quantile(upper_q))
    elif op == "clip":
        lo = params.get("min")
        hi = params.get("max")
        for c in columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").clip(lower=lo, upper=hi)
    elif op == "drop_column":
        out = out.drop(columns=columns)
    else:
        raise ValidationError(f"Unknown cleaning operation '{op}'.")

    return out


def _convert_dtype(series: pd.Series, target: str) -> pd.Series:
    if target in ("int", "integer"):
        return pd.to_numeric(series, errors="coerce")
    if target in ("float", "double"):
        return pd.to_numeric(series, errors="coerce")
    if target in ("str", "string"):
        return series.astype("string")
    if target in ("bool", "boolean"):
        return series.astype("string").str.lower().map(lambda v: {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}.get(v, None))
    if target in ("datetime", "date"):
        return pd.to_datetime(series, errors="coerce")
    if target in ("category", "categorical"):
        return series.astype("string").astype("category")
    return series