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
            "order_date", "order_id", "product_category", "marketing_channel", "country",# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# ---------- 配置：csv放在根目录！！ ----------
DATA_FILE = "ecommerce_orders.csv"

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE, parse_dates=["order_date"])
    # 计算订单总金额
    df["order_total"] = df["unit_price"] * df["quantity"] * (1 - df["discount_pct"] / 100) + df["shipping_cost"]
    return df

df = load_data()

# ========= 页面头部 =========
st.title("📊 电商订单运营看板 | Team OpsQuartet")
st.caption("目标用户：电商运营经理｜用于监控订单、退货风险，辅助履约与运营优化决策")

# -------- 筛选控件 --------
st.sidebar.header("🔍 筛选条件")
cat_list = ["全部"] + sorted(df["product_category"].dropna().unique().tolist())
selected_category = st.sidebar.selectbox("商品品类", cat_list)

channel_list = ["全部"] + sorted(df["marketing_channel"].dropna().unique().tolist())
selected_channel = st.sidebar.selectbox("营销渠道", channel_list)

# 应用筛选
df_filter = df.copy()
if selected_category != "全部":
    df_filter = df_filter[df_filter["product_category"] == selected_category]
if selected_channel != "全部":
    df_filter = df_filter[df_filter["marketing_channel"] == selected_channel]

# ========= 顶部3个核心KPI =========
total_orders = len(df_filter)
total_revenue = df_filter["order_total"].sum()
return_rate = df_filter["is_returned"].mean() * 100

# 2023、2024同比（用于delta）
df_2023 = df_filter[df_filter["order_date"].dt.year == 2023]
df_2024 = df_filter[df_filter["order_date"].dt.year == 2024]

ord_23 = len(df_2023)
ord_24 = len(df_2024)
rev_23 = df_2023["order_total"].sum()
rev_24 = df_2024["order_total"].sum()
ret_23 = df_2023["is_returned"].mean() *100 if len(df_2023)>0 else 0
ret_24 = df_2024["is_returned"].mean() *100 if len(df_2024)>0 else 0

delta_ord = round((ord_24 - ord_23)/ord_23*100,1) if ord_23>0 else None
delta_rev = round((rev_24 - rev_23)/rev_23*100,1) if rev_23>0 else None
delta_ret = round(ret_24 - ret_23,2)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="总订单数", value=f"{total_orders:,}", delta=f"{delta_ord}%" if delta_ord is not None else None)
with col2:
    st.metric(label="总营收", value=f"${total_revenue:,.2f}", delta=f"{delta_rev}%" if delta_rev is not None else None)
with col3:
    st.metric(label="退货率", value=f"{return_rate:.2f} %", delta=f"{delta_ret} pp" if delta_ret is not None else None, delta_color="inverse")

# ============ 图表1：月度趋势 =========
st.subheader("📈 月度订单&营收趋势")
df_filter["order_month"] = df_filter["order_date"].dt.to_period("M").dt.to_timestamp()
monthly = df_filter.groupby("order_month").agg(
    orders=("order_id","count"),
    revenue=("order_total","sum")
).reset_index()

fig_trend = px.line(monthly, x="order_month", y=["orders","revenue"],
                    labels={"value":"数值","order_month":"月份","variable":"指标"},
                    title="月度订单量 & 营收")
st.plotly_chart(fig_trend, width="stretch")
st.caption("⚠️提示：2024‑12月份数据可能不完全；本数据集为Kaggle合成快照")

# ============ 图表2：各品类退货率 =========
st.subheader("📉 各商品品类退货率")
cat_ret = df_filter.groupby("product_category").agg(
    order_count=("order_id","count"),
    return_rate_pct=("is_returned", lambda x: x.mean()*100)
).reset_index()
# 过滤样本太少的品类（订单少于20条，统计意义弱）
cat_ret = cat_ret[cat_ret["order_count"] >=20]
fig_cat = px.bar(cat_ret, x="product_category", y="return_rate_pct",
                 hover_data=["order_count"],
                 labels={"return_rate_pct":"退货率(%)","product_category":"商品品类"},
                 title="品类退货率（仅展示订单>=20的品类）")
st.plotly_chart(fig_cat, width="stretch")
st.caption("⚠️ 部分字段存在少量缺失；return_reason仅退货订单才有值")

# ========= 可展开原始数据表格 =========
with st.expander("📋 查看筛选后的原始订单明细"):
    st.dataframe(df_filter[["order_id","order_date","product_category","marketing_channel","order_total","is_returned","return_reason"]], width="stretch")

# ========= 底部：数据快照 & 生产环境刷新策略 =========
st.divider()
st.markdown("""
**数据信息：**
- 数据来源：Kaggle ecommerce‑orders 合成数据集，时间范围：2023‑01 至 2024‑12
- 当前为静态CSV快照。**生产环境刷新策略：**
  1. 数据夜间每日同步更新；运营经理每周一早上查看看板。
  2. 例外告警：品类退货率持续高于20%时，**当日触发告警通知，不等每周复盘**。
  3. 不需要实时刷新：订单履约、退货分析按周决策，实时数据不会改变业务动作，会增加系统成本。
""")
