"""Amazon Product Quality Dashboard — Streamlit class project."""
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Amazon Product Quality | Team Dashboard", page_icon="📦", layout="wide")

DATA_FILE = Path(__file__).resolve().parent / "amazon.csv"
LOW_RATING_THRESHOLD = 3.8


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # The dataset is a product snapshot, not an order-level sales dataset.
    df = df.drop_duplicates(subset="product_id", keep="first").copy()
    df["main_category"] = df["category"].fillna("Unknown").str.split("|").str[0]
    df["rating_num"] = pd.to_numeric(df["rating"], errors="coerce")
    df["rating_count_num"] = pd.to_numeric(
        df["rating_count"].astype("string").str.replace(",", "", regex=False), errors="coerce"
    )
    df["price_inr"] = pd.to_numeric(
        df["discounted_price"].astype("string").str.replace(r"[^\d.]", "", regex=True),
        errors="coerce",
    )
    return df


st.title("📦 Amazon Product Quality Dashboard — Team Name")
st.caption(
    "For an e-commerce category quality manager: identify which poorly rated, widely reviewed "
    "products should be investigated first."
)

if not DATA_FILE.exists():
    st.error("Missing amazon.csv. Put it in the same GitHub folder as streamlit_app.py.")
    st.stop()

data = load_data(str(DATA_FILE))

# Only a business-relevant selector: the category manager's area of responsibility.
categories = sorted(data["main_category"].dropna().unique().tolist())
selected_category = st.selectbox("Product category", ["All categories"] + categories)
view = data if selected_category == "All categories" else data.loc[
    data["main_category"] == selected_category
]
valid = view.dropna(subset=["rating_num"]).copy()
flagged = valid.loc[valid["rating_num"] < LOW_RATING_THRESHOLD].copy()
flagged["review_exposure"] = flagged["rating_count_num"].fillna(0)

# Three numbers answer: how much needs attention, how widespread, how strong is customer feedback?
a, b, c = st.columns(3)
a.metric("Products to investigate (rating < 3.8)", f"{len(flagged):,}")
b.metric("Share of rated products flagged", f"{len(flagged) / len(valid):.1%}" if len(valid) else "N/A")
c.metric("Ratings recorded for flagged products", f"{flagged['rating_count_num'].sum():,.0f}")

st.markdown("#### Where is the quality risk concentrated?")
cat_stats = valid.assign(flagged=valid["rating_num"] < LOW_RATING_THRESHOLD).groupby(
    "main_category", as_index=False
).agg(products=("product_id", "count"), flagged=("flagged", "sum"))
cat_stats["flagged_pct"] = 100 * cat_stats["flagged"] / cat_stats["products"]
cat_stats = cat_stats[cat_stats["products"] >= 10].sort_values("flagged_pct", ascending=False)
if len(cat_stats):
    st.bar_chart(cat_stats.set_index("main_category")["flagged_pct"], x_label="Category", y_label="Flagged products (%)")
else:
    st.info("Not enough products in this selection to compare category risk reliably (minimum: 10).")
st.caption("Categories with fewer than 10 rated products are excluded from this comparison to avoid unstable percentages.")

st.markdown("#### Which flagged products should be reviewed first?")
priority = flagged.sort_values("review_exposure", ascending=False).head(10).copy()
if len(priority):
    priority["label"] = priority["product_name"].str.slice(0, 48) + "… [" + priority["product_id"] + "]"
    st.bar_chart(priority.set_index("label")["review_exposure"], horizontal=True,
                 x_label="Number of recorded ratings", y_label="Flagged products")
    with st.expander("View product details for follow-up"):
        st.dataframe(
            priority[["product_name", "main_category", "rating_num", "rating_count_num", "price_inr", "product_link"]]
            .rename(columns={"product_name": "Product", "main_category": "Category", "rating_num": "Rating",
                             "rating_count_num": "Rating count", "price_inr": "Discounted price (₹)",
                             "product_link": "Product URL"}),
            hide_index=True, use_container_width=True,
            column_config={"Product URL": st.column_config.LinkColumn("Product URL")},
        )
else:
    st.success("No products with ratings below 3.8 in this selection.")

st.divider()
st.caption(
    "Data: undated historical Kaggle Amazon product snapshot (not live). "
    "Proposed production refresh: nightly; manager reviews weekly. "
    "Action rule (provisional): investigate products rated below 3.8, starting with the most-rated."
)
st.caption(
    "Interpretation: rating_count is a count of customer ratings, NOT sales or unique purchasers. "
    "This file has no timestamps, so trends and actual data freshness cannot be established. "
    "Products are deduplicated by product_id; invalid ratings are excluded. "
    "The 3.8 threshold is an illustrative operational rule, not an empirically validated cutoff."
)
