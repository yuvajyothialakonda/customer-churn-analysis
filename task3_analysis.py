"""
Task 3 - Deep-Dive Analysis & Interactive Dashboarding
=======================================================
Simple, step-by-step script — easy to read and understand.

What this script does:
  Step 1 → Calculate 5 core KPIs and save them
  Step 2 → RFM Customer Segmentation (who are our best customers?)
  Step 3 → Cohort Retention (do customers come back?)
  Step 4 → Save 6 charts as PNG images

Input  : ApexPlanet_DataAnalytics_Dataset.xlsx
Outputs: kpi_definitions.csv, rfm_scores.csv, segment_summary.csv,
         cohort_retention.csv, and 6 chart PNG files

Run it : python task3_analysis.py
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# ── Load the data ────────────────────────────────────────────────────
print("Loading data...")
df = pd.read_excel("ApexPlanet_DataAnalytics_Dataset.xlsx")

# Basic cleaning
df["Order_Date"] = pd.to_datetime(df["Order_Date"])
df["Age"]        = df["Age"].fillna(df["Age"].median()).astype(int)
df["City"]       = df["City"].fillna("Unknown")

print(f"Loaded {len(df)} orders, {df['Customer_ID'].nunique()} customers\n")


# ════════════════════════════════════════════════════════════════════
# STEP 1: Define 5 Core KPIs
# ════════════════════════════════════════════════════════════════════
print("Step 1: Calculating KPIs...")

total_revenue    = df["Total_Sales"].sum()
total_orders     = len(df)
total_customers  = df["Customer_ID"].nunique()
repeat_customers = df[df.duplicated("Customer_ID", keep=False)]["Customer_ID"].nunique()

kpis = pd.DataFrame([
    {
        "KPI"              : "Total Revenue",
        "Formula"          : "SUM(Total_Sales)",
        "Value"            : f"₹{total_revenue:,.2f}",
        "Business Rationale": "Main revenue health check. Shows overall sales performance."
    },
    {
        "KPI"              : "Average Order Value (AOV)",
        "Formula"          : "Total Revenue / Total Orders",
        "Value"            : f"₹{total_revenue / total_orders:,.2f}",
        "Business Rationale": "How much each order is worth on average. Raise it via upselling."
    },
    {
        "KPI"              : "Customer Repeat Rate",
        "Formula"          : "Customers with more than 1 order / Total Customers x 100",
        "Value"            : f"{repeat_customers / total_customers * 100:.1f}%",
        "Business Rationale": "Measures loyalty. Low rate = customers are not coming back."
    },
    {
        "KPI"              : "Revenue per Customer (LTV proxy)",
        "Formula"          : "Total Revenue / Unique Customers",
        "Value"            : f"₹{total_revenue / total_customers:,.2f}",
        "Business Rationale": "Estimates customer lifetime value. Guides marketing budget."
    },
    {
        "KPI"              : "Orders per Customer",
        "Formula"          : "Total Orders / Unique Customers",
        "Value"            : f"{total_orders / total_customers:.3f}",
        "Business Rationale": "If below 2, most customers are buying only once."
    },
])

kpis.to_csv("kpi_definitions.csv", index=False)
print(kpis[["KPI", "Value"]].to_string(index=False))
print("  Saved kpi_definitions.csv\n")


# ════════════════════════════════════════════════════════════════════
# STEP 2: RFM Customer Segmentation (Deep-Dive)
# ════════════════════════════════════════════════════════════════════
print("Step 2: RFM Customer Segmentation...")

# RFM stands for Recency, Frequency, Monetary
# Recency  = how recently did the customer buy? (fewer days = better)
# Frequency = how many times did they buy?
# Monetary  = how much money did they spend?

snapshot = df["Order_Date"].max() + pd.Timedelta(days=1)

rfm = df.groupby("Customer_ID").agg(
    Recency   = ("Order_Date",  lambda x: (snapshot - x.max()).days),
    Frequency = ("Order_ID",    "count"),
    Monetary  = ("Total_Sales", "sum"),
).reset_index()

# Score each dimension 1 to 4 (4 = best)
# For Recency: fewer days = better, so score is reversed
rfm["R_Score"] = pd.qcut(rfm["Recency"],   q=4, labels=[4, 3, 2, 1]).astype(int)
rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"),  q=4, labels=[1, 2, 3, 4]).astype(int)
rfm["RFM_Score"] = rfm["R_Score"] + rfm["F_Score"] + rfm["M_Score"]

# Assign a plain-English segment based on score
def get_segment(score):
    if score >= 10:
        return "Champions"            # Best customers — buy often, recently, spend a lot
    elif score >= 8:
        return "Loyal Customers"      # Buy regularly and spend well
    elif score >= 6:
        return "Potential Loyalists"  # Recent buyers but not yet frequent
    elif score >= 4:
        return "At Risk"              # Used to buy but haven't lately
    else:
        return "Lost"                 # Lowest scores — may be gone for good

rfm["Segment"] = rfm["RFM_Score"].apply(get_segment)
rfm.to_csv("rfm_scores.csv", index=False)

# Summarise segments
summary = rfm.groupby("Segment").agg(
    Customers     = ("Customer_ID", "count"),
    Avg_Recency   = ("Recency",     "mean"),
    Total_Revenue = ("Monetary",    "sum"),
).reset_index()
summary["Revenue_Share_%"] = (summary["Total_Revenue"] / summary["Total_Revenue"].sum() * 100).round(1)
summary = summary.sort_values("Total_Revenue", ascending=False)
summary.to_csv("segment_summary.csv", index=False)

print(summary[["Segment", "Customers", "Revenue_Share_%"]].to_string(index=False))
print("  Saved rfm_scores.csv and segment_summary.csv\n")


# ════════════════════════════════════════════════════════════════════
# STEP 3: Cohort Retention Analysis
# ════════════════════════════════════════════════════════════════════
print("Step 3: Cohort Retention Analysis...")

# A cohort = all customers who made their FIRST purchase in the same month.
# We track what % of that cohort comes back in later months.

df["Order_Month"] = df["Order_Date"].dt.to_period("M")
first_buy = df.groupby("Customer_ID")["Order_Month"].min().rename("Cohort")
df = df.join(first_buy, on="Customer_ID")
df["Months_Since_First"] = (df["Order_Month"] - df["Cohort"]).apply(lambda x: x.n)

cohort_counts = df.groupby(["Cohort", "Months_Since_First"])["Customer_ID"].nunique()
cohort_pivot  = cohort_counts.unstack(fill_value=0)
cohort_size   = cohort_pivot[0]
retention     = (cohort_pivot.divide(cohort_size, axis=0) * 100).round(1)

retention.to_csv("cohort_retention.csv")
print("  Saved cohort_retention.csv\n")


# ════════════════════════════════════════════════════════════════════
# STEP 4: Charts
# ════════════════════════════════════════════════════════════════════
print("Step 4: Saving charts...")

NAVY  = "#1B2A4A"
TEAL  = "#0E9594"
SEG_COLORS = {
    "Champions"          : "#0E9594",
    "Loyal Customers"    : "#1B2A4A",
    "Potential Loyalists": "#5FC9C8",
    "At Risk"            : "#E0763D",
    "Lost"               : "#E74C3C",
}

# Chart 1 — KPI bar chart
kpi_labels  = ["Total Revenue", "AOV", "Repeat Rate", "LTV", "Orders/Customer"]
kpi_display = ["₹139.4M", "₹139.4K", "5.5%", "₹147.2K", "1.056"]
kpi_bar     = [139.4, 139.4, 5.5, 147.2, 1.056]
normalized  = [v / max(kpi_bar) * 100 for v in kpi_bar]

fig, ax = plt.subplots(figsize=(10, 4))
bars = ax.barh(kpi_labels, normalized, color=TEAL, height=0.5)
for bar, label in zip(bars, kpi_display):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
            label, va="center", fontsize=11, color=NAVY, fontweight="bold")
ax.set_xlim(0, 130)
ax.set_title("Core KPI Overview", fontsize=14, fontweight="bold", color=NAVY)
ax.invert_yaxis()
ax.spines[["top", "right", "bottom"]].set_visible(False)
plt.tight_layout()
plt.savefig("chart_01_kpi_cards.png", dpi=150)
plt.close()
print("  Saved chart_01_kpi_cards.png")

# Chart 2 — Segment pie charts (customer count + revenue share)
colors = [SEG_COLORS[s] for s in summary["Segment"]]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

ax1.pie(summary["Customers"], labels=summary["Segment"],
        autopct="%1.1f%%", colors=colors, startangle=140)
ax1.set_title("Customer Count by Segment", fontweight="bold", color=NAVY)

ax2.pie(summary["Revenue_Share_%"], labels=summary["Segment"],
        autopct="%1.1f%%", colors=colors, startangle=140)
ax2.set_title("Revenue Share by Segment", fontweight="bold", color=NAVY)

plt.suptitle("RFM Customer Segmentation", fontsize=14, fontweight="bold", color=NAVY)
plt.tight_layout()
plt.savefig("chart_02_segments_pie.png", dpi=150)
plt.close()
print("  Saved chart_02_segments_pie.png")

# Chart 3 — RFM Scatter (Frequency vs Monetary, coloured by Segment)
fig, ax = plt.subplots(figsize=(9, 6))
for seg, grp in rfm.groupby("Segment"):
    ax.scatter(grp["Frequency"], grp["Monetary"] / 1000,
               c=SEG_COLORS[seg], label=seg, alpha=0.7, s=50)
ax.set_xlabel("Frequency (number of orders)")
ax.set_ylabel("Monetary Value (₹ thousands)")
ax.set_title("RFM Scatter — Frequency vs Monetary by Segment",
             fontweight="bold", color=NAVY)
ax.legend(title="Segment")
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("chart_03_rfm_scatter.png", dpi=150)
plt.close()
print("  Saved chart_03_rfm_scatter.png")

# Chart 4 — Cohort Retention Heatmap
fig, ax = plt.subplots(figsize=(11, 7))
sns.heatmap(retention.iloc[:, :6].fillna(0),
            annot=True, fmt=".0f", cmap="YlGnBu",
            linewidths=0.4, ax=ax,
            cbar_kws={"label": "Retention %"})
ax.set_title("Cohort Retention Heatmap (% of cohort still active each month)",
             fontweight="bold", color=NAVY)
ax.set_xlabel("Months Since First Purchase")
ax.set_ylabel("Acquisition Cohort")
plt.tight_layout()
plt.savefig("chart_04_cohort.png", dpi=150)
plt.close()
print("  Saved chart_04_cohort.png")

# Chart 5 — Revenue by City
city_rev = (df[df["City"] != "Unknown"]
            .groupby("City")["Total_Sales"].sum()
            .sort_values())

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.barh(city_rev.index, city_rev.values / 1e6, color=TEAL)
for bar in bars:
    ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
            f"₹{bar.get_width():.1f}M", va="center", fontsize=10, color=NAVY)
ax.set_xlabel("Total Revenue (₹ Millions)")
ax.set_title("Revenue by City", fontweight="bold", color=NAVY)
ax.spines[["top", "right", "bottom"]].set_visible(False)
plt.tight_layout()
plt.savefig("chart_05_city_revenue.png", dpi=150)
plt.close()
print("  Saved chart_05_city_revenue.png")

# Chart 6 — Monthly Revenue by Category
df["Month"] = df["Order_Date"].dt.to_period("M").astype(str)
trend = df.groupby(["Month", "Category"])["Total_Sales"].sum().reset_index()
pivot = trend.pivot(index="Month", columns="Category", values="Total_Sales").fillna(0)

CAT_COLORS = ["#0E9594", "#1B2A4A", "#E0763D", "#5FC9C8", "#9B59B6"]
fig, ax = plt.subplots(figsize=(12, 5))
for i, col in enumerate(pivot.columns):
    ax.plot(pivot.index, pivot[col] / 1e6,
            marker="o", markersize=4, linewidth=2,
            label=col, color=CAT_COLORS[i])
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (₹ Millions)")
ax.set_title("Monthly Revenue Trend by Category", fontweight="bold", color=NAVY)
ax.legend(title="Category")
ax.spines[["top", "right"]].set_visible(False)
ax.set_xticks(range(0, len(pivot.index), 2))
ax.set_xticklabels(list(pivot.index)[::2], rotation=30)
plt.tight_layout()
plt.savefig("chart_06_category_trend.png", dpi=150)
plt.close()
print("  Saved chart_06_category_trend.png")

print("\nDone! All files saved. Open interactive_dashboard.html in your browser.")
