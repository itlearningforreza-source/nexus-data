from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import ValidationError

PIPE_OPS = [
    "source", "select", "filter", "rename", "calculate", "aggregate",
    "join", "union", "pivot", "unpivot", "sort", "group", "normalize",
    "encode", "sample", "output", "dropna", "fillna", "slice",
]


def run_pipeline(df: pd.DataFrame, steps: list[dict[str, Any]]) -> pd.DataFrame:
    """Execute a transformation pipeline (list of steps). Purely functional."""
    out = df
    for step in steps:
        out = apply_step(out, step)
    return out


def apply_step(df: pd.DataFrame, step: dict[str, Any]) -> pd.DataFrame:
    op = step.get("op", step.get("type"))
    params = step.get("params", {})
    if op == "select":
        cols = _resolve(params.get("columns", []), df.columns)
        out = df[cols]
    elif op == "filter":
        column = params.get("column")
        rule = params.get("rule", "eq")
        value = params.get("value")
        if column not in df.columns:
            raise ValidationError(f"Filter column '{column}' not found.")
        s = df[column]
        if rule == "eq":
            mask = s == value
        elif rule == "neq":
            mask = s != value
        elif rule == "gt":
            mask = pd.to_numeric(s, errors="coerce") > float(value)
        elif rule == "gte":
            mask = pd.to_numeric(s, errors="coerce") >= float(value)
        elif rule == "lt":
            mask = pd.to_numeric(s, errors="coerce") < float(value)
        elif rule == "lte":
            mask = pd.to_numeric(s, errors="coerce") <= float(value)
        elif rule == "contains":
            mask = s.astype(str).str.contains(str(value), case=False, regex=False)
        elif rule == "startswith":
            mask = s.astype(str).str.startswith(str(value))
        elif rule == "endswith":
            mask = s.astype(str).str.endswith(str(value))
        elif rule == "in":
            mask = s.isin(params.get("value_list", []))
        elif rule == "notnull":
            mask = s.notna()
        elif rule == "isnull":
            mask = s.isna()
        else:
            raise ValidationError(f"Unknown filter rule '{rule}'.")
        out = df[mask].copy()
    elif op == "rename":
        mapping = params.get("mapping", {})
        out = df.rename(columns=mapping)
    elif op == "calculate":
        column = params.get("column", "calculated")
        expr = params.get("expression", "")
        expr = _rewrite_expr(expr)
        out = df.copy()
        out[column] = out.eval(expr)
    elif op == "aggregate":
        group_by = params.get("group_by", [])
        agg = params.get("aggregations", []) if params.get("aggregations") else [{"column": params.get("aggregate"), "func": params.get("func", "sum"), "alias": params.get("alias")}]
        if not group_by or not agg:
            raise ValidationError("Aggregation requires group_by and aggregations.")
        if isinstance(group_by, str):
            group_by = [group_by]
        agg_map = {}
        for a in agg:
            col = a["column"]
            func = a["func"]
            alias = a.get("alias") or f"{func}_{col}"
            agg_map[alias] = pd.NamedAgg(column=col, aggfunc=_aggfunc(func))
        out = df.groupby(group_by, as_index=False, dropna=False).agg(**agg_map)
    elif op == "join":
        right = params.get("right_df")
        on = params.get("on")
        how = params.get("how", "left")
        if right is None:
            raise ValidationError("Join requires a right DataFrame (provide dataset_id).")
        out = df.merge(right, on=on, how=how, suffixes=("", "_right"))
    elif op == "union":
        other = params.get("right_df")
        if other is None:
            raise ValidationError("Union requires another DataFrame (provide dataset_id).")
        out = pd.concat([df, other], ignore_index=True)
    elif op == "pivot":
        index = params.get("index", [])
        columns = params.get("columns", [])
        values = params.get("values", [])
        if not index or not columns or not values:
            raise ValidationError("Pivot requires index, columns and values.")
        if isinstance(values, str):
            values = [values]
        aggfunc = params.get("aggfunc", "mean")
        out = df.pivot_table(index=index, columns=columns, values=values, aggfunc=aggfunc).reset_index()
        out.columns = [str(c) if i < len(index) else _flatten_pivot(c) for i, c in enumerate(out.columns)]
    elif op == "unpivot":
        id_vars = params.get("id_vars", [])
        var = params.get("var_name", "variable")
        value = params.get("value_name", "value")
        out = df.melt(id_vars=id_vars, var_name=var, value_name=value)
    elif op == "sort":
        by = params.get("by", [])
        if isinstance(by, str):
            by = [by]
        ascending = params.get("ascending", True)
        out = df.sort_values(by=by, ascending=ascending).reset_index(drop=True)
    elif op == "group":
        by = params.get("by", [])
        out = df.groupby(by, sort=False).apply(lambda g: g, include_groups=False) if False else df
        # group is kept as passthrough until aggregate; mark attributes
        out = df.copy()
    elif op == "normalize":
        columns = params.get("columns", [])
        method = params.get("method", "minmax")
        for c in columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if method == "minmax":
                denom = (s.max() - s.min()) or 1
                df[c] = (s - s.min()) / denom
            elif method == "zscore":
                df[c] = (s - s.mean()) / (s.std() or 1)
            elif method == "log":
                df[c] = np.log1p(s.clip(lower=0))
            elif method == "rank":
                df[c] = s.rank(pct=True)
        out = df
    elif op == "encode":
        columns = params.get("columns", [])
        for c in columns:
            if c in df.columns:
                df[c] = df[c].astype("category").cat.codes.replace({-1: None})
        out = df
    elif op == "sample":
        n = int(params.get("n", 1000))
        frac = params.get("frac")
        out = df.sample(n=n, frac=frac, random_state=42).reset_index(drop=True)
    elif op == "dropna":
        subset = params.get("subset") or None
        out = df.dropna(subset=subset)
    elif op == "fillna":
        value = params.get("value", "")
        out = df.fillna(value)
    elif op in ("source", "output", "group"):
        out = df
    elif op == "slice":
        start = int(params.get("start", 0))
        end = params.get("end")
        out = df.iloc[start:end]
    else:
        raise ValidationError(f"Unknown pipeline operation '{op}'.")
    return out


def _resolve(cols: list[str], available) -> list[str]:
    cols = [str(c) for c in cols]
    return cols


def _aggfunc(func: str):
    func = (func or "sum").lower()
    if func == "sum":
        return "sum"
    if func == "mean":
        return "mean"
    if func == "count":
        return "count"
    if func == "min":
        return "min"
    if func == "max":
        return "max"
    if func == "median":
        return "median"
    if func == "std":
        return "std"
    if func == "first":
        return "first"
    if func == "nunique":
        return "nunique"
    raise ValidationError(f"Unknown aggregation '{func}'.")


def _flatten_pivot(col) -> str:
    if isinstance(col, tuple):
        parts = [str(p) for p in col if p is not None and str(p) != ""]
        return "_".join(parts)
    return str(col)


def _rewrite_expr(expr: str) -> str:
    """Rewrite Python-style arithmetic into pandas eval syntax."""
    expr = expr.strip()
    if not expr:
        raise ValidationError("Expression cannot be empty.")
    expr = re.sub(r"\bMath\.(pow|sqrt|log|abs)\b", r"np.\1", expr)
    expr = re.sub(r"\bnp\.log\b", "np.log", expr)
    expr = re.sub(r"\bMath\b", "np", expr)
    expr = re.sub(r"\*\*", "^", expr)
    return expr