≈**Live demo:** https://my-project11-yphc9epyw9wcbp6uil5v8p.streamlit.app/# My Project

A lightweight dashboard for small businesses to see **KPIs, trends, and top products** in seconds.

## Features
- KPI cards: total revenue, orders, average order value, top product
- Date range filter (with quick 7/30/90-day presets if enabled)
- Charts: revenue by month & by product
- CSV upload (columns: `date`, `product`, `channel` and either `revenue` OR both `quantity` & `unit_price`)
- Export filtered data as CSV

## Quickstart (local)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
