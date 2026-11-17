"""
Quantitative Finance Engine

Professional quantitative finance capabilities:
- Portfolio analysis and optimization
- Risk management (VaR, ES, stress testing)
- Performance attribution
- Factor models
- Derivatives pricing basics
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, Bounds, LinearConstraint

from app.core.errors import ValidationError

logger = logging.getLogger("nexus.quant")


@dataclass
class PortfolioResult:
    """Portfolio analysis result."""
    weights: np.ndarray
    expected_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    var_95: float
    es_95: float
    assets: list[str]
    covariance_matrix: np.ndarray
    correlation_matrix: np.ndarray
    efficient_frontier: Optional[list[dict[str, float]]] = None


class QuantFinanceEngine:
    """Quantitative finance computation engine."""
    
    def calculate_returns(self, prices: pd.DataFrame, method: str = "log") -> pd.DataFrame:
        """Calculate returns from price series."""
        if method == "log":
            returns = np.log(prices / prices.shift(1)).dropna()
        elif method == "simple":
            returns = (prices / prices.shift(1) - 1).dropna()
        else:
            raise ValidationError(f"Unknown return method: {method}")
        return returns
    
    def portfolio_metrics(self, returns: pd.DataFrame, weights: np.ndarray,
                          risk_free_rate: float = 0.02) -> dict[str, float]:
        """Calculate comprehensive portfolio metrics."""
        if len(weights) != len(returns.columns):
            raise ValidationError("Weights length must match number of assets")
        
        portfolio_returns = (returns * weights).sum(axis=1)
        
        # Basic metrics
        mean_return = portfolio_returns.mean() * 252  # Annualized
        volatility = portfolio_returns.std() * np.sqrt(252)
        
        # Sharpe ratio
        excess_returns = portfolio_returns - risk_free_rate / 252
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = portfolio_returns[portfolio_returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = (mean_return - risk_free_rate) / downside_std if downside_std > 0 else 0
        
        # Max drawdown
        cumulative = (1 + portfolio_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Calmar ratio
        calmar = mean_return / abs(max_drawdown) if max_drawdown < 0 else 0
        
        # VaR (Historical)
        var_95 = np.percentile(portfolio_returns, 5)
        var_99 = np.percentile(portfolio_returns, 1)
        
        # Expected Shortfall (CVaR)
        es_95 = portfolio_returns[portfolio_returns <= var_95].mean()
        es_99 = portfolio_returns[portfolio_returns <= var_99].mean()
        
        # Beta (if market proxy available)
        # This would need a market benchmark
        
        return {
            "expected_return": float(mean_return),
            "volatility": float(volatility),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "calmar_ratio": float(calmar),
            "var_95": float(var_95),
            "var_99": float(var_99),
            "es_95": float(es_95),
            "es_99": float(es_99),
            "skewness": float(portfolio_returns.skew()),
            "kurtosis": float(portfolio_returns.kurtosis()),
        }
    
    def covariance_matrix(self, returns: pd.DataFrame, method: str = "sample") -> np.ndarray:
        """Calculate covariance matrix with various estimators."""
        if method == "sample":
            return returns.cov().values * 252  # Annualized
        elif method == "shrunk":
            # Ledoit-Wolf shrinkage
            from sklearn.covariance import LedoitWolf
            lw = LedoitWolf().fit(returns)
            return lw.covariance_ * 252
        elif method == "oas":
            # Oracle Approximating Shrinkage
            from sklearn.covariance import OAS
            oas = OAS().fit(returns)
            return oas.covariance_ * 252
        elif method == "ewma":
            # Exponentially Weighted Moving Average
            lambda_decay = 0.94
            n_assets = len(returns.columns)
            cov = np.zeros((n_assets, n_assets))
            returns_np = returns.values
            
            for i in range(len(returns_np)):
                weight = (1 - lambda_decay) * (lambda_decay ** (len(returns_np) - i - 1))
                ret = returns_np[i].reshape(-1, 1)
                cov += weight * (ret @ ret.T)
            return cov * 252
        else:
            raise ValidationError(f"Unknown covariance method: {method}")
    
    def correlation_matrix(self, returns: pd.DataFrame) -> np.ndarray:
        """Calculate correlation matrix."""
        return returns.corr().values
    
    def optimize_portfolio(self, returns: pd.DataFrame, objective: str = "max_sharpe",
                          constraints: dict[str, Any] = None,
                          risk_free_rate: float = 0.02) -> PortfolioResult:
        """Optimize portfolio weights."""
        n_assets = len(returns.columns)
        assets = list(returns.columns)
        
        # Expected returns and covariance
        mean_returns = returns.mean().values * 252
        cov_matrix = self.covariance_matrix(returns)
        
        # Constraints
        if constraints is None:
            constraints = {}
        
        # Default: weights sum to 1, no short selling
        bounds = constraints.get("bounds", [(0, 1) for _ in range(n_assets)])
        
        # Sum to 1 constraint
        weight_sum_constraint = LinearConstraint(
            np.ones(n_assets), lb=1.0, ub=1.0
        )
        
        # Additional constraints
        additional_constraints = []
        if "max_weight" in constraints:
            # This would need individual upper bounds in bounds
            pass
        if "min_weight" in constraints:
            pass
        if "sector_constraints" in constraints:
            pass
        
        all_constraints = [weight_sum_constraint] + additional_constraints
        
        # Initial guess
        x0 = np.ones(n_assets) / n_assets
        
        # Objective functions
        def negative_sharpe(w):
            port_return = np.dot(w, mean_returns)
            port_vol = np.sqrt(np.dot(w, np.dot(cov_matrix, w)))
            if port_vol == 0:
                return 1e6
            return -(port_return - risk_free_rate) / port_vol
        
        def portfolio_volatility(w):
            return np.sqrt(np.dot(w, np.dot(cov_matrix, w)))
        
        def negative_return(w):
            return -np.dot(w, mean_returns)
        
        def risk_parity_objective(w):
            # Equal risk contribution
            port_vol = np.sqrt(np.dot(w, np.dot(cov_matrix, w)))
            marginal_contrib = np.dot(cov_matrix, w) / port_vol
            contrib = w * marginal_contrib
            target = port_vol / n_assets
            return np.sum((contrib - target) ** 2)
        
        if objective == "max_sharpe":
            obj_func = negative_sharpe
        elif objective == "min_vol":
            obj_func = portfolio_volatility
        elif objective == "max_return":
            obj_func = negative_return
        elif objective == "risk_parity":
            obj_func = risk_parity_objective
        else:
            raise ValidationError(f"Unknown objective: {objective}")
        
        result = minimize(
            obj_func, x0,
            method="SLSQP",
            bounds=bounds,
            constraints=all_constraints,
            options={"maxiter": 1000, "ftol": 1e-10}
        )
        
        if not result.success:
            logger.warning(f"Optimization failed: {result.message}")
        
        optimal_weights = result.x
        
        # Calculate metrics for optimal portfolio
        metrics = self.portfolio_metrics(returns, optimal_weights, risk_free_rate)
        
        # Efficient frontier
        frontier = self._efficient_frontier(returns, risk_free_rate, n_points=50)
        
        return PortfolioResult(
            weights=optimal_weights,
            expected_return=metrics["expected_return"],
            volatility=metrics["volatility"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            max_drawdown=metrics["max_drawdown"],
            var_95=metrics["var_95"],
            es_95=metrics["es_95"],
            assets=assets,
            covariance_matrix=cov_matrix,
            correlation_matrix=self.correlation_matrix(returns),
            efficient_frontier=frontier,
        )
    
    def _efficient_frontier(self, returns: pd.DataFrame, risk_free_rate: float,
                           n_points: int = 50) -> list[dict[str, float]]:
        """Generate efficient frontier points."""
        n_assets = len(returns.columns)
        mean_returns = returns.mean().values * 252
        cov_matrix = self.covariance_matrix(returns)
        
        # Find min and max return portfolios
        bounds = [(0, 1) for _ in range(n_assets)]
        weight_sum = LinearConstraint(np.ones(n_assets), lb=1.0, ub=1.0)
        
        def port_return(w):
            return np.dot(w, mean_returns)
        
        def port_vol(w):
            return np.sqrt(np.dot(w, np.dot(cov_matrix, w)))
        
        # Min vol
        min_vol_res = minimize(port_vol, np.ones(n_assets)/n_assets,
                              method="SLSQP", bounds=bounds, constraints=[weight_sum])
        min_return = port_return(min_vol_res.x)
        
        # Max return
        max_return_res = minimize(lambda w: -port_return(w), np.ones(n_assets)/n_assets,
                                 method="SLSQP", bounds=bounds, constraints=[weight_sum])
        max_return = port_return(max_return_res.x)
        
        # Generate frontier points
        target_returns = np.linspace(min_return, max_return, n_points)
        frontier = []
        
        for target in target_returns:
            ret_constraint = LinearConstraint(mean_returns, lb=target, ub=target)
            res = minimize(port_vol, np.ones(n_assets)/n_assets,
                          method="SLSQP", bounds=bounds, constraints=[weight_sum, ret_constraint])
            if res.success:
                w = res.x
                frontier.append({
                    "return": float(port_return(w)),
                    "volatility": float(port_vol(w)),
                    "sharpe": float((port_return(w) - risk_free_rate) / port_vol(w)) if port_vol(w) > 0 else 0,
                })
        
        return frontier
    
    def var_historical(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """Historical Value at Risk."""
        alpha = 1 - confidence
        return float(np.percentile(returns, alpha * 100))
    
    def var_parametric(self, returns: pd.Series, confidence: float = 0.95,
                       distribution: str = "normal") -> float:
        """Parametric Value at Risk."""
        mu = returns.mean()
        sigma = returns.std()
        alpha = 1 - confidence
        
        if distribution == "normal":
            z = stats.norm.ppf(alpha)
            return float(mu + z * sigma)
        elif distribution == "t":
            # Fit t-distribution
            df, loc, scale = stats.t.fit(returns)
            return float(stats.t.ppf(alpha, df, loc, scale))
        else:
            raise ValidationError(f"Unknown distribution: {distribution}")
    
    def var_monte_carlo(self, returns: pd.Series, confidence: float = 0.95,
                        n_simulations: int = 10000, horizon: int = 1) -> float:
        """Monte Carlo Value at Risk."""
        mu = returns.mean()
        sigma = returns.std()
        
        # Generate scenarios
        scenarios = np.random.normal(mu, sigma, (n_simulations, horizon))
        cumulative = scenarios.sum(axis=1)
        
        alpha = 1 - confidence
        return float(np.percentile(cumulative, alpha * 100))
    
    def expected_shortfall(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """Expected Shortfall (Conditional VaR)."""
        var = self.var_historical(returns, confidence)
        return float(returns[returns <= var].mean())
    
    def stress_test(self, returns: pd.DataFrame, weights: np.ndarray,
                    scenarios: dict[str, dict[str, float]]) -> dict[str, float]:
        """Stress test portfolio against scenarios."""
        portfolio_returns = (returns * weights).sum(axis=1)
        base_metrics = self.portfolio_metrics(returns, weights)
        
        results = {"base": base_metrics}
        
        for scenario_name, shocks in scenarios.items():
            # Apply shocks to returns
            shocked_returns = returns.copy()
            for asset, shock in shocks.items():
                if asset in shocked_returns.columns:
                    shocked_returns[asset] += shock
            
            results[scenario_name] = self.portfolio_metrics(shocked_returns, weights)
        
        return results
    
    def factor_model(self, returns: pd.DataFrame, factor_returns: pd.DataFrame,
                     asset: str) -> dict[str, Any]:
        """Estimate factor model (CAPM, Fama-French, etc.)."""
        # Align data
        common_idx = returns.index.intersection(factor_returns.index)
        y = returns.loc[common_idx, asset]
        X = factor_returns.loc[common_idx]
        
        # Add constant
        X = np.column_stack([np.ones(len(X)), X.values])
        
        # OLS
        beta, *_ = np.linalg.lstsq(X, y.values, rcond=None)
        
        # R-squared
        y_pred = X @ beta
        ss_res = np.sum((y.values - y_pred) ** 2)
        ss_tot = np.sum((y.values - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        
        # Standard errors
        n, k = X.shape
        residuals = y.values - y_pred
        sigma2 = np.sum(residuals ** 2) / (n - k)
        cov = sigma2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.diag(cov))
        t_stats = beta / se
        p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), n - k))
        
        factor_names = ["alpha"] + list(factor_returns.columns)
        
        coefficients = {}
        for i, name in enumerate(factor_names):
            coefficients[name] = {
                "coefficient": float(beta[i]),
                "std_error": float(se[i]),
                "t_stat": float(t_stats[i]),
                "p_value": float(p_values[i]),
                "significant": float(p_values[i]) < 0.05,
            }
        
        return {
            "asset": asset,
            "model": f"Factor model with {len(factor_returns.columns)} factors",
            "r_squared": float(r2),
            "adj_r_squared": float(1 - (1 - r2) * (n - 1) / (n - k)) if n > k else 0,
            "coefficients": coefficients,
            "residuals": residuals.tolist(),
            "interpretation": f"Factor model explains {r2*100:.1f}% of {asset} variance.",
        }
    
    def black_scholes(self, S: float, K: float, T: float, r: float, sigma: float,
                      option_type: str = "call") -> dict[str, float]:
        """Black-Scholes option pricing."""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == "call":
            price = S * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
            delta = stats.norm.cdf(d1)
        else:
            price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)
            delta = stats.norm.cdf(d1) - 1
        
        gamma = stats.norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * stats.norm.pdf(d1) * np.sqrt(T) / 100
        theta = (-S * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                 - r * K * np.exp(-r * T) * stats.norm.cdf(d2 if option_type == "call" else -d2)) / 365
        rho = K * T * np.exp(-r * T) * stats.norm.cdf(d2 if option_type == "call" else -d2) / 100
        
        return {
            "price": float(price),
            "delta": float(delta),
            "gamma": float(gamma),
            "vega": float(vega),
            "theta": float(theta),
            "rho": float(rho),
        }
    
    def monte_carlo_gbm(self, S0: float, mu: float, sigma: float, T: float,
                        n_steps: int = 252, n_sims: int = 10000) -> np.ndarray:
        """Monte Carlo simulation of Geometric Brownian Motion."""
        dt = T / n_steps
        paths = np.zeros((n_sims, n_steps + 1))
        paths[:, 0] = S0
        
        for t in range(1, n_steps + 1):
            z = np.random.standard_normal(n_sims)
            paths[:, t] = paths[:, t-1] * np.exp(
                (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
            )
        
        return paths
    
    def garch_simulation(self, returns: pd.Series, horizon: int = 30,
                         n_sims: int = 1000) -> np.ndarray:
        """GARCH(1,1) conditional volatility simulation."""
        # Simple GARCH(1,1) parameter estimation
        from arch import arch_model
        
        try:
            model = arch_model(returns * 100, vol="Garch", p=1, q=1)
            fitted = model.fit(disp="off")
            
            # Simulate
            sims = []
            for _ in range(n_sims):
                sim = fitted.simulate(horizon=horizon)
                sims.append(sim["data"]["returns"] / 100)
            
            return np.array(sims)
        except ImportError:
            # Fallback: use historical bootstrap
            n = len(returns)
            sims = []
            for _ in range(n_sims):
                idx = np.random.choice(n, horizon, replace=True)
                sims.append(returns.iloc[idx].values)
            return np.array(sims)


quant_engine = QuantFinanceEngine()


def run_quant_analysis(analysis_type: str, **params) -> Any:
    """Unified interface for quantitative finance analyses."""
    
    if analysis_type == "portfolio_metrics":
        return quant_engine.portfolio_metrics(
            params["returns"], params["weights"],
            params.get("risk_free_rate", 0.02)
        )
    
    elif analysis_type == "optimize_portfolio":
        return quant_engine.optimize_portfolio(
            params["returns"],
            params.get("objective", "max_sharpe"),
            params.get("constraints"),
            params.get("risk_free_rate", 0.02)
        )
    
    elif analysis_type == "var":
        method = params.get("method", "historical")
        if method == "historical":
            return quant_engine.var_historical(params["returns"], params.get("confidence", 0.95))
        elif method == "parametric":
            return quant_engine.var_parametric(params["returns"], params.get("confidence", 0.95),
                                              params.get("distribution", "normal"))
        elif method == "monte_carlo":
            return quant_engine.var_monte_carlo(params["returns"], params.get("confidence", 0.95),
                                               params.get("n_simulations", 10000),
                                               params.get("horizon", 1))
    
    elif analysis_type == "expected_shortfall":
        return quant_engine.expected_shortfall(params["returns"], params.get("confidence", 0.95))
    
    elif analysis_type == "stress_test":
        return quant_engine.stress_test(
            params["returns"], params["weights"], params["scenarios"]
        )
    
    elif analysis_type == "factor_model":
        return quant_engine.factor_model(
            params["returns"], params["factor_returns"], params["asset"]
        )
    
    elif analysis_type == "black_scholes":
        return quant_engine.black_scholes(
            params["S"], params["K"], params["T"], params["r"], params["sigma"],
            params.get("option_type", "call")
        )
    
    elif analysis_type == "monte_carlo_gbm":
        return quant_engine.monte_carlo_gbm(
            params["S0"], params["mu"], params["sigma"], params["T"],
            params.get("n_steps", 252), params.get("n_sims", 10000)
        )
    
    elif analysis_type == "garch":
        return quant_engine.garch_simulation(
            params["returns"], params.get("horizon", 30), params.get("n_sims", 1000)
        )
    
    else:
        raise ValidationError(f"Unknown quant analysis type: {analysis_type}")
