from __future__ import annotations

import json
import logging
import re
from typing import Any

import pandas as pd

from app.core.config import settings
from app.services import charts as chart_service
from app.services import profile as profile_service
from app.services import quality as quality_service
from app.services import stats as stats_service

logger = logging.getLogger("nexus")


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def _pct(v: Any) -> str:
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return str(v)


def build_dataset_context(df: pd.DataFrame, dataset_name: str) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "dataset": dataset_name,
        "rows": len(df),
        "columns_count": len(df.columns),
    }
    prof = profile_service.profile_dataframe(df)
    ctx["profile"] = {
        "columns": [
            {
                "name": c["name"], "dtype": c["dtype"], "numeric": c["numeric"],
                "null_pct": c["null_pct"], "unique": c["unique_count"],
                "mean": c["stats"].get("mean"), "min": c["stats"].get("min"),
                "max": c["stats"].get("max"), "sum": c["stats"].get("sum"),
                "median": c["stats"].get("median"),
            }
            for c in prof["columns"]
        ],
        "missing_pct": prof["null_pct"],
    }
    q = quality_service.quality_issues(df)
    ctx["quality"] = {
        "score": q["score"],
        "issues": [{"type": i["type"], "severity": i["severity"], "message": i["message"]} for i in q["issues"][:8]],
    }
    numerics = [c for c in prof["columns"] if c["numeric"]]
    if numerics:
        cols = [c["name"] for c in numerics[:6]]
        try:
            ctx["correlations"] = stats_service.correlation(df, cols, "pearson")["pairs"][:5]
        except Exception as e:
            logger.debug("Failed to compute correlations: %s", e)
            ctx["correlations"] = []
    cats = [c for c in prof["columns"] if c["dtype"] in ("object", "categorical")][:6]
    ctx["top_categories"] = {
        c["name"]: [t["value"] for t in c["top_values"][:5]]
        for c in prof["columns"] if c["name"] in [x["name"] for x in cats]
    }
    return ctx


def _detect_intent(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ("outlier", "extreme", "anomal")) and ("regres" not in q):
        return "outliers"
    if any(k in q for k in ("regress", "linear", "predict")):
        return "regression"
    if any(k in q for k in ("why", "decline", "drop", "fell", "down", "turun")):
        return "decline"
    if any(k in q for k in ("most profitable", "best selling", "top product", "top category",
                            "which product", "most revenue", "biggest")):
        return "top_breakdown"
    if any(k in q for k in ("compare", "comparison", "per region", "by region", "antar", "banding")):
        return "compare"
    if any(k in q for k in ("correlat")):
        return "correlation"
    if any(k in q for k in ("trend", "over time", "monthly", "time")):
        return "trend"
    if any(k in q for k in ("summary", "overview", "ringkasan", "analisis", "insight", "summary")):
        return "summary"
    if any(k in q for k in ("chart", "visual", "plot", "grafik")):
        return "chart"
    if any(k in q for k in ("clean", "missing", "quality", "duplicate", "data quality")):
        return "quality"
    if any(k in q for k in ("recommend", "suggestion", "saran")):
        return "recommend"
    return "summary"


def _top_by(df: pd.DataFrame, group: str, value: str, func: str = "sum", n: int = 8) -> list[dict[str, Any]]:
    agg = {"sum": "sum", "avg": "mean", "count": "count", "max": "max", "min": "min"}.get(func, "sum")
    grouped = df.groupby(group)[value].agg(agg).dropna().sort_values(ascending=False)
    return [
        {"group": str(k), "value": float(v)} for k, v in grouped.head(n).items()
    ]


