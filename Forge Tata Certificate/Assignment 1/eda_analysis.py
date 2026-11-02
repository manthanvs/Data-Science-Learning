"""Geldium delinquency dataset - EDA, cleaning and report builder (Tata iQ / Forage task).

Reads  : Delinquency_prediction_dataset.xlsx, EDA_SummaryReport_Template.docx
Writes : Delinquency_prediction_dataset_cleaned.csv, Geldium_EDA_Summary_Report.docx

Every number in the report is computed here, so the report always matches the data.
Run:  python eda_analysis.py
"""
import warnings
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
AUTHOR, REPORT_DATE = "Manthan Vijay Sankpal", "22 October 2026"
NAVY, BLUE, GREY = "#1f3864", "#365F91", "#8d99ae"

# =============================================================================================
# 1. LOAD AND PROFILE THE RAW DATA
# =============================================================================================
raw = pd.read_excel(HERE / "Delinquency_prediction_dataset.xlsx")
df = raw.copy()
y = df["Delinquent_Account"]
MONTHS = [f"Month_{i}" for i in range(1, 7)]
N = len(df)

miss = raw.isna().sum()
miss = miss[miss > 0]
assert list(miss.index) == ["Income", "Credit_Score", "Loan_Balance"], "unexpected missing-data pattern"

df["n_missed_6m"] = (df[MONTHS] == "Missed").sum(axis=1)
df["n_late_6m"] = (df[MONTHS] == "Late").sum(axis=1)

# Consistency checks on the raw data ----------------------------------------------------------
emp_raw = raw["Employment_Status"].value_counts()
emp_map = {"employed": "Employed", "emp": "Employed", "unemployed": "Unemployed",
           "retired": "Retired", "self-employed": "Self-employed"}
df["Employment_Status"] = raw["Employment_Status"].str.strip().str.lower().map(emp_map)
assert df["Employment_Status"].notna().all()
emp_clean = df["Employment_Status"].value_counts()

util_over = int((df["Credit_Utilization"] > 1).sum())
tenure_flag = df["Account_Tenure"] > df["Age"] - 18
mp_conflict = df["Missed_Payments"] < df["n_missed_6m"]
mp_zero_but_missed = int(((df["Missed_Payments"] == 0) & (df["n_missed_6m"] > 0)).sum())
unemp = df["Employment_Status"] == "Unemployed"
retired = df["Employment_Status"] == "Retired"
unemp_rich, retired_young = int((unemp & (df.Income > 100000)).sum()), int((retired & (df.Age < 50)).sum())
emp_income_p = stats.kruskal(*[g.Income.dropna() for _, g in df.groupby("Employment_Status")]).pvalue
loan_gt_income = int((df.Loan_Balance > df.Income).sum())
ks_uniform = {c: stats.kstest(((s := df[c].dropna()) - s.min()) / (s.max() - s.min()), "uniform").pvalue
              for c in ["Age", "Income", "Credit_Score", "Loan_Balance"]}
delinq_zero_mp = int(((y == 1) & (df.Missed_Payments == 0)).sum())

# Missingness mechanism ------------------------------------------------------------------------
mech = {}
for col in ["Income", "Loan_Balance"]:
    m = df[col].isna()
    mech[col] = {"emp_p": stats.chi2_contingency(pd.crosstab(m, df.Employment_Status))[1],
                 "age_p": stats.mannwhitneyu(df.Age[m], df.Age[~m]).pvalue,
                 "delinq_p": stats.fisher_exact(pd.crosstab(m, y))[1],
                 "rate_missing": y[m].mean(), "rate_present": y[~m].mean(), "n": int(m.sum())}
both_missing = int((df.Income.isna() & df.Loan_Balance.isna()).sum())
income_corr_max = df[["Age", "Credit_Score", "Credit_Utilization", "Missed_Payments", "Loan_Balance",
                      "Debt_to_Income_Ratio", "Account_Tenure"]].corrwith(df.Income).abs().max()
income_skew = df.Income.skew()

# =============================================================================================
# 2. CLEANING (missing data + labels) AND VALIDATION OF THE IMPUTATION
# =============================================================================================
before = {c: (raw[c].mean(), raw[c].median(), raw[c].std()) for c in miss.index}
clean = df.drop(columns=["n_missed_6m", "n_late_6m"]).copy()
clean["Income_Missing"] = raw["Income"].isna().astype(int)
clean["Loan_Balance_Missing"] = raw["Loan_Balance"].isna().astype(int)
for c in miss.index:                                   # median imputation (see report section 3)
    clean[c] = clean[c].fillna(raw[c].median())
clean["Credit_Score"] = clean["Credit_Score"].round().astype(int)
after = {c: (clean[c].mean(), clean[c].median(), clean[c].std()) for c in miss.index}
for i, m in enumerate(MONTHS, 1):                      # numeric codes from the Dataset Description Guide
    clean[f"{m}_Code"] = raw[m].map({"On-time": 0, "Late": 1, "Missed": 2})
