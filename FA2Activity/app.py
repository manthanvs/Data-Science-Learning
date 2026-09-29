"""Breast Cancer Diagnosis Assistant - Streamlit app for the FA2 case study.

Loads the four tuned models saved by the notebook (models/*.joblib), lets the user enter the
30 tumour measurements, and shows what every model predicts, how confident it is, and the
consensus of all four.

Run locally:  streamlit run app.py
Educational project - NOT a medical device.
"""
from pathlib import Path
import json

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.datasets import load_breast_cancer
from sklearn.metrics import (
    ConfusionMatrixDisplay, accuracy_score, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------------------------
MODEL_DIR = Path(__file__).parent / "models"
MODEL_FILES = {                       # display name -> file saved by the notebook
    "Logistic Regression": "logistic_regression.joblib",
    "Decision Tree": "decision_tree.joblib",
    "Random Forest": "random_forest.joblib",
    "SVM": "svm.joblib",
}
MALIGNANT, BENIGN = 0, 1              # scikit-learn's encoding of the target
LABELS = {MALIGNANT: "Malignant", BENIGN: "Benign"}
ICONS = {MALIGNANT: "🔴", BENIGN: "🟢"}
RANDOM_STATE = 42                     # must match the notebook so the test split is identical

MEASUREMENTS = {                      # tooltips for the sliders
    "radius": "Mean distance from the nucleus centre to points on its perimeter.",
    "texture": "Standard deviation of grey-scale values inside the nucleus.",
    "perimeter": "Length of the nucleus boundary.",
    "area": "Area of the nucleus.",
    "smoothness": "Local variation in radius lengths.",
    "compactness": "perimeter² / area − 1.0 (how tightly packed the shape is).",
    "concavity": "Severity of concave portions of the contour.",
    "concave points": "Number of concave portions of the contour.",
    "symmetry": "Symmetry of the nucleus shape.",
    "fractal dimension": "'Coastline approximation' − 1 (roughness of the contour).",
}
GROUP_HELP = {
    "mean": "Average over all nuclei in the image.",
    "error": "Standard error of the measurement across nuclei.",
    "worst": "Mean of the three largest values ('worst' case).",
}

st.set_page_config(page_title="Breast Cancer Diagnosis Assistant", page_icon="🩺", layout="wide")


# ---------------------------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    """Dataset plus the same stratified 80/20 test split that the notebook used."""
    data = load_breast_cancer(as_frame=True)
    X, y = data.data, data.target
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_STATE, stratify=y
    )
    return X, y, X_test, y_test


@st.cache_resource(show_spinner="Loading trained models…")
def load_models():
    models = {name: joblib.load(MODEL_DIR / f) for name, f in MODEL_FILES.items()}
    features = joblib.load(MODEL_DIR / "feature_names.joblib")
    return models, features


@st.cache_data(show_spinner="Evaluating the models on the held-out test set…")
def test_set_results():
    """Metrics and confusion matrices of the saved models on the 114 unseen test records."""
    models, features = load_models()
    _, _, X_test, y_test = load_data()
    rows, matrices = {}, {}
    for name, model in models.items():
        pred = model.predict(X_test[features])
        p_mal = model.predict_proba(X_test[features])[:, MALIGNANT]
        matrices[name] = confusion_matrix(y_test, pred, labels=[MALIGNANT, BENIGN])
        rows[name] = {
            "Accuracy": accuracy_score(y_test, pred),
            "Precision": precision_score(y_test, pred, pos_label=MALIGNANT),
            "Recall": recall_score(y_test, pred, pos_label=MALIGNANT),
            "F1-Score": f1_score(y_test, pred, pos_label=MALIGNANT),
            "ROC-AUC": roc_auc_score(y_test == MALIGNANT, p_mal),
            "Missed malignant": int(matrices[name][0, 1]),
            "False alarms": int(matrices[name][1, 0]),
        }
    return pd.DataFrame(rows).T.astype({"Missed malignant": int, "False alarms": int}), matrices


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------
def key(feature):
    return f"input::{feature}"


def pretty(feature):
    return feature[0].upper() + feature[1:]


def group_of(feature):
    return "worst" if feature.startswith("worst ") else "error" if feature.endswith(" error") else "mean"


def base_of(feature):
    return feature.removeprefix("mean ").removeprefix("worst ").removesuffix(" error")


def fill_inputs(values, record=None):
    """Button callback: write feature values into the slider state (runs before the rerun)."""
    for f, v in values.items():
        st.session_state[key(f)] = float(v)
    st.session_state["record"] = record


def random_record(X_test):
    idx = int(np.random.default_rng().choice(X_test.index))
    fill_inputs(X_test.loc[idx], record=idx)


