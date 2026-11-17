from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps


def _n(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").dropna()


def _nm(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    a = _n(s)
    return a, a


def descriptive(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    cols = columns or [str(c) for c in df.columns]
    out = {"columns": {}}
    for c in cols:
        if c not in df.columns:
            continue
        s = _n(df[c])
        if len(s) == 0:
            out["columns"][c] = {"error": "No numeric values"}
            continue
        out["columns"][c] = {
            "count": int(len(s)),
            "missing": int(df[c].isna().sum()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "mode": [float(v) for v in s.mode()[:3]] if len(s.mode()) else [],
            "std": float(s.std()),
            "var": float(s.var()),
            "min": float(s.min()),
            "max": float(s.max()),
            "range": float(s.max() - s.min()),
            "q1": float(s.quantile(0.25)),
            "q3": float(s.quantile(0.75)),
            "iqr": float(s.quantile(0.75) - s.quantile(0.25)),
            "skewness": float(s.skew()),
            "kurtosis": float(s.kurt()),
            "percentiles": {str(p): float(s.quantile(p / 100)) for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)},
        }
    return out


def _normality_note(s: pd.Series) -> tuple[bool, str]:
    if len(s) < 4 or len(s) > 5000:
        return True, ""
    st = sps.shapiro(s)
    if st.pvalue < 0.05:
        return False, f"Data significantly deviates from normality (Shapiro–Wilk p={st.pvalue:.4f} < 0.05). A non-parametric alternative is recommended."
    return True, ""


def ttest(df: pd.DataFrame, column: str, group: str | None = None,
          mu: float | None = None, paired: bool = False) -> dict[str, Any]:
    if group:
        a = _n(df[column])
        b = _n(df[group])
        if paired:
            idx = a.index.intersection(b.index)
            a, b = a.loc[idx], b.loc[idx]
            if len(a) < 2 or len(a) != len(b):
                raise ValueError("Paired test requires matching observations.")
            res = sps.ttest_rel(a, b)
            kind = "paired t-test"
            effect = float(np.mean(a - b) / np.std(a - b)) if np.std(a - b) else 0.0
        else:
            if len(a) < 2 or len(b) < 2:
                raise ValueError("Both groups need at least 2 observations.")
            res = sps.ttest_ind(a, b, equal_var=False)
            kind = "independent t-test"
            pooled = np.sqrt((a.var() + b.var()) / 2)
            effect = float((a.mean() - b.mean()) / pooled) if pooled else 0.0
        normal_a, note_a = _normality_note(a)
        normal_b, note_b = _normality_note(b)
        interpretation = f"The difference between the two groups is {'statistically significant' if res.pvalue < 0.05 else 'not statistically significant'} (p={res.pvalue:.4f})."
        if not (normal_a and normal_b):
            interpretation += " Warning: parametric result; consider Mann-Whitney or Wilcoxon test."
        return {
            "test": kind,
            "statistic": float(res.statistic),
            "p_value": float(res.pvalue),
            "sample_size": int(len(a)),
            "group_sample_sizes": [int(len(a)), int(len(b))],
            "effect_size": round(effect, 4),
            "group_means": [float(a.mean()), float(b.mean())],
            "confidence_level": 0.95,
            "confidence_interval": _diff_ci(a, b, paired),
            "assumptions": {"normality": normal_a and normal_b, "notes": [note_a, note_b]},
            "interpretation": interpretation,
            "significant": bool(res.pvalue < 0.05),
        }
    mu = mu if mu is not None else 0.0
    res = sps.ttest_1samp(a, mu)
    normal, note = _normality_note(a)
    interpretation = f"The sample mean ({a.mean():.3f}) is {'significantly' if res.pvalue < 0.05 else 'not significantly'} different from {mu} (p={res.pvalue:.4f})."
    return {
        "test": "one-sample t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_size": int(len(a)),
        "sample_mean": float(a.mean()),
        "hypothesized_mean": mu,
        "confidence_level": 0.95,
        "confidence_interval": _mean_ci(a),
        "assumptions": {"normality": normal, "notes": [note]},
        "interpretation": interpretation,
        "significant": bool(res.pvalue < 0.05),
    }


def _mean_ci(s: pd.Series) -> list[float]:
    se = s.std(ddof=1) / np.sqrt(len(s))
    m = s.mean()
    t = sps.t.ppf(0.975, len(s) - 1)
    return [round(m - t * se, 4), round(m + t * se, 4)]


def _diff_ci(a: pd.Series, b: pd.Series, paired: bool) -> list[float]:
    diff = a.values - b.values if not paired else (a - b).values
    se = np.std(diff, ddof=1) / np.sqrt(len(diff))
    t = sps.t.ppf(0.975, len(diff) - 1)
    return [round(diff.mean() - t * se, 4), round(diff.mean() + t * se, 4)]


def anova(df: pd.DataFrame, value: str, groups: str, **_) -> dict[str, Any]:
    s = _n(df[value])
    g = df[groups]
    samples = [s[g == lvl].values for lvl in g.dropna().unique() if len(s[g == lvl]) >= 2]
    if len(samples) < 2:
        raise ValueError("ANOVA requires at least two groups with 2+ observations.")
    res = sps.f_oneway(*samples)
    nobs = sum(len(x) for x in samples)
    effect = _eta_squared(samples)
    interpretation = "Group means are significantly different." if res.pvalue < 0.05 else "No significant difference between group means."
    return {
        "test": "one-way ANOVA",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_size": int(nobs),
        "groups": len(samples),
        "effect_size": round(effect, 4),
        "interpretation": interpretation,
        "significant": bool(res.pvalue < 0.05),
    }


def _eta_squared(samples: list[np.ndarray]) -> float:
    allv = np.concatenate(samples)
    grand = allv.mean()
    ss_between = sum(len(x) * (x.mean() - grand) ** 2 for x in samples)
    ss_total = ((allv - grand) ** 2).sum()
    return ss_between / ss_total if ss_total else 0.0


def chi_square(df: pd.DataFrame, col_a: str, col_b: str, **_) -> dict[str, Any]:
    ct = pd.crosstab(df[col_a], df[col_b])
    st, p, dof, expected = sps.chi2_contingency(ct)
    n = ct.values.sum()
    effect = float(np.sqrt(st / (n * (min(ct.shape) - 1)))) if n and min(ct.shape) > 1 else 0.0
    return {
        "test": "chi-square test of independence",
        "statistic": float(st),
        "p_value": float(p),
        "degrees_of_freedom": int(dof),
        "sample_size": int(n),
        "effect_size": round(effect, 4),
        "interpretation": "The two variables are associated." if p < 0.05 else "No significant association found.",
        "significant": bool(p < 0.05),
    }


def mann_whitney(df: pd.DataFrame, column: str, group: str, **_) -> dict[str, Any]:
    a = _n(df[column])
    b = _n(df[group])
    res = sps.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "test": "Mann-Whitney U test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_size": int(len(a) + len(b)),
        "interpretation": "Distributions differ significantly." if res.pvalue < 0.05 else "No significant difference in distributions.",
        "significant": bool(res.pvalue < 0.05),
    }


def wilcoxon(df: pd.DataFrame, column: str, group: str, **_) -> dict[str, Any]:
    a = _n(df[column])
    b = _n(df[group])
    idx = a.index.intersection(b.index)
    res = sps.wilcoxon(a.loc[idx], b.loc[idx])
    return {
        "test": "Wilcoxon signed-rank test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_size": int(len(idx)),
        "interpretation": "Paired values differ significantly." if res.pvalue < 0.05 else "No significant difference in paired values.",
        "significant": bool(res.pvalue < 0.05),
    }


def kruskal(df: pd.DataFrame, value: str, groups: str, **_) -> dict[str, Any]:
    s = _n(df[value])
    g = df[groups]
    samples = [s[g == lvl].values for lvl in g.dropna().unique() if len(s[g == lvl]) >= 2]
    res = sps.kruskal(*samples)
    return {
        "test": "Kruskal-Wallis H test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "sample_size": int(sum(len(x) for x in samples)),
        "interpretation": "Group distributions differ significantly." if res.pvalue < 0.05 else "No significant difference between group distributions.",
        "significant": bool(res.pvalue < 0.05),
    }


def correlation(df: pd.DataFrame, columns: list[str], method: str = "pearson") -> dict[str, Any]:
    method = method.lower()
    mat = df[columns].apply(pd.to_numeric, errors="coerce")
    if method == "pearson":
        corr = mat.corr(method="pearson")
    elif method == "spearman":
        corr = mat.corr(method="spearman")
    elif method == "kendall":
        corr = mat.corr(method="kendall")
    else:
        raise ValueError("Unknown correlation method")

    pairs = []
    for i, ca in enumerate(columns):
        for cb in columns[i + 1:]:
            a = _n(df[ca])
            b = _n(df[cb])
            idx = a.index.intersection(b.index)
            if len(idx) < 3:
                continue
            if method == "pearson":
                r, p = sps.pearsonr(a.loc[idx], b.loc[idx])
            elif method == "spearman":
                r, p = sps.spearmanr(a.loc[idx], b.loc[idx])
            else:
                r, p = sps.kendalltau(a.loc[idx], b.loc[idx])
            pairs.append({
                "x": str(ca),
                "y": str(cb),
                "r": round(float(r), 4),
                "p_value": round(float(p), 6),
                "n": int(len(idx)),
                "strength": _corr_strength(r),
                "significant": bool(p < 0.05),
            })
    pairs.sort(key=lambda x: abs(x["r"]), reverse=True)
    matrix = corr.round(4).fillna("").to_dict()
    return {
        "method": method,
        "matrix": matrix,
        "pairs": pairs,
        "note": "Correlation does not imply causation. A significant correlation only measures the strength of a linear association.",
    }


def _corr_strength(r: float) -> str:
    a = abs(r)
    if a >= 0.8:
        return "very strong"
    if a >= 0.6:
        return "strong"
    if a >= 0.4:
        return "moderate"
    if a >= 0.2:
        return "weak"
    return "very weak"


def linear_regression(df: pd.DataFrame, target: str, features: list[str]) -> dict[str, Any]:
    X = df[features].apply(pd.to_numeric, errors="coerce")
    y = _n(df[target])
    data = X.copy()
    data["__y"] = y
    data = data.dropna()
    if len(data) < len(features) + 2:
        raise ValueError("Not enough complete observations for regression.")
    Xm = data[features].values
    ym = data["__y"].values
    Xd = np.column_stack([np.ones(len(Xm)), Xm])
    try:
        beta, *_ = np.linalg.lstsq(Xd, ym, rcond=None)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Singular matrix; features may be collinear.") from exc
    pred = Xd @ beta
    resid = ym - pred
    n, k = Xd.shape
    sse = float((resid ** 2).sum())
    sst = float(((ym - ym.mean()) ** 2).sum())
    r2 = 1 - sse / sst if sst else 0.0
    rmse = float(np.sqrt(sse / n))
    mse = sse / n
    mae = float(np.abs(resid).mean())
    dof = n - k
    sigma2 = sse / dof if dof > 0 else 0
    cov = sigma2 * np.linalg.inv(Xd.T @ Xd)
    se = np.sqrt(np.diag(cov))
    tstats = beta / se
    from scipy import stats as sps
    pvals = 2 * (1 - sps.t.cdf(np.abs(tstats), dof))
    coefs = []
    names = ["intercept"] + features
    for i, nm in enumerate(names):
        coefs.append({
            "feature": nm,
            "coefficient": round(float(beta[i]), 6),
            "std_error": round(float(se[i]), 6),
            "t_stat": round(float(tstats[i]), 4),
            "p_value": round(float(pvals[i]), 6),
            "significant": bool(pvals[i] < 0.05),
        })
    return {
        "test": "Ordinary least squares (multiple linear regression)",
        "r_squared": round(r2, 4),
        "adjusted_r_squared": round(1 - (1 - r2) * (n - 1) / dof, 4) if dof > 0 else None,
        "rmse": round(rmse, 4),
        "mae": mae,
        "mse": round(mse, 4),
        "observations": int(n),
        "features": features,
        "coefficients": coefs,
        "equation": _equation_text(beta, features),
        "interpretation": f"The model explains {r2 * 100:.1f}% of the variance in {target}.",
    }


def _equation_text(beta: np.ndarray, features: list[str]) -> str:
    terms = [f"{beta[0]:.4f}"]
    for i, f in enumerate(features):
        sign = "+" if beta[i + 1] >= 0 else "-"
        terms.append(f"{sign} {abs(beta[i + 1]):.4f}·{f}")
    return f"y = {' '.join(terms)}"


def time_series(df: pd.DataFrame, date_col: str, value_col: str,
                freq: str = "D", window: int = 7) -> dict[str, Any]:
    s = pd.to_datetime(df[date_col], errors="coerce")
    v = pd.to_numeric(df[value_col], errors="coerce")
    ts = pd.Series(v.values, index=s).sort_index()
    ts = ts[~ts.index.duplicated(keep="last")].dropna()
    if len(ts) < 4:
        raise ValueError("Not enough time series observations.")
    series = ts.resample(freq).sum()
    moving_avg = series.rolling(window=window, min_periods=1).mean()
    if len(series) >= 8:
        x = np.arange(len(series))
        slope, intercept = np.polyfit(x, series.values, 1)
        trend = {"slope": float(slope), "direction": "increasing" if slope > 0 else ("decreasing" if slope < 0 else "flat")}
        pct_change = series.pct_change().dropna()
        growth = {"mean": float(pct_change.mean()), "cagr": float((series.iloc[-1] / series.iloc[0]) ** (1 / max(len(series) - 1, 1)) - 1) if series.iloc[0] else None}
    else:
        trend, growth = {"direction": "n/a"}, {}
    data = [
        {"date": str(idx)[:10], "value": _f(v), "moving_average": _f(ma)}
        for idx, (v, ma) in enumerate(zip(series.values, moving_avg.values))
    ]
    # TO keep payload small, aggregate to max 200 points
    if len(data) > 200:
        step = len(data) / 200
        data = [data[int(i * step)] for i in range(200)]
    return {
        "series": data,
        "trend": trend,
        "growth": growth,
        "count": int(len(series)),
        "start": str(series.index.min())[:10],
        "end": str(series.index.max())[:10],
        "freq": freq,
        "window": window,
    }


def _f(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), 4)


STAT_TESTS = {
    "ttest": ttest,
    "anova": anova,
    "chi_square": chi_square,
    "mann_whitney": mann_whitney,
    "wilcoxon": wilcoxon,
    "kruskal": kruskal,
}


def run_test(name: str, df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    if name not in STAT_TESTS:
        raise ValueError(f"Unknown statistical test '{name}'")
    return STAT_TESTS[name](df, **params)