clean["Credit_Utilization_Over_100pct"] = (raw["Credit_Utilization"] > 1).astype(int)
clean["Tenure_Exceeds_Adult_Years"] = tenure_flag.astype(int)
clean["Missed_Payments_Conflict"] = mp_conflict.astype(int)
assert clean[["Income", "Credit_Score", "Loan_Balance"]].isna().sum().sum() == 0
clean.to_csv(HERE / "Delinquency_prediction_dataset_cleaned.csv", index=False)

# =============================================================================================
# 3. PATTERNS AND RISK FACTORS
# =============================================================================================
num_cols = ["Age", "Income", "Credit_Score", "Credit_Utilization", "Missed_Payments", "Loan_Balance",
            "Debt_to_Income_Ratio", "Account_Tenure"]
corr = raw[num_cols].corrwith(y)
mwu = {c: stats.mannwhitneyu(raw.loc[y == 1, c].dropna(), raw.loc[y == 0, c].dropna()).pvalue for c in num_cols}
chi = {c: stats.chi2_contingency(pd.crosstab(df[c], y))[1] for c in ["Employment_Status", "Credit_Card_Type", "Location", "Month_1"]}
assert corr.abs().max() < 0.06 and min(mwu.values()) > 0.05 and min(chi.values()) > 0.05, "text below assumes no significant signal"
pred_corr = {"score_util": df.Credit_Score.corr(df.Credit_Utilization), "inc_loan": df.Income.corr(df.Loan_Balance)}

# Predictive-signal check: repeated 5-fold CV ROC-AUC with all available fields --------------------
feat_num = num_cols + ["n_missed_6m", "n_late_6m"]
feat_cat = ["Employment_Status", "Credit_Card_Type", "Location"] + MONTHS
pre = ColumnTransformer([("n", Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler())]), feat_num),
                         ("c", OneHotEncoder(handle_unknown="ignore"), feat_cat)])
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=42)
X_all = df[feat_num + feat_cat]
auc = {}
for name, model in [("Logistic Regression", LogisticRegression(max_iter=2000)),
                    ("Random Forest", RandomForestClassifier(300, min_samples_leaf=5, random_state=42)),
                    ("Gradient Boosting", GradientBoostingClassifier(random_state=42))]:
    auc[name] = cross_val_score(Pipeline([("p", pre), ("m", model)]), X_all, y, cv=cv, scoring="roc_auc").mean()
y_shuf = pd.Series(np.random.default_rng(0).permutation(y.values))
auc_shuffled = cross_val_score(Pipeline([("p", pre), ("m", LogisticRegression(max_iter=2000))]), X_all, y_shuf, cv=cv, scoring="roc_auc").mean()

# Candidate risk indicators: group vs reference, Fisher exact test ---------------------------------
mp, ut, dti, sc, ten = (df[c] for c in ["Missed_Payments", "Credit_Utilization", "Debt_to_Income_Ratio", "Credit_Score", "Account_Tenure"])
lbm = raw["Loan_Balance"].isna()
indicators = [  # (label, group mask, reference mask, why it matters)
    ("4+ missed payments (vs 0-1)", mp >= 4, mp <= 1,
     "Missed payments are the most direct sign of repayment stress and the usual top predictor in credit-risk models."),
    ("Credit utilization >70% (vs <30%)", ut > 0.7, ut < 0.3,
     "Using most of the available credit signals liquidity stress and is strongly linked to default in practice."),
    ("Debt-to-income >40% (vs <20%)", dti > 0.4, dti < 0.2,
     "Little income headroom to absorb a shock; lenders cap DTI for this reason."),
    ("Credit score <580 (vs 580+)", sc < 580, sc >= 580,
     "The score summarises past repayment behaviour, so low scores should flag higher risk."),
    ("Account tenure 4 years or less (vs longer)", ten <= 4, ten > 4,
     "Newer customers have a short repayment record and weaker ties to the lender."),
    ("Unemployed (vs employed)", df.Employment_Status == "Unemployed", df.Employment_Status == "Employed",
     "Loss of income is a common trigger of missed payments."),
    ("Business card holders (vs other cards)", df.Credit_Card_Type == "Business", df.Credit_Card_Type != "Business",
     "Product segments can carry different cash-flow patterns, so this is worth testing on a larger sample."),
    ("Loan_Balance missing (vs present)", lbm, ~lbm,
     "Incomplete records may be more common for riskier accounts, so the flag is kept as a feature."),
]
ind_rows = []
for label, g, r, why in indicators:
    p = stats.fisher_exact([[y[g].sum(), (1 - y[g]).sum()], [y[r].sum(), (1 - y[r]).sum()]])[1]
    ind_rows.append((label, y[g].mean(), int(g.sum()), y[r].mean(), int(r.sum()), p, why))
