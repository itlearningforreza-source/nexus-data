"""
Nexus Data - Services Package

Exports all service modules for the Nexus Data platform.
"""

# Core data services
from .datastore import (
    validate_upload, store_incoming, save_canonical, load_canonical,
    parse_file, dataframe_hash, parse_nulls,
    data_profile_cache_key, write_cache, read_cache, dtype_to_str,
)
from .profile import profile_dataframe
from .quality import quality_issues
from .cleaning import apply_clean_operation, CLEAN_OPS
from .pipeline import run_pipeline, apply_step, PIPE_OPS
from .stats import (
    descriptive, ttest, anova, chi_square, mann_whitney,
    wilcoxon, kruskal, correlation, linear_regression, time_series,
    run_test, STAT_TESTS,
)
from .charts import (
    schema_profile, recommend_charts, build_chart_data,
    AGG_FUNCS,
)
from .sql_engine import validate_sql, execute_sql, SQLResult
from .ml import run_ml, REGRESSORS, CLASSIFIERS, TASKS
from .notebook import execute_cell, compute_analysis_from_code
from .ai import answer, run_intent, build_dataset_context
from .export import export_dataset, export_query
from .demo import demo_dataset, loads_demo

# Advanced services (Phase 2+)
from .execution_engine import (
    ExecutionEngine, EngineType, ExecutionMode, DatasetRef, QueryPlan,
    execution_engine, engine_context, create_dataset_ref,
)
from .formula_engine import (
    FormulaEngine, FormulaParser, FormulaRegistry, Workbook, Sheet,
    FormulaError, FormulaContext, ASTNode, NodeType, FunctionHandler,
)
from .econometrics import (
    EconometricEngine, PanelEngine, TimeSeriesEngine, CausalInferenceEngine,
    ModelResult, EconometricsError,
    econometric_engine, panel_engine, ts_engine, causal_engine,
    run_econometric_analysis,
)
from .advanced_charts import (
    AdvancedChartEngine, ChartData, advanced_chart_engine,
    create_advanced_chart,
)
from .causal_inference import (
    CausalInferenceEngine, CausalResult, causal_engine,
    run_causal_analysis,
)
from .quant_finance import (
    QuantFinanceEngine, PortfolioResult, quant_engine,
    run_quant_analysis,
)
from .mlflow_integration import (
    MLflowTracker, NexusMLflowTracker, ExperimentConfig, RunConfig,
    nexus_mlflow, init_mlflow,
)

__all__ = [
    # Core
    "validate_upload", "store_incoming", "save_canonical", "load_canonical",
    "parse_file", "dataframe_hash", "parse_nulls",
    "data_profile_cache_key", "write_cache", "read_cache", "dtype_to_str",
    "profile_dataframe", "quality_issues",
    "apply_clean_operation", "CLEAN_OPS",
    "run_pipeline", "apply_step", "PIPE_OPS",
    "descriptive", "ttest", "anova", "chi_square", "mann_whitney",
    "wilcoxon", "kruskal", "correlation", "linear_regression", "time_series",
    "run_test", "STAT_TESTS",
    "schema_profile", "recommend_charts", "build_chart_data", "AGG_FUNCS",
    "validate_sql", "execute_sql", "SQLResult",
    "run_ml", "REGRESSORS", "CLASSIFIERS", "TASKS",
    "execute_cell", "compute_analysis_from_code",
    "answer", "run_intent", "build_dataset_context",
    "export_dataset", "export_query",
    "demo_dataset", "loads_demo",
    # Advanced
    "ExecutionEngine", "EngineType", "ExecutionMode", "DatasetRef", "QueryPlan",
    "execution_engine", "engine_context", "create_dataset_ref",
    "FormulaEngine", "FormulaParser", "FormulaRegistry", "Workbook", "Sheet",
    "FormulaError", "FormulaContext", "ASTNode", "NodeType", "FunctionHandler",
    "EconometricEngine", "PanelEngine", "TimeSeriesEngine", "CausalInferenceEngine",
    "ModelResult", "EconometricsError",
    "econometric_engine", "panel_engine", "ts_engine", "causal_engine",
    "run_econometric_analysis",
    "AdvancedChartEngine", "ChartData", "advanced_chart_engine",
    "create_advanced_chart",
    "CausalInferenceEngine", "CausalResult", "causal_engine",
    "run_causal_analysis",
    "QuantFinanceEngine", "PortfolioResult", "quant_engine",
    "run_quant_analysis",
    "MLflowTracker", "NexusMLflowTracker", "ExperimentConfig", "RunConfig",
    "nexus_mlflow", "init_mlflow",
]
