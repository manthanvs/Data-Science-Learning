"""Builds the FA2 PDF report (helper script - NOT one of the three files to submit).

Every table is filled from models/summary.json (written by the notebook) and every figure is drawn
from the dataset and the saved models, so the report always matches the notebook.

Usage:  python build_report.py --url https://your-app.streamlit.app --name "Your Name" --roll "Roll No"
"""
import argparse
import json
from io import BytesIO
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sklearn.datasets import load_breast_cancer
from sklearn.metrics import ConfusionMatrixDisplay, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

HERE = Path(__file__).parent
MODELS = {"Logistic Regression": "logistic_regression", "Decision Tree": "decision_tree",
          "Random Forest": "random_forest", "SVM": "svm"}
MALIGNANT = 0
RED, GREEN, NAVY = "#d1495b", "#2a9d8f", "#1d3557"

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="", help="live Streamlit app URL")
parser.add_argument("--name", default="", help="student name")
parser.add_argument("--roll", default="", help="roll number / PRN")
parser.add_argument("--out", default=str(HERE / "FA2_Report_Breast_Cancer.pdf"))
args = parser.parse_args()

# DejaVu Sans ships with matplotlib and, unlike the built-in PDF fonts, has  ≈ → γ × –
ttf = Path(font_manager.findfont("DejaVu Sans")).parent
for face, file in {"DV": "DejaVuSans.ttf", "DV-B": "DejaVuSans-Bold.ttf", "DV-I": "DejaVuSans-Oblique.ttf"}.items():
    pdfmetrics.registerFont(TTFont(face, str(ttf / file)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-B")

BODY = ParagraphStyle("body", fontName="DV", fontSize=8.8, leading=12.4, spaceAfter=3)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=11, bulletIndent=1, spaceAfter=1.5)
H1 = ParagraphStyle("h1", fontName="DV-B", fontSize=12, textColor=colors.HexColor(NAVY), spaceBefore=9, spaceAfter=4)
TITLE = ParagraphStyle("title", fontName="DV-B", fontSize=17, leading=21, alignment=TA_CENTER, textColor=colors.HexColor(NAVY))
SUB = ParagraphStyle("sub", parent=BODY, alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
CELL = ParagraphStyle("cell", fontName="DV", fontSize=7.4, leading=9.4)
CAPTION = ParagraphStyle("cap", parent=BODY, fontName="DV-I", fontSize=7.6, textColor=colors.HexColor("#555555"), alignment=TA_CENTER)

# ---------------------------------------------------------------------------------------------
# Data, saved models, notebook results
# ---------------------------------------------------------------------------------------------
data = load_breast_cancer(as_frame=True)
X, y = data.data, data.target
_, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
models = {n: joblib.load(HERE / "models" / f"{f}.joblib") for n, f in MODELS.items()}
summary = json.loads((HERE / "models" / "summary.json").read_text())
tuning = pd.DataFrame(summary["tuning"]).set_index("Model")
test_tuned = pd.DataFrame(summary["test_tuned"]).set_index("Model")
test_base = pd.DataFrame(summary["test_baseline"]).set_index("Model")
best = test_tuned.sort_values(["F1-Score", "ROC-AUC"], ascending=False).index[0]


def fig_image(fig, width_cm):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    img.drawHeight, img.drawWidth = width_cm * cm * img.imageHeight / img.imageWidth, width_cm * cm
    return img


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


HEADER = ParagraphStyle("hdr", parent=CELL, textColor=colors.white, fontName="DV-B", fontSize=7.0)


def table(rows, widths, header_bg=NAVY, highlight_row=None):
    cells = [[Paragraph(str(c), HEADER if i == 0 else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(cells, colWidths=[w * cm for w in widths], repeatRows=1)
    style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f9")]),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if highlight_row:
        style.append(("BACKGROUND", (0, highlight_row), (-1, highlight_row), colors.HexColor("#d8f0e6")))
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})

# Figure 1 - EDA: class balance, correlation with malignancy, class-wise distribution
fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(11, 3.1))
counts = y.value_counts().sort_index()
a1.bar(["malignant", "benign"], counts.values, color=[RED, GREEN])
for i, n in enumerate(counts.values):
    a1.text(i, n + 5, f"{n} ({n / len(y):.0%})", ha="center", fontweight="bold")
a1.set(title="Class distribution", ylabel="samples", ylim=(0, counts.max() * 1.15))
corr = X.corrwith((y == MALIGNANT).astype(int)).sort_values().iloc[-8:]
a2.barh(corr.index, corr.values, color=RED)
a2.set(title="Top-8 correlations with malignancy", xlabel="Pearson r")
for cls, name, col in [(MALIGNANT, "malignant", RED), (1, "benign", GREEN)]:
    a3.hist(X.loc[y == cls, "mean concave points"], bins=25, alpha=0.6, color=col, label=name, density=True)
a3.set(title="Mean concave points by class", xlabel="mean concave points", ylabel="density")
a3.legend()
fig.tight_layout()
eda_img = fig_image(fig, 17.2)

# Figure 2 - ROC curves and baseline-vs-tuned F1
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.3))
for name, m in models.items():
    p_mal = m.predict_proba(X_test)[:, MALIGNANT]
    fpr, tpr, _ = roc_curve(y_test == MALIGNANT, p_mal)
    a1.plot(fpr, tpr, label=f"{name} (AUC = {roc_auc_score(y_test == MALIGNANT, p_mal):.3f})")
