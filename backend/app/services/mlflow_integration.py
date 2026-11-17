"""
MLflow Integration for Experiment Tracking

Provides:
- Experiment and run management
- Parameter, metric, and artifact logging
- Model registry
- Run comparison
- Reproducibility manifests
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    from mlflow.entities import Experiment, Run
    from mlflow.models import infer_signature
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

from app.core.config import settings
from app.core.errors import ValidationError

logger = logging.getLogger("nexus.mlflow")


@dataclass
class ExperimentConfig:
    """MLflow experiment configuration."""
    name: str
    artifact_location: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class RunConfig:
    """MLflow run configuration."""
    experiment_id: str
    run_name: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)
    nested: bool = False


class MLflowTracker:
    """MLflow experiment tracking wrapper."""
    
    def __init__(self, tracking_uri: str = None):
        if not HAS_MLFLOW:
            raise ValidationError("MLflow not installed. Install: pip install mlflow")
        
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "./mlruns")
        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = MlflowClient(tracking_uri=self.tracking_uri)
    
    def create_experiment(self, config: ExperimentConfig) -> str:
        """Create or get experiment."""
        try:
            exp_id = self.client.create_experiment(
                name=config.name,
                artifact_location=config.artifact_location,
                tags=config.tags
            )
        except mlflow.exceptions.MlflowException:
            # Experiment might already exist
            exp = self.client.get_experiment_by_name(config.name)
            if exp:
                exp_id = exp.experiment_id
            else:
                raise
        
        logger.info(f"Using experiment: {config.name} (ID: {exp_id})")
        return exp_id
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID."""
        return self.client.get_experiment(experiment_id)
    
    def list_experiments(self) -> list[Experiment]:
        """List all experiments."""
        return self.client.search_experiments()
    
    @contextmanager
    def start_run(self, config: RunConfig):
        """Context manager for MLflow run."""
        run = self.client.create_run(
            experiment_id=config.experiment_id,
            tags=config.tags,
            run_name=config.run_name,
        )
        run_id = run.info.run_id
        
        mlflow.start_run(run_id=run_id, nested=config.nested)
        try:
            yield run_id
            mlflow.end_run(status="FINISHED")
        except Exception as e:
            mlflow.end_run(status="FAILED")
            raise
    
    def log_params(self, run_id: str, params: dict[str, Any]) -> None:
        """Log parameters."""
        for key, value in params.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            mlflow.log_param(key, value)
    
    def log_metrics(self, run_id: str, metrics: dict[str, float], step: int = None) -> None:
        """Log metrics."""
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)
    
    def log_artifact(self, run_id: str, local_path: str, artifact_path: str = None) -> None:
        """Log artifact."""
        mlflow.log_artifact(local_path, artifact_path)
    
    def log_artifacts(self, run_id: str, local_dir: str, artifact_path: str = None) -> None:
        """Log directory of artifacts."""
        mlflow.log_artifacts(local_dir, artifact_path)
    
    def log_model(self, run_id: str, model, artifact_path: str,
                  signature=None, input_example=None, **kwargs) -> None:
        """Log model."""
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path=artifact_path,
            signature=signature,
            input_example=input_example,
            **kwargs
        )
    
    def log_figure(self, run_id: str, figure, artifact_file: str) -> None:
        """Log matplotlib figure."""
        mlflow.log_figure(figure, artifact_file)
    
    def set_tags(self, run_id: str, tags: dict[str, str]) -> None:
        """Set run tags."""
        mlflow.set_tags(tags)
    
    def search_runs(self, experiment_ids: list[str], filter_string: str = "",
                    max_results: int = 1000) -> list[Run]:
        """Search runs."""
        return self.client.search_runs(
            experiment_ids=experiment_ids,
            filter_string=filter_string,
            max_results=max_results,
            order_by=["attributes.start_time DESC"]
        )
    
    def compare_runs(self, run_ids: list[str]) -> pd.DataFrame:
        """Compare multiple runs."""
        runs = []
        for run_id in run_ids:
            run = self.client.get_run(run_id)
            run_data = {
                "run_id": run_id,
                "status": run.info.status,
                "start_time": run.info.start_time,
                "end_time": run.info.end_time,
                **run.data.params,
                **run.data.metrics,
                **run.data.tags,
            }
            runs.append(run_data)
        
        return pd.DataFrame(runs)
    
    def get_run_artifacts(self, run_id: str, path: str = None) -> list:
        """List run artifacts."""
        return self.client.list_artifacts(run_id, path)
    
    def download_artifacts(self, run_id: str, path: str, dst_path: str = None) -> str:
        """Download artifacts."""
        return self.client.download_artifacts(run_id, path, dst_path)
    
    # Model Registry
    def register_model(self, run_id: str, model_name: str, artifact_path: str = "model") -> str:
        """Register model in MLflow Model Registry."""
        model_uri = f"runs:/{run_id}/{artifact_path}"
        mv = mlflow.register_model(model_uri, model_name)
        return mv.version
    
    def get_model_version(self, name: str, version: str) -> Any:
        """Get model version."""
        return self.client.get_model_version(name, version)
    
    def transition_model_stage(self, name: str, version: str, stage: str,
                               archive_existing: bool = True) -> None:
        """Transition model stage."""
        self.client.transition_model_version_stage(
            name=name, version=version, stage=stage,
            archive_existing_versions=archive_existing
        )
    
    def get_latest_model(self, name: str, stage: str = "Production") -> tuple[str, str]:
        """Get latest model version in stage."""
        versions = self.client.get_latest_versions(name, stages=[stage])
        if versions:
            return versions[0].version, versions[0].source
        return None, None
    
    def create_reproducibility_manifest(self, run_id: str) -> dict[str, Any]:
        """Create reproducibility manifest for a run."""
        run = self.client.get_run(run_id)
        
        manifest = {
            "run_id": run_id,
            "experiment_id": run.info.experiment_id,
            "run_name": run.data.tags.get("mlflow.runName", ""),
            "status": run.info.status,
            "start_time": datetime.fromtimestamp(run.info.start_time / 1000).isoformat() if run.info.start_time else None,
            "end_time": datetime.fromtimestamp(run.info.end_time / 1000).isoformat() if run.info.end_time else None,
            "user": run.info.user_id,
            "parameters": dict(run.data.params),
            "metrics": dict(run.data.metrics),
            "tags": dict(run.data.tags),
            "artifacts": [f.path for f in self.client.list_artifacts(run_id)],
            "environment": self._capture_environment(),
        }
        
        return manifest
    
    def _capture_environment(self) -> dict[str, str]:
        """Capture Python environment."""
        import subprocess
        import sys
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True, text=True, timeout=30
            )
            packages = result.stdout.strip().split("\n")
        except Exception:
            packages = []
        
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "packages": packages,
        }
    
    def export_run(self, run_id: str, export_dir: str) -> str:
        """Export run with all artifacts for portability."""
        run = self.client.get_run(run_id)
        export_path = Path(export_dir) / f"run_{run_id}"
        export_path.mkdir(parents=True, exist_ok=True)
        
        # Save manifest
        manifest = self.create_reproducibility_manifest(run_id)
        with open(export_path / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        
        # Download artifacts
        artifacts = self.client.list_artifacts(run_id)
        for artifact in artifacts:
            local_path = self.client.download_artifacts(run_id, artifact.path, str(export_path))
        
        logger.info(f"Exported run {run_id} to {export_path}")
        return str(export_path)
    
    def import_run(self, export_dir: str, experiment_name: str) -> str:
        """Import run from export directory."""
        export_path = Path(export_dir)
        
        with open(export_path / "manifest.json", "r") as f:
            manifest = json.load(f)
        
        # Create/get experiment
        exp_config = ExperimentConfig(name=experiment_name)
        exp_id = self.create_experiment(exp_config)
        
        # Create run
        run_config = RunConfig(
            experiment_id=exp_id,
            run_name=manifest.get("run_name"),
            tags=manifest.get("tags", {})
        )
        
        with self.start_run(run_config) as run_id:
            # Log params
            self.log_params(run_id, manifest.get("parameters", {}))
            
            # Log metrics (use final values)
            self.log_metrics(run_id, manifest.get("metrics", {}))
            
            # Note: Artifacts would need to be re-uploaded
            logger.info(f"Imported run as {run_id} (artifacts need manual upload)")
        
        return run_id


# Auto-tracking for Nexus components
class NexusMLflowTracker:
    """MLflow tracker integrated with Nexus components."""
    
    def __init__(self):
        self.tracker = MLflowTracker()
        self._current_run_id = None
    
    def track_dataset_upload(self, dataset_id: str, file_info: dict[str, Any]) -> str:
        """Track dataset upload."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-datasets"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"dataset-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "filename": file_info.get("filename", ""),
                "size_bytes": file_info.get("size", 0),
                "format": file_info.get("format", ""),
            })
            self.tracker.set_tags(run_id, {"nexus.component": "dataset_upload"})
        
        return run_id
    
    def track_cleaning(self, dataset_id: str, operations: list[dict], 
                       before_stats: dict, after_stats: dict) -> str:
        """Track data cleaning operations."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-cleaning"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"cleaning-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "operations": json.dumps(operations),
                "n_operations": len(operations),
            })
            self.tracker.log_metrics(run_id, {
                "rows_before": before_stats.get("rows", 0),
                "rows_after": after_stats.get("rows", 0),
                "cols_before": before_stats.get("columns", 0),
                "cols_after": after_stats.get("columns", 0),
                "null_pct_before": before_stats.get("null_pct", 0),
                "null_pct_after": after_stats.get("null_pct", 0),
            })
            self.tracker.set_tags(run_id, {"nexus.component": "cleaning"})
        
        return run_id
    
    def track_ml_training(self, dataset_id: str, target: str, features: list[str],
                          task: str, algorithm: str, metrics: dict,
                          model) -> str:
        """Track ML model training."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-ml"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"ml-{algorithm}-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "target": target,
                "features": json.dumps(features),
                "n_features": len(features),
                "task": task,
                "algorithm": algorithm,
            })
            self.tracker.log_metrics(run_id, metrics)
            
            # Log model
            try:
                signature = infer_signature(
                    pd.DataFrame(columns=features),
                    pd.Series(dtype=float)
                )
                self.tracker.log_model(run_id, model, "model", signature=signature)
            except Exception as e:
                logger.warning(f"Could not log model: {e}")
            
            self.tracker.set_tags(run_id, {
                "nexus.component": "ml_training",
                "model_type": algorithm,
            })
        
        return run_id
    
    def track_statistical_analysis(self, dataset_id: str, analysis_type: str,
                                    params: dict, results: dict) -> str:
        """Track statistical analysis."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-statistics"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"stats-{analysis_type}-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "analysis_type": analysis_type,
                **{k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                   for k, v in params.items()},
            })
            
            # Extract numeric metrics from results
            metrics = self._extract_metrics(results)
            if metrics:
                self.tracker.log_metrics(run_id, metrics)
            
            self.tracker.set_tags(run_id, {
                "nexus.component": "statistics",
                "analysis_type": analysis_type,
            })
        
        return run_id
    
    def track_econometric_analysis(self, dataset_id: str, analysis_type: str,
                                    params: dict, results: Any) -> str:
        """Track econometric analysis."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-econometrics"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"econ-{analysis_type}-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "analysis_type": analysis_type,
                **{k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                   for k, v in params.items()},
            })
            
            if isinstance(results, dict) and "coefficients" in str(results):
                # ModelResult object
                if hasattr(results, "r_squared") and results.r_squared is not None:
                    self.tracker.log_metrics(run_id, {"r_squared": results.r_squared})
                if hasattr(results, "adj_r_squared") and results.adj_r_squared is not None:
                    self.tracker.log_metrics(run_id, {"adj_r_squared": results.adj_r_squared})
                if hasattr(results, "nobs"):
                    self.tracker.log_metrics(run_id, {"nobs": results.nobs})
            
            self.tracker.set_tags(run_id, {
                "nexus.component": "econometrics",
                "analysis_type": analysis_type,
            })
        
        return run_id
    
    def track_causal_analysis(self, dataset_id: str, analysis_type: str,
                               params: dict, results: Any) -> str:
        """Track causal inference analysis."""
        exp_id = self.tracker.create_experiment(ExperimentConfig(name="nexus-causal"))
        
        with self.tracker.start_run(RunConfig(experiment_id=exp_id, run_name=f"causal-{analysis_type}-{dataset_id}")) as run_id:
            self.tracker.log_params(run_id, {
                "dataset_id": dataset_id,
                "analysis_type": analysis_type,
                **{k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                   for k, v in params.items()},
            })
            
            if hasattr(results, "effect"):
                self.tracker.log_metrics(run_id, {
                    "effect": results.effect,
                    "se": results.se,
                    "ci_lower": results.ci_lower,
                    "ci_upper": results.ci_upper,
                    "p_value": results.p_value,
                })
            
            self.tracker.set_tags(run_id, {
                "nexus.component": "causal_inference",
                "analysis_type": analysis_type,
            })
        
        return run_id
    
    def _extract_metrics(self, results: Any) -> dict[str, float]:
        """Extract numeric metrics from various result objects."""
        metrics = {}
        
        if isinstance(results, dict):
            for k, v in results.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    metrics[k] = float(v)
                elif isinstance(v, dict):
                    for sk, sv in v.items():
                        if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                            metrics[f"{k}.{sk}"] = float(sv)
        elif hasattr(results, "__dict__"):
            for k, v in results.__dict__.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    metrics[k] = float(v)
        
        return metrics


# Global instance
nexus_mlflow = NexusMLflowTracker()


def init_mlflow(tracking_uri: str = None) -> MLflowTracker:
    """Initialize MLflow tracker."""
    return MLflowTracker(tracking_uri)