def run_intent(df: pd.DataFrame, intent: str, question: str) -> dict[str, Any]:
    ctx = build_dataset_context(df, "dataset")
    numerics = [c for c in ctx["profile"]["columns"] if c["numeric"] and c["null_pct"] < 60]
    cats = [c for c in ctx["profile"]["columns"] if c["dtype"] in ("object", "categorical") and c["null_pct"] < 60]

    out: dict[str, Any] = {"intent": intent, "finds": [], "charts": [], "insights": [], "answer_md": ""}
    if intent == "summary":
        out["finds"] = _make_summary(ctx)
        out["charts"] = _recommended_chart_specs(df)
    elif intent == "outliers":
        o = _outlier_analysis(df, ctx)
        out.update(o)
    elif intent == "regression":
        r = _regression_analysis(df, ctx)
        out.update(r)
    elif intent == "decline":
        d = _decline_analysis(df)
        out.update(d)
    elif intent == "top_breakdown":
        detail = _top_breakdown_analysis(df)
        out.update(detail)
    elif intent == "compare":
        c = _compare_analysis(df)
        out.update(c)
    elif intent == "correlation":
        corr = _correlation_analysis(df, ctx)
        out.update(corr)
    elif intent == "trend":
        t = _trend_analysis(df)
        out.update(t)
    elif intent == "quality":
        qq = _quality_analysis(ctx)
        out.update(qq)
    elif intent == "chart":
        out.update({"charts": _recommended_chart_specs(df), "finds": _make_summary(ctx)})
    else:  # recommend
        rec = chart_service.recommend_charts(df)
        out["charts"] = [
            {"chart_type": c["chart_type"], "x": c.get("x"), "y": c.get("y"),
             "title": f"{c['chart_type']}: {c.get('y') or c.get('x')}",
             "reason": c["reason"]}
            for c in rec[:5]
        ]
        out["finds"] = _make_summary(ctx)

    out["answer_md"] = _render_answer(out, question)
    return out


def _make_summary(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    prof = ctx["profile"]
    finds = []
    nums = [c for c in prof["columns"] if c["numeric"]]
    if nums:
        biggest = max(nums, key=lambda c: c.get("sum") or 0)
        finds.append({
            "title": f"Highest total: {biggest['name']}",
            "detail": f"Sum of {biggest['sum']:,.0f} · mean {biggest['mean']:,.2f} · range [{biggest['min']:,.2f}, {biggest['max']:,.2f}]",
        })
    missing = [c for c in prof["columns"] if c["null_pct"] > 5]
    if missing:
        worst = max(missing, key=lambda c: c["null_pct"])
        finds.append({
            "title": f"Missing data in {worst['name']}",
            "detail": f"{worst['null_pct']}% of values are empty; fill or drop before modelling.",
        })
    if ctx.get("correlations"):
        top = ctx["correlations"][0]
        finds.append({
            "title": f"Strongest relationship: {top['x']} ↔ {top['y']}",
            "detail": f"r = {top['r']:.3f} (p = {top['p_value']:.4g}, {top['strength']}). Correlation is not causation.",
        })
    q = ctx.get("quality", {})
    finds.append({
        "title": f"Data quality score: {q.get('score', 'n/a')}/100",
        "detail": f"{q.get('issues', []) and len(q['issues'])} issue(s) detected.",
    })
    return finds


def _outlier_analysis(df: pd.DataFrame, ctx: dict[str, Any]) -> dict[str, Any]:
    numerics = [c["name"] for c in ctx["profile"]["columns"] if c["numeric"]]
    res = {"finds": [], "charts": []}
    for c in numerics[:6]:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) < 5:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        mask = (s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)
        n = int(mask.sum())
        if n > 0:
            pct = n / len(s) * 100
            res["finds"].append({
                "title": f"{n} outliers in {c}",
                "detail": f"{pct:.1f}% of values fall beyond 3×IQR [{q1 - 3 * iqr:,.2f}, {q3 + 3 * iqr:,.2f}]. Consider clipping or winsorizing.",
            })
            res["charts"].append({
                "chart_type": "box", "x": None, "y": c, "title": f"Outliers in {c}", "reason": "Box plot visualizes the spread and extreme values.",
            })
    if not res["finds"]:
        res["finds"] = [{"title": "No major outliers", "detail": "No values exceeded the 3×IQR threshold for the numeric columns analysed."}]
    return res


