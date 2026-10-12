"""Amazon Discount Paradox: a focused category-manager decision dashboard."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
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

st.markdown("### The question: are deep discounts hiding weak customer experience?")
k1, k2, k3 = st.columns(3)
k1.metric("Typical advertised discount", f"{view['discount_n'].median():.0f}%" if len(view) else "—",
          help="Median displayed discount percentage, not realized savings.")
deep_count = int(view["deep"].sum())
weak_deep = int((view["deep"] & view["weak"]).sum())
k2.metric("Weak-rating share among deep deals", f"{weak_deep/deep_count:.1%}" if deep_count else "—",
          help="Share rated below 3.8 among listings with advertised discount ≥60%.")
k3.metric("Deals needing investigation", f"{view['priority'].sum():,}",
          help=f"Discount ≥60%, rating <3.8, and at least {min_evidence:,} recorded ratings.")

st.markdown("### 01 / Is the ‘bigger discount = happier customer’ assumption true?")
st.caption("Each dot is one product. Color shows rating risk; larger dots have more recorded ratings. Association is not causation.")
plot = view.dropna(subset=["count_n"])
fig, ax = plt.subplots(figsize=(11, 4.4))
fig.patch.set_facecolor("#FAF9F6")
ax.set_facecolor("#FFFFFF")
if not plot.empty:
    sizes = 18 + 85 * np.sqrt(plot["count_n"].clip(lower=0) / max(plot["count_n"].max(), 1))
    good = plot[~plot["weak"]]
    bad = plot[plot["weak"]]
    ax.scatter(good["discount_n"], good["rating_n"], s=sizes.loc[good.index], color="#139C95", alpha=.42, edgecolor="none", label="Rating ≥ 3.8")
    ax.scatter(bad["discount_n"], bad["rating_n"], s=sizes.loc[bad.index], color="#EA7457", alpha=.65, edgecolor="none", label="Rating < 3.8")
ax.axvline(DEEP, ls="--", c="#E9A837", lw=1.8, label="60% deep-deal rule")
ax.axhline(LOW, ls=":", c="#8B76B9", lw=1.8, label="3.8 low-rating rule")
ax.set(xlabel="Advertised discount (%)", ylabel="Average star rating", xlim=(0, 100), ylim=(1, 5.1))
ax.grid(alpha=.15)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(loc="lower left", ncol=2, fontsize=9, frameon=False)
fig.tight_layout()
st.pyplot(fig, use_container_width=True)
plt.close(fig)

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

st.markdown("### Investigation queue · Which listings should we check first?")
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
