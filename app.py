# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# ---------- 配置：csv放在项目根目录 ----------
DATA_FILE = "ecommerce_orders.csv"

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE, parse_dates=["order_date"])
    # 计算订单总金额：单价*数量，扣折扣，加运费
    df["order_total"] = df["unit_price"] * df["quantity"] * (1 - df["discount_pct"] / 100) + df["shipping_cost"]
    return df

df = load_data()

# ========= 页面头部 =========
st.title("📊 电商订单运营看板 | Team 9")
st.caption("目标用户：电商运营经理｜用于监控订单、退货风险，辅助履约与运营优化决策")

# -------- 侧边栏筛选控件 --------
st.sidebar.header("🔍 筛选条件")
cat_list = ["全部"] + sorted(df["product_category"].dropna().unique().tolist())
selected_category = st.sidebar.selectbox("商品品类", cat_list)

channel_list = ["全部"] + sorted(df["marketing_channel"].dropna().unique().tolist())
selected_channel = st.sidebar.selectbox("营销渠道", channel_list)

# 应用筛选逻辑
df_filter = df.copy()
if selected_category != "全部":
    df_filter = df_filter[df_filter["product_category"] == selected_category]
if selected_channel != "全部":
    df_filter = df_filter[df_filter["marketing_channel"] == selected_channel]

# ========= 顶部3个核心KPI =========
total_orders = len(df_filter)
total_revenue = df_filter["order_total"].sum()
return_rate = df_filter["is_returned"].mean() * 100

# 拆分2023、2024数据，计算同比变化delta
df_2023 = df_filter[df_filter["order_date"].dt.year == 2023]
df_2024 = df_filter[df_filter["order_date"].dt.year == 2024]

ord_23 = len(df_2023)
ord_24 = len(df_2024)
rev_23 = df_2023["order_total"].sum()
rev_24 = df_2024["order_total"].sum()
ret_23 = df_2023["is_returned"].mean() * 100 if len(df_2023) > 0 else 0
ret_24 = df_2024["is_returned"].mean() * 100 if len(df_2024) > 0 else 0

delta_ord = round((ord_24 - ord_23)/ord_23*100,1) if ord_23 > 0 else None
delta_rev = round((rev_24 - rev_23)/rev_23*100,1) if rev_23 > 0 else None
delta_ret = round(ret_24 - ret_23,2)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="总订单数", value=f"{total_orders:,}", delta=f"{delta_ord}%" if delta_ord is not None else None)
with col2:
    st.metric(label="总营收", value=f"${total_revenue:,.2f}", delta=f"{delta_rev}%" if delta_rev is not None else None)
with col3:
    st.metric(label="退货率", value=f"{return_rate:.2f} %", delta=f"{delta_ret} pp" if delta_ret is not None else None, delta_color="inverse")

# ============ 图表1：月度订单&营收趋势 =========
st.subheader("📈 月度订单&营收趋势")
df_filter["order_month"] = df_filter["order_date"].dt.to_period("M").dt.to_timestamp()
monthly = df_filter.groupby("order_month").agg(
    orders=("order_id","count"),
    revenue=("order_total","sum")
).reset_index()

fig_trend = px.line(
    monthly,
    x="order_month",
    y=["orders","revenue"],
    labels={"value":"数值","order_month":"月份","variable":"指标"},
    title="月度订单量 & 营收"
)
st.plotly_chart(fig_trend, width="stretch")
st.caption("⚠️提示：2024‑12月份数据可能不完全；本数据集为Kaggle合成快照")

# ============ 图表2：各商品品类退货率 =========
st.subheader("📉 各商品品类退货率")
cat_ret = df_filter.groupby("product_category").agg(
    order_count=("order_id","count"),
    return_rate_pct=("is_returned", lambda x: x.mean()*100)
).reset_index()

# 过滤样本过小的品类，订单小于20条统计结果不可信
cat_ret = cat_ret[cat_ret["order_count"] >= 20]

fig_cat = px.bar(
    cat_ret,
    x="product_category",
    y="return_rate_pct",
    hover_data=["order_count"],
    labels={"return_rate_pct":"退货率(%)","product_category":"商品品类"},
    title="品类退货率（仅展示订单>=20的品类）"
)
st.plotly_chart(fig_cat, width="stretch")
st.caption("⚠️ 部分字段存在少量缺失；return_reason仅退货订单才有值")

# ========= 可展开查看筛选后的原始订单明细 =========
with st.expander("📋 查看筛选后的原始订单明细"):
    show_cols = ["order_id","order_date","product_category","marketing_channel","order_total","is_returned","return_reason"]
    st.dataframe(df_filter[show_cols], width="stretch")

# ========= 页面底部：数据快照 & 生产环境刷新策略 =========
st.divider()
st.markdown("""
**数据信息：**
- 数据来源：Kaggle ecommerce‑orders 合成数据集，时间范围：2023‑01 至 2024‑12
- 当前为静态CSV快照。**生产环境刷新策略：**
  1. 数据夜间每日同步更新；运营经理每周一早上查看看板。
  2. 例外告警：品类退货率持续高于20%时，**当日触发告警通知，不等每周复盘**。
  3. 不需要实时刷新：订单履约、退货分析按周决策，实时数据不会改变业务动作，会增加系统成本。
""")