def _regression_analysis(df: pd.DataFrame, ctx: dict[str, Any]) -> dict[str, Any]:
    numerics = [c["name"] for c in ctx["profile"]["columns"] if c["numeric"] and c["null_pct"] < 50]
    if not numerics:
        return {"finds": [{"title": "Regression unavailable", "detail": "No numeric columns with enough clean data."}], "charts": []}
    target = numerics[0]
    features = [c for c in numerics[1:5]]
    if not features:
        return {"finds": [{"title": "Regression unavailable", "detail": "Need at least one numeric feature besides the target."}], "charts": []}
    try:
        r = stats_service.linear_regression(df, target, features[:3])
        coeff_line = "; ".join(
            f"{c['feature']} {c['coefficient']:+.4f} (p={c['p_value']:.4g})"
            for c in r["coefficients"][1:6]
        )
        sig = [c["feature"] for c in r["coefficients"] if c.get("significant")]
        return {
            "finds": [
                {"title": f"Regression on {target}", "detail": f"R² = {r['r_squared']:.3f}, RMSE = {r['rmse']:.3f}, n = {r['observations']}"},
                {"title": "Model equation", "detail": r["equation"]},
                {"title": "Coefficients", "detail": coeff_line or "No significant predictors"},
            ],
            "charts": [{"chart_type": "bar", "x": None, "y": target, "title": f"Feature importance for {target}", "reason": "Model coefficients measure each feature's contribution."}],
        }
    except Exception as exc:  # noqa: BLE001
        return {"finds": [{"title": "Regression failed", "detail": str(exc)}], "charts": []}


def _decline_analysis(df: pd.DataFrame) -> dict[str, Any]:
    cols = [str(c) for c in df.columns]
    date_col = None
    num_col = None
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(df[c]) and date_col is None:
            date_col = c
    if date_col is None:
        for c in cols:
            if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.8 and "id" not in c.lower():
                date_col = c
                break
    for c in cols:
        if pd.api.types.is_numeric_dtype(df[c]) and num_col is None:
            num_col = c
    if not date_col or not num_col:
        return {"finds": [{"title": "Decline analysis unavailable", "detail": "The dataset needs a date and a numeric measure."}], "charts": []}
    ts = df.copy()
    ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
    ts[num_col] = pd.to_numeric(ts[num_col], errors="coerce")
    g = ts.dropna(subset=[date_col, num_col]).groupby(ts[date_col].dt.to_period("M"))[num_col].sum()
    if len(g) < 4:
        return {"finds": [{"title": "Decline analysis unavailable", "detail": "Not enough monthly data points."}], "charts": []}
    diffs = g.diff().dropna()
    drops = diffs[diffs < 0]
    worst = drops.sort_values().head(3) if len(drops) else None
    finds = []
    total_change = ((g.iloc[-1] / g.iloc[0]) - 1) * 100 if g.iloc[0] else 0
    finds.append({
        "title": f"Overall change: {total_change:+.1f}%",
        "detail": f"From {str(g.index[0])} ({g.iloc[0]:,.0f}) to {str(g.index[-1])} ({g.iloc[-1]:,.0f}).",
    })
    if worst is not None and len(worst):
        for period, v in worst.items():
            finds.append({
                "title": f"Largest drop: {period}",
                "detail": f"{v:,.0f} vs. the previous period.",
            })
    finds.append({
        "title": "Monthly trend",
        "detail": "See the line chart; consider seasonality before concluding a structural decline.",
    })
    return {
        "finds": finds,
        "charts": [{"chart_type": "line", "x": date_col, "y": num_col, "title": "Monthly trend", "reason": "Time series of the measure reveals the decline pattern."}],
    }