def predict_all(models, row):
    """Label and P(malignant) from every model for one row of inputs."""
    return {
        name: {"label": int(m.predict(row)[0]), "p_malignant": float(m.predict_proba(row)[0, MALIGNANT])}
        for name, m in models.items()
    }


# ---------------------------------------------------------------------------------------------
# Load everything (friendly error instead of a stack trace if a file is missing)
# ---------------------------------------------------------------------------------------------
try:
    models, features = load_models()
    X, y, X_test, y_test = load_data()
except Exception as exc:  # noqa: BLE001 - show any loading problem to the user
    st.error(f"Could not load the trained models from `{MODEL_DIR}`. Run the notebook first to create them.\n\n`{exc}`")
    st.stop()

median_all = X.median()
median_by_class = X.groupby(y).median()
lo, hi = X.min() * 0.9, X.max() * 1.1                    # sliders extend slightly beyond the data range

for f in features:                                        # initial slider values = dataset median
    st.session_state.setdefault(key(f), float(median_all[f]))
st.session_state.setdefault("record", None)

# ---------------------------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚡ Quick examples")
    st.caption("Fill all 30 sliders in one click, then press **Predict**.")
    st.button("🟢 Typical benign case", width="stretch",
              on_click=fill_inputs, args=(median_by_class.loc[BENIGN],))
    st.button("🔴 Typical malignant case", width="stretch",
              on_click=fill_inputs, args=(median_by_class.loc[MALIGNANT],))
    st.button("🎲 Random real test record", width="stretch",
              on_click=random_record, args=(X_test,),
              help="A record the models never saw during training; the dataset's recorded diagnosis is revealed after prediction.")
    st.button("↺ Reset to dataset average", width="stretch",
              on_click=fill_inputs, args=(median_all,))
    st.divider()
    st.header("ℹ️ About")
    st.markdown(
        "Four classifiers trained on the **Breast Cancer Wisconsin (Diagnostic)** dataset "
        "(569 tumours, 30 measurements) and tuned with `GridSearchCV`:\n"
        "- Logistic Regression\n- Decision Tree\n- Random Forest\n- Support Vector Machine"
    )
    st.warning("Educational project. **Not a medical device** – never use it to make health decisions.", icon="⚠️")

# ---------------------------------------------------------------------------------------------
# Header + tabs
# ---------------------------------------------------------------------------------------------
st.title("🩺 Breast Cancer Diagnosis Assistant")
st.markdown(
    "Enter the measurements of a cell-nucleus sample and **four machine-learning models** will each "
    "predict whether the tumour is **benign** or **malignant**."
)

tab_predict, tab_compare, tab_data = st.tabs(["🔬 Predict", "📊 Model comparison", "🗂️ Dataset & features"])

# ------------------------------- Tab 1: prediction -------------------------------------------
with tab_predict:
    st.markdown("##### 1 · Enter the measurements")
    st.caption("Start from a quick example in the sidebar, or move the sliders. Hover the ⓘ icons for a description.")

    with st.form("input_form"):
        group_tabs = st.tabs(["📏 Mean values", "📐 Standard errors", "🔺 Worst values"])
        for tab, group in zip(group_tabs, ["mean", "error", "worst"]):
            with tab:
                cols = st.columns(2)
                for i, f in enumerate([f for f in features if group_of(f) == group]):
                    lo_f, hi_f = float(lo[f]), float(hi[f])
                    with cols[i % 2]:
                        st.slider(
                            pretty(f), min_value=lo_f, max_value=hi_f, step=(hi_f - lo_f) / 200, key=key(f),
                            format="%.4f" if hi_f < 1 else "%.2f" if hi_f < 100 else "%.1f",
                            help=f"{MEASUREMENTS[base_of(f)]} {GROUP_HELP[group]}",
                        )
        submitted = st.form_submit_button("🔍 Predict", type="primary", width="stretch")

    if submitted:
        row = pd.DataFrame([{f: st.session_state[key(f)] for f in features}])[features]
        results = predict_all(models, row)

        malignant_votes = sum(r["label"] == MALIGNANT for r in results.values())
        avg_p = np.mean([r["p_malignant"] for r in results.values()])
        if malignant_votes * 2 == len(results):           # 2-2 tie -> use the average probability
            consensus = MALIGNANT if avg_p >= 0.5 else BENIGN
        else:
            consensus = MALIGNANT if malignant_votes * 2 > len(results) else BENIGN
        agree = malignant_votes if consensus == MALIGNANT else len(results) - malignant_votes

        st.markdown("##### 2 · Result")
        banner = f"### {ICONS[consensus]} Consensus: **{LABELS[consensus]}** — {agree} of {len(results)} models agree"
        (st.error if consensus == MALIGNANT else st.success)(banner)

        for col, (name, r) in zip(st.columns(len(results)), results.items()):
            with col.container(border=True):
                st.markdown(f"**{name}**")
                st.markdown(f"### {ICONS[r['label']]} {LABELS[r['label']]}")
                st.progress(r["p_malignant"], text=f"Malignant probability: {r['p_malignant']:.1%}")

        if malignant_votes not in (0, len(results)):
            st.info("The models disagree on this input – it lies close to the boundary between the two classes.")

        record = st.session_state["record"]
        if record is not None and np.allclose(row.iloc[0].values, X_test.loc[record, features].values):
            st.info(f"This input is real test record **#{record}**. Its recorded diagnosis in the dataset is "
                    f"**{LABELS[int(y_test.loc[record])]}**.", icon="📋")

        with st.expander("How does this input compare with typical cases?"):
            rf = models["Random Forest"].named_steps["model"]
            top = pd.Series(rf.feature_importances_, index=features).nlargest(6).index
            st.dataframe(pd.DataFrame({
                "Your input": row.loc[0, top],
                "Typical benign (median)": median_by_class.loc[BENIGN, top],
                "Typical malignant (median)": median_by_class.loc[MALIGNANT, top],
            }).round(3), width="stretch")
            st.caption("The six features the Random Forest relies on most.")
        st.caption("⚠️ Educational demo – predictions are not a diagnosis.")

