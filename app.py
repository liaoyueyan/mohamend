from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Order Ops Dashboard · OpsQuartet", layout="wide")

TEAM = "Team OpsQuartet"
DATA_FILE = "data/ecommerce_orders.csv"
DATA_NOTE = (
    "Data: Jan 2023 – Dec 2024 · Kaggle snapshot (synthetic). "
    "In production: refresh nightly; the ops manager reviews every Monday."
)

# ---------------------------------------------------------------------------
# Load + prep (cached; the CSV is a frozen snapshot, ~1.2 MB)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE, parse_dates=["order_date"])
    # Net revenue after the line-item discount.
    df["revenue"] = df["unit_price"] * df["quantity"] * (1 - df["discount_pct"] / 100.0)
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.to_period("M").astype(str)
    return df


df = load_data()

# ---------------------------------------------------------------------------
# Filters — only the two levers an ops manager actually pulls.
# Category and channel both drive return rates; that is where they act.
# (Country was deliberately cut — see README.)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    categories = st.multiselect(
        "Product category",
        options=sorted(df["product_category"].dropna().unique()),
        default=sorted(df["product_category"].dropna().unique()),
    )
    channels = st.multiselect(
        "Marketing channel",
        options=sorted(df["marketing_channel"].dropna().unique()),
        default=sorted(df["marketing_channel"].dropna().unique()),
    )
    st.caption(
        "≈3% of rows have a missing country/device; they are ignored where not "
        "needed and don't affect these KPIs. Return reasons only exist on returns."
    )

sel = df[df["product_category"].isin(categories) & df["marketing_channel"].isin(channels)].copy()

# ---------------------------------------------------------------------------
# KPI helpers + year-over-year delta (current year vs prior year in the data)
# ---------------------------------------------------------------------------
def compute(part: pd.DataFrame) -> dict:
    return {
        "orders": int(len(part)),
        "revenue": float(part["revenue"].sum()),
        "return_rate": float(part["is_returned"].mean() * 100),
    }


def year_delta(part: pd.DataFrame) -> dict:
    """Delta of the latest full year vs the year before it (or None)."""
    years = sorted(part["year"].unique())
    if len(years) < 2:
        return {"orders": None, "revenue": None, "return_rate": None}
    cur, prev = compute(part[part["year"] == years[-1]]), compute(part[part["year"] == years[-2]])
    return {
        "orders": cur["orders"] - prev["orders"],
        "revenue": cur["revenue"] - prev["revenue"],
        "return_rate": cur["return_rate"] - prev["return_rate"],  # percentage points
    }


k = compute(sel)
delta = year_delta(sel)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title(TEAM)
st.caption(
    "Built for the **E-commerce Operations Manager** — spot where returns eat into "
    "margin and whether order volume is healthy, in the first five seconds, then act."
)

# ---------------------------------------------------------------------------
# Headline KPIs — the "is anything wrong right now?" row
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric(
    "Total revenue",
    f"${k['revenue']:,.0f}",
    delta=f"{delta['revenue']:+,.0f} vs prior year" if delta["revenue"] is not None else None,
)
c2.metric(
    "Orders",
    f"{k['orders']:,}",
    delta=f"{delta['orders']:+,} vs prior year" if delta["orders"] is not None else None,
)
c3.metric(
    "Return rate",
    f"{k['return_rate']:.1f}%",
    delta=f"{delta['return_rate']:+.1f} pts vs prior year"
    if delta["return_rate"] is not None
    else None,
)
st.caption(f"Selection currently covers {len(sel):,} of {len(df):,} orders.")

st.divider()

# ---------------------------------------------------------------------------
# Supporting chart 1 — monthly revenue & orders trend
# Explains *why* a headline number moved (seasonality / a bad or good month).
# ---------------------------------------------------------------------------
st.subheader("Orders & revenue over time")
monthly = (
    sel.groupby("month", as_index=False)
    .agg(orders=("order_id", "count"), revenue=("revenue", "sum"))
    .sort_values("month")
)
fig = go.Figure()
fig.add_bar(x=monthly["month"], y=monthly["revenue"], name="Revenue", yaxis="y")
fig.add_scatter(
    x=monthly["month"], y=monthly["orders"], name="Orders", yaxis="y2", line=dict(color="#ef553b", width=2.5)
)
fig.update_layout(
    height=360,
    hovermode="x unified",
    yaxis=dict(title="Revenue ($)", gridcolor="#eee"),
    yaxis2=dict(title="Orders", overlaying="y", side="right", showgrid=False),
    legend=dict(orientation="h", y=1.12),
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig, width="stretch")
st.caption(
    "Caution: the trailing month (Dec 2024) may be a partial snapshot — a dip at the end "
    "of the line is often just a calendar effect, not a real slowdown."
)

# ---------------------------------------------------------------------------
# Supporting chart 2 — return rate by category (the ops manager's biggest lever)
# ---------------------------------------------------------------------------
st.subheader("Return rate by category")
cat = (
    sel.groupby("product_category", as_index=False)
    .agg(orders=("order_id", "count"), returns=("is_returned", "sum"))
)
cat["return_rate"] = cat["returns"] / cat["orders"] * 100
# Hide tiny categories: a 100% return rate on 5 orders is noise, not a signal.
cat = cat[cat["orders"] >= 20].sort_values("return_rate", ascending=True)
fig2 = px.bar(
    cat,
    x="return_rate",
    y="product_category",
    orientation="h",
    text=cat["return_rate"].round(1).astype(str) + "%",
    color="return_rate",
    color_continuous_scale=["#2b7bba", "#f0ad4e", "#d9534f"],
)
fig2.update_layout(
    height=420,
    xaxis=dict(title="Return rate (%)"),
    yaxis=dict(title=""),
    coloraxis_showscale=False,
    margin=dict(l=10, r=10, t=10, b=10),
)
fig2.update_traces(textposition="outside")
st.plotly_chart(fig2, width="stretch")
st.caption(
    "Categories with fewer than 20 orders are hidden — small-sample return rates mislead. "
    "A rate above ~20% is the trigger to review product quality / listing accuracy."
)

st.divider()

# ---------------------------------------------------------------------------
# Bottom — order-level detail for anyone who wants to dig in
# ---------------------------------------------------------------------------
with st.expander("Order-level detail (dig in)"):
    detail = sel.sort_values("order_date", ascending=False)[
        [
            "order_date", "order_id", "product_category", "marketing_channel", "country",
            "unit_price", "quantity", "revenue", "is_returned", "return_reason",
        ]
    ]
    st.dataframe(detail.head(500), width="stretch", hide_index=True)
    st.caption(f"Showing up to 500 of {len(detail):,} matching orders, newest first.")

st.divider()
st.caption(f"{DATA_NOTE} — this is a frozen Kaggle snapshot; it does not update.")
