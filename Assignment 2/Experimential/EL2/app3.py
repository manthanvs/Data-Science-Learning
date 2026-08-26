import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


# Page Configuration
st.set_page_config(page_title="Movie Ratings Explorer", page_icon="🎬", layout="wide" )
st.title("🎬 Movie Ratings Explorer")


# Load Dataset
df = pd.read_csv("movies.csv")
# Remove Missing Values
df = df.dropna()
# Genre Selection
genre = st.selectbox( "Select Movie Genre", sorted(df["Genre"].unique()) )


# Filter Data
filtered_df = df[df["Genre"] == genre]
# Display Movies
st.subheader("Movies")
st.dataframe(filtered_df)


# Statistics
st.subheader("Summary Statistics")
col1, col2, col3 = st.columns(3)
col1.metric( "Average Rating", f"{filtered_df['Rating'].mean():.2f}" )
col2.metric( "Average Votes",f"{filtered_df['Votes'].mean():.0f}" )
col3.metric( "Median Release Year", int(filtered_df["Year"].median()))


# Boxplot
st.subheader("Ratings Distribution")
fig, ax = plt.subplots(figsize=(6,4))
ax.boxplot(filtered_df["Rating"])
ax.set_ylabel("Rating")
st.pyplot(fig)


# Scatter Plot
st.subheader("Votes vs Rating")
fig, ax = plt.subplots(figsize=(8,5))
scatter = ax.scatter(
    filtered_df["Votes"],
    filtered_df["Rating"],
    s=filtered_df["Votes"] / 50,
    c=filtered_df["Rating"]
)
ax.set_xlabel("Votes")
ax.set_ylabel("Rating")
plt.colorbar(scatter)
st.pyplot(fig)