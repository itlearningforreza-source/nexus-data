from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    HistGradientBoostingClassifier, HistGradientBoostingRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor, IsolationForest,
)
from sklearn.linear_model import (
    LinearRegression, Ridge, Lasso, ElasticNet, LogisticRegression,
)

logger = logging.getLogger("nexus")
from sklearn.cluster import KMeans, DBSCAN
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, silhouette_score,
)
from sklearn.inspection import permutation_importance

from app.core.errors import ValidationError

REGRESSORS = {
    "linear_regression": LinearRegression,
    "ridge": lambda: Ridge(alpha=1.0),
    "lasso": lambda: Lasso(alpha=0.1, max_iter=20000),
    "elasticnet": lambda: ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=20000),
    "random_forest": lambda: RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
    "gradient_boosting": lambda: GradientBoostingRegressor(random_state=42),
    "hist_gradient_boosting": lambda: HistGradientBoostingRegressor(random_state=42),
    "knn": lambda: KNeighborsRegressor(),
    "svm": lambda: SVR(kernel="rbf"),
}

CLASSIFIERS = {
    "logistic_regression": lambda: LogisticRegression(max_iter=2000, random_state=42),
    "random_forest": lambda: RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
    "gradient_boosting": lambda: GradientBoostingClassifier(random_state=42),
    "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(random_state=42),
    "knn": lambda: KNeighborsClassifier(),
    "svm": lambda: SVC(probability=True, random_state=42),
}


def _prepare_xy(df: pd.DataFrame, target: str, features: list[str], task: str):
    X = df[features].copy()
    y = df[target].copy()
    if task == "classification":
        le = LabelEncoder()
        y = le.fit_transform(y.astype(str))
        y = pd.Series(y, index=df.index)
    else:
        try_count = 0
    return X, y


