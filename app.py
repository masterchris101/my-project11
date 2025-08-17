import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Sales Dashboard", layout="wide")

DATA_PATH = Path("data/sales.csv")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---- Generate mock data on first run ----
def bootstrap_mock_data(n_orders: int = 1200, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = datetime.today().date()
    start = end - timedelta(days=180)

    dates = pd.to_datetime(
        rng.integers(int(pd.Timestamp(start).value // 1e9),
                     int(pd.Timestamp(end).value // 1e9),
                     n_orders), unit="s"
    ).date
    products = np.array(["Basic", "Plus", "Pro", "Enterprise"])
    channels = np.array(["In-Store", "Online", "Phone"])
    prices = {"Basic": 19, "Plus": 39, "Pro": 79, "Enterprise": 199}

    df = pd.DataFrame({
        "order_id": np.arange(1, n_orders + 1),
        "date": pd.to_datetime(dates),
        "product": rng.choice(products, n_orders, p=[0.35, 0.35, 0.22, 0.08]),
        "channel": rng.choice(channels, n_orders, p=[0.5, 0.45, 0.05]),
        "quantity": rng.integers(1, 5, n_orders),
        "customer_id": rng.integers(10_000, 99_999, n_orders),
    })
    df["unit_price"] = df["product"].map(prices)
    df["revenue"] = df["unit_price"] * df["quantity"]
    df.sort_values("date", inplace=True)
    return df

if not DATA_PATH.exists():
    df0 = bootstrap_mock_data()
    df0.to_csv(DATA_PATH, index=False)

# ---- Load data ----
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df

df = load_data(DATA_PATH)

# ---- Sidebar filters ----
st.sidebar.header("Filters")
min_d, max_d = df["date"].min().date(), df["date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_d, end_d = pd.to_datetime(date_range), pd.to_datetime(date_range)
if start_d > end_d:
    start_d, end_d = end_d, start_d

prod_sel = st.sidebar.multiselect("Products", sorted(df["product"].unique()), default=sorted(df["product"].unique()))
chan_sel = st.sidebar.multiselect("Channels", sorted(df["channel"].unique()), default=sorted(df["channel"].unique()))

mask = (
    (df["date"].between(start_d, end_d)) &
    (df["product"].isin(prod_sel)) &
    (df["channel"].isin(chan_sel))
)
fdf = df.loc[mask].copy()

# ---- KPIs ----
total_rev = float(fdf["revenue"].sum())
orders = int(fdf["order_id"].nunique())
aov = (total_rev / orders) if orders else 0.0
top_product = fdf.groupby("product")["revenue"].sum().sort_values(ascending=False).head(1)
top_product_name = top_product.index[0] if not top_product.empty else "—"
top_product_rev = float(top_product.iloc[0]) if not top_product.empty else 0.0

st.title("📊 Sales Dashboard")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue", f"${total_rev:,.0f}")
k2.metric("Orders", f"{orders:,}")
k3.metric("Avg. Order Value", f"${aov:,.2f}")
k4.metric("Top Product", f"{top_product_name} (${top_product_rev:,.0f})")

# ---- Charts ----
fdf["month"] = fdf["date"].dt.to_period("M").dt.to_timestamp()

col1, col2 = st.columns(2)

with col1:
    m = fdf.groupby("month")["revenue"].sum().reset_index()
    fig = px.line(m, x="month", y="revenue", markers=True, title="Revenue by Month")
    fig.update_layout(yaxis_tickprefix="$")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    p = fdf.groupby("product")["revenue"].sum().reset_index().sort_values("revenue", ascending=False)
    fig = px.bar(p, x="product", y="revenue", title="Revenue by Product")
    fig.update_layout(yaxis_tickprefix="$")
    st.plotly_chart(fig, use_container_width=True)

tab1, tab2 = st.tabs(["Orders Table", "Raw Data"])
with tab1:
    st.dataframe(fdf.sort_values("date", ascending=False), use_container_width=True, height=420)
with tab2:
    st.code(DATA_PATH.read_text()[:1000] + ("\n...\n" if DATA_PATH.stat().st_size > 1000 else ""), language="csv")

st.caption("Tip: replace `data/sales.csv` with your real data to turn this into a client-ready dashboard.")

