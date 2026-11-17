"""
Advanced Visualization Engine

Extended chart types for academic and professional use:
- Statistical plots (violin, box, Q-Q, residual)
- Financial charts (candlestick, OHLC, volume profile)
- ML diagnostics (ROC, PR curves, learning curves, calibration)
- Network/graph visualizations
- Geographic maps
- Correlation matrices, pair plots
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import gaussian_kde

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import seaborn as sns
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

logger = logging.getLogger("nexus.advanced_charts")


@dataclass
class ChartData:
    """Standardized chart data output."""
    chart_type: str
    data: dict[str, Any]
    metadata: dict[str, Any]
    config: dict[str, Any]


class AdvancedChartEngine:
    """Advanced visualization engine with Matplotlib/Seaborn backend."""
    
    def __init__(self):
        if not HAS_MPL:
            raise ImportError("matplotlib and seaborn required for advanced charts")
        
        # Set style
        sns.set_theme(style="whitegrid", context="notebook")
        
    def violin_plot(self, df: pd.DataFrame, x: str, y: str,
                    hue: str = None, split: bool = False,
                    inner: str = "box", scale: str = "area") -> ChartData:
        """Create violin plot."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        sns.violinplot(data=df, x=x, y=y, hue=hue, split=split,
                      inner=inner, scale=scale, ax=ax)
        
        ax.set_title(f"Violin Plot: {y} by {x}")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        
        if hue:
            ax.legend(title=hue)
        
        plt.tight_layout()
        
        # Convert to base64
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="violin",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"x": x, "y": y, "hue": hue},
            config={}
        )
    
    def pair_plot(self, df: pd.DataFrame, vars: list[str] = None,
                  hue: str = None, diag_kind: str = "hist",
                  corner: bool = False) -> ChartData:
        """Create pair plot (scatterplot matrix)."""
        plot_vars = vars or df.select_dtypes(include=[np.number]).columns.tolist()[:6]
        
        g = sns.pairplot(df, vars=plot_vars, hue=hue,
                        diag_kind=diag_kind, corner=corner,
                        height=2.5, aspect=1)
        
        g.fig.suptitle("Pair Plot", y=1.02)
        
        import io, base64
        buf = io.BytesIO()
        g.fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(g.fig)
        
        return ChartData(
            chart_type="pairplot",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"variables": plot_vars, "hue": hue},
            config={}
        )
    
    def qq_plot(self, series: pd.Series, dist: str = "norm",
                fit: bool = True, line: str = "45") -> ChartData:
        """Create Q-Q plot for normality assessment."""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        clean_series = series.dropna()
        
        if dist == "norm":
            stats.probplot(clean_series, dist="norm", plot=ax)
        else:
            stats.probplot(clean_series, dist=dist, plot=ax)
        
        ax.set_title(f"Q-Q Plot vs {dist.upper()} Distribution")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="qq_plot",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"distribution": dist, "n_obs": len(clean_series)},
            config={}
        )
    
    def residual_plot(self, fitted: np.ndarray, residuals: np.ndarray,
                      studentized: bool = False) -> ChartData:
        """Create residual vs fitted plot."""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # Residuals vs Fitted
        axes[0].scatter(fitted, residuals, alpha=0.5, edgecolors='none')
        axes[0].axhline(y=0, color='red', linestyle='--', alpha=0.7)
        axes[0].set_xlabel("Fitted Values")
        axes[0].set_ylabel("Residuals")
        axes[0].set_title("Residuals vs Fitted")
        axes[0].grid(True, alpha=0.3)
        
        # Q-Q plot of residuals
        stats.probplot(residuals, dist="norm", plot=axes[1])
        axes[1].set_title("Q-Q Plot of Residuals")
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="residual_plot",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"n_obs": len(residuals)},
            config={}
        )
    
    def roc_curve(self, y_true: np.ndarray, y_score: np.ndarray,
                  pos_label: Any = None) -> ChartData:
        """Create ROC curve."""
        from sklearn.metrics import roc_curve, auc
        
        fpr, tpr, thresholds = roc_curve(y_true, y_score, pos_label=pos_label)
        roc_auc = auc(fpr, tpr)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.plot(fpr, tpr, color='darkorange', lw=2,
               label=f'ROC curve (AUC = {roc_auc:.3f})')
        ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--',
               label='Random classifier')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title('Receiver Operating Characteristic (ROC) Curve')
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="roc_curve",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"auc": float(roc_auc), "n_thresholds": len(thresholds)},
            config={}
        )
    
    def precision_recall_curve(self, y_true: np.ndarray, y_score: np.ndarray) -> ChartData:
        """Create Precision-Recall curve."""
        from sklearn.metrics import precision_recall_curve, average_precision_score
        
        precision, recall, thresholds = precision_recall_curve(y_true, y_score)
        avg_precision = average_precision_score(y_true, y_score)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.plot(recall, precision, color='blue', lw=2,
               label=f'PR curve (AP = {avg_precision:.3f})')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Recall')
        ax.set_ylabel('Precision')
        ax.set_title('Precision-Recall Curve')
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="pr_curve",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"average_precision": float(avg_precision)},
            config={}
        )
    
    def learning_curve(self, train_sizes: np.ndarray, train_scores: np.ndarray,
                       test_scores: np.ndarray) -> ChartData:
        """Create learning curve."""
        train_mean = np.mean(train_scores, axis=1)
        train_std = np.std(train_scores, axis=1)
        test_mean = np.mean(test_scores, axis=1)
        test_std = np.std(test_scores, axis=1)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.plot(train_sizes, train_mean, 'o-', color='blue', label='Training score')
        ax.fill_between(train_sizes, train_mean - train_std, train_mean + train_std,
                       alpha=0.1, color='blue')
        
        ax.plot(train_sizes, test_mean, 'o-', color='red', label='Cross-validation score')
        ax.fill_between(train_sizes, test_mean - test_std, test_mean + test_std,
                       alpha=0.1, color='red')
        
        ax.set_xlabel('Training Set Size')
        ax.set_ylabel('Score')
        ax.set_title('Learning Curve')
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="learning_curve",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"train_sizes": train_sizes.tolist()},
            config={}
        )
    
    def calibration_plot(self, y_true: np.ndarray, y_prob: np.ndarray,
                         n_bins: int = 10) -> ChartData:
        """Create calibration plot."""
        from sklearn.calibration import calibration_curve
        
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        ax.plot([0, 1], [0, 1], 'k:', label='Perfectly calibrated')
        ax.plot(prob_pred, prob_true, 's-', label='Model')
        
        ax.set_xlabel('Mean Predicted Probability')
        ax.set_ylabel('Fraction of Positives')
        ax.set_title('Calibration Plot (Reliability Diagram)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="calibration_plot",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"n_bins": n_bins},
            config={}
        )
    
    def candlestick(self, df: pd.DataFrame, date_col: str,
                    open_col: str, high_col: str, low_col: str, close_col: str,
                    volume_col: str = None, n_bars: int = 100) -> ChartData:
        """Create candlestick chart."""
        # Prepare data
        plot_df = df.tail(n_bars).copy()
        dates = pd.to_datetime(plot_df[date_col])
        opens = plot_df[open_col].values
        highs = plot_df[high_col].values
        lows = plot_df[low_col].values
        closes = plot_df[close_col].values
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        
        # Candlesticks
        for i in range(len(dates)):
            color = 'green' if closes[i] >= opens[i] else 'red'
            # High-low line
            axes[0].plot([dates[i], dates[i]], [lows[i], highs[i]], color='black', linewidth=0.5)
            # Open-close body
            axes[0].plot([dates[i], dates[i]], [opens[i], closes[i]], color=color, linewidth=4)
        
        axes[0].set_ylabel('Price')
        axes[0].set_title(f'Candlestick Chart ({len(dates)} bars)')
        axes[0].grid(True, alpha=0.3)
        
        # Volume
        if volume_col and volume_col in plot_df.columns:
            volumes = plot_df[volume_col].values
            colors = ['green' if closes[i] >= opens[i] else 'red' for i in range(len(dates))]
            axes[1].bar(dates, volumes, color=colors, alpha=0.7, width=0.8)
            axes[1].set_ylabel('Volume')
            axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="candlestick",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"n_bars": len(dates)},
            config={}
        )
    
    def correlation_heatmap(self, df: pd.DataFrame, method: str = "pearson",
                           annot: bool = True, cmap: str = "RdBu_r",
                           center: float = 0, vmin: float = -1, vmax: float = 1) -> ChartData:
        """Create correlation heatmap."""
        corr_matrix = df.corr(method=method)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(corr_matrix, annot=annot, cmap=cmap, center=center,
                   vmin=vmin, vmax=vmax, square=True, ax=ax,
                   cbar_kws={"shrink": 0.8, "label": f"{method.capitalize()} Correlation"})
        
        ax.set_title(f"Correlation Matrix ({method.capitalize()})")
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="correlation_heatmap",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"method": method, "variables": list(corr_matrix.columns)},
            config={}
        )
    
    def distribution_plot(self, df: pd.DataFrame, column: str,
                         fit_dist: str = None, kde: bool = True,
                         bins: int = 30) -> ChartData:
        """Create distribution plot with optional fit."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        data = df[column].dropna()
        
        # Histogram
        n, bins_edges, patches = ax.hist(data, bins=bins, density=True,
                                        alpha=0.5, color='skyblue', edgecolor='black',
                                        label='Data')
        
        # KDE
        if kde:
            kde_est = gaussian_kde(data)
            x_range = np.linspace(data.min(), data.max(), 200)
            ax.plot(x_range, kde_est(x_range), 'r-', lw=2, label='KDE')
        
        # Fitted distribution
        if fit_dist == "norm":
            from scipy.stats import norm
            mu, sigma = norm.fit(data)
            x_range = np.linspace(data.min(), data.max(), 200)
            ax.plot(x_range, norm.pdf(x_range, mu, sigma), 'g--', lw=2,
                   label=f'Normal fit (μ={mu:.2f}, σ={sigma:.2f})')
        
        ax.set_xlabel(column)
        ax.set_ylabel('Density')
        ax.set_title(f'Distribution of {column}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        import io, base64
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)
        
        return ChartData(
            chart_type="distribution",
            data={"image": f"data:image/png;base64,{img_base64}"},
            metadata={"column": column, "n_obs": len(data)},
            config={}
        )
    
    def sankey_diagram(self, source: list[str], target: list[str],
                       value: list[float], node_labels: list[str] = None) -> ChartData:
        """Create Sankey diagram (requires plotly)."""
        # This would need plotly - return message if not available
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure(data=[go.Sankey(
                node=dict(
                    pad=15, thickness=20, line=dict(color="black", width=0.5),
                    label=node_labels or list(set(source + target)),
                ),
                link=dict(
                    source=[node_labels.index(s) if node_labels else source.index(s) for s in source],
                    target=[node_labels.index(t) if node_labels else target.index(t) for t in target],
                    value=value
                ))])
            
            fig.update_layout(title_text="Sankey Diagram", font_size=10)
            
            # Convert to static image
            img_bytes = fig.to_image(format="png", width=800, height=600, scale=2)
            import base64
            img_base64 = base64.b64encode(img_bytes).decode()
            
            return ChartData(
                chart_type="sankey",
                data={"image": f"data:image/png;base64,{img_base64}"},
                metadata={"n_nodes": len(node_labels or set(source + target)), "n_links": len(source)},
                config={}
            )
        except ImportError:
            return ChartData(
                chart_type="sankey",
                data={"error": "Plotly required for Sankey diagrams. Install with: pip install plotly kaleido"},
                metadata={},
                config={}
            )
    
    def network_graph(self, edges: list[tuple], nodes: list = None,
                      layout: str = "spring") -> ChartData:
        """Create network graph (requires networkx)."""
        try:
            import networkx as nx
            
            G = nx.Graph()
            G.add_edges_from(edges)
            if nodes:
                G.add_nodes_from(nodes)
            
            if layout == "spring":
                pos = nx.spring_layout(G, k=1, iterations=50)
            elif layout == "circular":
                pos = nx.circular_layout(G)
            elif layout == "kamada_kawai":
                pos = nx.kamada_kawai_layout(G)
            else:
                pos = nx.spring_layout(G)
            
            fig, ax = plt.subplots(figsize=(10, 10))
            
            nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightblue', ax=ax)
            nx.draw_networkx_edges(G, pos, alpha=0.5, edge_color='gray', ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=8, ax=ax)
            
            ax.set_title(f"Network Graph ({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
            ax.axis('off')
            
            plt.tight_layout()
            
            import io, base64
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode()
            plt.close(fig)
            
            return ChartData(
                chart_type="network_graph",
                data={"image": f"data:image/png;base64,{img_base64}"},
                metadata={"n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges()},
                config={}
            )
        except ImportError:
            return ChartData(
                chart_type="network_graph",
                data={"error": "NetworkX required for network graphs. Install with: pip install networkx"},
                metadata={},
                config={}
            )


advanced_chart_engine = AdvancedChartEngine()


def create_advanced_chart(chart_type: str, **params) -> ChartData:
    """Unified interface for advanced charts."""
    if chart_type == "violin":
        return advanced_chart_engine.violin_plot(
            params["df"], params["x"], params["y"],
            params.get("hue"), params.get("split", False),
            params.get("inner", "box"), params.get("scale", "area")
        )
    elif chart_type == "pairplot":
        return advanced_chart_engine.pair_plot(
            params["df"], params.get("vars"), params.get("hue"),
            params.get("diag_kind", "hist"), params.get("corner", False)
        )
    elif chart_type == "qq_plot":
        return advanced_chart_engine.qq_plot(
            params["series"], params.get("dist", "norm"),
            params.get("fit", True), params.get("line", "45")
        )
    elif chart_type == "residual_plot":
        return advanced_chart_engine.residual_plot(
            params["fitted"], params["residuals"], params.get("studentized", False)
        )
    elif chart_type == "roc_curve":
        return advanced_chart_engine.roc_curve(
            params["y_true"], params["y_score"], params.get("pos_label")
        )
    elif chart_type == "pr_curve":
        return advanced_chart_engine.precision_recall_curve(
            params["y_true"], params["y_score"]
        )
    elif chart_type == "learning_curve":
        return advanced_chart_engine.learning_curve(
            params["train_sizes"], params["train_scores"], params["test_scores"]
        )
    elif chart_type == "calibration_plot":
        return advanced_chart_engine.calibration_plot(
            params["y_true"], params["y_prob"], params.get("n_bins", 10)
        )
    elif chart_type == "candlestick":
        return advanced_chart_engine.candlestick(
            params["df"], params["date_col"], params["open_col"],
            params["high_col"], params["low_col"], params["close_col"],
            params.get("volume_col"), params.get("n_bars", 100)
        )
    elif chart_type == "correlation_heatmap":
        return advanced_chart_engine.correlation_heatmap(
            params["df"], params.get("method", "pearson"),
            params.get("annot", True), params.get("cmap", "RdBu_r"),
            params.get("center", 0), params.get("vmin", -1), params.get("vmax", 1)
        )
    elif chart_type == "distribution":
        return advanced_chart_engine.distribution_plot(
            params["df"], params["column"], params.get("fit_dist"),
            params.get("kde", True), params.get("bins", 30)
        )
    elif chart_type == "sankey":
        return advanced_chart_engine.sankey_diagram(
            params["source"], params["target"], params["value"], params.get("node_labels")
        )
    elif chart_type == "network":
        return advanced_chart_engine.network_graph(
            params["edges"], params.get("nodes"), params.get("layout", "spring")
        )
    else:
        raise ValueError(f"Unknown advanced chart type: {chart_type}")
