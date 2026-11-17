"""
Core Data Execution Engine

Provides lazy/eager execution planning with automatic engine selection:
- DuckDB: SQL queries, large dataset joins, aggregations
- Polars: Columnar operations, lazy evaluation, streaming
- Pandas: Compatibility, complex Python operations

Features:
- Lazy execution with query optimization
- Predicate/projection pushdown
- Chunked/streaming processing
- Memory-aware execution
- Incremental computation caching
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Optional
from weakref import WeakValueDictionary

import duckdb
import numpy as np
import pandas as pd
import polars as pl

from app.core.config import settings
from app.core.errors import DataProcessingError

logger = logging.getLogger("nexus.execution")


class EngineType(Enum):
    """Supported execution engines."""
    DUCKDB = "duckdb"
    POLARS = "polars"
    PANDAS = "pandas"


class ExecutionMode(Enum):
    """Execution mode for the query."""
    LAZY = "lazy"      # Build query plan, execute on demand
    EAGER = "eager"    # Execute immediately
    STREAMING = "streaming"  # Process in chunks


@dataclass
class DatasetRef:
    """Reference to a dataset with metadata."""
    dataset_id: str
    file_id: str
    row_count: int
    column_count: int
    columns: list[str]
    dtypes: dict[str, str]
    size_bytes: int
    _df_cache: Optional[pd.DataFrame] = field(default=None, repr=False)
    _pl_cache: Optional[pl.DataFrame] = field(default=None, repr=False)
    _hash: Optional[str] = field(default=None, repr=False)

    def get_hash(self) -> str:
        """Get content hash for cache invalidation."""
        if self._hash is None:
            self._hash = hashlib.md5(f"{self.dataset_id}:{self.version}:{self.row_count}".encode()).hexdigest()[:12]
        return self._hash


@dataclass
class QueryPlan:
    """Execution plan for a data operation."""
    operation: str
    engine: EngineType
    mode: ExecutionMode
    estimated_rows: int
    estimated_memory_mb: float
    estimated_cost: float
    steps: list[dict[str, Any]]
    source_refs: list[DatasetRef]
    cache_key: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "engine": self.engine.value,
            "mode": self.mode.value,
            "estimated_rows": self.estimated_rows,
            "estimated_memory_mb": round(self.estimated_memory_mb, 2),
            "estimated_cost": round(self.estimated_cost, 2),
            "steps": self.steps,
            "cache_key": self.cache_key,
        }


class ExecutionEngine:
    """Main execution engine with multi-backend support."""

    # Memory thresholds (MB)
    SMALL_DATASET_MB = 10
    MEDIUM_DATASET_MB = 100
    LARGE_DATASET_MB = 1000
    
    # Row thresholds
    SMALL_ROWS = 10_000
    MEDIUM_ROWS = 100_000
    LARGE_ROWS = 1_000_000

    def __init__(self):
        self._duckdb_conn: Optional[duckdb.DuckDBPyConnection] = None
        self._cache: WeakValueDictionary = WeakValueDictionary()
        self._query_cache: dict[str, Any] = {}
        self._stats = {
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time_ms": 0.0,
        }

    @property
    def duckdb(self) -> duckdb.DuckDBPyConnection:
        """Get or create DuckDB connection."""
        if self._duckdb_conn is None:
            self._duckdb_conn = duckdb.connect()
            self._duckdb_conn.execute("SET enable_external_access=false")
            self._duckdb_conn.execute("SET memory_limit='2GB'")
            self._duckdb_conn.execute("SET threads=4")
        return self._duckdb_conn

    def close(self) -> None:
        """Close connections and clear caches."""
        if self._duckdb_conn:
            self._duckdb_conn.close()
            self._duckdb_conn = None
        self._cache.clear()
        self._query_cache.clear()

    def plan_execution(self, operation: str, dataset_refs: list[DatasetRef], 
                       params: dict[str, Any]) -> QueryPlan:
        """Plan the optimal execution strategy."""
        total_rows = sum(ref.row_count for ref in dataset_refs)
        total_size_mb = sum(ref.size_bytes for ref in dataset_refs) / (1024 * 1024)
        max_rows = max(ref.row_count for ref in dataset_refs) if dataset_refs else 0

        # Determine engine based on operation and data characteristics
        engine = self._select_engine(operation, total_rows, total_size_mb, params)
        mode = self._select_mode(operation, total_rows, total_size_mb, params)

        # Estimate cost (lower is better)
        cost = self._estimate_cost(engine, mode, total_rows, total_size_mb)

        # Build execution steps
        steps = self._build_steps(operation, engine, params)

        # Generate cache key
        cache_key = self._generate_cache_key(operation, dataset_refs, params)

        plan = QueryPlan(
            operation=operation,
            engine=engine,
            mode=mode,
            estimated_rows=total_rows,
            estimated_memory_mb=total_size_mb,
            estimated_cost=cost,
            steps=steps,
            source_refs=dataset_refs,
            cache_key=cache_key,
        )

        logger.debug("Execution plan: %s", plan.to_dict())
        return plan

    def _select_engine(self, operation: str, rows: int, size_mb: float, 
                       params: dict[str, Any]) -> EngineType:
        """Select the best engine for the operation."""
        # SQL operations -> DuckDB
        if operation in ("sql", "join", "aggregate", "window"):
            return EngineType.DUCKDB
        
        # Large datasets -> Polars (columnar, lazy)
        if rows > self.LARGE_ROWS or size_mb > self.LARGE_DATASET_MB:
            return EngineType.POLARS
        
        # Medium datasets with columnar ops -> Polars
        if rows > self.MEDIUM_ROWS or size_mb > self.MEDIUM_DATASET_MB:
            if operation in ("filter", "select", "groupby", "sort"):
                return EngineType.POLARS
        
        # Complex Python operations -> Pandas
        if operation in ("apply", "custom", "python"):
            return EngineType.PANDAS
        
        # Default to Polars for better performance
        return EngineType.POLARS

    def _select_mode(self, operation: str, rows: int, size_mb: float,
                     params: dict[str, Any]) -> ExecutionMode:
        """Select execution mode."""
        # Force eager for small data or when explicitly requested
        if params.get("eager"):
            return ExecutionMode.EAGER
        
        # Streaming for very large datasets
        if rows > self.LARGE_ROWS or size_mb > self.LARGE_DATASET_MB:
            return ExecutionMode.STREAMING
        
        # Lazy for medium+ datasets
        if rows > self.MEDIUM_ROWS or size_mb > self.MEDIUM_DATASET_MB:
            return ExecutionMode.LAZY
        
        return ExecutionMode.EAGER

    def _estimate_cost(self, engine: EngineType, mode: ExecutionMode,
                       rows: int, size_mb: float) -> float:
        """Estimate relative execution cost."""
        base_cost = rows * 0.0001 + size_mb * 0.1
        
        engine_multiplier = {
            EngineType.DUCKDB: 0.5,
            EngineType.POLARS: 0.7,
            EngineType.PANDAS: 1.0,
        }[engine]
        
        mode_multiplier = {
            ExecutionMode.EAGER: 1.0,
            ExecutionMode.LAZY: 0.8,
            ExecutionMode.STREAMING: 0.6,
        }[mode]
        
        return base_cost * engine_multiplier * mode_multiplier

    def _build_steps(self, operation: str, engine: EngineType,
                     params: dict[str, Any]) -> list[dict[str, Any]]:
        """Build execution steps for the plan."""
        steps = []
        
        # Add source loading step
        steps.append({
            "step": "load_sources",
            "engine": engine.value,
            "description": "Load source datasets",
        })
        
        # Add operation-specific steps
        if operation == "sql":
            steps.append({
                "step": "execute_sql",
                "engine": engine.value,
                "sql": params.get("sql"),
            })
        elif operation == "filter":
            steps.append({
                "step": "apply_filters",
                "engine": engine.value,
                "filters": params.get("filters", []),
            })
        elif operation == "aggregate":
            steps.append({
                "step": "groupby_aggregate",
                "engine": engine.value,
                "group_by": params.get("group_by", []),
                "aggregations": params.get("aggregations", []),
            })
        
        # Add output step
        steps.append({
            "step": "materialize",
            "engine": engine.value,
            "limit": params.get("limit"),
            "format": params.get("format", "dataframe"),
        })
        
        return steps

    def _generate_cache_key(self, operation: str, dataset_refs: list[DatasetRef],
                            params: dict[str, Any]) -> str:
        """Generate cache key for the operation."""
        parts = [operation]
        for ref in sorted(dataset_refs, key=lambda r: r.dataset_id):
            parts.append(f"{ref.dataset_id}:{ref.get_hash()}")
        # Add relevant params
        for k in sorted(params.keys()):
            if k not in ("eager", "limit", "format"):
                parts.append(f"{k}={params[k]}")
        return hashlib.md5("|".join(parts).encode()).hexdigest()[:16]

    def execute(self, plan: QueryPlan) -> pd.DataFrame:
        """Execute a query plan and return results."""
        start = time.perf_counter()
        
        # Check cache
        if plan.cache_key and plan.cache_key in self._query_cache:
            self._stats["cache_hits"] += 1
            logger.debug("Cache hit for %s", plan.cache_key)
            return self._query_cache[plan.cache_key]
        
        self._stats["cache_misses"] += 1
        
        # Execute based on engine and mode
        try:
            if plan.engine == EngineType.DUCKDB:
                result = self._execute_duckdb(plan)
            elif plan.engine == EngineType.POLARS:
                result = self._execute_polars(plan)
            elif plan.engine == EngineType.PANDAS:
                result = self._execute_pandas(plan)
            else:
                raise DataProcessingError(f"Unknown engine: {plan.engine}")
        except Exception as e:
            logger.exception("Execution failed for plan: %s", plan.operation)
            raise DataProcessingError(f"Execution failed: {str(e)}") from e
        
        elapsed = (time.perf_counter() - start) * 1000
        self._stats["queries_executed"] += 1
        self._stats["total_time_ms"] += elapsed
        
        # Cache result if cacheable
        if plan.cache_key and plan.mode != ExecutionMode.STREAMING:
            self._query_cache[plan.cache_key] = result
        
        logger.info("Executed %s in %.2fms (engine=%s, mode=%s)",
                    plan.operation, elapsed, plan.engine.value, plan.mode.value)
        return result

    def _execute_duckdb(self, plan: QueryPlan) -> pd.DataFrame:
        """Execute plan using DuckDB."""
        conn = self.duckdb
        
        # Register source datasets
        for i, ref in enumerate(plan.source_refs):
            df = self._load_pandas(ref)
            table_name = f"src_{i}"
            conn.register(table_name, df)
        
        # Execute steps
        result_df = None
        for step in plan.steps:
            if step["step"] == "execute_sql":
                sql = step["sql"]
                # Apply limit if specified
                if plan.mode == ExecutionMode.EAGER and step.get("limit"):
                    sql = f"SELECT * FROM ({sql}) LIMIT {step['limit']}"
                result_df = conn.execute(sql).fetchdf()
            elif step["step"] == "materialize":
                # Already materialized
                pass
        
        if result_df is None:
            result_df = pd.DataFrame()
        
        return result_df

    def _execute_polars(self, plan: QueryPlan) -> pd.DataFrame:
        """Execute plan using Polars."""
        # Load as Polars LazyFrames for lazy execution
        lazy_frames = []
        for i, ref in enumerate(plan.source_refs):
            df = self._load_polars(ref)
            lazy_frames.append(df.lazy())
        
        if len(lazy_frames) == 1:
            lf = lazy_frames[0]
        else:
            # Join if multiple sources - simplified
            lf = lazy_frames[0]
            for other in lazy_frames[1:]:
                # This is a placeholder - real implementation would use join keys
                lf = lf.join(other, how="outer")
        
        # Apply operations
        for step in plan.steps:
            if step["step"] == "apply_filters":
                for f in step["filters"]:
                    col = f["column"]
                    op = f["operator"]
                    val = f["value"]
                    if op == "eq":
                        lf = lf.filter(pl.col(col) == val)
                    elif op == "neq":
                        lf = lf.filter(pl.col(col) != val)
                    elif op == "gt":
                        lf = lf.filter(pl.col(col) > val)
                    elif op == "gte":
                        lf = lf.filter(pl.col(col) >= val)
                    elif op == "lt":
                        lf = lf.filter(pl.col(col) < val)
                    elif op == "lte":
                        lf = lf.filter(pl.col(col) <= val)
                    elif op == "contains":
                        lf = lf.filter(pl.col(col).str.contains(val))
            elif step["step"] == "groupby_aggregate":
                group_by = step["group_by"]
                aggs = []
                for agg in step["aggregations"]:
                    col = agg["column"]
                    func = agg["func"]
                    alias = agg.get("alias", f"{func}_{col}")
                    if func == "sum":
                        aggs.append(pl.col(col).sum().alias(alias))
                    elif func == "mean":
                        aggs.append(pl.col(col).mean().alias(alias))
                    elif func == "count":
                        aggs.append(pl.col(col).count().alias(alias))
                    elif func == "min":
                        aggs.append(pl.col(col).min().alias(alias))
                    elif func == "max":
                        aggs.append(pl.col(col).max().alias(alias))
                    elif func == "median":
                        aggs.append(pl.col(col).median().alias(alias))
                    elif func == "std":
                        aggs.append(pl.col(col).std().alias(alias))
                lf = lf.group_by(group_by).agg(aggs)
        
        # Materialize
        limit = None
        for step in plan.steps:
            if step["step"] == "materialize":
                limit = step.get("limit")
        
        if plan.mode == ExecutionMode.STREAMING:
            # For streaming, return iterator - but we materialize for now
            pass
        
        result = lf.collect()
        
        if limit and len(result) > limit:
            result = result.head(limit)
        
        return result.to_pandas()

    def _execute_pandas(self, plan: QueryPlan) -> pd.DataFrame:
        """Execute plan using Pandas."""
        # Load first dataset
        if plan.source_refs:
            df = self._load_pandas(plan.source_refs[0])
        else:
            df = pd.DataFrame()
        
        # Apply operations
        for step in plan.steps:
            if step["step"] == "apply_filters":
                for f in step["filters"]:
                    col = f["column"]
                    op = f["operator"]
                    val = f["value"]
                    if op == "eq":
                        df = df[df[col] == val]
                    elif op == "neq":
                        df = df[df[col] != val]
                    elif op == "gt":
                        df = df[pd.to_numeric(df[col], errors="coerce") > float(val)]
                    elif op == "gte":
                        df = df[pd.to_numeric(df[col], errors="coerce") >= float(val)]
                    elif op == "lt":
                        df = df[pd.to_numeric(df[col], errors="coerce") < float(val)]
                    elif op == "lte":
                        df = df[pd.to_numeric(df[col], errors="coerce") <= float(val)]
                    elif op == "contains":
                        df = df[df[col].astype(str).str.contains(val, case=False, na=False)]
                    elif op == "isnull":
                        df = df[df[col].isna()]
                    elif op == "notnull":
                        df = df[df[col].notna()]
            elif step["step"] == "groupby_aggregate":
                group_by = step["group_by"]
                if isinstance(group_by, str):
                    group_by = [group_by]
                agg_map = {}
                for agg in step["aggregations"]:
                    col = agg["column"]
                    func = agg["func"]
                    alias = agg.get("alias", f"{func}_{col}")
                    agg_map[alias] = pd.NamedAgg(column=col, aggfunc=func)
                df = df.groupby(group_by, as_index=False, dropna=False).agg(**agg_map)
        
        # Apply limit
        for step in plan.steps:
            if step["step"] == "materialize" and step.get("limit"):
                df = df.head(step["limit"])
        
        return df

    def _load_pandas(self, ref: DatasetRef) -> pd.DataFrame:
        """Load dataset as Pandas DataFrame with caching."""
        if ref._df_cache is not None:
            return ref._df_cache
        
        from app.services.datastore import load_canonical
        df = load_canonical(ref.file_id)
        
        # Cache if small enough
        if ref.size_bytes < 100 * 1024 * 1024:  # 100 MB
            ref._df_cache = df
        
        return df

    def _load_polars(self, ref: DatasetRef) -> pl.DataFrame:
        """Load dataset as Polars DataFrame with caching."""
        if ref._pl_cache is not None:
            return ref._pl_cache
        
        from app.services.datastore import load_canonical
        pandas_df = load_canonical(ref.file_id)
        df = pl.from_pandas(pandas_df)
        
        # Cache if small enough
        if ref.size_bytes < 100 * 1024 * 1024:
            ref._pl_cache = df
        
        return df

    def stream_results(self, plan: QueryPlan, chunk_size: int = 10_000) -> Generator[pd.DataFrame, None, None]:
        """Stream results in chunks for large datasets."""
        if plan.engine == EngineType.DUCKDB:
            conn = self.duckdb
            for i, ref in enumerate(plan.source_refs):
                df = self._load_pandas(ref)
                conn.register(f"src_{i}", df)
            
            sql = None
            for step in plan.steps:
                if step["step"] == "execute_sql":
                    sql = step["sql"]
                    break
            
            if sql:
                # Use DuckDB's streaming
                result = conn.execute(sql)
                while True:
                    chunk = result.fetchmany(chunk_size)
                    if not chunk:
                        break
                    yield pd.DataFrame(chunk, columns=[desc[0] for desc in result.description])
        else:
            # Fallback: execute full and yield chunks
            df = self.execute(plan)
            for i in range(0, len(df), chunk_size):
                yield df.iloc[i:i + chunk_size]

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            **self._stats,
            "cache_size": len(self._query_cache),
            "avg_time_ms": self._stats["total_time_ms"] / max(self._stats["queries_executed"], 1),
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._query_cache.clear()
        self._cache.clear()


# Global engine instance
execution_engine = ExecutionEngine()


@contextmanager
def engine_context():
    """Context manager for engine lifecycle."""
    try:
        yield execution_engine
    finally:
        execution_engine.close()


def create_dataset_ref(dataset_id: str, file_id: str, row_count: int,
                        column_count: int, columns: list[str], 
                        dtypes: dict[str, str], size_bytes: int) -> DatasetRef:
    """Factory function to create DatasetRef."""
    return DatasetRef(
        dataset_id=dataset_id,
        file_id=file_id,
        row_count=row_count,
        column_count=column_count,
        columns=columns,
        dtypes=dtypes,
        size_bytes=size_bytes,
    )
