from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent.parent / "data"


def _rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


def sales_dataset(n: int = 5000) -> pd.DataFrame:
    rng = _rng(1)
    dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    regions = ["North", "South", "East", "West"]
    categories = ["Electronics", "Furniture", "Office Supplies", "Clothing", "Groceries"]
    channels = ["Online", "Retail", "Wholesale", "Mobile App"]
    products = ["Aurora Laptop", "Horizon Desk", "Vertex Chair", "Pulse Monitor", "Nimbus Tablet",
                "Cascade Printer", "Ember Keyboard", "Frost Mouse", "Orbit Speaker", "Dune Router"]
    rows = []
    for i in range(n):
        d = dates[i % len(dates)]
        region = regions[rng.integers(len(regions))]
        cat = categories[rng.integers(len(categories))]
        channel = channels[rng.integers(len(channels))]
        price = float(np.round(rng.uniform(15, 1200), 2))
        qty = int(rng.integers(1, 30))
        discount = float(np.round(rng.uniform(0, 0.4), 2))
        unit_cost = float(np.round(price * rng.uniform(0.45, 0.75), 2))
        revenue = float(np.round(price * qty * (1 - discount), 2))
        profit = float(np.round(revenue - unit_cost * qty, 2))
        rows.append({
            "order_id": f"ORD-{10000 + i}",
            "date": d,
            "region": region,
            "product": products[rng.integers(len(products))],
            "category": cat,
            "channel": channel,
            "customer_type": "New" if rng.random() < 0.3 else "Returning",
            "quantity": qty,
            "unit_price": price,
            "discount": discount,
            "revenue": revenue,
            "unit_cost": unit_cost,
            "profit": profit,
            "rating": round(min(5.0, max(1.0, float(rng.normal(4.0, 0.8)))), 1),
            "shipping_days": int(rng.integers(1, 9)),
            "returned": bool(rng.random() < 0.08),
            "priority": "High" if revenue > 8000 else ("Medium" if revenue > 2000 else "Low"),
        })
    df = pd.DataFrame(rows)
    # inject realistic data-quality issues
    df.loc[rng.choice(len(df), 120, replace=False), "region"] = None
    df.loc[rng.choice(len(df), 60, replace=False), "rating"] = None
    df.loc[rng.choice(len(df), 25, replace=False), "shipping_days"] = 99
    dup = df.iloc[rng.choice(len(df), 40, replace=False)]
    df = pd.concat([df, dup], ignore_index=True)
    return df


def ecommerce_dataset(n: int = 4500) -> pd.DataFrame:
    rng = _rng(2)
    df = sales_dataset(n // 2)
    df = df.rename(columns={"order_id": "transaction_id", "date": "purchased_at"})
    df["purchased_at"] = df["purchased_at"] + pd.to_timedelta(rng.integers(0, 86400, len(df)), unit="s")
    df = df.drop(columns=["priority", "unit_cost", "shipping_days", "returned"])
    df["coupon_used"] = rng.random(len(df)) < 0.22
    df["basket_size"] = rng.integers(1, 8, len(df))
    return df


def marketing_dataset(n: int = 3000) -> pd.DataFrame:
    rng = _rng(3)
    channels = ["Social Media", "Search Ads", "Email", "Display", "Referral", "Organic"]
    campaigns = ["Spring Push", "Summer Sale", "Autumn Launch", "Winter Promo", "Evergreen"]
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    rows = []
    for i in range(n):
        d = dates[i % len(dates)]
        ch = channels[rng.integers(len(channels))]
        spend = float(np.round(rng.uniform(100, 5000), 2))
        impressions = int(rng.integers(2000, 200000))
        clicks = int(impressions * rng.uniform(0.005, 0.09))
        conversions = int(clicks * rng.uniform(0.01, 0.25))
        revenue = float(np.round(conversions * rng.uniform(20, 300), 2))
        rows.append({
            "campaign_id": f"CP-{100 + i}",
            "date": d,
            "channel": ch,
            "campaign": campaigns[rng.integers(len(campaigns))],
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions, 5),
            "conversions": conversions,
            "conversion_rate": round(conversions / max(clicks, 1), 5),
            "revenue": revenue,
            "roas": round(revenue / spend, 3),
            "region": ["US", "EU", "APAC", "LATAM"][rng.integers(4)],
        })
    df = pd.DataFrame(rows)
    df.loc[rng.choice(len(df), 50, replace=False), "channel"] = None
    df.loc[rng.choice(len(df), 30, replace=False), "revenue"] = None
    return df


