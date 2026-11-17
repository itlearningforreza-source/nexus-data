from __future__ import annotations

import logging
import re
import time
from typing import Any

import duckdb
import pandas as pd

from app.core.errors import SQLSafetyError, DataProcessingError

logger = logging.getLogger("nexus")

ALLOWED_FIRST = {"select", "with", "explain", "values", "show", "describe", "pragma"}
BLOCKED_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|install|load|copy|call|import|export|security_integration)\b",
    re.IGNORECASE,
)
FILE_READS = re.compile(r"(read_csv|read_parquet|read_json|read_csv_auto|glob|write_csv|write_parquet|copy)\s*\(", re.IGNORECASE)


def _safe_table(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name or "t")


def validate_sql(sql: str) -> str:
    stripped = _strip_strings(sql)
    first = stripped.lstrip().split("\n")[0].lstrip()
    m = re.match(r"^([a-zA-Z]+)\b", first)
    if not m or m.group(1).lower() not in ALLOWED_FIRST:
        raise SQLSafetyError(
            "This query is not allowed. Only read-only analytics queries (SELECT / WITH / EXPLAIN) are supported."
        )
    if BLOCKED_KEYWORDS.search(stripped):
        raise SQLSafetyError("This query contains statements that are not permitted on the analytical engine.")
    if FILE_READS.search(stripped):
        raise SQLSafetyError("Reading or writing external files is not permitted.")
    if ".." in sql or "://" in sql.replace("http", ""):
        pass
    return sql


def _strip_strings(sql: str) -> str:
    out = []
    i = 0
    in_str = False
    quote = ""
    while i < len(sql):
        ch = sql[i]
        if in_str:
            out.append(" ")
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(" ")
                    i += 2
                    continue
                in_str = False
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_str = True
            quote = ch
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class SQLResult:
    def __init__(self, columns: list[str], rows: list[list[Any]], row_count: int,
                 truncated: bool, execution_time_ms: float, byte_size: int):
        self.columns = columns
        self.rows = rows
        self.row_count = row_count
        self.truncated = truncated
        self.execution_time_ms = execution_time_ms
        self.byte_size = byte_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "byte_size": self.byte_size,
        }


MAX_ROWS = 5_000
MAX_COLS = 100


def execute_sql(sql: str, tables: dict[str, pd.DataFrame],
                limit: int = MAX_ROWS) -> SQLResult:
    validate_sql(sql)
    if not tables:
        raise DataProcessingError("No dataset is available as an SQL table. Select or upload one first.")
    conn = duckdb.connect()
    try:
        conn.execute("SET enable_external_access=false")
        for name, df in tables.items():
            safe = _safe_table(name)
            conn.register(safe, df)
        start = time.perf_counter()
        # Stream limited result: query wrapped so we only fetch MAX_ROWS
        limited_sql = f"SELECT * FROM (\n{sql}\n) AS _nexus LIMIT {limit}"
        result = conn.execute(limited_sql)
        df = result.fetchdf()
        elapsed = (time.perf_counter() - start) * 1000
        columns = [str(c) for c in df.columns[:MAX_COLS]]
        df = df.iloc[:, :MAX_COLS]

        # total row count (without limit) via COUNT when possible
        total = len(df)
        try:
            count_sql = f"SELECT COUNT(*) FROM (\n{sql}\n) AS _nexus"
            total = int(conn.execute(count_sql).fetchone()[0])
        except Exception as e:
            logger.debug("Failed to get total count: %s", e)
            total = len(df)

        df = df.fillna(value={"": None})
        rows = df.where(pd.notna(df), None).values.tolist()
        truncated = total > len(rows)
        byte_size = int(df.memory_usage(deep=True).sum())
        return SQLResult(columns, rows, int(total), truncated, elapsed, byte_size)
    except SQLSafetyError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DataProcessingError(
            "The SQL query could not be executed.",
            detail={"error": _safe_user_message(str(exc))},
        ) from exc
    finally:
        try:
            conn.close()
        except Exception as e:
            logger.debug("Failed to close connection: %s", e)


def _safe_user_message(msg: str) -> str:
    if "does not exist" in msg or "not found" in msg:
        return "One or more tables or columns do not exist. Check the schema explorer."
    return msg[:500]