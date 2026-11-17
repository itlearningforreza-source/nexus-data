from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import DataProcessingError

logger = logging.getLogger("nexus")

ALLOWED_IMPORTS = {
    "pandas", "numpy", "matplotlib", "seaborn", "scipy", "sklearn", "statsmodels",
    "plotly", "json", "math", "statistics", "re", "datetime", "random", "pyarrow",
}
DENIED_IMPORTS = {
    "os", "sys", "subprocess", "socket", "shutil", "requests", "urllib",
    "http", "pathlib", "importlib", "ctypes", "multiprocessing",
    "sqlalchemy", "fastapi", "flask", "django", "pickle", "marshal",
    "shelve", "sqlite3", "psycopg2", "ftplib", "telnetlib", "paramiko",
    "xlsxwriter", "openpyxl", "getpass", "glob", "tempfile", "zipfile",
    "tarfile", "gzip", "bz2", "build", "email", "ftplib",
}

RUNNER_SOURCE = r"""
import sys, json, base64, io, traceback, os, ast
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

_ALLOWED = {ALLOWED}
_DENIED = {DENIED}

_SAFE_BUILTINS = dict(__builtins__.__dict__)
for _bad in ["open", "exec", "eval", "compile", "input", "quit", "exit", "help", "breakpoint"]:
    _SAFE_BUILTINS.pop(_bad, None)

def _check_imports(source):
    tree = ast.parse(source)
    checked = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                checked.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.module:
                checked.append((node.module, node.lineno))
            elif root:
                checked.append((root, node.lineno))
    for name, lineno in checked:
        root = name.split(".")[0]
        if root in _DENIED:
            raise ImportError(f"Import '{name}' is blocked in the sandbox (line {lineno}).")
        if root not in _ALLOWED:
            raise ImportError(f"Import '{name}' is not allowed in the sandbox (line {lineno}).")

ns = {**{"pd": pd, "np": np, "plt": plt}, "__builtins__": _SAFE_BUILTINS}

df_path = sys.argv[1]
if df_path and os.path.exists(df_path):
    ns["df"] = pd.read_parquet(df_path)

def _summarize(v):
    try:
        if isinstance(v, pd.DataFrame):
            return {"type": "DataFrame", "shape": list(v.shape), "columns": [str(c) for c in v.columns[:20]]}
        if isinstance(v, pd.Series):
            return {"type": "Series", "shape": list(v.shape), "dtype": str(v.dtype), "name": str(v.name)}
        if isinstance(v, np.ndarray):
            return {"type": "ndarray", "shape": list(v.shape), "dtype": str(v.dtype)}
        if callable(v):
            return {"type": "callable", "name": getattr(v, "__name__", type(v).__name__)}
        try:
            return {"type": type(v).__name__, "value": str(v)[:200]}
        except Exception:
            return {"type": type(v).__name__}
    except Exception:
        return {"type": "unknown"}

code = {CODE_JSON}
out = io.StringIO()
_old = sys.stdout
sys.stdout = out
err = None
figs = []
df_preview = None
try:
    _check_imports(code)
    _tree = ast.parse(code)
    compiled = compile(code, "<cell>", "exec")
    exec(compiled, ns, ns)
    if _tree.body:
        _last = _tree.body[-1]
        if isinstance(_last, ast.Expr):
            _val = eval(compile(ast.Expression(_last.value), "<cell>", "eval"), ns)
            if _val is not None and not isinstance(_val, (pd.DataFrame,)):
                _s = str(_val)
                if len(_s) > 2000:
                    _s = _s[:2000] + " ... (truncated)"
                print(_s)
except Exception:
    err = traceback.format_exc()
finally:
    sys.stdout = _old

stdout_text = out.getvalue()
for i in plt.get_fignums():
    fig = plt.figure(i)
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=110)
        figs.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode())
    except Exception:
        pass
    plt.close(fig)

_d = ns.get("df")
if _d is not None and hasattr(_d, "dtypes") and hasattr(_d, "head"):
    try:
        head = _d.head(50)
        import datetime as _dt_mod
        def _js(v):
            try:
                if pd.isna(v):
                    return None
            except (TypeError, ValueError):
                pass
            if isinstance(v, pd.Timestamp):
                return v.isoformat()
            if isinstance(v, _dt_mod.datetime):
                return v.isoformat()
            if isinstance(v, _dt_mod.date):
                return v.isoformat()
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return float(v)
            if isinstance(v, (np.bool_,)):
                return bool(v)
            return v
        grid = head.astype(object).where(pd.notna(head), None)
        rows = [[_js(c) for c in row] for row in grid.values.tolist()]
        df_preview = {
            "columns": [str(c) for c in head.columns],
            "rows": rows,
            "shape": list(_d.shape),
            "dtypes": {str(c): str(t) for c, t in _d.dtypes.items()},
        }
    except Exception:
        df_preview = None

vars_out = []
for k, v in list(ns.items()):
    if k.startswith("_"):
        continue
    if k in ("pd", "np", "plt", "df"):
        continue
    try:
        vars_out.append({"name": k, **(_summarize(v))})
    except Exception:
        pass
vars_out = vars_out[:30]

result = json.dumps({"stdout": stdout_text[:300000], "figures": figs, "df_preview": df_preview, "vars": vars_out, "error": err})
sys.stdout = sys.__stdout__  # ensure the JSON payload goes to the captured pipe
print(result)
"""


