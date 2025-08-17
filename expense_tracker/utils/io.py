import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .rules import normalize_text


DATE_CANDIDATES = [
    "date",
    "transaction date",
    "posted date",
    "posting date",
    "trans date",
    "value date",
]

DESC_CANDIDATES = [
    "description",
    "details",
    "payee",
    "memo",
    "narrative",
]

AMOUNT_CANDIDATES = [
    "amount",
    "transaction amount",
    "value",
]

DEBIT_CANDIDATES = ["debit", "withdrawal"]
CREDIT_CANDIDATES = ["credit", "deposit"]
TYPE_CANDIDATES = ["type", "transaction type"]
ACCOUNT_CANDIDATES = ["account name", "account", "account number", "card number"]
CATEGORY_CANDIDATES = ["category", "categorization"]


def _canonicalize_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    colmap: Dict[str, Optional[str]] = {"date": None, "description": None, "amount": None, "debit": None, "credit": None, "type": None, "account": None, "category": None}

    lowered = {c.lower().strip(): c for c in df.columns}

    def pick(candidates: List[str]) -> Optional[str]:
        for cand in candidates:
            if cand in lowered:
                return lowered[cand]
        return None

    colmap["date"] = pick(DATE_CANDIDATES)
    colmap["description"] = pick(DESC_CANDIDATES)
    colmap["amount"] = pick(AMOUNT_CANDIDATES)
    colmap["debit"] = pick(DEBIT_CANDIDATES)
    colmap["credit"] = pick(CREDIT_CANDIDATES)
    colmap["type"] = pick(TYPE_CANDIDATES)
    colmap["account"] = pick(ACCOUNT_CANDIDATES)
    colmap["category"] = pick(CATEGORY_CANDIDATES)
    return colmap


def _parse_date(value) -> Optional[pd.Timestamp]:
    try:
        return pd.to_datetime(value, errors="coerce")
    except Exception:
        return None


def extract_merchant(description: str) -> str:
    text = normalize_text(description)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = text.split()
    # Heuristic: first 2 tokens excluding generic words
    filtered = [t for t in tokens if t not in {"purchase", "pos", "debit", "credit", "payment", "card", "visa", "mastercard", "amzn", "amazon"}]
    merchant = " ".join(filtered[:2]) if filtered else (tokens[0] if tokens else "")
    return merchant.strip()


def normalize_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    colmap = _canonicalize_columns(df)

    # Build normalized frame
    out = pd.DataFrame()

    # Date
    if colmap["date"] is not None:
        out["date"] = pd.to_datetime(df[colmap["date"]], errors="coerce")
    else:
        out["date"] = pd.NaT

    # Description
    if colmap["description"] is not None:
        out["description"] = df[colmap["description"]].astype(str)
    else:
        # Try to combine various columns as fallback
        possible_cols = [c for c in df.columns if c.lower() in DESC_CANDIDATES]
        if possible_cols:
            out["description"] = df[possible_cols[0]].astype(str)
        else:
            out["description"] = ""

    # Amount logic
    amount_series = None
    if colmap["amount"] is not None:
        amount_series = pd.to_numeric(df[colmap["amount"]], errors="coerce")
    else:
        debit = pd.to_numeric(df[colmap["debit"]], errors="coerce") if colmap["debit"] is not None else None
        credit = pd.to_numeric(df[colmap["credit"]], errors="coerce") if colmap["credit"] is not None else None
        if debit is not None or credit is not None:
            debit_filled = debit.fillna(0) if debit is not None else 0
            credit_filled = credit.fillna(0) if credit is not None else 0
            amount_series = credit_filled - debit_filled
    if amount_series is None:
        amount_series = 0.0
    out["amount"] = pd.to_numeric(amount_series, errors="coerce").fillna(0.0)

    # Type
    if colmap["type"] is not None:
        out["type"] = df[colmap["type"]].astype(str).str.lower()
    else:
        out["type"] = None

    # Account
    if colmap["account"] is not None:
        out["account"] = df[colmap["account"]].astype(str)
    else:
        out["account"] = None

    # Category if given
    if colmap["category"] is not None:
        out["category"] = df[colmap["category"]].astype(str)
    else:
        out["category"] = None

    # Merchant heuristic
    out["merchant"] = out["description"].map(extract_merchant)

    # Clean invalid dates
    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    # Normalize amount sign: expenses negative, income positive
    # If bank exports positive for expenses (some do), infer by type keywords
    def normalize_sign(row):
        amt = row["amount"]
        t = (row.get("type") or "").lower()
        if pd.isna(amt):
            return 0.0
        if "debit" in t or "withdraw" in t or "purchase" in t:
            return -abs(amt)
        if "credit" in t or "deposit" in t or "income" in t or "refund" in t:
            return abs(amt)
        # Fallback heuristic: if both debit/credit present originally handled above
        return amt

    out["amount"] = out.apply(normalize_sign, axis=1)

    # Reorder
    for col in ["date", "description", "merchant", "amount", "category", "type", "account"]:
        if col not in out.columns:
            out[col] = None
    out = out[["date", "description", "merchant", "amount", "category", "type", "account"]]

    return out


def load_csv(file_path_or_buffer) -> pd.DataFrame:
    df = pd.read_csv(file_path_or_buffer)
    return normalize_dataframe(df)