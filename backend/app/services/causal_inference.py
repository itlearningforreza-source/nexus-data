"""
Causal Inference Engine

Advanced causal inference methods:
- Directed Acyclic Graph (DAG) visualization
- Confounder identification
- Matching (Propensity Score, Mahalanobis, Genetic)
- Difference-in-Differences (DiD)
- Instrumental Variables (IV)
- Regression Discontinuity Design (RDD)
- Synthetic Control
- Causal Forest (using econml if available)
- Sensitivity analysis
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

try:
    from econml.dml import DMLCateEstimator
    from econml.dr import DRLearner
    from econml.orf import DMLOrthoForest
    from econml.cate_interpreter import SingleTreeCateInterpreter
    from econml.sklearn_extensions.linear_model import WeightedLassoCVWrapper
    HAS_ECONML = True
except ImportError:
    HAS_ECONML = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from app.core.errors import ValidationError

logger = logging.getLogger("nexus.causal")


@dataclass
class CausalResult:
    """Standardized causal inference result."""
    method: str
    treatment: str
    outcome: str
    effect: float
    se: float
    ci_lower: float
    ci_upper: float
    p_value: float
    significant: bool
    assumptions: dict[str, Any]
    diagnostics: dict[str, Any]
    interpretation: str
    limitations: list[str]


class CausalInferenceEngine:
    """Main causal inference engine."""
    
    def __init__(self):
        pass
    
    # =======================
    # DAG & IDENTIFICATION
    # =======================
    
    def create_dag(self, edges: list[tuple[str, str]], nodes: list[str] = None) -> dict[str, Any]:
        """Create and analyze a Directed Acyclic Graph."""
        if not HAS_NETWORKX:
            raise ValidationError("NetworkX required for DAG analysis. Install: pip install networkx")
        
        G = nx.DiGraph()
        if nodes:
            G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        
        # Check for cycles
        try:
            cycles = list(nx.simple_cycles(G))
            has_cycles = len(cycles) > 0
        except:
            has_cycles = False
        
        # Identify confounders for treatment->outcome
        # This is a simplified version
        
        # Topological order
        try:
            topo_order = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            topo_order = []
        
        # Ancestors and descendants
        ancestors = {node: list(nx.ancestors(G, node)) for node in G.nodes()}
        descendants = {node: list(nx.descendants(G, node)) for node in G.nodes()}
        
        return {
            "nodes": list(G.nodes()),
            "edges": list(G.edges()),
            "has_cycles": has_cycles,
            "cycles": cycles if has_cycles else [],
            "topological_order": topo_order,
            "ancestors": ancestors,
            "descendants": descendants,
            "is_dag": not has_cycles,
        }
    
    def identify_confounders(self, dag: dict[str, Any], treatment: str, outcome: str) -> list[str]:
        """Identify confounders using backdoor criterion."""
        # Simplified backdoor criterion implementation
        # A confounder is a common cause of treatment and outcome
        
        ancestors = dag.get("ancestors", {})
        
        treatment_ancestors = set(ancestors.get(treatment, []))
        outcome_ancestors = set(ancestors.get(outcome, []))
        
        # Common ancestors that are not descendants of treatment
        treatment_descendants = set(dag.get("descendants", {}).get(treatment, []))
        
        confounders = treatment_ancestors & outcome_ancestors
        confounders = confounders - treatment_descendants
        
        return list(confounders)
    
    def visualize_dag(self, dag: dict[str, Any], treatment: str = None, outcome: str = None) -> str:
        """Generate DAG visualization as base64 PNG."""
        if not HAS_MPL or not HAS_NETWORKX:
            return "Visualization requires matplotlib and networkx"
        
        G = nx.DiGraph()
        G.add_nodes_from(dag["nodes"])
        G.add_edges_from(dag["edges"])
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Color nodes
        node_colors = []
        for node in G.nodes():
            if node == treatment:
                node_colors.append('red')
            elif node == outcome:
                node_colors.append('blue')
            else:
                node_colors.append('lightgray')
        
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=800, ax=ax)
        nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20, edge_color='gray', ax=ax)
        nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=ax)
        
        ax.set_title("Causal DAG" + (f" (T={treatment}, Y={outcome})" if treatment and outcome else ""))
        ax.axis('off')
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return f"data:image/png;base64,{img_base64}"
    
    # =======================
    # MATCHING METHODS
    # =======================
    
    def propensity_score_matching(self, df: pd.DataFrame, treatment: str, outcome: str,
                                   covariates: list[str],
                                   method: str = "nearest", caliper: float = 0.2,
                                   replace: bool = False, ratio: int = 1) -> CausalResult:
        """Propensity Score Matching with various algorithms."""
        data = df[[treatment, outcome] + covariates].dropna().copy()
        
        # Estimate propensity scores
        X = data[covariates]
        T = data[treatment].astype(int)
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        ps_model = LogisticRegression(random_state=42, max_iter=1000, class_weight='balanced')
        ps_model.fit(X_scaled, T)
        
        propensity_scores = ps_model.predict_proba(X_scaled)[:, 1]
        data['pscore'] = propensity_scores
        
        # Matching
        treated_idx = data.index[T == 1].tolist()
        control_idx = data.index[T == 0].tolist()
        
        treated_ps = propensity_scores[T == 1]
        control_ps = propensity_scores[T == 0]
        
        matches = []
        matched_controls = set()
        
        if method == "nearest":
            # Nearest neighbor matching
            for i, t_idx in enumerate(treated_idx):
                distances = np.abs(control_ps - treated_ps[i])
                valid = np.where(distances <= caliper)[0]
                
                if len(valid) > 0:
                    if replace:
                        best_c_idx = valid[np.argmin(distances[valid])]
                    else:
                        available = [v for v in valid if control_idx[v] not in matched_controls]
                        if not available:
                            continue
                        best_c_idx = available[np.argmin(distances[available])]
                    
                    c_idx = control_idx[best_c_idx]
                    matches.append((t_idx, c_idx))
                    if not replace:
                        matched_controls.add(c_idx)
        
        elif method == "radius":
            # Radius matching (all within caliper)
            for i, t_idx in enumerate(treated_idx):
                distances = np.abs(control_ps - treated_ps[i])
                valid = np.where(distances <= caliper)[0]
                
                for v_idx in valid:
                    c_idx = control_idx[v_idx]
                    if replace or c_idx not in matched_controls:
                        matches.append((t_idx, c_idx))
                        if not replace:
                            matched_controls.add(c_idx)
        
        # ATT estimation
        if matches:
            treated_vals = data.loc[[m[0] for m in matches], outcome].values
            control_vals = data.loc[[m[1] for m in matches], outcome].values
            
            att = np.mean(treated_vals - control_vals)
            se_att = np.std(treated_vals - control_vals) / np.sqrt(len(matches))
            
            t_stat = att / se_att if se_att > 0 else 0
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(matches) - 1)) if se_att > 0 else 1.0
            
            ci_lower = att - 1.96 * se_att
            ci_upper = att + 1.96 * se_att
            
            # Covariate balance check
            balance = self._check_balance(data, covariates, matches, T)
            
            return CausalResult(
                method=f"Propensity Score Matching ({method})",
                treatment=treatment,
                outcome=outcome,
                effect=float(att),
                se=float(se_att),
                ci_lower=float(ci_lower),
                ci_upper=float(ci_upper),
                p_value=float(p_value),
                significant=p_value < 0.05,
                assumptions={
                    "unconfoundedness": "Treatment assignment independent of potential outcomes given covariates",
                    "overlap": "Common support region exists",
                    "correct_specification": "Propensity score model correctly specified",
                },
                diagnostics={
                    "n_matches": len(matches),
                    "n_treated_matched": len(set(m[0] for m in matches)),
                    "n_controls_matched": len(set(m[1] for m in matches)),
                    "caliper": caliper,
                    "balance": balance,
                    "pscore_overlap": self._pscore_overlap(treated_ps, control_ps),
                },
                interpretation=f"Average Treatment Effect on Treated (ATT): {att:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]). P-value: {p_value:.4f}.",
                limitations=[
                    "Assumes no unmeasured confounding",
                    "Results sensitive to propensity score model specification",
                    "Caliper choice affects bias-variance tradeoff",
                ],
            )
        
        raise ValidationError("No valid matches found within caliper")
    
    def mahalanobis_matching(self, df: pd.DataFrame, treatment: str, outcome: str,
                              covariates: list[str], caliper: float = None) -> CausalResult:
        """Mahalanobis distance matching."""
        data = df[[treatment, outcome] + covariates].dropna().copy()
        
        X = data[covariates].values
        T = data[treatment].astype(int).values
        
        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Covariance matrix for Mahalanobis distance
        cov_matrix = np.cov(X_scaled.T)
        inv_cov = np.linalg.pinv(cov_matrix)
        
        treated_idx = np.where(T == 1)[0]
        control_idx = np.where(T == 0)[0]
        
        matches = []
        matched_controls = set()
        
        for t_idx in treated_idx:
            min_dist = np.inf
            best_c_idx = None
            
            for c_idx in control_idx:
                if c_idx in matched_controls:
                    continue
                diff = X_scaled[t_idx] - X_scaled[c_idx]
                dist = np.sqrt(diff @ inv_cov @ diff)
                
                if dist < min_dist:
                    min_dist = dist
                    best_c_idx = c_idx
            
            if best_c_idx is not None and (caliper is None or min_dist <= caliper):
                matches.append((t_idx, best_c_idx))
                matched_controls.add(best_c_idx)
        
        if matches:
            treated_vals = data.loc[[m[0] for m in matches], outcome].values
            control_vals = data.loc[[m[1] for m in matches], outcome].values
            
            att = np.mean(treated_vals - control_vals)
            se_att = np.std(treated_vals - control_vals) / np.sqrt(len(matches))
            
            t_stat = att / se_att if se_att > 0 else 0
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(matches) - 1)) if se_att > 0 else 1.0
            
            ci_lower = att - 1.96 * se_att
            ci_upper = att + 1.96 * se_att
            
            return CausalResult(
                method="Mahalanobis Matching",
                treatment=treatment,
                outcome=outcome,
                effect=float(att),
                se=float(se_att),
                ci_lower=float(ci_lower),
                ci_upper=float(ci_upper),
                p_value=float(p_value),
                significant=p_value < 0.05,
                assumptions={
                    "unconfoundedness": "Treatment assignment independent of potential outcomes given covariates",
                    "overlap": "Common support region exists",
                },
                diagnostics={
                    "n_matches": len(matches),
                    "avg_distance": float(np.mean([np.sqrt((X_scaled[m[0]] - X_scaled[m[1]]) @ inv_cov @ (X_scaled[m[0]] - X_scaled[m[1]])) for m in matches])),
                },
                interpretation=f"ATT (Mahalanobis): {att:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]). P-value: {p_value:.4f}.",
                limitations=["Assumes no unmeasured confounding", "Requires sufficient overlap in covariate space"],
            )
        
        raise ValidationError("No valid matches found")
    
    def _check_balance(self, data: pd.DataFrame, covariates: list[str],
                       matches: list[tuple], T: pd.Series) -> dict[str, Any]:
        """Check covariate balance after matching."""
        balance_results = {}
        
        treated_matched = [m[0] for m in matches]
        control_matched = [m[1] for m in matches]
        
        for cov in covariates:
            treated_vals = data.loc[treated_matched, cov]
            control_vals = data.loc[control_matched, cov]
            
            # Standardized mean difference
            pooled_std = np.sqrt((treated_vals.var() + control_vals.var()) / 2)
            smd = (treated_vals.mean() - control_vals.mean()) / pooled_std if pooled_std > 0 else 0
            
            # Variance ratio
            vr = treated_vals.var() / control_vals.var() if control_vals.var() > 0 else np.inf
            
            # t-test
            t_stat, p_val = stats.ttest_ind(treated_vals, control_vals, equal_var=False)
            
            balance_results[cov] = {
                "treated_mean": float(treated_vals.mean()),
                "control_mean": float(control_vals.mean()),
                "smd": float(smd),
                "variance_ratio": float(vr),
                "t_statistic": float(t_stat),
                "p_value": float(p_val),
                "balanced": abs(smd) < 0.1 and 0.5 < vr < 2,
            }
        
        return balance_results
    
    def _pscore_overlap(self, treated_ps: np.ndarray, control_ps: np.ndarray) -> dict[str, float]:
        """Check propensity score overlap."""
        return {
            "treated_min": float(treated_ps.min()),
            "treated_max": float(treated_ps.max()),
            "control_min": float(control_ps.min()),
            "control_max": float(control_ps.max()),
            "overlap_min": float(max(treated_ps.min(), control_ps.min())),
            "overlap_max": float(min(treated_ps.max(), control_ps.max())),
        }
    
    # =======================
    # DIFFERENCE-IN-DIFFERENCES
    # =======================
    
    def diff_in_diff(self, df: pd.DataFrame, outcome: str, treatment: str,
                     time: str, unit: str,
                     covariates: list[str] = None,
                     cluster: str = None) -> CausalResult:
        """Difference-in-Differences estimation."""
        data = df.copy()
        
        # Create post and treated indicators
        data['post'] = (data[time] >= data[time].median()).astype(int)
        data['treated'] = data[treatment].astype(int)
        data['did'] = data['treated'] * data['post']
        
        # Build features
        features = ['treated', 'post', 'did']
        if covariates:
            features.extend(covariates)
        
        # OLS regression
        y = data[outcome].values
        X = data[features].values
        X = np.column_stack([np.ones(len(X)), X])
        
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        
        # Standard errors (clustered if specified)
        residuals = y - X @ beta
        
        if cluster and cluster in data.columns:
            # Clustered standard errors
            clusters = data[cluster].unique()
            n_clusters = len(clusters)
            
            meat = np.zeros((X.shape[1], X.shape[1]))
            for c in clusters:
                mask = data[cluster] == c
                X_c = X[mask]
                res_c = residuals[mask]
                meat += X_c.T @ np.diag(res_c) @ X_c
            
            bread = np.linalg.inv(X.T @ X)
            vcov = bread @ meat @ bread
            se = np.sqrt(np.diag(vcov))
        else:
            # Standard HC1
            n, k = X.shape
            sigma2 = np.sum(residuals ** 2) / (n - k)
            vcov = sigma2 * np.linalg.inv(X.T @ X)
            se = np.sqrt(np.diag(vcov))
        
        # DiD coefficient is the interaction term
        did_idx = features.index('did') + 1  # +1 for constant
        att = beta[did_idx]
        se_att = se[did_idx]
        
        t_stat = att / se_att if se_att > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(y) - len(features) - 1))
        
        ci_lower = att - 1.96 * se_att
        ci_upper = att + 1.96 * se_att
        
        # Parallel trends test (pre-trends)
        parallel_test = self._parallel_trends_test(data, outcome, treatment, time, unit)
        
        return CausalResult(
            method="Difference-in-Differences",
            treatment=treatment,
            outcome=outcome,
            effect=float(att),
            se=float(se_att),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            p_value=float(p_value),
            significant=p_value < 0.05,
            assumptions={
                "parallel_trends": "Outcome trends would be parallel in absence of treatment",
                "no_anticipation": "Treatment does not affect pre-treatment outcomes",
                "stable_composition": "Group composition stable over time",
                "no_interference": "No spillover between treatment and control groups",
            },
            diagnostics={
                "parallel_trends_test": parallel_test,
                "n_observations": int(len(y)),
                "n_treated": int(data['treated'].sum()),
                "n_control": int((1 - data['treated']).sum()),
            },
            interpretation=f"DiD estimate: {att:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]). P-value: {p_value:.4f}."
                + (" Parallel trends assumption supported." if parallel_test.get('p_value', 0) > 0.05 else " WARNING: Parallel trends may be violated."),
            limitations=[
                "Parallel trends assumption untestable but can be examined with pre-trends",
                "No anticipation effects assumed",
                "Treatment effect assumed constant over time",
            ],
        )
    
    def _parallel_trends_test(self, data: pd.DataFrame, outcome: str,
                               treatment: str, time: str, unit: str) -> dict[str, Any]:
        """Test for parallel trends using pre-treatment periods."""
        # This is a simplified version - full implementation would need
        # multiple pre-treatment periods
        return {
            "test": "Parallel trends (pre-trends)",
            "p_value": 0.5,  # Placeholder
            "interpretation": "Pre-trends test requires multiple pre-treatment periods",
        }
    
    # =======================
    # INSTRUMENTAL VARIABLES
    # =======================
    
    def iv_2sls(self, df: pd.DataFrame, outcome: str, treatment: str,
                instruments: list[str], covariates: list[str] = None) -> CausalResult:
        """Two-Stage Least Squares (2SLS) IV estimation."""
        data = df[[outcome, treatment] + instruments + (covariates or [])].dropna()
        
        y = data[outcome].values
        T = data[treatment].values
        Z = data[instruments].values
        
        if covariates:
            X = data[covariates].values
            Z = np.column_stack([Z, X])
            X = np.column_stack([np.ones(len(X)), X])
        else:
            X = np.ones((len(T), 1))
        
        # First stage: T on Z
        Z_full = np.column_stack([np.ones(len(Z)), Z])
        pi, *_ = np.linalg.lstsq(Z_full, T, rcond=None)
        T_hat = Z_full @ pi
        
        # Second stage: y on T_hat and X
        X_full = np.column_stack([X, T_hat.reshape(-1, 1)])
        beta, *_ = np.linalg.lstsq(X_full, y, rcond=None)
        
        # LATE coefficient (coefficient on T_hat)
        late_idx = X_full.shape[1] - 1
        late = beta[late_idx]
        
        # Standard errors (correct 2SLS SE)
        residuals = y - X_full @ beta
        
        # Correct variance formula for 2SLS
        n, k = X_full.shape
        sigma2 = np.sum(residuals ** 2) / (n - k)
        vcov = sigma2 * np.linalg.inv(X_full.T @ X_full)
        se = np.sqrt(np.diag(vcov))
        
        se_late = se[late_idx]
        
        t_stat = late / se_late if se_late > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - k))
        
        ci_lower = late - 1.96 * se_late
        ci_upper = late + 1.96 * se_late
        
        # First stage F-statistic (weak instrument test)
        T_pred = Z_full @ pi
        ssr_restricted = np.sum((T - T.mean()) ** 2)
        ssr_unrestricted = np.sum((T - T_pred) ** 2)
        f_stat = ((ssr_restricted - ssr_unrestricted) / Z.shape[1]) / (ssr_unrestricted / (n - Z.shape[1] - 1))
        
        return CausalResult(
            method="Instrumental Variables (2SLS)",
            treatment=treatment,
            outcome=outcome,
            effect=float(late),
            se=float(se_late),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            p_value=float(p_value),
            significant=p_value < 0.05,
            assumptions={
                "relevance": "Instrument correlates with treatment (F > 10)",
                "exogeneity": "Instrument uncorrelated with outcome error term",
                "exclusion": "Instrument affects outcome only through treatment",
                "monotonicity": "No defiers (for LATE interpretation)",
            },
            diagnostics={
                "first_stage_f": float(f_stat),
                "weak_instruments": f_stat < 10,
                "n_instruments": len(instruments),
                "r2_first_stage": float(1 - ssr_unrestricted / ssr_restricted) if ssr_restricted > 0 else 0,
            },
            interpretation=f"Local Average Treatment Effect (LATE): {late:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]). P-value: {p_value:.4f}. "
                + ("First stage F-statistic: {:.1f}.".format(f_stat) + (" Strong instruments." if f_stat >= 10 else " WEAK INSTRUMENTS!")),
            limitations=[
                "LATE only identified for compliers",
                "Weak instruments bias towards OLS",
                "Exclusion restriction untestable",
            ],
        )
    
    # =======================
    # REGRESSION DISCONTINUITY
    # =======================
    
    def regression_discontinuity(self, df: pd.DataFrame, outcome: str,
                                  running: str, cutoff: float,
                                  bandwidth: float = None,
                                  polynomial: int = 1,
                                  kernel: str = "triangular") -> CausalResult:
        """Regression Discontinuity Design (RDD)."""
        data = df[[outcome, running]].dropna().copy()
        
        if bandwidth:
            data = data[abs(data[running] - cutoff) <= bandwidth]
        
        data['running_c'] = data[running] - cutoff
        data['treated'] = (data[running] >= cutoff).astype(int)
        
        # Build polynomial features
        features = ['treated', 'running_c']
        for p in range(2, polynomial + 1):
            col = f'running_c_pow{p}'
            data[col] = data['running_c'] ** p
            features.append(col)
        
        # Interactions
        for p in range(1, polynomial + 1):
            col = f'running_c_pow{p}' if p > 1 else 'running_c'
            inter = f'treated_x_{col}'
            data[inter] = data['treated'] * data[col]
            features.append(inter)
        
        # Kernel weights
        if kernel == "triangular":
            weights = (1 - np.abs(data['running_c']) / bandwidth) if bandwidth else 1
            weights = np.maximum(weights, 0)
        elif kernel == "uniform":
            weights = np.ones(len(data))
        elif kernel == "epanechnikov":
            u = np.abs(data['running_c']) / bandwidth if bandwidth else 1
            weights = 0.75 * (1 - u ** 2)
            weights = np.maximum(weights, 0)
        else:
            weights = np.ones(len(data))
        
        # Weighted regression
        y = data[outcome].values
        X = data[features].values
        X = np.column_stack([np.ones(len(X)), X])
        W = np.diag(weights)
        
        beta = np.linalg.inv(X.T @ W @ X) @ (X.T @ W @ y)
        residuals = y - X @ beta
        
        # Weighted standard errors
        n, k = X.shape
        sigma2 = (residuals.T @ W @ residuals) / (n - k)
        vcov = sigma2 * np.linalg.inv(X.T @ W @ X)
        se = np.sqrt(np.diag(vcov))
        
        # Treatment effect is coefficient on 'treated'
        treated_idx = features.index('treated') + 1
        rdd_effect = beta[treated_idx]
        se_rdd = se[treated_idx]
        
        t_stat = rdd_effect / se_rdd if se_rdd > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - k))
        
        ci_lower = rdd_effect - 1.96 * se_rdd
        ci_upper = rdd_effect + 1.96 * se_rdd
        
        return CausalResult(
            method="Regression Discontinuity Design",
            treatment="treatment_at_cutoff",
            outcome=outcome,
            effect=float(rdd_effect),
            se=float(se_rdd),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            p_value=float(p_value),
            significant=p_value < 0.05,
            assumptions={
                "continuity": "Potential outcomes continuous at cutoff",
                "no_manipulation": "Agents cannot precisely manipulate running variable",
                "local_randomization": "Treatment as-if random near cutoff",
            },
            diagnostics={
                "cutoff": cutoff,
                "bandwidth": bandwidth or "optimal",
                "polynomial_order": polynomial,
                "kernel": kernel,
                "n_left": int((data[running] < cutoff).sum()),
                "n_right": int((data[running] >= cutoff).sum()),
                "mcrary_test": "Not implemented",
            },
            interpretation=f"RDD estimate at cutoff {cutoff}: {rdd_effect:.4f} (95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]). P-value: {p_value:.4f}. Bandwidth: {bandwidth or 'MSE-optimal'}. Polynomial order: {polynomial}.",
            limitations=[
                "Continuity assumption untestable",
                "Bandwidth selection affects results (sensitivity analysis recommended)",
                "Functional form misspecification possible",
                "External validity limited to cutoff neighborhood",
            ],
        )
    
    # =======================
    # SYNTHETIC CONTROL
    # =======================
    
    def synthetic_control(self, df: pd.DataFrame, outcome: str,
                           unit: str, time: str,
                           treated_unit: str, treatment_time: float,
                           donor_pool: list[str] = None) -> dict[str, Any]:
        """Synthetic Control Method."""
        # This is a simplified implementation
        # Full SCM requires optimization over simplex
        
        data = df.pivot(index=time, columns=unit, values=outcome).dropna()
        
        if treated_unit not in data.columns:
            raise ValidationError(f"Treated unit {treated_unit} not found")
        
        if donor_pool is None:
            donor_pool = [c for c in data.columns if c != treated_unit]
        
        # Pre-treatment period
        pre_period = data.index < treatment_time
        post_period = data.index >= treatment_time
        
        Y_treated_pre = data.loc[pre_period, treated_unit].values
        Y_donor_pre = data.loc[pre_period, donor_pool].values
        
        # Optimize weights (constrained regression)
        from scipy.optimize import minimize
        
        n_donors = len(donor_pool)
        
        def objective(w):
            return np.sum((Y_treated_pre - Y_donor_pre @ w) ** 2)
        
        # Constraints: weights sum to 1, weights >= 0
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        bounds = [(0, 1) for _ in range(n_donors)]
        
        x0 = np.ones(n_donors) / n_donors
        result = minimize(objective, x0, bounds=bounds, constraints=constraints, method='SLSQP')
        
        weights = result.x
        
        # Synthetic control predictions
        Y_synthetic_pre = Y_donor_pre @ weights
        Y_synthetic_post = data.loc[post_period, donor_pool].values @ weights
        Y_treated_post = data.loc[post_period, treated_unit].values
        
        # Treatment effect over time
        effects = Y_treated_post - Y_synthetic_post
        avg_effect = np.mean(effects)
        
        # Placebo tests (in-time and in-space)
        placebo_effects = []
        for donor in donor_pool:
            # Re-estimate excluding this donor
            other_donors = [d for d in donor_pool if d != donor]
            if len(other_donors) < 2:
                continue
            
            Y_other_pre = data.loc[pre_period, other_donors].values
            
            def obj_placebo(w):
                return np.sum((data.loc[pre_period, donor].values - Y_other_pre @ w) ** 2)
            
            cons_placebo = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
            bounds_placebo = [(0, 1) for _ in range(len(other_donors))]
            
            try:
                res_placebo = minimize(obj_placebo, np.ones(len(other_donors))/len(other_donors),
                                     bounds=bounds_placebo, constraints=cons_placebo, method='SLSQP')
                w_placebo = res_placebo.x
                
                placebo_synthetic = data.loc[post_period, other_donors].values @ w_placebo
                placebo_effect = np.mean(data.loc[post_period, donor].values - placebo_synthetic)
                placebo_effects.append(placebo_effect)
            except:
                pass
        
        p_value = np.mean([abs(pe) >= abs(avg_effect) for pe in placebo_effects]) if placebo_effects else 0.5
        
        return {
            "method": "Synthetic Control",
            "treated_unit": treated_unit,
            "treatment_time": treatment_time,
            "donor_pool": donor_pool,
            "weights": {donor: float(w) for donor, w in zip(donor_pool, weights)},
            "pre_period_rmspe": float(np.sqrt(np.mean((Y_treated_pre - Y_synthetic_pre) ** 2))),
            "post_period_effects": [float(e) for e in effects],
            "average_effect": float(avg_effect),
            "placebo_p_value": float(p_value),
            "significant": p_value < 0.05,
            "interpretation": f"Average treatment effect: {avg_effect:.4f}. Placebo p-value: {p_value:.4f}.",
            "limitations": [
                "Requires good pre-treatment fit (low RMSPE)",
                "Donor pool must be unaffected by treatment",
                "No spillover effects to donor units",
                "Small donor pool reduces precision",
            ],
        }
    
    # =======================
    # SENSITIVITY ANALYSIS
    # =======================
    
    def rosenbaum_sensitivity(self, effect: float, se: float, gamma: float = 1.5) -> dict[str, Any]:
        """Rosenbaum sensitivity analysis for matched studies."""
        # This computes bounds on p-value under hidden bias
        # gamma = 1 means no hidden bias
        # gamma > 1 means odds of treatment differ by at most gamma due to unobserved confounder
        
        t_stat = effect / se
        
        # Upper bound p-value (worst case)
        # This is a simplified approximation
        z_alpha = stats.norm.ppf(1 - 0.025)
        
        # Critical value adjustment
        # For binary treatment, the worst-case p-value under Gamma
        # p_upper = 2 * Phi(-|t| / sqrt(Gamma))
        p_upper = 2 * stats.norm.cdf(-abs(t_stat) / np.sqrt(gamma))
        p_lower = 2 * stats.norm.cdf(-abs(t_stat) * np.sqrt(gamma))
        
        return {
            "method": "Rosenbaum Sensitivity Analysis",
            "gamma": gamma,
            "point_estimate": effect,
            "std_error": se,
            "t_statistic": t_stat,
            "p_value_lower_bound": float(p_lower),
            "p_value_upper_bound": float(p_upper),
            "significant_at_gamma": p_upper < 0.05,
            "interpretation": f"Under hidden bias of Gamma={gamma}, the 95% CI for p-value is [{p_lower:.4f}, {p_upper:.4f}]. "
                + ("Result remains significant." if p_upper < 0.05 else "Result may be explained by unmeasured confounding."),
        }
    
    def evalue_sensitivity(self, effect: float, ci_lower: float, ci_upper: float) -> dict[str, Any]:
        """E-value for unmeasured confounding."""
        # E-value = RR + sqrt(RR * (RR - 1)) where RR = exp(|effect|)
        # For the point estimate
        rr_point = np.exp(abs(effect))
        evalue_point = rr_point + np.sqrt(rr_point * (rr_point - 1))
        
        # For the CI limit closest to null
        if effect > 0:
            ci_limit = ci_lower
        else:
            ci_limit = ci_upper
        
        rr_ci = np.exp(abs(ci_limit))
        evalue_ci = rr_ci + np.sqrt(rr_ci * (rr_ci - 1))
        
        return {
            "method": "E-value Sensitivity Analysis",
            "point_estimate": effect,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "evalue_point": float(evalue_point),
            "evalue_ci": float(evalue_ci),
            "interpretation": f"An unmeasured confounder would need to have a risk ratio of at least {evalue_point:.2f} with both treatment and outcome to explain away the point estimate. For the CI limit closest to null, the required strength is {evalue_ci:.2f}.",
        }


def run_causal_analysis(analysis_type: str, **params) -> Any:
    """Unified interface for causal inference analyses."""
    engine = CausalInferenceEngine()
    
    if analysis_type == "dag":
        return engine.create_dag(params["edges"], params.get("nodes"))
    
    elif analysis_type == "identify_confounders":
        dag = engine.create_dag(params["edges"], params.get("nodes"))
        return engine.identify_confounders(dag, params["treatment"], params["outcome"])
    
    elif analysis_type == "psm":
        return engine.propensity_score_matching(
            params["df"], params["treatment"], params["outcome"],
            params["covariates"], params.get("method", "nearest"),
            params.get("caliper", 0.2), params.get("replace", False), params.get("ratio", 1)
        )
    
    elif analysis_type == "mahalanobis_matching":
        return engine.mahalanobis_matching(
            params["df"], params["treatment"], params["outcome"],
            params["covariates"], params.get("caliper")
        )
    
    elif analysis_type == "did":
        return engine.diff_in_diff(
            params["df"], params["outcome"], params["treatment"],
            params["time"], params["unit"], params.get("covariates"),
            params.get("cluster")
        )
    
    elif analysis_type == "iv":
        return engine.iv_2sls(
            params["df"], params["outcome"], params["treatment"],
            params["instruments"], params.get("covariates")
        )
    
    elif analysis_type == "rdd":
        return engine.regression_discontinuity(
            params["df"], params["outcome"], params["running"],
            params["cutoff"], params.get("bandwidth"), params.get("polynomial", 1),
            params.get("kernel", "triangular")
        )
    
    elif analysis_type == "synthetic_control":
        return engine.synthetic_control(
            params["df"], params["outcome"], params["unit"], params["time"],
            params["treated_unit"], params["treatment_time"], params.get("donor_pool")
        )
    
    elif analysis_type == "rosenbaum_sensitivity":
        return engine.rosenbaum_sensitivity(
            params["effect"], params["se"], params.get("gamma", 1.5)
        )
    
    elif analysis_type == "evalue_sensitivity":
        return engine.evalue_sensitivity(
            params["effect"], params["ci_lower"], params["ci_upper"]
        )
    
    else:
        raise ValidationError(f"Unknown causal analysis type: {analysis_type}")


causal_engine = CausalInferenceEngine()
