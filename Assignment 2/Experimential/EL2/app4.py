import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="Titanic Survival Dashboard",
    page_icon="🚢",
    layout="wide"
)

st.title("🚢 Titanic Survival Analysis Dashboard")

df = pd.read_csv("titanic.csv")

df = df.dropna()

df["SurvivalStatus"] = df["Survived"].replace({
    0: "Not Survived",
    1: "Survived"
})

df["PassengerClass"] = df["Pclass"].replace({
    1: "First Class",
    2: "Second Class",
    3: "Third Class"
})

st.header("Dataset Preview")

st.dataframe(df.head())

st.header("Survival Percentage by Gender")

gender_survival = (
    df.groupby("Sex")["Survived"]
      .mean()
      * 100
)

st.dataframe(gender_survival.round(2))

st.header("Survival Percentage by Passenger Class")

class_survival = (
    df.groupby("PassengerClass")["Survived"]
      .mean()
      * 100
)

st.dataframe(class_survival.round(2))

st.header("Average Age")

average_age = (
    df.groupby("SurvivalStatus")["Age"]
      .mean()
)

st.dataframe(average_age.round(2))

st.header("Age Distribution by Survival Status")

fig, ax = plt.subplots(figsize=(6,5))

df.boxplot(
    column="Age",
    by="SurvivalStatus",
    ax=ax
)

plt.suptitle("")

ax.set_xlabel("Survival Status")
ax.set_ylabel("Age")

st.pyplot(fig)

st.markdown("---")
st.write("Advanced Data Science Lab - Assignment 02")