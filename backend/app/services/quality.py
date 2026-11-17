from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.services.datastore import dtype_to_str

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _dtype_str(s: pd.Series) -> str:
    return dtype_to_str(s.dtype)


def quality_issues(df: pd.DataFrame) -> dict[str, Any]:
    total_cells = len(df) * len(df.columns)
    if total_cells == 0:
        return {"score": 100.0, "subscores": {}, "issues": [], "issues_count": 0}

    missing_count = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    constant_cols = []
    high_card_cols = []
    mismatch_types = []
    malformed_dates = []
    impossible_values = []
    suspicious_ids = []
    casing_issues = []
    outliers_list = []

    completeness_ratio = 1.0 - (missing_count / total_cells)

    for col in df.columns:
        s = df[col]
        non_null = s.dropna()
        if len(non_null) == 0:
            continue
        dtype = _dtype_str(s)

        if non_null.nunique() == 1:
            constant_cols.append({"column": str(col), "reason": "Single value for every row."})

        if dtype == "object":
            n_unique = non_null.nunique(dropna=True)
            if n_unique / max(len(non_null), 1) > 0.99 and n_unique > 50:
                high_card_cols.append({"column": str(col), "reason": f"Near-unique values ({n_unique} distinct)."})

            sample = non_null.astype(str).str.strip()
            non_alpha = sample[sample.str.contains(r"[^a-zA-Z0-9 _\-/&+.#()'%]", regex=True)]
            if len(non_alpha) > 0 and len(non_alpha) / max(len(sample), 1) > 0.03:
                casing_issues.append({
                    "column": str(col),
                    "reason": f"{len(non_alpha)} values contain unusual punctuation or mixed casing.",
                })

        if dtype in ("integer", "float"):
            numeric = pd.to_numeric(s, errors="coerce").dropna()
            if len(numeric) > 1:
                q1 = numeric.quantile(0.25)
                q3 = numeric.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    lo = q1 - 3 * iqr
                    hi = q3 + 3 * iqr
                    n_out = int(((numeric < lo) | (numeric > hi)).sum())
                    if n_out > 0:
                        outliers_list.append({
                            "column": str(col),
                            "reason": f"{n_out} extreme values beyond 3×IQR.",
                            "count": n_out,
                            "low": float(lo),
                            "high": float(hi),
                        })
                lower = numeric.min()
                upper = numeric.max()
                if "age" in col.lower() and (lower < 0 or upper > 120):
                    impossible_values.append({
                        "column": str(col), "reason": f"Values outside the plausible range for column name '{col}' ({lower}–{upper})."
                    })
                if "email" in col.lower() and upper > 10000:
                    impossible_values.append({"column": str(col), "reason": "Ranges far exceed a plausible email metric."})

        if re.search(r"date|year|month", col.lower(), re.I):
            if dtype == "object":
                parsed = pd.to_datetime(s, errors="coerce")
                if parsed.notna().sum() / max(len(s), 1) < 0.9 and (s.notna().sum() > 0):
                    malformed_dates.append({
                        "column": str(col),
                        "reason": "A significant share of values cannot be parsed as dates.",
                    })

        if re.search(r"(id|code|sku|key|no)", col.lower()):
            n_unique = non_null.nunique(dropna=True)
            if n_unique / max(len(non_null), 1) < 0.5 and n_unique < 50 and len(non_null) > 20:
                suspicious_ids.append({
                    "column": str(col),
                    "reason": f"Low uniqueness ({n_unique}) for an identifier-like column.",
                })

    consistency = 1.0 - min(1.0, len(mismatch_types) * 0.2)
    validity = 1.0 - min(
        1.0,
        (len(malformed_dates) + len(impossible_values) + len(suspicious_ids) + len(casing_issues)) / max(len(df.columns), 1) * 0.4,
    )
    uniqueness = 1.0 - min(1.0, duplicate_rows / max(len(df), 1) * 2)

    score = round(
        100 * (
            0.45 * completeness_ratio
            + 0.15 * validity
            + 0.2 * consistency
            + 0.2 * max(0.0, uniqueness)
        ),
        1,
    )

    issues: list[dict[str, Any]] = []
    if missing_count:
        issues.append({
            "type": "missing",
            "severity": "medium" if missing_count / total_cells < 0.1 else "high",
            "title": f"{missing_count:,} missing values",
            "column": "*",
            "message": f"{missing_count:,} of {total_cells:,} cells are empty.",
            "remediation": "Fill or drop missing values.",
        })
    if duplicate_rows:
        issues.append({
            "type": "duplicates",
            "severity": "medium",
            "title": f"{duplicate_rows:,} duplicate rows",
            "column": "*",
            "message": f"{duplicate_rows:,} fully duplicate rows were detected.",
            "remediation": "Remove duplicate rows.",
        })
    for it in constant_cols:
        issues.append({"type": "constant", "severity": "low", "title": f"Constant column: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Drop the column if it carries no information."})
    for it in high_card_cols:
        issues.append({"type": "high_cardinality", "severity": "low", "title": f"High cardinality: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Group rare categories or sample."})
    for it in malformed_dates:
        issues.append({"type": "malformed_dates", "severity": "medium", "title": f"Malformed dates: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Parse date columns to a consistent format."})
    for it in impossible_values:
        issues.append({"type": "impossible_values", "severity": "medium", "title": f"Impossible values: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Review the data sources."})
    for it in suspicious_ids:
        issues.append({"type": "suspicious_ids", "severity": "low", "title": f"Suspicious IDs: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Check uniqueness of the identifier."})
    for it in outliers_list:
        issues.append({"type": "outliers", "severity": "low" if it["count"] / max(len(df), 1) < 0.02 else "medium", "title": f"Outliers: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Clip, winsorize or remove the extreme values."})
    for it in casing_issues:
        issues.append({"type": "inconsistent_casing", "severity": "low", "title": f"Inconsistent text: {it['column']}", "column": it["column"], "message": it["reason"], "remediation": "Normalize case."})

    if issues:
        issues.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))

    return {
        "score": score,
        "subscores": {
            "completeness": round(completeness_ratio * 100, 1),
            "validity": round(max(0.0, validity) * 100, 1),
            "consistency": round(consistency * 100, 1),
            "uniqueness": round(max(0.0, uniqueness) * 100, 1),
        },
        "issues": issues,
        "issues_count": len(issues),
        "row_count": len(df),
        "duplicate_rows": duplicate_rows,
        "missing_count": missing_count,
    }