def _top_breakdown_analysis(df: pd.DataFrame) -> dict[str, Any]:
    cols = [str(c) for c in df.columns]
    cat = None
    num = None
    for c in cols:
        if df[c].dtype == object and cat is None and "id" not in c.lower():
            cat = c
    for c in cols:
        if pd.api.types.is_numeric_dtype(df[c]) and num is None:
            num = c
    if not cat or not num:
        return {"finds": [{"title": "Breakdown unavailable", "detail": "Need a categorical column and a numeric measure."}], "charts": []}
    top = _top_by(df, cat, num, "sum", 8)
    if not top:
        return {"finds": [{"title": "Breakdown unavailable", "detail": "Could not aggregate the columns."}], "charts": []}
    total = sum(t["value"] for t in top)
    finds = [{
        "title": f"Top contributor: {top[0]['group']}",
        "detail": f"{top[0]['value']:,.0f} · {top[0]['value'] / total * 100:.1f}% of the analysed total.",
    }] if total else []
    finds.append({
        "title": "Leaderboard",
        "detail": "; ".join(f"{t['group']}: {t['value']:,.0f}" for t in top[:5]),
    })
    return {
        "finds": finds,
        "charts": [{"chart_type": "bar", "x": cat, "y": num, "title": f"{num} by {cat}", "reason": "Ranked categories show where value concentrates."}],
    }


def _compare_analysis(df: pd.DataFrame) -> dict[str, Any]:
    cols = [str(c) for c in df.columns]
    cats = [c for c in cols if df[c].dtype == object and "id" not in c.lower()]
    nums = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    if not cats or not nums:
        return {"finds": [{"title": "Comparison unavailable", "detail": "Need a categorical grouping column and a numeric measure."}], "charts": []}
    cat, num = cats[0], nums[0]
    means = df.groupby(cat)[num].mean().sort_values(ascending=False)
    top = means.index[0]
    lowest = means.index[-1]
    ratio = means.iloc[0] / means.iloc[-1] if means.iloc[-1] != 0 else None
    finds = [{
        "title": f"Highest average: {top}",
        "detail": f"Mean {num} = {means.iloc[0]:,.2f}" + (f" · {ratio:,.2f}× the lowest ({lowest})" if ratio else ""),
    }]
    return {
        "finds": finds,
        "charts": [{"chart_type": "bar", "x": cat, "y": num, "title": f"Average {num} by {cat}", "reason": "Side-by-side means surface the strongest and weakest groups."}],
    }


def _correlation_analysis(df: pd.DataFrame, ctx: dict[str, Any]) -> dict[str, Any]:
    nums = [c["name"] for c in ctx["profile"]["columns"] if c["numeric"]][:8]
    if len(nums) < 2:
        return {"finds": [{"title": "Correlation unavailable", "detail": "Need at least two numeric columns."}], "charts": []}
    c = stats_service.correlation(df, nums, "pearson")
    finds = []
    for p in c["pairs"][:5]:
        finds.append({
            "title": f"{p['x']} ↔ {p['y']}: r = {p['r']:.3f}",
            "detail": f"{p['strength'].title()} relationship (p = {p['p_value']:.4g}). Correlation does not imply causation.",
        })
    return {
        "finds": finds,
        "charts": [{"chart_type": "heatmap", "x": None, "y": None, "title": "Correlation matrix", "reason": "Heatmap of pairwise Pearson correlations."}],
    }


