import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Sales Dashboard", layout="wide")

DATA_PATH = Path("data/sales.csv")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------
# Mock data bootstrap (first run)
# ---------------------------
def bootstrap_mock_data(n_orders: int = 1200, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = datetime.today().date()
    start = end - timedelta(days=180)

    dates = pd.to_datetime(rng.choice(pd.date_range(start, end, freq="D"), n_orders))
    products = np.array(["Basic", "Plus", "Pro", "Enterprise"])
    channels = np.array(["In-Store", "Online", "Phone"])
    prices = {"Basic": 19, "Plus": 39, "Pro": 79, "Enterprise": 199}

    df = pd.DataFrame({
        "order_id": np.arange(1, n_orders + 1),
        "date": dates,
        "product": rng.choice(products, n_orders, p=[0.35, 0.35, 0.22, 0.08]),
        "channel": rng.choice(channels, n_orders, p=[0.50, 0.45, 0.05]),
        "quantity": rng.integers(1, 5, n_orders),
        "customer_id": rng.integers(10_000, 99_999, n_orders),
    })
    df["unit_price"] = df["product"].map(prices)
    df["revenue"] = df["unit_price"] * df["quantity"]
    df.sort_values("date", inplace=True)
    return df

if not DATA_PATH.exists():
    bootstrap_mock_data().to_csv(DATA_PATH, index=False)

@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df

# ---------------------------
# Source data: upload or fallback
# ---------------------------
st.sidebar.header("Filters")

st.sidebar.subheader("Upload CSV")
up = st.sidebar.file_uploader(
    "Columns: date, product, channel and either revenue OR (quantity & unit_price)",
    type="csv",
)

if up is not None:
    df = pd.read_csv(up)
    if "date" not in df.columns:
        st.error("CSV must include a 'date' column."); st.stop()
    df["date"] = pd.to_datetime(df["date"])
    # If no revenue column, try to derive it
    if "revenue" not in df.columns:
        need = {"quantity", "unit_price"}
        if need.issubset(df.columns):
            df["revenue"] = df["quantity"] * df["unit_price"]
        else:
            st.error("Add a 'revenue' column OR both 'quantity' and 'unit_price'."); st.stop()
else:
    df = load_data(DATA_PATH)

# Ensure an order_id exists (some uploads won't have it)
if "order_id" not in df.columns:
    df = df.copy()
    df["order_id"] = np.arange(1, len(df) + 1)

# ---------------------------
# Sidebar filters (date + quick presets + facets)
# ---------------------------
min_d, max_d = df["date"].min().date(), df["date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
if isinstance(date_range, tuple):
    start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
else:
    start_d, end_d = pd.to_datetime(date_range), pd.to_datetime(date_range)

# Quick range presets (overrides start date)
range_choice = st.sidebar.radio("Quick range", ["All", "Last 7 days", "Last 30 days", "Last 90 days"], index=0)
if range_choice != "All":
    days = int(range_choice.split()[1])
    start_d = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)

prod_sel = st.sidebar.multiselect("Products", sorted(df["product"].dropna().unique().tolist()),
                                  default=sorted(df["product"].dropna().unique().tolist()))
chan_sel = st.sidebar.multiselect("Channels", sorted(df["channel"].dropna().unique().tolist()),
                                  default=sorted(df["channel"].dropna().unique().tolist()))

mask = (
    df["date"].between(start_d, end_d) &
    df["product"].isin(prod_sel) &
    df["channel"].isin(chan_sel)
)
fdf = df.loc[mask].copy()

# Allow download of filtered data
st.sidebar.download_button(
    "Download filtered CSV",
    fdf.to_csv(index=False).encode("utf-8"),
    file_name="filtered.csv",
    mime="text/csv",
)

# ---------------------------
# KPIs
# ---------------------------
st.title("📊 Sales Dashboard")

total_rev = float(fdf["revenue"].sum()) if not fdf.empty else 0.0
orders = int(fdf["order_id"].nunique()) if not fdf.empty else 0
aov = (total_rev / orders) if orders else 0.0
top_product_grp = fdf.groupby("product")["revenue"].sum().sort_values(ascending=False)
top_product_name = top_product_grp.index[0] if len(top_product_grp) else "—"
top_product_rev = float(top_product_grp.iloc[0]) if len(top_product_grp) else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue", f"${total_rev:,.0f}")
k2.metric("Orders", f"{orders:,}")
k3.metric("Avg. Order Value", f"${aov:,.2f}")
k4.metric("Top Product Revenue", f"${top_product_rev:,.0f}")
st.caption(f"Top product: {top_product_name}")

# ---------------------------
# Charts
# ---------------------------
if fdf.empty:
    st.info("No data for the selected filters.")
else:
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

    tab1, tab2 = st.tabs(["Orders Table", "Raw Data Snapshot"])
    with tab1:
        st.dataframe(fdf.sort_values("date", ascending=False), use_container_width=True, height=420)
    with tab2:
        st.code(DATA_PATH.read_text()[:1000] + ("\n...\n" if DATA_PATH.stat().st_size > 1000 else ""), language="csv")

st.caption("Tip: Upload your CSV on the left or replace `data/sales.csv` to turn this into a client-ready dashboard.")

