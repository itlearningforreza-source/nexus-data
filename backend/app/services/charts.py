from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import ValidationError

AGG_FUNCS = {"sum", "avg", "count", "min", "max", "median", "std"}


def _dtype_kind(dtype) -> str:
    s = str(dtype)
    if s.startswith("int") or s.startswith("float"):
        return "numeric"
    if s.startswith("datetime") or s.startswith("timestamp"):
        return "datetime"
    if s.startswith("bool"):
        return "boolean"
    return "categorical"


def schema_profile(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = []
    for c in df.columns:
        dt = _dtype_kind(df[c].dtype)
        out.append({
            "name": str(c),
            "type": dt,
            "distinct_count": int(df[c].nunique(dropna=True)) if len(df) else 0,
            "null_pct": round(float(df[c].isna().mean()) * 100, 2) if len(df) else 0,
        })
    return out


def recommend_charts(df: pd.DataFrame) -> list[dict[str, Any]]:
    cols = schema_profile(df)
    numerics = [c for c in cols if c["type"] == "numeric"]
    categories = [c for c in cols if c["type"] == "categorical"]
    datetimes = [c for c in cols if c["type"] == "datetime"]
    recs: list[dict[str, Any]] = []

    def _add(chart_type: str, x: str | None, y: str | None, reason: str):
        recs.append({
            "chart_type": chart_type,
            "x": x, "y": y,
            "dimension": x,
            "measure": y,
            "reason": reason,
        })

    if datetimes and numerics:
        _add("line", datetimes[0]["name"], numerics[0]["name"],
             f"'{datetimes[0]['name']}' is a date and '{numerics[0]['name']}' is numeric — a time trend is best shown as a line chart.")
    if categories and numerics:
        _add("bar", categories[0]["name"], numerics[0]["name"],
             f"Compare '{numerics[0]['name']}' across categories of '{categories[0]['name']}' — a column chart makes differences easy to scan.")
    if len(numerics) >= 2:
        _add("scatter", numerics[0]["name"], numerics[1]["name"],
             f"Two numeric columns ('{numerics[0]['name']}', '{numerics[1]['name']}') suggest a scatter plot to inspect the relationship.")
    if numerics:
        _add("histogram", None, numerics[0]["name"],
             f"'{numerics[0]['name']}' is numeric and continuous — a histogram shows its distribution.")
    if categories:
        _add("donut", categories[0]["name"], None,
             f"Share of values in '{categories[0]['name']}' is naturally shown as a donut chart.")
        if len(categories) >= 2:
            _add("heatmap", categories[0]["name"], categories[1]["name"],
                 f"Two categorical columns ('{categories[0]['name']}' × '{categories[1]['name']}') can be cross-tabulated in a heatmap.")
    if numerics:
        _add("box", None, numerics[0]["name"],
             f"A box plot summarises the range and spread of '{numerics[0]['name']}'.")
    return recs


def _agg(df: pd.DataFrame, y: str, func: str) -> float:
    s = pd.to_numeric(df[y], errors="coerce").dropna()
    if func == "sum":
        return float(s.sum())
    if func == "avg" or func == "mean":
        return float(s.mean())
    if func == "count":
        return float(len(s))
    if func == "min":
        return float(s.min())
    if func == "max":
        return float(s.max())
    if func == "median":
        return float(s.median())
    if func == "std":
        return float(s.std())
    raise ValidationError(f"Unknown aggregation '{func}'.")


def _coerce_numeric(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce")


def build_chart_data(df: pd.DataFrame, chart_type: str,
                     config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Return (data, error). chart_type: bar, column, line, area, pie, donut, scatter,
    bubble, histogram, heatmap, treemap, radar, funnel, gauge, kpi, table, box, stacked_bar,
    stacked_column, hundred_bar, sunburst, waterfall."""
    ct = chart_type
    x = config.get("x")
    y = config.get("y")
    color = config.get("color")
    agg = config.get("aggregation", "sum")
    limit = min(int(config.get("limit", 30)), 200)
    sort = config.get("sort", "desc")

    if ct in ("kpi",):
        if not y:
            return {}, "Select a measure column."
        value = _agg(df, y, agg)
        return {
            "kpi": {
                "label": config.get("label") or y,
                "value": round(value, 4) if isinstance(value, float) else value,
                "aggregation": agg,
                "column": y,
                "row_count": len(df),
            }
        }, ""

    if ct == "histogram":
        col = y or x
        if not col:
            return {}, "Select a numeric column."
        s = _coerce_numeric(df, col).dropna()
        if len(s) == 0:
            return {}, "No numeric values in the selected column."
        bins = int(config.get("bins", 20))
        counts, edges = np.histogram(s, bins=min(bins, 50))
        data = {
            "values": [float(v) for v in counts],
            "edges": [round(float(e), 4) for e in edges],
            "labels": data_labels(edges),
            "column": col,
        }
        return data, ""

    if ct == "box":
        group_by = config.get("group_by")
        if not y:
            return {}, "Select a numeric column."
        if group_by and group_by not in df.columns:
            return {}, f"Group column '{group_by}' not found."
        if group_by:
            boxes = []
            for name, grp in df.groupby(group_by, dropna=False):
                s = _coerce_numeric(grp, y).dropna()
                if len(s) == 0:
                    continue
                boxes.append(_box_stats(name, s))
            return {"boxes": boxes[:30], "column": y, "group_by": group_by}, ""
        s = _coerce_numeric(df, y).dropna()
        if len(s) == 0:
            return {}, "No numeric values."
        return {"boxes": [_box_stats(y, s)], "column": y}, ""

    if ct in ("gauge",):
        if not y:
            return {}, "Select a measure."
        val = _agg(df, y, agg)
        return {
            "gauge": {
                "value": round(float(val), 4),
                "min": float(config.get("min", 0)),
                "max": float(config.get("max", float(df[y].max()) if df[y].dtype.kind in "fi" else 100)),
                "label": config.get("label") or y,
            }
        }, ""

    if ct == "heatmap":
        xh = x
        yh = y
        vh = config.get("value")
        if not xh or not yh or not vh:
            return {}, "Select an x column, y column and a value column for the heatmap."
        if vh not in df.columns:
            return {}, f"Value column '{vh}' not found."
        if xh not in df.columns or yh not in df.columns:
            return {}, "Heatmap columns not found."
        xvals = [str(v) for v in df[xh].fillna("").astype(str)]
        yvals = [str(v) for v in df[yh].fillna("").astype(str)]
        vvals = pd.to_numeric(df[vh], errors="coerce").fillna(0)
        from collections import defaultdict
        grid_sum = defaultdict(float)
        grid_count = defaultdict(int)
        for xi, yi, vi in zip(xvals, yvals, vvals):
            grid_sum[(xi, yi)] += float(vi)
            grid_count[(xi, yi)] += 1
        x_labels = list(dict.fromkeys(xvals))[:60]
        y_labels = list(dict.fromkeys(yvals))[:60]
        agg_f = _agg_name(agg)
        matrix = []
        for yi in y_labels:
            for xi in x_labels:
                key = (xi, yi)
                if grid_count.get(key, 0) == 0:
                    matrix.append({"x": xi, "y": yi, "value": None})
                    continue
                dom = grid_sum[key]
                if agg_f == "mean":
                    dom = dom / grid_count[key]
                elif agg_f == "sum":
                    dom = dom
                elif agg_f in ("min", "max", "median", "std"):
                    vals = [float(v) for ixyz, v in enumerate(vvals) if xvals[ixyz] == xi and yvals[ixyz] == yi]
                    dom = float(np.nanmin(vals)) if agg_f == "min" else float(np.nanmax(vals)) if agg_f == "max" else float(np.nanmedian(vals)) if agg_f == "median" else float(np.nanstd(vals))
                else:
                    dom = grid_sum[key]
                matrix.append({"x": xi, "y": yi, "value": round(float(dom), 6)})
        return {
            "matrix": matrix,
            "x_labels": x_labels,
            "y_labels": y_labels,
            "x_column": xh,
            "y_column": yh,
            "value_column": vh,
        }, ""

    if ct == "table":
        limit = min(int(config.get("limit", 100)), 1000)
        # Get columns from config, fallback to all columns
        config_cols = config.get("columns")
        if config_cols:
            cols = [str(c) for c in config_cols if str(c) in df.columns]
        else:
            cols = [str(c) for c in df.columns[:20]]
        sub = df[cols].head(limit)
        return {
            "columns": [str(c) for c in sub.columns],
            "rows": sub.fillna("").values.tolist(),
            "row_count": len(df),
        }, ""

    if ct == "pie":
        if not x:
            return {}, "Select a categorical column."
        s = df[x]
        value_col = y
        if y and y in df.columns and _dtype_kind(df[y].dtype) == "numeric":
            grouped = df.groupby(x)[y].agg(_agg_name(agg)).dropna().sort_values(ascending=(sort == "asc"))
        else:
            grouped = df[x].astype(str).value_counts().sort_values(ascending=(sort == "asc"))
        grouped = grouped.head(limit)
        if len(grouped) == 0:
            return {}, "No values to plot."
        return {
            "labels": [str(k) for k in grouped.index],
            "values": [float(v) for v in grouped.values],
            "column_x": x,
            "column_y": y,
        }, ""

    if ct in ("treemap", "sunburst"):
        if not x:
            return {}, "Select at least one dimension."
        if y and y in df.columns and _dtype_kind(df[y].dtype) == "numeric":
            grouped = df.groupby(x)[y].agg(_agg_name(agg)).dropna().sort_values(ascending=False)
        else:
            grouped = df[x].astype(str).value_counts().sort_values(ascending=False)
        grouped = grouped.head(200)
        return {
            "labels": [str(k) for k in grouped.index],
            "values": [float(v) for v in grouped.values],
            "column_x": x,
            "column_y": y,
        }, ""

    if ct in ("radar",):
        if not x or not y:
            return {}, "Select a dimension (radar axis) and a measure."
        grouped = df.groupby(x)[y].agg(_agg_name(agg)).dropna()
        grouped = grouped.head(limit)
        return {
            "categories": [str(k) for k in grouped.index],
            "values": [float(v) for v in grouped.values],
            "column": y,
        }, ""

    if ct == "funnel":
        if not x or not y:
            return {}, "Select a stage dimension and a measure."
        grouped = df.groupby(x, as_index=False)[y].agg(_agg_name(agg)).sort_values(by=y, ascending=False).head(limit)
        return {
            "labels": [str(v) for v in grouped[x]],
            "values": [float(v) for v in grouped[y]],
        }, ""

    if ct == "waterfall":
        if not x or not y:
            return {}, "Select a dimension and a measure."
        grouped = df.groupby(x, as_index=False)[y].agg(_agg_name(agg)).sort_values(by=y, ascending=False).head(limit)
        values = [float(v) for v in grouped[y]]
        return {
            "labels": [str(v) for v in grouped[x]],
            "values": values,
            "running": _running(values),
        }, ""

    if ct in ("scatter", "bubble"):
        if not x or not y:
            return {}, "Select two numeric columns."
        if _dtype_kind(df[x].dtype) != "numeric" or _dtype_kind(df[y].dtype) != "numeric":
            return {}, "Scatter and bubble charts require numeric columns."
        xv = pd.to_numeric(df[x], errors="coerce")
        yv = pd.to_numeric(df[y], errors="coerce")
        mask = xv.notna() & yv.notna()
        if color:
            if _dtype_kind(df[color].dtype) == "numeric":
                cnum = True
                cv = pd.to_numeric(df[color], errors="coerce")
            else:
                cnum = False
                cv = df[color].astype(str)
        else:
            cnum = False
            cv = pd.Series([""] * len(df), index=df.index)
        size_col = config.get("size")
        if size_col and _dtype_kind(df[size_col].dtype) == "numeric":
            sv = pd.to_numeric(df[size_col], errors="coerce")
        else:
            sv = pd.Series([10.0] * len(df), index=df.index)
        n = int(config.get("limit", 2000))
        cap = int(min(n, mask.sum()))
        # deterministic spaced sample preserves outliers
        idx = np.linspace(0, mask.sum() - 1, num=cap, dtype=int)
        rows = []
        sub_mask = mask[mask].index[idx]
        for i in sub_mask:
            rows.append({
                "x": float(xv[i]), "y": float(yv[i]),
                "size": float(sv[i]) if pd.notna(sv[i]) else 5.0,
                "color": (float(cv[i]) if cnum and i in cv.index and pd.notna(cv[i]) else (cv[i] if i in cv.index else "")),
                "label": str(df[color][i]) if color else f"({_f(xv[i])}, {_f(yv[i])})",
            })
        return {"points": rows, "x_column": x, "y_column": y, "color_column": color}, ""

    # Bar / Column / Line / Area / Stacked variants
    if not x or not y:
        return {}, "Select a dimension (x) and a measure (y)."
    if x not in df.columns:
        return {}, f"Column '{x}' not found."
    if y not in df.columns:
        return {}, f"Column '{y}' not found."

    if ct in ("line", "area") and _dtype_kind(df[x].dtype) == "datetime":
        grouped = df.sort_values(x).groupby(x)[y].agg(_agg_name(agg)).reset_index()
        labels = [str(v)[:10] for v in grouped[x]]
        series = [{"label": str(v).strip(), "value": float(_f(v1)) if pd.notna(v1) else None} for v, v1 in zip(grouped[x], grouped[y])]
        if len(series) > 500:
            step = len(series) / 500
            series = [series[int(i * step)] for i in range(500)]
        return {
            "labels": [s["label"] for s in series],
            "values": [s["value"] for s in series],
            "raw_labels": labels,
            "x_column": x, "y_column": y,
        }, ""

    if ct in ("bar", "column", "area") and _dtype_kind(df[x].dtype) == "numeric" and _dtype_kind(df[y].dtype) == "numeric":
        grouped = df.groupby(x)[y].agg(_agg_name(agg)).dropna()
        return {
            "labels": [str(k) for k in grouped.index],
            "values": [float(_f(v)) if pd.notna(v) else 0 for v in grouped.values],
            "numerical_x": True,
            "x_column": x, "y_column": y,
        }, ""

    if ct in ("stacked_bar", "stacked_column", "hundred_bar", "hundred_column", "grouped_bar", "grouped_column", "line", "area", "bar", "column"):
        color = config.get("color") or color
        base_x = x
        if color and _dtype_kind(df[color].dtype) != "numeric":
            grouped = df.groupby([base_x, color], as_index=False)[y].agg(_agg_name(agg))
            cats = list(dict.fromkeys([str(v) for v in grouped[base_x]]))
            series_names = sorted(set(str(v) for v in grouped[color]))
            series = []
            for sn in series_names:
                sub = grouped[grouped[color].astype(str) == sn]
                m = {str(r[base_x]): _f(r[y]) for _, r in sub.iterrows()}
                series.append({
                    "name": sn,
                    "values": [m.get(c, 0) for c in cats],
                })
            if ct.startswith("hundred"):
                cat_totals = {c: sum(s["values"][i] for s in series) for i, c in enumerate(cats)}
                for s in series:
                    s["values"] = [round((v / cat_totals.get(c, 0)) * 100, 4) if cat_totals.get(c, 0) else 0 for c, v in zip(cats, s["values"])]
            out = {
                "labels": cats[:limit],
                "series": [{**s, "values": s["values"][:limit]} for s in series],
                "stacked": ct.startswith("stacked") or ct.startswith("hundred"),
                "hundred": ct.startswith("hundred"),
                "x_column": base_x, "y_column": y, "color_column": color,
            }
            if len(out["labels"]) > 60:
                out["labels"] = out["labels"][:60]
                out["series"] = [{**s, "values": s["values"][:60]} for s in out["series"]]
            return out, ""

        if ct.startswith("grouped") and color:
            grouped = df.groupby([base_x, color], as_index=False)[y].agg(_agg_name(agg))
            cats = list(dict.fromkeys([str(v) for v in grouped[base_x]]))
            series_names = sorted(set(str(v) for v in grouped[color]))
            series = []
            for sn in series_names:
                sub = grouped[grouped[color].astype(str) == sn]
                m = {str(r[base_x]): _f(r[y]) for _, r in sub.iterrows()}
                series.append({"name": sn, "values": [m.get(c, 0) for c in cats]})
            return {"labels": cats[:60], "series": [dict(s, values=s["values"][:60]) for s in series], "stacked": False, "grouped": True, "x_column": base_x, "y_column": y, "color_column": color}, ""

        grouped = df.groupby(base_x)[y].agg(_agg_name(agg)).dropna().sort_values(ascending=(sort == "asc"))
        grouped = grouped.head(limit)
        if ct in ("line", "area"):
            return {
                "labels": [str(k) for k in grouped.index],
                "values": [float(_f(v)) if pd.notna(v) else 0 for v in grouped.values],
                "x_column": x, "y_column": y,
            }, ""
        out = {
            "labels": [str(k) for k in grouped.index],
            "values": [float(_f(v)) if pd.notna(v) else 0 for v in grouped.values],
            "x_column": x, "y_column": y,
        }
        return out, ""

    return {}, f"Unsupported chart type '{ct}'."


def _aggregate_for(df: pd.DataFrame, x: str, y: str, agg: str, color: str | None, ct: str):
    if color and _dtype_kind(df[color].dtype) != "numeric":
        grouped = df.groupby([x, color], as_index=False)[y].agg(_agg_name(agg))
        return {
            "labels": [str(v) for v in grouped[x].drop_duplicates()],
            "series": [{"name": str(r[color]), "values": []} for _, r in grouped.iterrows()],
        }
    return None


def _box_stats(name: Any, s: pd.Series) -> dict[str, Any]:
    return {
        "name": str(name),
        "min": float(s.min()),
        "q1": float(s.quantile(0.25)),
        "median": float(s.median()),
        "q3": float(s.quantile(0.75)),
        "max": float(s.max()),
        "outliers": [float(v) for v in s.values if v < s.quantile(0.25) - 1.5 * (s.quantile(0.75) - s.quantile(0.25)) or v > s.quantile(0.75) + 1.5 * (s.quantile(0.75) - s.quantile(0.25))][:50],
        "count": int(len(s)),
    }


def _agg_name(agg: str) -> str:
    return {"avg": "mean"}.get(agg, agg or "sum")


def data_labels(edges: list[float]) -> list[str]:
    return [f"{edges[i]:g}–{edges[i + 1]:g}" for i in range(len(edges) - 1)]


def _running(values: list[float]) -> list[float]:
    out = []
    run = 0.0
    for v in values:
        run += v
        out.append(run)
    return out


def _f(v: Any) -> float:
    try:
        return round(float(v), 6)
    except (TypeError, ValueError):
        return 0.0