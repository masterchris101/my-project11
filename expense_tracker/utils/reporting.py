from typing import Dict, Tuple

import pandas as pd


def compute_kpis(df: pd.DataFrame) -> Dict[str, float]:
    expenses = df[df["amount"] < 0]["amount"].sum()
    income = df[df["amount"] > 0]["amount"].sum()
    net = income + expenses
    return {
        "total_expenses": float(expenses),
        "total_income": float(income),
        "net": float(net),
    }


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    dfe = df[df["amount"] < 0].copy()
    if dfe.empty:
        return pd.DataFrame({"category": [], "spend": []})
    dfe["spend"] = -dfe["amount"]
    agg = dfe.groupby(dfe["category"].fillna("Uncategorized"))[["spend"]].sum().reset_index()
    agg = agg.sort_values("spend", ascending=False)
    agg.rename(columns={"category": "Category", "spend": "Spend"}, inplace=True)
    return agg


def by_month(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"month": [], "spend": [], "income": []})
    temp = df.copy()
    temp["month"] = pd.to_datetime(temp["date"]).dt.to_period("M").astype(str)
    spend = temp[temp["amount"] < 0].groupby("month")["amount"].sum().mul(-1)
    inc = temp[temp["amount"] > 0].groupby("month")["amount"].sum()
    out = pd.concat([spend, inc], axis=1).fillna(0.0)
    out.columns = ["Spend", "Income"]
    out = out.reset_index().rename(columns={"month": "Month"})
    return out