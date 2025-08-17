import io
import os
from typing import List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.io import load_csv, normalize_dataframe
from utils.model import load_model, predict_categories, save_model, train_model
from utils.reporting import by_category, by_month, compute_kpis
from utils.rules import RuleEngine, normalize_text


st.set_page_config(page_title="Expense Tracker", layout="wide")


@st.cache_data
def load_seed_data() -> pd.DataFrame:
    seed_path = os.path.join(os.path.dirname(__file__), "data", "seed_training.csv")
    if os.path.exists(seed_path):
        try:
            df = pd.read_csv(seed_path)
            return normalize_dataframe(df)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def ensure_session_state():
    if "transactions" not in st.session_state:
        st.session_state.transactions = pd.DataFrame(columns=["date", "description", "merchant", "amount", "category", "type", "account"])    
    if "model" not in st.session_state:
        st.session_state.model = None
    if "rules" not in st.session_state:
        st.session_state.rules = RuleEngine()


def apply_rules(df: pd.DataFrame, engine: RuleEngine) -> pd.Series:
    return df["description"].map(lambda t: engine.categorize(t) or None)


def apply_hybrid_categorization(df: pd.DataFrame, seed: pd.DataFrame, engine: RuleEngine) -> pd.DataFrame:
    out = df.copy()

    # Rules first
    rule_cats = apply_rules(out, engine)
    out["category"] = out["category"].where(out["category"].notna(), rule_cats)

    # Prepare labeled data for ML
    labeled_frames: List[pd.DataFrame] = []
    if not seed.empty:
        labeled_frames.append(seed.dropna(subset=["category", "description"]))
    labeled_frames.append(out.dropna(subset=["category", "description"]))
    labeled = pd.concat(labeled_frames, axis=0, ignore_index=True) if labeled_frames else pd.DataFrame()

    model = st.session_state.model or load_model()

    if labeled.empty or labeled["category"].nunique() < 2:
        st.session_state.model = None
        return out

    # (Re)train model on available labels
    model, report = train_model(labeled["description"], labeled["category"])
    st.session_state.model = model
    try:
        save_model(model)
    except Exception:
        pass

    # Predict for uncategorized
    mask_uncat = out["category"].isna() | (out["category"].astype(str).str.strip() == "")
    if mask_uncat.any():
        preds = predict_categories(model, out.loc[mask_uncat, "description"].astype(str))
        out.loc[mask_uncat, "category"] = preds

    return out


def sidebar_controls():
    st.sidebar.header("Upload & Rules")
    uploaded = st.sidebar.file_uploader("Upload transactions CSV", type=["csv"])

    with st.sidebar.expander("Create a quick rule"):
        rule_cat = st.text_input("Category name", key="rule_cat")
        rule_kw = st.text_input("Keyword or regex to match", key="rule_kw")
        if st.button("Add rule"):
            if rule_cat and rule_kw:
                st.session_state.rules.add_rule(rule_cat, rule_kw)
                st.success(f"Rule added: {rule_cat} ← {rule_kw}")

    st.sidebar.download_button(
        label="Download CSV template",
        data=(
            "date,description,amount,category\n"
            "2024-05-01,TRADER JOES #123,-45.67,Groceries\n"
            "2024-05-02,UBER TRIP 9Q8W2,-12.34,Transport\n"
            "2024-05-03,ACME PAYROLL,2500.00,Income\n"
        ).encode("utf-8"),
        file_name="transactions_template.csv",
        mime="text/csv",
    )

    return uploaded


def render_kpis(df: pd.DataFrame):
    kpis = compute_kpis(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Expenses", f"${-kpis['total_expenses']:.2f}")
    c2.metric("Total Income", f"${kpis['total_income']:.2f}")
    c3.metric("Net", f"${kpis['net']:.2f}")


def render_reports(df: pd.DataFrame):
    st.subheader("Spending Reports")

    # Filters
    col1, col2 = st.columns(2)
    min_date = pd.to_datetime(df["date"].min()) if not df.empty else None
    max_date = pd.to_datetime(df["date"].max()) if not df.empty else None
    min_date_val = min_date.date() if (min_date is not None and not pd.isna(min_date)) else None
    max_date_val = max_date.date() if (max_date is not None and not pd.isna(max_date)) else None
    start = col1.date_input("Start date", value=min_date_val)
    end = col2.date_input("End date", value=max_date_val)

    if start and end:
        mask = (pd.to_datetime(df["date"]).dt.date >= start) & (pd.to_datetime(df["date"]).dt.date <= end)
        dff = df.loc[mask].copy()
    else:
        dff = df.copy()

    render_kpis(dff)

    left, right = st.columns(2)

    # Category pie
    cat = by_category(dff)
    if not cat.empty:
        fig = px.pie(cat, values="Spend", names="Category", title="Expenses by Category")
        left.plotly_chart(fig, use_container_width=True)
    else:
        left.info("No expense data to chart.")

    # Monthly line
    monthly = by_month(dff)
    if not monthly.empty:
        fig2 = px.bar(monthly, x="Month", y=["Spend", "Income"], barmode="group", title="Monthly Spend vs Income")
        right.plotly_chart(fig2, use_container_width=True)
    else:
        right.info("No monthly data to chart.")

    st.divider()

    # Transactions table with inline edits on category
    st.subheader("Transactions")
    editable = dff.copy()
    editable["date"] = pd.to_datetime(editable["date"]).dt.date
    edited = st.data_editor(editable, num_rows="dynamic", use_container_width=True, key="editor")

    if st.button("Apply edits and re-train model"):
        # Merge edited categories back
        df_update = df.copy()
        df_update.loc[dff.index, "category"] = edited["category"].values
        st.session_state.transactions = apply_hybrid_categorization(df_update, load_seed_data(), st.session_state.rules)
        st.success("Edits applied and model retrained.")

    csv = dff.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered CSV", data=csv, file_name="categorized_transactions.csv", mime="text/csv")


def main():
    ensure_session_state()

    st.title("Expense Tracker — Auto-categorize & Report")
    st.caption("Upload bank transactions, auto-categorize with rules + ML, and generate spending reports.")

    uploaded = sidebar_controls()

    seed = load_seed_data()

    if uploaded is not None:
        try:
            df = load_csv(uploaded)
        except Exception as e:
            st.error(f"Failed to load file: {e}")
            return
    else:
        df = st.session_state.transactions

    if df is not None and not df.empty:
        df = apply_hybrid_categorization(df, seed, st.session_state.rules)
        st.session_state.transactions = df

        render_reports(df)
    else:
        st.info("Upload a CSV file to get started. Use the template in the sidebar.")


if __name__ == "__main__":
    main()