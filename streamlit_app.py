"""Amazon Discount Paradox: a focused category-manager decision dashboard."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Amazon | The Discount Paradox", page_icon="🛍️", layout="wide")
PATH = Path(__file__).resolve().parent / "amazon.csv"

st.markdown("""<style>
.stApp {background: #FAF9F6; color: #222B37;}
.block-container {max-width: 1200px; padding-top: 2rem;}
h1,h2,h3 {color:#20263B !important; letter-spacing:-.025em;}
[data-testid="stMetric"] {background:white; border:1px solid #E9E5DF; border-radius:16px; padding:16px; box-shadow:0 4px 16px #25203909;}
[data-testid="stMetricLabel"] {color:#536273;}
[data-testid="stMetricValue"] {color:#20263B;}
[data-testid="stCaptionContainer"] {color:#687482;}
div[data-testid="stExpander"] {background:white; border-radius:12px;}
</style>""", unsafe_allow_html=True)

@st.cache_data
def load():
    d = pd.read_csv(PATH).drop_duplicates("product_id", keep="first").copy()
    d["category_main"] = d["category"].fillna("Unknown").str.split("|").str[0]
    for raw, col in [("rating", "rating_n"), ("rating_count", "count_n"),
                     ("discounted_price", "price_n"), ("actual_price", "original_n"),
                     ("discount_percentage", "discount_n")]:
        d[col] = pd.to_numeric(d[raw].astype("string").str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    d.loc[~d["rating_n"].between(1, 5), "rating_n"] = np.nan
    d.loc[~d["discount_n"].between(0, 100), "discount_n"] = np.nan
    return d

st.title("🛍️ The Discount Paradox")
st.markdown("**Amazon Marketplace · Category Decision Dashboard**")
st.caption("For an e-commerce category manager: decide which heavily discounted but poorly rated products deserve a listing, pricing, or quality review.")
if not PATH.exists():
    st.error("amazon.csv is missing. Upload it beside streamlit_app.py in your GitHub repository.")
    st.stop()

df = load()
main_categories = df["category_main"].value_counts()
options = main_categories[main_categories >= 15].index.tolist()
left, right = st.columns([2, 1])
with left:
    category = st.selectbox("Your category responsibility", ["All major categories"] + options)
with right:
    min_evidence = st.selectbox("Minimum rating count (evidence)", [100, 1000, 5000], index=0,
                                help="Exclude products with very little customer feedback from the action list.")
view = df if category == "All major categories" else df[df["category_main"] == category]
view = view.dropna(subset=["rating_n", "discount_n"]).copy()
DEEP = 60  # initial business rule; adjustable after validation
LOW = 3.8
view["deep"] = view["discount_n"] >= DEEP
view["weak"] = view["rating_n"] < LOW
view["priority"] = view["deep"] & view["weak"] & (view["count_n"].fillna(0) >= min_evidence)

st.markdown("### At a glance · Traditional product indicators")
k1, k2, k3 = st.columns(3)
k1.metric("Products in selection", f"{len(view):,}", help="Unique product listings with usable rating and discount values.")
k2.metric("Average current price", f"₹{view['price_n'].mean():,.0f}" if view['price_n'].notna().any() else "—", help="Mean listed discounted price; not sales or realized revenue.")
k3.metric("Average customer rating", f"{view['rating_n'].mean():.2f} / 5" if len(view) else "—", help="Unweighted average of product-level star ratings.")

with st.expander("📋 More traditional indicators · Product summary"):
    summary = pd.DataFrame({
        "Indicator": ["Median advertised discount", "Total recorded rating counts", "Median listed price", "Products with a deep discount (≥60%)"],
        "Value": [f"{view['discount_n'].median():.1f}%" if len(view) else "—",
                  f"{view['count_n'].fillna(0).sum():,.0f}",
                  f"₹{view['price_n'].median():,.0f}" if view['price_n'].notna().any() else "—",
                  f"{int(view['deep'].sum()):,}"],
        "Interpretation": ["Listed discount, not verified savings", "Number of ratings, NOT sales volume", "Typical listed discounted price", "Count of listings meeting the working discount rule"]
    })
    st.dataframe(summary, hide_index=True, use_container_width=True)

st.markdown("### Beyond the basics · Three questions worth investigating")
deep_count = int(view["deep"].sum())
weak_deep = int((view["deep"] & view["weak"]).sum())
share = f"{weak_deep / deep_count:.1%}" if deep_count else "not measurable"
st.markdown(f"**Decision signal:** {share} of deeply discounted products have a rating below {LOW}; "
            f"**{int(view['priority'].sum()):,} listings** also meet the review-evidence threshold "
            f"and enter the investigation queue. These are exploratory screening rules, not confirmed defects.")

st.markdown("### 01 / Is the ‘bigger discount = happier customer’ assumption true?")
st.caption("Hover over a dot (or tap it on mobile) to see its product name, price, discount, rating, and rating count. Dot size reflects rating count; correlation is not causation.")
plot = view.dropna(subset=["count_n", "discount_n", "rating_n"]).copy()
if not plot.empty:
    plot["Rating band"] = np.where(plot["weak"], "Below 3.8 · Check", "3.8 or higher")
    plot["Product"] = plot["product_name"].fillna("Unnamed product").str.slice(0, 110)
    plot["Price (₹)"] = plot["price_n"]
    plot["Rating count"] = plot["count_n"].astype(int)
    plot["Discount (%)"] = plot["discount_n"]
    plot["Star rating"] = plot["rating_n"]
    # A square-root scale keeps very heavily reviewed products from obscuring everything else.
    plot["Bubble size"] = np.sqrt(plot["count_n"].clip(lower=0) + 1)
    scatter = px.scatter(
        plot, x="Discount (%)", y="Star rating", color="Rating band",
        size="Bubble size", size_max=18,
        color_discrete_map={"Below 3.8 · Check": "#EA7457", "3.8 or higher": "#139C95"},
        custom_data=["Product", "Price (₹)", "Rating count", "product_id"],
        labels={"Rating band": "Customer-rating group"},
        category_orders={"Rating band": ["3.8 or higher", "Below 3.8 · Check"]},
        opacity=0.67,
    )
    scatter.update_traces(
        hovertemplate=("<b>%{customdata[0]}</b><br>Discount: %{x:.0f}%"
                       "<br>Rating: %{y:.1f} / 5"
                       "<br>Current price: ₹%{customdata[1]:,.0f}"
                       "<br>Rating count: %{customdata[2]:,}"
                       "<br>Product ID: %{customdata[3]}<extra></extra>"),
        marker=dict(line=dict(width=0)),
    )
    scatter.add_vline(x=DEEP, line_dash="dash", line_color="#E9A837", line_width=2)
    scatter.add_hline(y=LOW, line_dash="dot", line_color="#8B76B9", line_width=2)
    scatter.update_layout(
        height=480, plot_bgcolor="#FFFFFF", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#293244"), legend=dict(orientation="h", y=-0.24, x=0),
        margin=dict(l=10, r=10, t=12, b=60),
        hoverlabel=dict(bgcolor="white", font_size=13, font_color="#293244"),
    )
    scatter.update_xaxes(range=[0, 100], showgrid=True, gridcolor="#EFEFEF", title="Advertised discount (%)")
    scatter.update_yaxes(range=[1, 5.1], showgrid=True, gridcolor="#EFEFEF", title="Average star rating")
    st.plotly_chart(scatter, use_container_width=True, config={"displayModeBar": True, "scrollZoom": False})
else:
    st.info("No products with valid ratings, discounts, and review counts in this selection.")

st.markdown("#### 🏆 Best 10 and ⚠️ Worst 10 rated products")
st.caption("Rankings use the current category filter and require at least the selected minimum rating count. High/low refers to customer star ratings, not product value or verified quality. Ties are broken by rating count.")
ranked = view.dropna(subset=["rating_n", "count_n"]).copy()
ranked = ranked[ranked["count_n"] >= min_evidence]

def product_ranking_table(frame):
    if frame.empty:
        return pd.DataFrame(columns=["Product", "Rating ★", "Rating count", "Discount (%)", "Current price (₹)", "Product link"])
    out = frame[["product_name", "rating_n", "count_n", "discount_n", "price_n", "product_link"]].copy()
    out.columns = ["Product", "Rating ★", "Rating count", "Discount (%)", "Current price (₹)", "Product link"]
    out["Product"] = out["Product"].fillna("Unnamed product").str.slice(0, 85)
    return out

rank_columns = {
    "Product link": st.column_config.LinkColumn("Product link", display_text="Open product ↗"),
    "Rating ★": st.column_config.NumberColumn("Rating ★", format="%.1f"),
    "Discount (%)": st.column_config.NumberColumn("Discount (%)", format="%.0f%%"),
    "Rating count": st.column_config.NumberColumn("Rating count", format="%d"),
    "Current price (₹)": st.column_config.NumberColumn("Current price (₹)", format="₹%.0f"),
}
if ranked.empty:
    st.info("No products meet the selected minimum rating-count threshold. Try a smaller threshold.")
else:
    best = ranked.sort_values(["rating_n", "count_n"], ascending=[False, False]).head(10)
    worst = ranked.sort_values(["rating_n", "count_n"], ascending=[True, False]).head(10)
    st.markdown("**Top 10 · Highest customer ratings**")
    st.dataframe(product_ranking_table(best), hide_index=True, use_container_width=True, column_config=rank_columns)
    st.markdown("**Bottom 10 · Lowest customer ratings**")
    st.dataframe(product_ranking_table(worst), hide_index=True, use_container_width=True, column_config=rank_columns)

st.markdown("### 02 / Which category has the most questionable deep deals?")
st.caption("Compare the share of deeply discounted listings with low ratings within each category; minimum 15 deeply discounted products for comparison.")
agg = view.groupby("category_main").agg(deep_deals=("deep", "sum"), suspect=("priority", "sum"),
                                         weak_deep=("weak", lambda x: 0))
# Use the same rate definition as KPI 2; minimum-feedback filter only affects the investigation queue.
agg["weak_deep"] = view.assign(both=view["deep"] & view["weak"]).groupby("category_main")["both"].sum()
agg = agg[agg["deep_deals"] >= 15].copy()
agg["risk_pct"] = agg["weak_deep"] / agg["deep_deals"] * 100
agg = agg.sort_values("risk_pct")
if not agg.empty:
    fig2, ax2 = plt.subplots(figsize=(11, max(2.4, .65 * len(agg) + .7)))
    fig2.patch.set_facecolor("#FAF9F6")
    ax2.set_facecolor("#FFFFFF")
    bars = ax2.barh(agg.index, agg["risk_pct"], color=["#EA7457" if r >= 15 else "#8B76B9" for r in agg["risk_pct"]])
    for b, (_, row) in zip(bars, agg.iterrows()):
        ax2.text(b.get_width()+.5, b.get_y()+b.get_height()/2,
                 f"{row['risk_pct']:.1f}%  (n={int(row['deep_deals'])})", va="center", fontsize=10)
    ax2.set_xlim(0, max(30, float(agg["risk_pct"].max())+18))
    ax2.set_xlabel("Low-rated share of deeply discounted listings (%)")
    ax2.spines[["top", "right", "left"]].set_visible(False)
    ax2.grid(axis="x", alpha=.12)
    fig2.tight_layout()
    st.pyplot(fig2, use_container_width=True)
    plt.close(fig2)
else:
    st.info("Too few deeply discounted products to make a stable category comparison in this selection.")

st.markdown("### 03 / Which listings should we investigate first?")
st.caption("Sorted by rating-count evidence, not sales. Investigate complaints, listing accuracy, and advertised reference prices before changing a price.")
queue = view[view["priority"]].sort_values(["count_n", "rating_n"], ascending=[False, True]).head(15)
if not queue.empty:
    tbl = queue[["product_name", "category_main", "discount_n", "rating_n", "count_n", "price_n", "product_link"]].rename(columns={
        "product_name":"Product", "category_main":"Category", "discount_n":"Discount (%)", "rating_n":"Rating", "count_n":"Rating count", "price_n":"Current price (₹)", "product_link":"Product link"})
    st.dataframe(tbl, hide_index=True, use_container_width=True,
                 column_config={"Product link":st.column_config.LinkColumn("Product link")})
else:
    st.info("No listings meet the three investigation criteria in the selected view.")

with st.expander("📌 How to use this dashboard & what it cannot prove"):
    st.markdown("""**Decision rule (illustrative):** investigate a listing when discount ≥60%, average rating <3.8, and rating count meets the chosen evidence threshold. These values are working assumptions, not validated business targets.\n\n**Two deliberate omissions:** (1) Revenue/sales KPIs — no sales transactions are present. (2) Time trends — this file has no reliable observation dates.\n\n**Interpretation limits:** Advertised discounts rely on listed reference prices, which may not reflect real savings. Rating counts are neither sales nor unique buyers. A discount-rating relationship in a snapshot does not establish that discounts caused customer dissatisfaction. Category comparisons are suppressed when denominators are small.""")
st.divider()
st.caption("**Data:** undated Kaggle Amazon product snapshot · **Production proposal:** refresh nightly from the catalog/reviews system; category manager reviews weekly · **Escalation:** investigate newly qualifying listings when evidence exceeds the selected minimum. No real-time feed is connected.")