def _build_preprocessor(features: list[str], df: pd.DataFrame) -> ColumnTransformer:
    transformers = []
    numeric = []
    categorical = []
    for f in features:
        dt = str(df[f].dtype)
        if dt.startswith("int") or dt.startswith("float") or dt.startswith("bool"):
            numeric.append(f)
        else:
            categorical.append(f)
    if numeric:
        transformers.append(("num", SkPipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric))
    if categorical:
        from sklearn.preprocessing import OneHotEncoder
        transformers.append(("cat", SkPipeline([("impute", SimpleImputer(strategy="constant", fill_value="missing")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical))
    return ColumnTransformer(transformers, remainder="drop")


def run_ml(df: pd.DataFrame, *, target: str, features: list[str] | None = None,
           task: str | None = None, algorithms: list[str] | None = None,
           test_size: float = 0.25, random_state: int = 42) -> dict[str, Any]:
    if target not in df.columns:
        raise ValidationError(f"Target column '{target}' not found in the dataset.")
    n_classes_guess = df[target].nunique(dropna=True)

    infer_task = task
    if not infer_task:
        if pd.api.types.is_numeric_dtype(df[target]) and (n_classes_guess > 12 or str(df[target].dtype).startswith("float")):
            infer_task = "regression"
        else:
            infer_task = "classification"

    if features is None:
        default_features = []
        for c in df.columns:
            if c == target:
                continue
            nunique = df[c].nunique(dropna=True)
            if str(df[c].dtype) in ("object", "category"):
                if nunique <= 20 and nunique > 1:
                    default_features.append(c)
            elif nunique > 1:
                default_features.append(c)
        features = default_features[:30]
    features = [c for c in features if c != target]
    missing = [c for c in features if c not in df.columns]
    if missing:
        raise ValidationError(f"Unknown feature column(s): {', '.join(missing)}")
    if len(features) < 1:
        raise ValidationError("No usable feature columns. Provide at least one numeric or low-cardinality categorical column.")

    if infer_task == "clustering":
        result = _run_clustering(df, features, algorithms)
        result["task"] = "clustering"
        return result
    if infer_task == "anomaly":
        result = _run_anomaly(df, features, algorithms)
        result["task"] = "anomaly"
        return result

    X, y_raw = _prepare_xy(df, target, features, infer_task)
    idx = X.index.intersection(y_raw.index)
    X, y_raw = X.loc[idx], y_raw.loc[idx]
    valid = pd.Series(True, index=X.index)
    for c in features:
        if str(df[c].dtype) not in ("object", "category") or df[c].nunique() > 50:
            valid = valid & pd.to_numeric(X[c], errors="coerce").notna()
        else:
            valid = valid & X[c].notna()
    X, y_raw = X[valid], y_raw[valid]
    if len(X) < 10:
        raise ValidationError("Too few clean observations to train a model (need ≥ 10).")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_raw, test_size=test_size, random_state=random_state, stratify=y_raw if infer_task == "classification" else None
    )

    pre = _build_preprocessor(features, df)
    algorithms = algorithms or (list(CLASSIFIERS) if infer_task == "classification" else list(REGRESSORS))
    algorithms = [a for a in algorithms if a in (CLASSIFIERS if infer_task == "classification" else REGRESSORS)][:8]

    runs = []
    for algo in algorithms:
        try:
            model_cls = (CLASSIFIERS if infer_task == "classification" else REGRESSORS)[algo]
            model = model_cls()
            pipe = SkPipeline([("pre", pre), ("model", model)])
            start = time.perf_counter()
            pipe.fit(X_train, y_train)
            duration = (time.perf_counter() - start) * 1000
            pred = pipe.predict(X_test)
            metrics = _eval_metrics(infer_task, y_test, pred, pipe, X_test)
            runs.append({
                "algorithm": algo,
                "metrics": metrics,
                "duration_ms": round(duration, 1),
            })
        except Exception as exc:  # noqa: BLE001
            runs.append({"algorithm": algo, "error": str(exc)[:300]})

    runs = [r for r in runs if "error" not in r]
    if not runs:
        raise ValidationError("All model algorithms failed to train. Check the target column and features.")

    if infer_task == "regression":
        runs.sort(key=lambda r: r["metrics"]["rmse"])
        best_key = "rmse"
    else:
        runs.sort(key=lambda r: r["metrics"]["f1"], reverse=True)
        best_key = "f1"

    best = runs[0]
    best_pipe = None
    best_algo = best["algorithm"]
    model_cls = (CLASSIFIERS if infer_task == "classification" else REGRESSORS)[best_algo]
    pipe = SkPipeline([("pre", pre), ("model", model_cls())])
    pipe.fit(X_train, y_train)

    importance = _feature_importance(pipe, X_train, X_test, y_test, best_algo, infer_task, features)

    confusion = None
    if infer_task == "classification":
        pred_final = pipe.predict(X_test)
        cm = confusion_matrix(y_test, pred_final)
        confusion = cm.tolist()
        classes = sorted(set(np.unique(y_test).tolist() + np.unique(pred_final).tolist()))
        try:
            y_prob = pipe.predict_proba(X_test)
            pos = y_prob[:, -1]
            auc = roc_auc_score(y_test, pos) if len(set(y_test)) == 2 else None
        except Exception as e:
            logger.debug("Failed to compute AUC: %s", e)
            auc = None
        best["metrics"]["roc_auc"] = round(float(auc), 4) if auc is not None else None
        best["metrics"]["confusion"] = {"matrix": confusion, "classes": [str(c) for c in classes]}
        # accuracy is already in best["metrics"]

    return {
        "task": infer_task,
        "target": target,
        "features": features,
        "sample_size": int(len(X)),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "models": runs,
        "best_model": best_algo,
        "best_metric": best["metrics"].get(best_key),
        "best_metrics": best["metrics"],
        "feature_importance": importance,
    }


def _eval_metrics(task: str, y_true, y_pred, pipe, X_test) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    if task == "regression":
        metrics["mae"] = round(float(mean_absolute_error(y_true, y_pred)), 4)
        metrics["mse"] = round(float(mean_squared_error(y_true, y_pred)), 4)
        metrics["rmse"] = round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4)
        metrics["r2"] = round(float(r2_score(y_true, y_pred)), 4)
        yt = np.asarray(y_true)
        mask = yt != 0
        metrics["mape"] = round(float(np.mean(np.abs((yt[mask] - np.asarray(y_pred)[mask]) / yt[mask])) * 100), 2) if mask.sum() else None
    else:
        metrics["accuracy"] = round(float(accuracy_score(y_true, y_pred)), 4)
        try:
            metrics["precision"] = round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 4)
            metrics["recall"] = round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 4)
            metrics["f1"] = round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 4)
        except Exception as e:
            logger.debug("Failed to compute classification metrics: %s", e)
    return metrics