a1.plot([0, 1], [0, 1], "k--", alpha=0.35)
a1.set(title="ROC curves – tuned models (malignant = positive)", xlabel="False positive rate", ylabel="True positive rate")
a1.legend(loc="lower right", fontsize=7)
x = np.arange(len(models))
a2.bar(x - 0.2, test_base.loc[list(models), "F1-Score"], 0.4, color="#adb5bd", label="Baseline")
a2.bar(x + 0.2, test_tuned.loc[list(models), "F1-Score"], 0.4, color=NAVY, label="Tuned")
a2.set(xticks=x, xticklabels=[m.replace(" ", "\n") for m in models], ylim=(0.8, 1.0), title="Test F1 (malignant), y-axis from 0.8")
a2.legend(loc="lower right")
fig.tight_layout()
perf_img = fig_image(fig, 15.5)

# Figure 3 - confusion matrices of the tuned models
fig, axes = plt.subplots(1, 4, figsize=(11, 2.7))
for ax, (name, m) in zip(axes, models.items()):
    ConfusionMatrixDisplay.from_estimator(m, X_test, y_test, display_labels=["malig.", "benign"],
                                          cmap="Blues", colorbar=False, ax=ax)
    ax.set_title(name, fontsize=8.5)
    ax.grid(False)
fig.tight_layout()
cm_img = fig_image(fig, 17.2)

# ---------------------------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------------------------
S = []
S += [Paragraph("Breast Cancer Diagnosis using Machine Learning", TITLE),
      Paragraph("Formative Assessment-02 · Data Analysis Case Study &amp; Streamlit Deployment", SUB),
      Paragraph("Advanced Data Science [MCA33PE17] · MCA · SYMCA · Academic Year 2026–2027 · Semester I", SUB)]
if args.name or args.roll:
    S.append(Paragraph(f"<b>{args.name}</b>{' · ' + args.roll if args.roll else ''}", SUB))
S.append(Spacer(1, 4))
link = (f'<b>Live Streamlit app:</b> <a href="{args.url}" color="#1d7a8c"><u>{args.url}</u></a>' if args.url
        else "<b>Live Streamlit app:</b> <font color='#b00020'>[link to be added after deployment]</font>")
t = Table([[Paragraph(link, BODY)]], colWidths=[17.4 * cm])
t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1d7a8c")),
                       ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eaf5f7")), ("TOPPADDING", (0, 0), (-1, -1), 5)]))
S += [t]