def finance_dataset(n: int = 4000) -> pd.DataFrame:
    rng = _rng(4)
    dates = pd.date_range("2023-01-15", "2025-08-15", freq="D")
    accounts = ["Checking", "Savings", "Credit Card", "Investment", "Payroll"]
    descriptors = ["Transfer", "Payment", "Purchase", "Fee", "Refund", "Deposit", "Withdrawal"]
    rows = []
    for i in range(n):
        d = dates[i % len(dates)]
        acct = accounts[rng.integers(len(accounts))]
        desc = descriptors[rng.integers(len(descriptors))]
        amount = float(np.round(rng.normal(500, 400), 2))
        if acct == "Payroll":
            amount = float(np.round(rng.uniform(2500, 7000), 2))
        rows.append({
            "transaction_id": f"TXN-{202300 + i}",
            "date": d,
            "account": acct,
            "category": descriptors[rng.integers(len(descriptors))],
            "merchant": f"Vendor {rng.integers(1, 60)}",
            "amount": amount,
            "balance_after": float(np.round(abs(amount) + rng.uniform(0, 5000), 2)),
            "status": "Cleared" if rng.random() < 0.8 else "Pending",
            "method": ["Card", "ACH", "Wire"][rng.integers(3)],
        })
    df = pd.DataFrame(rows)
    df.rename(columns={"category": "description"}, inplace=True)
    df.loc[rng.choice(len(df), 40, replace=False), "amount"] = None
    return df


def students_dataset(n: int = 2500) -> pd.DataFrame:
    rng = _rng(5)
    majors = ["Computer Science", "Business", "Psychology", "Engineering", "Mathematics", "Biology", "Economics"]
    grades = ["A", "B", "C", "D", "F"]
    rows = []
    for i in range(n):
        study = float(np.clip(rng.normal(25, 8), 0, 60))
        sleep = float(np.clip(rng.normal(6.5, 1.5), 0, 12))
        prev = float(np.clip(rng.normal(3.0, 0.6), 0, 4))
        gpa = float(np.clip(2.0 + 0.035 * study + 0.08 * prev + rng.normal(0, 0.35), 0.0, 4.0))
        passed = gpa > 2.5 or rng.random() < (gpa / 4.2)
        rows.append({
            "student_id": f"S{1000 + i}",
            "major": majors[rng.integers(len(majors))],
            "gender": ["Male", "Female", "Other"][rng.integers(3)],
            "age": int(np.clip(rng.normal(20, 2), 17, 40)),
            "study_hours": round(study, 1),
            "sleep_hours": round(sleep, 1),
            "attendance_pct": round(float(np.clip(rng.normal(88, 9), 20, 100)), 1),
            "previous_gpa": round(prev, 2),
            "gpa": round(gpa, 2),
            "absences": int(rng.poisson(3)),
            "passed": bool(passed),
            "honor_roll": bool(gpa >= 3.5),
        })
    df = pd.DataFrame(rows)
    df.loc[rng.choice(len(df), 70, replace=False), "gpa"] = None
    return df


def churn_dataset(n: int = 3200) -> pd.DataFrame:
    rng = _rng(6)
    rows = []
    for i in range(n):
        tenure = float(np.clip(rng.exponential(24), 0, 80))
        monthly = float(np.clip(rng.normal(65, 30), 10, 200))
        support = int(rng.poisson(3 + (70 - tenure) / 15))
        usage = float(np.clip(rng.normal(60, 25), 0, 100))
        contract = ["Month-to-month", "One year", "Two year"][rng.integers(3)]
        churn_prob = 0.05 + (tenure < 12) * 0.25 + (contract == "Month-to-month") * 0.2 + (support > 8) * 0.15 - (usage > 70) * 0.1
        churned = rng.random() < np.clip(churn_prob, 0.01, 0.95)
        rows.append({
            "customer_id": f"C{5000 + i}",
            "tenure_months": round(tenure, 1),
            "monthly_charges": round(monthly, 2),
            "total_charges": round(monthly * tenure + rng.normal(0, 20), 2),
            "contract": contract,
            "payment_method": ["Credit card", "Bank transfer", "Electronic check"][rng.integers(3)],
            "support_tickets": support,
            "downloads_gb": round(usage, 1),
            "streaming": bool(rng.random() < 0.6),
            "online_security": bool(rng.random() < 0.5),
            "auto_pay": bool(rng.random() < 0.55),
            "churn": bool(churned),
        })
    df = pd.DataFrame(rows)
    return df


def stock_dataset(n: int = 1200) -> pd.DataFrame:
    rng = _rng(7)
    dates = pd.date_range("2022-06-01", "2025-06-30", freq="B")
    tickers = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX"]
    rows = []
    for t in tickers:
        price = {"AAPL": 150.0, "MSFT": 300.0, "NVDA": 180.0, "GOOGL": 120.0, "AMZN": 105.0, "TSLA": 220.0, "META": 200.0, "NFLX": 350.0}[t]
        for d in dates:
            r = rng.normal(0.0004, 0.018)
            price = max(5.0, price * (1 + r))
            rows.append({
                "date": d,
                "symbol": t,
                "open": round(price, 2),
                "high": round(price * (1 + abs(rng.normal(0, 0.01))), 2),
                "low": round(price * (1 - abs(rng.normal(0, 0.01))), 2),
                "close": round(price, 2),
                "volume": int(rng.integers(2_000_000, 120_000_000)),
                "daily_return": round(r, 5),
            })
    df = pd.DataFrame(rows)
    df.loc[rng.choice(len(df), 40, replace=False), "volume"] = None
    return df