def _feature_importance(pipe, X_train, X_test, y_test, algo, task, features) -> list[dict[str, Any]]:
    try:
        model = pipe.named_steps["model"]
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            coef = np.asarray(model.coef_).ravel()
            importances = np.abs(coef)
        else:
            importances = None
        if importances is not None:
            names = _transformed_feature_names(pipe, X_train, features)
            if names is None or len(names) != len(importances):
                # fall back to permutation importance
                perm = permutation_importance(pipe, X_test, y_test, n_repeats=3, random_state=42)
                importances = perm.importances_mean
                names = _perm_feature_names(pipe, X_test, features)
            top = sorted(zip(names, importances), key=lambda t: -abs(t[1]))[:30]
            total = sum(abs(v) for _, v in top) or 1
            return [{"feature": n, "importance": round(float(v), 6), "normalized": round(float(abs(v)) / total, 4)} for n, v in top]
    except Exception as e:
        logger.debug("Failed to compute feature importance: %s", e)
    return []


def _transformed_feature_names(pipe, X: pd.DataFrame, features: list[str]):
    try:
        pre = pipe.named_steps["pre"]
        return pre.get_feature_names_out()
    except Exception as e:
        logger.debug("Failed to get feature names: %s", e)
        return None


def _perm_feature_names(pipe, X_test: pd.DataFrame, features: list[str]):
    try:
        return pipe.named_steps["pre"].get_feature_names_out()
    except Exception as e:
        logger.debug("Failed to get perm feature names: %s", e)
        return features


def _run_clustering(df: pd.DataFrame, features: list[str], algorithms: list[str] | None) -> dict[str, Any]:
    X = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 5:
        raise ValidationError("Clustering requires at least 5 complete rows.")
    data = X.values
    scaler = StandardScaler()
    Xs = scaler.fit_transform(data)
    k = min(int(len(Xs)) // 2, 5) if len(Xs) < 20 else 5
    algos = algorithms or ["kmeans", "dbscan"]
    results = []
    for algo in algos:
        try:
            if algo == "kmeans":
                model = KMeans(n_clusters=min(k, len(np.unique(Xs, axis=0))), random_state=42, n_init=10)
                labels = model.fit_predict(Xs)
            elif algo == "dbscan":
                model = DBSCAN(eps=0.5, min_samples=3)
                labels = model.fit_predict(Xs)
            else:
                continue
            sil = silhouette_score(Xs, labels) if len(set(labels)) > 1 else 0.0
            results.append({
                "algorithm": algo,
                "silhouette_score": round(float(sil), 4),
                "clusters": int(labels.max() + 1),
                "distribution": [int((labels == c).sum()) for c in range(int(labels.max()) + 1)],
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"algorithm": algo, "error": str(exc)[:300]})
    results = [r for r in results if "error" not in r]
    best = max(results, key=lambda r: r["silhouette_score"]) if results else None
    return {
        "clustering": results,
        "best_model": best["algorithm"] if best else None,
        "features": features,
        "sample_size": int(len(X)),
    }


def _run_anomaly(df: pd.DataFrame, features: list[str], algorithms: list[str] | None) -> dict[str, Any]:
    X = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 10:
        raise ValidationError("Anomaly detection requires at least 10 complete rows.")
    model = IsolationForest(random_state=42, contamination="auto")
    preds = model.fit_predict(X)
    n_anomalies = int((preds == -1).sum())
    return {
        "anomalies_count": n_anomalies,
        "anomaly_share": round(n_anomalies / len(X) * 100, 2),
        "features": features,
        "sample_size": int(len(X)),
        "algorithm": "isolation_forest",
        "predictions_probe": [int(p) for p in preds[:100]],
    }


TASKS = {
    "classification": {
        "models": list(CLASSIFIERS),
        "metrics": ["accuracy", "precision", "recall", "f1", "roc_auc"],
    },
    "regression": {
        "models": list(REGRESSORS),
        "metrics": ["mae", "mse", "rmse", "r2", "mape"],
    },
    "clustering": {
        "models": ["kmeans", "dbscan"],
        "metrics": ["silhouette_score"],
    },
    "anomaly": {
        "models": ["isolation_forest"],
        "metrics": ["anomalies_count"],
    },
}