assert min(r[5] for r in ind_rows) > 0.05, "text assumes no indicator reaches p < 0.05"

month1 = df.groupby("Month_1")["Delinquent_Account"].mean()
score_band = df.groupby(pd.cut(df.Credit_Score, [299, 450, 600, 750, 850]), observed=True)["Delinquent_Account"].mean()

# =============================================================================================
# 4. FIGURES
# =============================================================================================
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8.5, "axes.titleweight": "bold",
                     "axes.spines.top": False, "axes.spines.right": False})


def png(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=250, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# Figure 1 - missing data and effect of imputation
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.0, 2.2), gridspec_kw={"width_ratios": [0.9, 1.3]})
pct = (miss / N * 100).sort_values()
a1.barh(pct.index, pct.values, color=BLUE)
for i, (v, n) in enumerate(zip(pct.values, miss[pct.index].values)):
    a1.text(v + 0.15, i, f"{v:.1f}%  (n={n})", va="center", fontsize=7)
a1.set(title="Missing values by column", xlabel="% of 500 records", xlim=(0, 11))
a2.hist(raw["Income"].dropna() / 1000, bins=20, alpha=0.6, color=GREY, label="Original (461 values)")
a2.hist(clean["Income"] / 1000, bins=20, histtype="step", color=NAVY, lw=1.4, label="After median imputation (500)")
a2.set(title="Income before vs. after imputation", xlabel="Income (USD thousands)", ylabel="customers")
a2.legend(fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, frameon=False)
fig.tight_layout()
fig_missing = png(fig)

# Figure 2 - delinquency rate across bands of the main candidate predictors
overall = y.mean() * 100
bands = [("Missed payments (12 m)", df.Missed_Payments.astype(str)),
         ("Credit utilization", pd.cut(df.Credit_Utilization, [0, .3, .5, .7, 1.1], labels=["<30%", "30-50", "50-70", ">70%"])),
         ("Credit score", pd.cut(df.Credit_Score, [299, 450, 600, 750, 850], labels=["300-450", "451-600", "601-750", "751-850"])),
         ("Debt-to-income", pd.cut(df.Debt_to_Income_Ratio, [0, .2, .3, .4, 1], labels=["<20%", "20-30", "30-40", ">40%"])),
         ("Account tenure (years)", pd.cut(df.Account_Tenure, [-1, 4, 9, 14, 20], labels=["0-4", "5-9", "10-14", "15-19"])),
         ("Employment status", df.Employment_Status.str.replace("Self-employed", "Self-emp.").str.replace("Unemployed", "Unempl."))]
fig, axes = plt.subplots(2, 3, figsize=(6.0, 3.9))
for ax, (title, grp) in zip(axes.ravel(), bands):
    g = y.groupby(grp, observed=True).agg(["mean", "size"])
    ax.bar(range(len(g)), g["mean"] * 100, color=BLUE, width=0.7)
    ax.axhline(overall, color="#d1495b", ls="--", lw=1)
    for i, (m, n) in enumerate(zip(g["mean"] * 100, g["size"])):
        ax.text(i, m + 0.6, f"{m:.0f}%", ha="center", fontsize=6.5)
    ax.set_xticks(range(len(g)))
    many = len(g) > 5                                   # 7 narrow bars: omit n labels (n = 54-83 each, see caption)
    ax.set_xticklabels([str(k) if many else f"{k}\nn={n}" for k, n in zip(g.index.astype(str), g["size"])], fontsize=5.8)
    ax.set(title=title, ylim=(0, 32))
    ax.tick_params(axis="y", labelsize=6.5)
for ax in axes[:, 0]:
    ax.set_ylabel("% delinquent")
axes[0, 2].text(0.98, 0.95, "dashed line = overall 16.0 %", transform=axes[0, 2].transAxes, ha="right", va="top", fontsize=6, color="#d1495b")
fig.tight_layout(h_pad=1.0)
fig_bands = png(fig)

# =============================================================================================
# 5. FILL THE WORD TEMPLATE
# =============================================================================================
doc = Document(HERE / "EDA_SummaryReport_Template.docx")
P = list(doc.paragraphs)
FONT = "Arial"


def style_run(r, size=10, bold=None, italic=None, color=None):
    r.font.name = FONT
    r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
    r.font.size = Pt(size)
    if bold is not None:
        r.bold = bold
    if italic is not None:
        r.italic = italic
    if color:
        r.font.color.rgb = RGBColor.from_string(color)