def _load_pandas_code() -> str:
    return "\n".join(
        line for line in (
            "import pandas as pd", "import numpy as np",
        )
    )


def execute_cell(code: str, dataset_df=None, dataset_name: str | None = None,
                 timeout: int = 30) -> dict[str, Any]:
    """Execute a sandboxed Python cell. The dataset (if any) is injected as `df`."""
    code = (code or "").replace("\r", "")
    if not code.strip():
        return {"stdout": "", "figures": [], "df_preview": None, "vars": [], "error": None}

    runner_code = RUNNER_SOURCE
    runner_code = runner_code.replace("{ALLOWED}", json.dumps(sorted(ALLOWED_IMPORTS)))
    runner_code = runner_code.replace("{DENIED}", json.dumps(sorted(DENIED_IMPORTS)))
    runner_code = runner_code.replace("{CODE_JSON}", json.dumps(code))

    with tempfile.TemporaryDirectory(prefix="nexus_nb_", dir=settings.cache_dir) as td:
        runner_path = Path(td) / "runner.py"
        df_path = Path(td) / "df.parquet"
        if dataset_df is not None:
            try:
                dataset_df.head(5000).to_parquet(df_path)
            except Exception as e:
                logger.debug("Failed to write parquet, trying feather: %s", e)
                dataset_df.head(5000).to_feather(df_path.with_suffix(".feather"))

        runner_path.write_text(runner_code)
        cmd = [sys.executable, "-u", str(runner_path), str(df_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                cwd=td,
                env={
                    **{k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)},
                    "MPLBACKEND": "Agg",
                },
            )
        except subprocess.TimeoutExpired:
            return {
                "stdout": "", "figures": [], "df_preview": None, "vars": [],
                "error": f"Execution timed out after {timeout} seconds.",
            }
        except Exception as exc:
            logger.warning("Failed to start sandbox: %s", exc)
            return {"stdout": "", "figures": [], "df_preview": None, "vars": [], "error": f"Failed to start sandbox: {exc}"}

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        result: dict[str, Any] = {"stdout": "", "figures": [], "df_preview": None, "vars": [], "error": None}
        for line in reversed(stdout.strip().splitlines()):
            if line.lstrip().startswith("{"):
                try:
                    result = json.loads(line)
                    return result
                except json.JSONDecodeError:
                    continue
        # fallback: no JSON payload
        result["stdout"] = stdout[-5000:] + stderr[-3000:]
        if proc.returncode != 0:
            result["error"] = stderr[-3000:] or "Sandbox process crashed."
        return result


def compute_analysis_from_code(code: str, df=None) -> dict[str, Any]:
    """Convenience wrapper used by the AI analyst for grounded computation."""
    return execute_cell(code, df)