# ------------------------------- Tab 2: model comparison -------------------------------------
with tab_compare:
    metrics, matrices = test_set_results()
    st.markdown("##### Performance on the 114 held-out test records (malignant = positive class)")
    float_cols = ["Accuracy", "Precision", "Recall", "F1-Score", "ROC-AUC"]
    st.dataframe(
        metrics.style.format("{:.3f}", subset=float_cols).highlight_max(subset=float_cols, color="#b7e4c7"),
        width="stretch",
    )
    st.caption("Green = best value per metric. **Recall** = share of malignant tumours caught; "
               "**Missed malignant** = malignant tumours predicted benign (the costly error).")

    left, right = st.columns([3, 2])
    with left:
        st.markdown("##### Metric comparison")
        fig, ax = plt.subplots(figsize=(6.5, 5))
        metrics[["Precision", "Recall", "F1-Score", "ROC-AUC"]].plot.bar(ax=ax, rot=15, width=0.8)
        ax.set(ylim=(0.75, 1.02), ylabel="Score (y-axis starts at 0.75)")
        ax.legend(loc="lower right", ncol=2, fontsize=8)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    with right:
        st.markdown("##### Confusion matrices")
        fig, axes = plt.subplots(2, 2, figsize=(5.5, 5))
        for ax, (name, cm) in zip(axes.ravel(), matrices.items()):
            ConfusionMatrixDisplay(cm, display_labels=["Malig.", "Benign"]).plot(
                ax=ax, cmap="Blues", colorbar=False)
            ax.set_title(name, fontsize=9)
            ax.tick_params(labelsize=8)
            ax.grid(False)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    summary_file = MODEL_DIR / "summary.json"
    if summary_file.exists():
        st.markdown("##### GridSearchCV tuning results (5-fold CV on the training data)")
        tuning = pd.DataFrame(json.loads(summary_file.read_text())["tuning"])
        st.dataframe(tuning[["Model", "Best parameters", "Baseline CV F1", "Tuned CV F1"]],
                     hide_index=True, width="stretch")

# ------------------------------- Tab 3: dataset ----------------------------------------------
with tab_data:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Samples", len(X))
    c2.metric("Features", X.shape[1])
    c3.metric("Benign", int((y == BENIGN).sum()))
    c4.metric("Malignant", int((y == MALIGNANT).sum()))

    left, right = st.columns(2)
    with left:
        st.markdown("##### Most influential features (Random Forest)")
        rf = models["Random Forest"].named_steps["model"]
        st.bar_chart(pd.Series(rf.feature_importances_, index=features).nlargest(10).sort_values(),
                     horizontal=True)
    with right:
        st.markdown("##### Median value by diagnosis")
        show = ["mean radius", "mean area", "mean concave points", "worst perimeter", "mean texture"]
        st.dataframe(median_by_class[show].rename(index=LABELS).T.round(3), width="stretch")
        st.caption("Malignant tumours are larger and have more concave contour points than benign ones.")

    with st.expander("Preview the raw data"):
        st.dataframe(X.assign(diagnosis=y.map(LABELS)).head(15), width="stretch")
    st.caption("Source: UCI Machine Learning Repository – Breast Cancer Wisconsin (Diagnostic), "
               "Wolberg, Street & Mangasarian (1995).")