def rich(par, text, size=10, color=None):
    """**bold**, __italic__ and `code` markup inside a string."""
    import re
    for part in re.split(r"(\*\*.+?\*\*|__.+?__|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("`"):
            r = par.add_run(part[1:-1])
            style_run(r, size - 1, color=color)
            r.font.name = "Consolas"
            r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Consolas")
        elif part.startswith("**"):
            style_run(par.add_run(part[2:-2]), size, bold=True, color=color)
        elif part.startswith("__"):
            style_run(par.add_run(part[2:-2]), size, italic=True, color=color)
        else:
            style_run(par.add_run(part), size, color=color)


def set_text(par, text, size=10):
    for r in list(par.runs):
        r._r.getparent().remove(r._r)
    rich(par, text, size)


def new_par_after(el, style="Normal"):
    p = OxmlElement("w:p")
    el.addnext(p)
    par = Paragraph(p, doc._body)
    par.style = doc.styles[style]
    return par


class Cursor:
    """Inserts content, in order, after a given paragraph/table element."""

    def __init__(self, anchor_par):
        self.el = anchor_par._p

    def par(self, text="", style="Normal", size=10, after=4, before=0, align=None, keep_next=False):
        p = new_par_after(self.el, style)
        self.el = p._p
        p.paragraph_format.space_after, p.paragraph_format.space_before = Pt(after), Pt(before)
        p.paragraph_format.line_spacing = 1.08
        if align:
            p.alignment = align
        if keep_next:
            p.paragraph_format.keep_with_next = True
        if text:
            rich(p, text, size)
        return p

    def bullet(self, text, size=10):
        return self.par(text, style="List Bullet", size=size, after=2)

    def label(self, text):
        return self.par(f"**{text}**", after=2, before=4, keep_next=True)

    def picture(self, buf, width_cm, caption):
        p = self.par(after=2, align=WD_ALIGN_PARAGRAPH.CENTER, keep_next=True, before=4)
        shape = p.add_run().add_picture(buf, width=Cm(width_cm))
        shape._inline.docPr.set("descr", caption)
        c = self.par(f"__{caption}__", size=8.5, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)
        return c

    def table(self, header, rows, widths_cm, size=8.5, align_center=()):
        t = make_table(header, rows, widths_cm, size, align_center)
        self.el.addnext(t._tbl)
        self.el = t._tbl
        return self.par(after=4)           # spacer paragraph after the table


# --- table helpers (python-docx has no API for shading / borders) --------------------------------
TCPR = ["w:cnfStyle", "w:tcW", "w:gridSpan", "w:hMerge", "w:vMerge", "w:tcBorders", "w:shd", "w:noWrap", "w:tcMar",
        "w:textDirection", "w:tcFitText", "w:vAlign", "w:hideMark"]
TBLPR = ["w:tblStyle", "w:tblpPr", "w:tblOverlap", "w:bidiVisual", "w:tblStyleRowBandSize", "w:tblStyleColBandSize", "w:tblW",
         "w:jc", "w:tblCellSpacing", "w:tblInd", "w:tblBorders", "w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook"]
TRPR = ["w:cnfStyle", "w:divId", "w:gridBefore", "w:gridAfter", "w:wBefore", "w:wAfter", "w:cantSplit", "w:trHeight", "w:tblHeader"]


def put(parent, order, tag, **attrs):
    """Create <tag> with attributes and insert it at its schema-correct position inside parent."""
    for old in parent.findall(qn(tag)):
        parent.remove(old)
    el = OxmlElement(tag)
    for k, v in attrs.items():
        el.set(qn("w:" + k), str(v))
    mine = order.index(tag)
    for child in parent:
        names = [t for t in order if qn(t) == child.tag]
        if names and order.index(names[0]) > mine:
            child.addprevious(el)
            return el
    parent.append(el)
    return el


def make_table(header, rows, widths_cm, size, align_center):
    t = doc.add_table(rows=1 + len(rows), cols=len(header))
    t.autofit = False
    tblPr = t._tbl.tblPr
    put(tblPr, TBLPR, "w:tblW", w=int(sum(widths_cm) * 567), type="dxa")
    borders = put(tblPr, TBLPR, "w:tblBorders")
    for side, sz, col in [("top", 8, "365F91"), ("bottom", 8, "365F91"), ("insideH", 4, "C9D3DF")]:
        b = OxmlElement(f"w:{side}")
        for k, v in dict(val="single", sz=sz, space=0, color=col).items():
            b.set(qn("w:" + k), str(v))
        borders.append(b)
    mar = put(tblPr, TBLPR, "w:tblCellMar")
    for side, w in [("top", 45), ("left", 80), ("bottom", 45), ("right", 80)]:
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), str(w))
        m.set(qn("w:type"), "dxa")
        mar.append(m)
    for ri, row in enumerate([header] + rows):
        tr = t.rows[ri]._tr
        trPr = tr.get_or_add_trPr()
        put(trPr, TRPR, "w:cantSplit")
        if ri == 0:
            put(trPr, TRPR, "w:tblHeader")
        for ci, text in enumerate(row):
            cell = t.cell(ri, ci)
            cell.width = Cm(widths_cm[ci])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            tcPr = cell._tc.get_or_add_tcPr()
            fill = "365F91" if ri == 0 else ("EEF3F9" if ri % 2 == 0 else "FFFFFF")
            put(tcPr, TCPR, "w:shd", val="clear", color="auto", fill=fill)
            par = cell.paragraphs[0]
            par.paragraph_format.space_after = Pt(0)
            if ci in align_center:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if ri == 0:
                style_run(par.add_run(text), size, bold=True, color="FFFFFF")
            else:
                rich(par, str(text), size)
    return t


# --- Title ---------------------------------------------------------------------------------------
P[0].runs[2].text = "Report"                                    # "Report Template" -> "Report"
sub = P[1]
for r in list(sub.runs):
    r._r.getparent().remove(r._r)
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.paragraph_format.space_after = Pt(2)
rich(sub, "**Geldium - Delinquency Risk Dataset** | Tata iQ Data Analytics Job Simulation", size=10.5, color="365F91")
c = Cursor(sub)
c.par(f"Prepared by {AUTHOR}  |  {REPORT_DATE}", size=9, after=8, align=WD_ALIGN_PARAGRAPH.CENTER)

# --- 1. Introduction -----------------------------------------------------------------------------
set_text(P[3], "Geldium wants to refine its delinquency-risk model and its intervention strategy. Before any predictive modelling, "
               "this report checks whether the customer dataset is complete, accurate and internally consistent, and looks for early "
               "indicators of delinquency. **Goals:** (1) profile the data and flag quality problems; (2) treat missing values with "
               "documented, defensible methods; (3) test how each variable relates to delinquency; and (4) recommend next steps for "
               "Tata iQ's analytics team and Geldium's decision-makers.")

# --- 2. Dataset overview -------------------------------------------------------------------------
for i in (7, 8, 9):
    P[i]._p.getparent().remove(P[i]._p)
P[6].runs[0].bold = True
c = Cursor(P[6])
c.bullet(f"**Number of records:** {N} customers (one row each) and 19 columns; no duplicate rows or duplicate Customer_IDs.")
c.bullet("**Key variables:** __Target__ - Delinquent_Account (1 = delinquent: 80 customers, 16.0%; 0 = not: 420). "
         "__Financial__ - Income, Credit_Score, Credit_Utilization, Loan_Balance, Debt_to_Income_Ratio. "
         "__Behaviour/account__ - Missed_Payments (past 12 months), Month_1 to Month_6 payment status, Account_Tenure, Credit_Card_Type. "
         "__Profile__ - Age, Employment_Status, Location.")
c.bullet("**Data types:** 9 numerical (8 predictors plus the binary target) and 10 categorical (Customer_ID, Employment_Status, "
         "Credit_Card_Type, Location, and the six text-coded payment-status columns).")
c.label("Initial review - notable missing or inconsistent data and anomalies:")
c.bullet(f"**Missing values** in 3 of 19 columns: Income {miss['Income']} ({miss['Income']/N:.1%}), Loan_Balance {miss['Loan_Balance']} "
         f"({miss['Loan_Balance']/N:.1%}) and Credit_Score {miss['Credit_Score']} ({miss['Credit_Score']/N:.1%}).")
c.bullet(f"**Inconsistent labels:** Employment_Status has 6 spellings for 4 categories (Employed {emp_raw['Employed']}, employed {emp_raw['employed']}, "
         f"EMP {emp_raw['EMP']}, Unemployed, retired, Self-employed); standardised to Employed {emp_clean['Employed']}, Unemployed "
         f"{emp_clean['Unemployed']}, Retired {emp_clean['Retired']}, Self-employed {emp_clean['Self-employed']}.")
c.bullet("**Mismatch with the Dataset Description Guide:** Month_1-6 hold text (On-time / Late / Missed) instead of the 0/1/2 codes, and "
         "Credit_Utilization and Debt_to_Income_Ratio are decimals (0.05-1.03 and 0.10-0.55), not 0-100% values.")
c.bullet(f"**Logical contradictions:** for {int(mp_conflict.sum())} customers ({mp_conflict.mean():.0%}) the 12-month Missed_Payments total is lower than "
         f"the number of 'Missed' months in their own 6-month history ({mp_zero_but_missed} of them show zero). {unemp_rich} of "
         f"{int(unemp.sum())} 'Unemployed' customers earn over $100k, {retired_young} of {int(retired.sum())} 'Retired' customers are under 50 "
         f"(youngest 18), and income does not differ by employment status (p = {emp_income_p:.2f}). Account_Tenure exceeds adult years "
         f"(age - 18) for {int(tenure_flag.sum())} customers ({tenure_flag.mean():.0%}), and Loan_Balance exceeds annual Income for {loan_gt_income}.")
c.bullet(f"**Other anomalies:** Credit_Utilization is above 100% for {util_over} customers (maximum 1.03; plausible over-limit accounts, kept and flagged). "
         f"Age, Income, Credit_Score and Loan_Balance are statistically uniform (Kolmogorov-Smirnov p = {min(ks_uniform.values()):.2f}-{max(ks_uniform.values()):.2f}, "
         "skewness about 0) and payment status is split roughly one-third per category every month - unlike real credit data, which is skewed "
         "and clustered. The data may be simulated.")
c.label("Early indicators of delinquency risk (domain-driven; tested in section 4):")
c.bullet("**Top 3 candidates:** (1) payment history - Missed_Payments and Month_1-6 status; (2) Credit_Utilization; (3) Debt_to_Income_Ratio "
         "(Credit_Score is the closest alternative). They are the variables credit-risk practice treats as strongest, but **this dataset does not "
         "confirm them** (section 4).")
c.label("Summary of initial data-quality observations:")
c.par("The dataset is structurally clean - 500 unique customers, no duplicates and only 3 of 19 columns with gaps (at most 7.8% missing). "
      "It has, however, substantial consistency problems: mixed category labels, units that differ from the documentation, and contradictions "
      "between related fields such as missed payments versus monthly history and employment versus income and age. The numeric fields are "
      "near-uniformly distributed and almost uncorrelated with each other and with the target, which is unusual for real credit data and "
      "suggests simulated values. With only 80 delinquent accounts, the sample is also small for modelling a 16% event.", after=4)

# --- 3. Missing data analysis ----------------------------------------------------------------------
for i in (13, 14):
    P[i]._p.getparent().remove(P[i]._p)
P[12].runs[0].bold = True
c = Cursor(P[12])
c.bullet(f"**Variables with missing values:** Income ({miss['Income']}, {miss['Income']/N:.1%}), Loan_Balance ({miss['Loan_Balance']}, "
         f"{miss['Loan_Balance']/N:.1%}), Credit_Score ({miss['Credit_Score']}, {miss['Credit_Score']/N:.1%}). The other 16 columns, including "
         "Credit_Utilization and every payment-history field, are complete. No column is near a drop threshold, so none was removed.")
c.bullet(f"**Missingness looks random (MCAR):** it is unrelated to employment status (chi-square p = {mech['Income']['emp_p']:.2f} Income, "
         f"{mech['Loan_Balance']['emp_p']:.2f} Loan_Balance) or age (p = {mech['Income']['age_p']:.2f} / {mech['Loan_Balance']['age_p']:.2f}), only "
         f"{both_missing} rows miss both fields, and it is not significantly linked to delinquency (Fisher p = {mech['Income']['delinq_p']:.2f} Income, "
         f"{mech['Loan_Balance']['delinq_p']:.2f} Loan_Balance). Loan_Balance-missing customers are delinquent at {mech['Loan_Balance']['rate_missing']:.1%} "
         f"vs {mech['Loan_Balance']['rate_present']:.1%} (n = {mech['Loan_Balance']['n']}), too few to conclude anything, so a missing-flag is kept.")
c.bullet("**Missing data treatment:** median imputation plus a missing-value indicator for Income and Loan_Balance; median imputation for "
         "Credit_Score. Synthetic values were considered and rejected (see table).")
c.label("Table 1 - Missing-data issues and chosen handling")
c.table(["Issue", "Handling method", "Justification"],
        [[f"**Income** - {miss['Income']} missing ({miss['Income']/N:.1%})", "Median imputation + `Income_Missing` flag",
          f"Distribution is symmetric (skew {income_skew:.2f}) and Income is uncorrelated with every other field (max |r| = {income_corr_max:.2f}), so "
          "KNN/regression imputation adds nothing over the median; synthetic incomes would invent financial data."],
         [f"**Loan_Balance** - {miss['Loan_Balance']} missing ({miss['Loan_Balance']/N:.1%})", "Median imputation + `Loan_Balance_Missing` flag",
          "Missingness is random, so the median is unbiased and robust to outliers; the flag preserves any information in the gap (24.1% vs 15.5% delinquency, not yet significant)."],
         [f"**Credit_Score** - {miss['Credit_Score']} missing ({miss['Credit_Score']/N:.1%})", "Median imputation (no flag)",
          "Only 2 records: the effect on any model is negligible, and dropping them would waste the rest of those customers' data."]],
        [4.0, 3.6, 7.6], size=8)
Pn = c.par(f"**Check after imputation:** the median is unchanged by construction and the standard deviation shrinks only slightly (Income "
           f"{before['Income'][2]:,.0f} to {after['Income'][2]:,.0f}; Loan_Balance {before['Loan_Balance'][2]:,.0f} to {after['Loan_Balance'][2]:,.0f}), "
           f"so the overall shape and spread are preserved apart from the expected spike at the median (Figure 1). Limits: median filling slightly understates variance, and the missing-flags should be tested for value once the data are validated.", after=4)
c.picture(fig_missing, 14.2, "Figure 1 - Missing values by column and the effect of median imputation on Income.")
c.label("Other data-quality fixes applied (no missing values involved):")
c.bullet("Employment_Status labels standardised (6 spellings to 4 categories); Month_1-6 also encoded as 0/1/2 (`Month_k_Code`) as in the Description Guide.")
c.bullet("Not altered but **flagged** for review: utilization above 100% (`Credit_Utilization_Over_100pct`), tenure longer than adult years "
         "(`Tenure_Exceeds_Adult_Years`) and missed-payment conflicts (`Missed_Payments_Conflict`). Decimal units of utilization and DTI are kept and documented.")
c.bullet("Cleaned file: `Delinquency_prediction_dataset_cleaned.csv` (500 rows, no missing values).")

# --- 4. Key findings and risk indicators -------------------------------------------------------------
for i in (18, 19):
    P[i]._p.getparent().remove(P[i]._p)
P[17].runs[0].bold = True
c = Cursor(P[17])
cs = corr
c.bullet(f"**Correlations observed between key variables and delinquency:** all are essentially zero - Income {cs['Income']:+.3f}, Credit_Score "
         f"{cs['Credit_Score']:+.3f}, Credit_Utilization {cs['Credit_Utilization']:+.3f}, Debt_to_Income_Ratio {cs['Debt_to_Income_Ratio']:+.3f}, "
         f"Age {cs['Age']:+.3f}, Missed_Payments {cs['Missed_Payments']:+.3f}, Account_Tenure {cs['Account_Tenure']:+.3f}, Loan_Balance "
         f"{cs['Loan_Balance']:+.3f}. None is significant (Mann-Whitney p >= {min(mwu.values()):.2f}); nor are Employment_Status (chi-square p = "
         f"{chi['Employment_Status']:.2f}), Credit_Card_Type ({chi['Credit_Card_Type']:.2f}), Location ({chi['Location']:.2f}) or Month_1 status ({chi['Month_1']:.2f}).")
c.bullet(f"**Predictors are also uncorrelated with each other:** Credit_Score vs Credit_Utilization r = {pred_corr['score_util']:+.2f} (a clear negative link is "
         f"expected in real data) and Income vs Loan_Balance r = {pred_corr['inc_loan']:+.2f}.")
c.bullet(f"**Model check:** with all fields and 5x5 repeated cross-validation, ROC-AUC is {auc['Logistic Regression']:.2f} (Logistic Regression), "
         f"{auc['Random Forest']:.2f} (Random Forest) and {auc['Gradient Boosting']:.2f} (Gradient Boosting) - no better than chance and no better than "
         f"{auc_shuffled:.2f} obtained with shuffled labels. In this sample the current fields carry no usable signal for delinquency.")
c.picture(fig_bands, 14.4, "Figure 2 - Delinquency rate by band of the main candidate predictors (54-83 customers per missed-payment level). Rates stay within sampling noise of the overall 16%.")
c.label("Table 2 - High-risk indicators (domain logic, with an empirical check on this data)")
rows = [[lbl, f"{g:.1%} (n={ng}) vs {r:.1%} (n={nr}); p = {p:.2f}", why] for lbl, g, ng, r, nr, p, why in ind_rows]
c.table(["Indicator", "Observed delinquency rate: group vs reference", "Why it is important"], rows, [4.0, 4.6, 6.6], size=8)
expected = [r for r in ind_rows if r[1] > r[3]]
opposite = [r[0].split(" (vs")[0].lower() for r in ind_rows if r[1] <= r[3]]
c.par(f"**Reading the table:** {len(expected)} of {len(ind_rows)} indicators point in the expected direction, but the most established ones "
      f"({' and '.join(opposite)}) point the **opposite** way, and every difference is within sampling noise (Fisher exact p > 0.05; only 80 delinquent "
      "cases). They are hypotheses to test on validated data, not confirmed risk factors.", after=4)
c.label("Unexpected anomalies requiring further investigation:")
c.bullet(f"**Reversed patterns:** customers whose Month_1 payment was on time have the highest delinquency rate ({month1['On-time']:.1%}) against "
         f"{month1['Late']:.1%} for late payers; the 601-750 credit-score band is highest ({score_band.iloc[2]:.1%}) and 451-600 lowest ({score_band.iloc[1]:.1%}). "
         "The 'Delinquent_Account' definition and timing need confirming.")
c.bullet(f"**{delinq_zero_mp} of 80 delinquent customers ({delinq_zero_mp/80:.0%}) had no missed payments** in the last 12 months, and Missed_Payments does not "
         f"agree with the monthly history ({int(mp_conflict.sum())} conflicts), so the Missed_Payments window or definition may be wrong.")
c.bullet(f"**Employment contradicts income and age** (unemployed with high income, retired customers aged 18+), and {util_over} customers exceed 100% utilization "
         "yet none is delinquent. Together with the uniform distributions, this points to simulated or incorrectly joined data - lineage should be verified before modelling.")

# --- 5. AI & GenAI usage ----------------------------------------------------------------------------------
for i in (23, 24):
    P[i]._p.getparent().remove(P[i]._p)
P[22].runs[0].bold = True
c = Cursor(P[22])
for prompt in ["Summarize key patterns, outliers, and missing values in this dataset. Highlight any fields that might present problems for modeling delinquency.",
               "Identify the top 3 variables most likely to predict delinquency based on this dataset. Provide brief reasoning.",
               "Suggest an imputation strategy for missing values in this dataset based on industry best practices.",
               "Analyze relationships between variables and delinquency outcomes (e.g. is high credit utilization associated with missed payments?)."]:
    c.bullet(f"__'{prompt}'__")
c.label("How the AI output was used and checked:")
c.bullet("Claude (Anthropic) profiled the data with Python/pandas, evaluated imputation options (median, KNN/regression, synthetic generation) against the "
         "properties of the data, and ran the statistical tests; the full analysis is reproducible in `eda_analysis.py`.")
c.bullet("Every figure in this report was computed from the data and cross-checked in code. The analysis reports what the data show rather than the "
         "expected answer, which is why the 'top 3 predictors' are presented as unconfirmed.")
c.bullet("Synthetic income generation (offered as an option in the task) was considered but **not** used: it would fabricate financial values that carry no "
         "information and could mask the data-quality issues the analytics team needs to see.")

# --- 6. Conclusion & next steps ----------------------------------------------------------------------------
set_text(P[26], "The Geldium dataset is complete enough to work with (at most 7.8% missing, randomly distributed, now imputed and flagged) but is **not yet "
                "fit for building a delinquency model**: its fields contradict one another and none of them separates delinquent from non-delinquent "
                f"customers (cross-validated ROC-AUC {min(auc.values()):.2f}-{max(auc.values()):.2f}). Payment history, credit utilization and debt-to-income "
                "remain the right variables to prioritise, but this sample cannot confirm them.")
c = Cursor(P[26])
c.label("Recommended next steps:")
for step in ["**Validate data lineage with Geldium:** confirm whether the data are simulated, and the exact definitions of Delinquent_Account, the Missed_Payments window "
             "(12 vs 6 months), Credit_Utilization and Debt_to_Income_Ratio units.",
             "**Resolve contradictions at source:** Missed_Payments vs monthly history, Employment_Status vs Income/Age, and Account_Tenure vs Age.",
             "**Enrich and enlarge the data:** obtain many more delinquent cases (80 is too few) and add days-past-due, payment amounts, bureau attributes and dated history.",
             "**Model only after validation:** use the cleaned file and missing-flags, stratified cross-validation and PR-AUC for the imbalance, and treat any result with ROC-AUC near 0.5 as no signal.",
             "**For interventions meanwhile:** use standard industry watch-rules (utilization above 70%, DTI above 40%, repeated missed payments) as monitoring heuristics, not as findings of this analysis."]:
    c.par(step, style="List Number", after=2)

# remove the two trailing empty template paragraphs, add page-number footer
for i in (27, 28):
    if not P[i].text.strip() and i == len(P) - 1:
        P[i]._p.getparent().remove(P[i]._p)
sec = doc.sections[0]
fp = sec.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(fp.add_run("Geldium Delinquency Risk - EDA Summary Report  |  Page "), 8, color="7F7F7F")
for kind, text in (("begin", None), ("instr", " PAGE "), ("end", None)):
    r = fp.add_run()
    style_run(r, 8, color="7F7F7F")
    if kind == "instr":
        el = OxmlElement("w:instrText")
        el.set(qn("xml:space"), "preserve")
        el.text = text
    else:
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
    r._r.append(el)

doc.core_properties.title = "Geldium Delinquency Dataset - EDA Summary Report"
doc.core_properties.author = AUTHOR
out = HERE / "Geldium_EDA_Summary_Report.docx"
doc.save(out)
print("wrote", out.name, "| cleaned csv:", (HERE / "Delinquency_prediction_dataset_cleaned.csv").exists())
print("AUC", {k: round(v, 3) for k, v in auc.items()}, "shuffled", round(auc_shuffled, 3))
for r in ind_rows:
    print(f"  {r[0]:<44} {r[1]:.3f} (n={r[2]}) vs {r[3]:.3f} (n={r[4]}) p={r[5]:.3f}")