S += [Paragraph("1. Problem and dataset", H1),
      Paragraph("<b>Goal:</b> predict whether a breast tumour is <b>malignant</b> or <b>benign</b> from measurements of a digitised "
                "fine-needle-aspirate image, and compare four classification algorithms. <b>Dataset:</b> <i>Breast Cancer Wisconsin "
                "(Diagnostic)</i> – UCI Machine Learning Repository (Wolberg, Street &amp; Mangasarian, 1995), 569 samples × 30 numeric "
                "features (10 nucleus measurements, each as mean, standard error and worst value); 357 benign (62.7 %) and "
                "212 malignant (37.3 %).", BODY),
      Paragraph("<b>Why this dataset:</b> a real, high-impact screening problem where the <i>type</i> of error matters; clean numeric data "
                "so the focus stays on modelling; moderate class imbalance that justifies precision/recall/F1 over accuracy; strongly "
                "correlated features that make scaling and regularisation meaningful; and small enough that all four models can be tuned "
                "and cross-validated fairly. Metrics are reported for the <b>malignant</b> class, because a missed cancer "
                "(false negative) is the costly error.", BODY)]

S += [Paragraph("2. Exploratory data analysis – key insights", H1), eda_img,
      Paragraph("Figure 1 – class balance, strongest correlations with malignancy, and class-wise distribution of one key feature.", CAPTION)]
S += bullets([
    "<b>Data quality is high:</b> no missing values, no duplicates, all 30 features numeric – nothing to impute or encode.",
    "<b>Size and shape drive malignancy:</b> median mean area 932 vs 458 (2.0×), mean concave points 0.086 vs 0.023 (3.7×); "
    "worst concave points, worst perimeter and mean concave points correlate ≈ 0.78–0.79 with malignancy. Five features "
    "(e.g. fractal dimension, texture error) carry almost no linear signal (|r| &lt; 0.1).",
    "<b>Strong multicollinearity:</b> 21 of 435 feature pairs have |r| &gt; 0.9 (radius ↔ perimeter ↔ area), so regularised or "
    "tree-based models are appropriate.",
    "<b>Outliers are genuine:</b> 608 IQR-flagged values (171 of 569 rows), mostly right-skewed “error” features; they are large "
    "tumours, so they were kept.",
    "<b>Different scales</b> (mean area up to 2501 vs smoothness ≈ 0.1) → scaling is required for Logistic Regression and SVM.",
])

S += [Paragraph("3. Preprocessing", H1)]
S += bullets([
    "<b>Missing values / encoding:</b> none present; a median <font face='DV-I'>SimpleImputer</font> is still the first pipeline step as a safeguard. "
    "No categorical features; the target is already label-encoded (0 = malignant, 1 = benign).",
    "<b>Scaling:</b> <font face='DV-I'>StandardScaler</font> for Logistic Regression and SVM only (trees are scale-invariant), placed <i>inside</i> a "
    "<font face='DV-I'>Pipeline</font> so it is fitted on training data only (no leakage).",
    "<b>Split:</b> stratified 80 % train (455) / 20 % test (114), random_state = 42; both sets keep ≈ 37 % malignant.",
])

rows = [["Model", "Best parameters (GridSearchCV)", "Combos", "Baseline CV F1", "Tuned CV F1"]]
for name, r in tuning.iterrows():
    rows.append([name, r["Best parameters"], r["Combinations"], f"{r['Baseline CV F1']:.4f}", f"{r['Tuned CV F1']:.4f}"])
S += [Paragraph("4. Models, cross-validation and tuning", H1),
      Paragraph("Four algorithms were implemented with scikit-learn: <b>Logistic Regression, Decision Tree, Random Forest and SVM (RBF)</b>. "
                "Each was first checked with <b>stratified 5-fold cross-validation</b> on the training data (mean ± std shows stability; "
                "the untuned Decision Tree scores 100 % on training folds but only ≈ 92 % in CV, i.e. it over-fits). "
                "<b>GridSearchCV</b> (same 5 folds, scoring = F1 of the malignant class) was then applied to <b>all four</b> models; "
                "the test set was never used to choose parameters.", BODY),
      KeepTogether([table(rows, [3.3, 6.5, 1.9, 2.8, 2.8]), Spacer(1, 2),
                    Paragraph("Table 1 – GridSearchCV results: tuning raised cross-validated F1 for every model, most for the Decision Tree.", CAPTION)])]