def crypto_dataset(n: int = 2000) -> pd.DataFrame:
    rng = _rng(8)
    dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    coins = ["BTC", "ETH", "SOL", "ADA", "XRP", "DOGE"]
    rows = []
    for c in coins:
        price = {"BTC": 30000, "ETH": 2000, "SOL": 25, "ADA": 0.4, "XRP": 0.5, "DOGE": 0.09}[c]
        for d in dates:
            r = rng.normal(0.0008, 0.045)
            price = max(price * (1 + r), 0.001)
            rows.append({
                "date": d,
                "symbol": c,
                "price": round(price, 6),
                "market_cap": round(price * rng.integers(1_000_000, 500_000_000), 0),
                "volume_24h": round(rng.uniform(1e6, 5e10), 0),
                "daily_return": round(r, 5),
                "sentiment_score": round(float(np.clip(rng.normal(0, 0.4), -1, 1)), 3),
                "active_addresses": int(rng.integers(10000, 2000000)),
            })
    df = pd.DataFrame(rows)
    return df


def weather_dataset(n: int = 1800) -> pd.DataFrame:
    rng = _rng(9)
    dates = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    cities = ["Jakarta", "Bandung", "Surabaya", "Bali", "Medan", "Makassar", "Yogyakarta", "Semarang"]
    rows = []
    for city in cities:
        base_temp = {"Jakarta": 28.0, "Bandung": 23.0, "Surabaya": 28.5, "Bali": 27.0, "Medan": 27.5, "Makassar": 28.0, "Yogyakarta": 26.5, "Semarang": 27.5}[city]
        for d in dates:
            seasonal = 1.0 * np.sin(2 * np.pi * (d.dayofyear - 20) / 365)
            temp = base_temp + seasonal + rng.normal(0, 2.5)
            rain = float(np.clip(rng.exponential(8 if city in ("Jakarta", "Medan") else 4), 0, 80))
            rows.append({
                "date": d,
                "city": city,
                "temperature_c": round(temp, 1),
                "humidity_pct": round(float(np.clip(rng.normal(75, 10), 30, 100)), 1),
                "precipitation_mm": round(rain, 1),
                "wind_speed_kmh": round(float(np.clip(rng.normal(12, 6), 0, 60)), 1),
                "air_pressure_hpa": round(float(rng.normal(1010, 4)), 1),
                "air_quality_psi": round(float(np.clip(rng.normal(55, 25), 10, 200)), 0),
                "condition": ["Sunny", "Cloudy", "Rainy", "Stormy"][rng.integers(4)],
            })
    df = pd.DataFrame(rows)
    df.loc[rng.choice(len(df), 90, replace=False), "precipitation_mm"] = None
    return df


def manufacturing_dataset(n: int = 3000) -> pd.DataFrame:
    rng = _rng(10)
    dates = pd.date_range("2024-01-01", "2025-08-30", freq="D")
    lines = ["Line A", "Line B", "Line C"]
    products = ["Bearing X", "Gear Y", "Shaft Z", "Pump W", "Valve V"]
    rows = []
    for i in range(n):
        d = dates[i % len(dates)]
        line = lines[rng.integers(len(lines))]
        prod = products[rng.integers(len(products))]
        produced = int(rng.integers(50, 400))
        defective = int(rng.poisson(produced * 0.02))
        downtime = float(np.clip(rng.exponential(1.5), 0, 24))
        temp = float(np.clip(rng.normal(210, 30), 80, 400))
        pressure = float(np.clip(rng.normal(95, 12), 40, 160))
        rows.append({
            "date": d,
            "production_line": line,
            "product": prod,
            "units_produced": produced,
            "defective_units": defective,
            "defect_rate": round(defective / produced, 4),
            "downtime_hours": round(downtime, 2),
            "machine_temperature_c": round(temp, 1),
            "pressure_psi": round(pressure, 1),
            "operator_count": int(rng.integers(1, 8)),
            "shift": ["Day", "Night"][rng.integers(2)],
        })
    df = pd.DataFrame(rows)
    return df


def loads_demo() -> list[str]:
    return ["sales", "ecommerce", "marketing", "finance", "students", "churn",
            "stock", "crypto", "weather", "manufacturing"]


def demo_dataset(name: str, n: int | None = None) -> pd.DataFrame:
    name = name.lower()
    builders = {
        "sales": sales_dataset,
        "ecommerce": ecommerce_dataset,
        "marketing": marketing_dataset,
        "finance": finance_dataset,
        "students": students_dataset,
        "churn": churn_dataset,
        "stock": stock_dataset,
        "crypto": crypto_dataset,
        "weather": weather_dataset,
        "manufacturing": manufacturing_dataset,
    }
    if name not in builders:
        raise ValueError(f"Unknown demo dataset '{name}'. Choose from: {', '.join(loads_demo())}")
    if n:
        return builders[name](n)
    return builders[name]()