def _trend_analysis(df: pd.DataFrame) -> dict[str, Any]:
    cols = [str(c) for c in df.columns]
    date_col = next((c for c in cols if pd.api.types.is_datetime64_any_dtype(df[c])), None)
    if not date_col:
        for c in cols:
            if pd.to_datetime(df[c], errors="coerce").notna().mean() > 0.8 and "id" not in c.lower():
                date_col = c
                break
    num = next((c for c in cols if pd.api.types.is_numeric_dtype(df[c])), None)
    if not date_col or not num:
        return {"finds": [{"title": "Trend unavailable", "detail": "Need a date column and numeric measure."}], "charts": []}
    ts = df.copy()
    ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
    ts[num] = pd.to_numeric(ts[num], errors="coerce")
    g = ts.dropna(subset=[date_col, num]).groupby(ts[date_col].dt.to_period("M"))[num].sum()
    if len(g) < 3:
        return {"finds": [{"title": "Trend unavailable", "detail": "Not enough time points."}], "charts": []}
    slope = None
    if len(g) >= 4:
        import numpy as np
        x = list(range(len(g)))
        slope, _ = np.polyfit(x, g.values, 1)
    return {
        "finds": [{
            "title": f"Trend of {num} over time",
            "detail": f"{'Rising' if slope and slope > 0 else ('Falling' if slope and slope < 0 else 'Flat')} · total {g.sum():,.0f} across {len(g)} periods."
        }],
        "charts": [{"chart_type": "line", "x": date_col, "y": num, "title": f"{num} over time", "reason": "Monthly aggregation shows direction and seasonality."}],
    }


def _quality_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
    q = ctx["quality"]
    finds = [{"title": f"Quality score: {q['score']}/100", "detail": f"Completeness, validity, consistency and uniqueness are measured on a weighted scale."}]
    for i in q["issues"][:5]:
        finds.append({"title": f"{i['type'].replace('_', ' ').title()}", "detail": i["message"]})
    return {"finds": finds, "charts": []}


def _recommended_chart_specs(df: pd.DataFrame, k: int = 4) -> list[dict[str, Any]]:
    rec = chart_service.recommend_charts(df)
    out = []
    for c in rec[:k]:
        out.append({
            "chart_type": c["chart_type"], "x": c.get("x"), "y": c.get("y"),
            "title": f"{c['chart_type']}: {c.get('y') or c.get('x')}",
            "reason": c["reason"],
        })
    return out


def _render_answer(result: dict[str, Any], question: str) -> str:
    lines = [f"## Analysis: {question[:90]}\n"]
    finds = result.get("finds", [])
    if finds:
        lines.append("**Key findings**")
        for f in finds:
            lines.append(f"- **{f['title']}** — {f['detail']}")
    charts = result.get("charts", [])
    if charts:
        lines.append("\n**Recommended visualizations**")
        for c in charts:
            lines.append(f"- `{c['chart_type']}` {c.get('x')} × {c.get('y')} — {c.get('reason', '')}")
    lines.append("\n> Every figure above was computed on the actual dataset using the Nexus computation engine.")
    return "\n".join(lines)


def answer(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """Main entrypoint: detect intent, compute, optionally enhance with an external LLM."""
    intent = _detect_intent(question)
    result = run_intent(df, intent, question)

    if settings.AI_API_KEY and settings.AI_BASE_URL:
        try:
            enhanced = _llm_narrative(df, question, result)
            if enhanced:
                result["answer_md"] = enhanced
                result["llm_enhanced"] = True
        except Exception as e:
            logger.warning("LLM enhancement failed: %s", e)
    return result


def _llm_narrative(df: pd.DataFrame, question: str, result: dict[str, Any]) -> str | None:
    import urllib.request

    facts = []
    for f in result.get("finds", []):
        facts.append(f"- {f['title']}: {f['detail']}")
    context = build_dataset_context(df, "dataset")
    profile_line = "Rows: %d, columns: %d. Missing: %s%%. Quality score: %s/100." % (
        context["rows"], context["columns_count"], context["profile"]["missing_pct"], context["quality"]["score"]
    )
    system = (
        "You are a precise data analyst assistant embedded in Nexus Data. "
        "Every number in your answer MUST come from the provided FACTS. Do not invent statistics. "
        "Keep it concise, structured in markdown, beginner-friendly."
    )
    prompt = (
        f"Question: {question}\n\n"
        f"Dataset facts:\n{profile_line}\n\n"
        f"Computed findings (ground truth — use these exact numbers):\n"
        + "\n".join(facts) + "\n"
    )
    payload = {
        "model": settings.AI_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        f"{settings.AI_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.AI_API_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]