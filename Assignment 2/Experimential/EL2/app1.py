import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="Retail Sales Dashboard",
    page_icon="🛍️",
    layout="wide" )
st.title("🛍️ Retail Sales Dashboard")
st.write("Analyze daily retail sales data and visualize product performance.")


df = pd.read_csv("sales.csv")
df["Date"] = pd.to_datetime(df["Date"])


st.header("Dataset Preview")
st.dataframe(df.head())


st.header("Summary Statistics")
mean_revenue = df["Revenue"].mean()
median_revenue = df["Revenue"].median()
col1, col2 = st.columns(2)
with col1:
    st.metric("Mean Revenue", f"{mean_revenue:.2f}")
with col2:
    st.metric("Median Revenue", f"{median_revenue:.2f}")


st.header("Revenue and Units Sold by Category")
category_summary = ( df.groupby("ProductCategory")[["UnitsSold", "Revenue"]].sum().reset_index() )
st.dataframe(category_summary)

st.header("Daily Revenue Trend")
daily_revenue = ( df.groupby("Date")["Revenue"].sum().reset_index())
fig, ax = plt.subplots(figsize=(10,5))
ax.plot( daily_revenue["Date"], daily_revenue["Revenue"], marker="o" )
ax.set_title("Daily Revenue Trend")
ax.set_xlabel("Date")
ax.set_ylabel("Revenue")
plt.xticks(rotation=45)
st.pyplot(fig)


st.header("Revenue by Product Category")
fig, ax = plt.subplots(figsize=(8,5))

ax.bar( category_summary["ProductCategory"], category_summary["Revenue"] )
ax.set_xlabel("Product Category")
ax.set_ylabel("Revenue")
ax.set_title("Revenue by Product Category")
st.pyplot(fig)

st.markdown("---")
st.write("Advanced Data Science Lab - Assignment 02")