rows = [["Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "Missed malignant", "False alarms", "Baseline F1"]]
order = test_tuned.sort_values(["F1-Score", "ROC-AUC"], ascending=False).index
for name in order:
    r = test_tuned.loc[name]
    rows.append([name, f"{r['Accuracy']:.3f}", f"{r['Precision']:.3f}", f"{r['Recall']:.3f}", f"{r['F1-Score']:.3f}",
                 f"{r['ROC-AUC']:.3f}", int(r["Missed malignant (FN)"]), int(r["False alarms (FP)"]), f"{test_base.loc[name, 'F1-Score']:.3f}"])
S += [Paragraph("5. Results and model comparison (unseen test set, malignant = positive class)", H1),
      KeepTogether([table(rows, [2.9, 1.9, 1.9, 1.5, 1.2, 1.9, 2.1, 1.8, 2.0], highlight_row=1), Spacer(1, 2),
                    Paragraph("Table 2 – tuned models on the 114 test records (best model highlighted); last column shows the untuned baseline F1.", CAPTION)]),
      Spacer(1, 4), perf_img,
      Paragraph("Figure 2 – ROC curves of the tuned models and baseline-vs-tuned F1.", CAPTION), cm_img,
      Paragraph("Figure 3 – confusion matrices (rows = actual, columns = predicted).", CAPTION)]

S += [Paragraph("6. Insights and conclusions", H1)]
S += bullets([
    f"<b>Best model: {best}</b> – F1 {test_tuned.loc[best, 'F1-Score']:.3f}, ROC-AUC {test_tuned.loc[best, 'ROC-AUC']:.3f}, only "
    f"{int(test_tuned.loc[best, 'Missed malignant (FN)'])} of 42 malignant tumours missed. Logistic Regression is a very close second and is the more "
    "explainable choice.",
    "<b>Ranking SVM ≈ Logistic Regression &gt; Random Forest &gt; Decision Tree</b> is the same in cross-validation and on the test set. The classes are "
    "almost linearly separable in standardised space, which suits smooth boundaries better than axis-aligned tree splits.",
    "<b>Ensembling fixes over-fitting:</b> Random Forest beats a single Decision Tree by ≈ 5 F1 points.",
    "<b>Tuning gains are real in cross-validation but small on the test set:</b> with only 114 test records (42 malignant) one prediction moves "
    "recall by 2.4 points, so models were selected on cross-validation and the test set was used only for reporting.",
    "<b>What drives predictions:</b> six of the top-10 features are shared by Random Forest importances and Logistic Regression coefficients – all "
    "size / concavity measures (worst radius / perimeter / area, concave points), matching the EDA. They differ on texture: Logistic Regression "
    "ranks <i>worst texture</i> first (weakly correlated with size, r ≈ 0.35, so it adds complementary evidence), Random Forest ranks it 12th.",
    "<b>Limitations:</b> single dataset, small test set, no external validation. This is an educational model, <b>not a diagnostic tool</b>.",
])

S += [Paragraph("7. Streamlit application (deployment)", H1),
      Paragraph("<font face='DV-I'>app.py</font> loads the four tuned models saved with <font face='DV-I'>joblib</font> and provides: "
                "(1) an input form with 30 grouped sliders (mean / standard error / worst) inside a <b>Predict</b> button flow, plus one-click "
                "examples – typical benign, typical malignant, random real test record; "
                "(2) results showing <b>every model's prediction and malignant probability</b> and a consensus vote; "
                "(3) a <b>Model comparison</b> tab (metrics, confusion matrices, tuning results computed live on the test split); "
                "(4) a <b>Dataset</b> tab (class balance, feature importance, data preview). "
                "Run locally with <font face='DV-I'>streamlit run app.py</font>.", BODY),
      Paragraph(link, BODY),
      Paragraph("<i>Educational demo – predictions are not a medical diagnosis.</i>", BODY)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawCentredString(A4[0] / 2, 0.9 * cm, f"FA2 · Advanced Data Science · Breast Cancer Diagnosis · page {doc.page}")
    canvas.restoreState()


SimpleDocTemplate(args.out, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                  title="FA2 Report – Breast Cancer Diagnosis using Machine Learning",
                  author=args.name or "Student").build(S, onFirstPage=footer, onLaterPages=footer)
print("wrote", args.out)
