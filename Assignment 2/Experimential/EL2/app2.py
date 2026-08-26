import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


st.set_page_config(
    page_title="Student Grades Explorer",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Student Grades Explorer")

df = pd.read_csv("grades.csv")

st.header("Dataset Preview")

st.dataframe(df.head())

subjects = df["Subject"].unique()

selected_subject = st.selectbox(
    "Select Subject",
    subjects
)

subject_data = df[df["Subject"] == selected_subject]

mean_marks = subject_data["Final"].mean()
median_marks = subject_data["Final"].median()
std_marks = subject_data["Final"].std()

st.header("Summary Statistics")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Mean", f"{mean_marks:.2f}")

with col2:
    st.metric("Median", f"{median_marks:.2f}")

with col3:
    st.metric("Std Deviation", f"{std_marks:.2f}")
    
    

st.header("Box Plot of Final Marks")

fig, ax = plt.subplots(figsize=(5,5))

ax.boxplot(subject_data["Final"])

ax.set_ylabel("Marks")

st.pyplot(fig)

st.header("Test1 vs Final Marks")

fig, ax = plt.subplots(figsize=(6,5))

ax.scatter(
    subject_data["Test1"],
    subject_data["Final"]
)

ax.set_xlabel("Test1 Marks")
ax.set_ylabel("Final Marks")
ax.set_title("Test1 vs Final")

st.pyplot(fig)

st.markdown("---")
st.write("Advanced Data Science Lab - Assignment 02")