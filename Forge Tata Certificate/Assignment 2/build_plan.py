"""Builds Geldium_Model_Plan.docx from the Forage Task 2 template (conceptual plan, no model code is run)."""
import re
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

HERE = Path(__file__).parent
doc = Document(HERE / "Task 2_ModelPlan_Template.docx")
P = list(doc.paragraphs)
FONT = "Arial"


def run(par, text, size=10, bold=None, italic=None, color=None, mono=False):
    r = par.add_run(text)
    r.font.name = "Consolas" if mono else FONT
    r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), r.font.name)
    r.font.size = Pt(size - 1 if mono else size)
    r.bold, r.italic = bold, italic
    if color:
        r.font.color.rgb = RGBColor.from_string(color)


def rich(par, text, size=10, color=None):
    for part in re.split(r"(\*\*.+?\*\*|__.+?__|`[^`]+`)", text):
        if part.startswith("**"):
            run(par, part[2:-2], size, bold=True, color=color)
        elif part.startswith("__"):
            run(par, part[2:-2], size, italic=True, color=color)
        elif part.startswith("`"):
            run(par, part[1:-1], size, mono=True, color=color)
        elif part:
            run(par, part, size, color=color)


def shade_par(par, fill):
    pPr = par._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    for k, v in dict(val="clear", color="auto", fill=fill).items():
        shd.set(qn("w:" + k), v)
    pPr.append(shd)


class Cur:
    """Inserts content, in order, after the given paragraph."""

    def __init__(self, par):
        self.el = par._p

    def par(self, text="", style="Normal", size=10, after=4, before=0, keep=False):
        p = OxmlElement("w:p")
        self.el.addnext(p)
        self.el = p
        par = Paragraph(p, doc._body)
        par.style = doc.styles[style]
        par.paragraph_format.space_after, par.paragraph_format.space_before = Pt(after), Pt(before)
        par.paragraph_format.line_spacing = 1.08
        par.paragraph_format.keep_with_next = keep
        if text:
            rich(par, text, size)
        return par

    def bullet(self, text):
        return self.par(text, "List Bullet", after=2)

    def num(self, text):
        return self.par(text, "List Number", after=2)

    def label(self, text):
        return self.par(f"**{text}**", before=5, after=2, keep=True)

    def code(self, lines):
        for ln in lines:
            p = self.par(after=0)
            run(p, ln, 8.5, mono=True)
            shade_par(p, "F2F4F7")
        self.par(after=2)

    def table(self, header, rows, widths):
        t = doc.add_table(rows=1 + len(rows), cols=len(header))
        t.autofit = False
        b = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{side}")
            for k, v in dict(val="single", sz=4, space=0, color="BFC9D6").items():
                e.set(qn("w:" + k), str(v))
            b.append(e)
        t._tbl.tblPr.append(b)
        for ri, row in enumerate([header] + rows):
            for ci, text in enumerate(row):
                cell = t.cell(ri, ci)
                cell.width = Cm(widths[ci])
                shd = OxmlElement("w:shd")
                fill = "365F91" if ri == 0 else ("EEF3F9" if ri % 2 == 0 else "FFFFFF")
                for k, v in dict(val="clear", color="auto", fill=fill).items():
                    shd.set(qn("w:" + k), v)
                cell._tc.get_or_add_tcPr().append(shd)
                par = cell.paragraphs[0]
                par.paragraph_format.space_after = Pt(0)
                if ri == 0:
                    run(par, text, 8.5, bold=True, color="FFFFFF")
                else:
                    rich(par, text, 8.5)
        self.el.addnext(t._tbl)
        self.el = t._tbl
        return self.par(after=4)


def drop(*idx):
    for i in idx:
        P[i]._p.getparent().remove(P[i]._p)


# ---- title block --------------------------------------------------------------------------------
for i, (text, size, bold, color) in {0: ("Predictive Model Plan - Geldium Delinquency Risk", 16, True, None),
                                     1: ("Tata iQ Data Analytics Job Simulation  |  Prepared by Manthan Vijay Sankpal  |  22 October 2026", 9, None, "595959")}.items():
    for r in list(P[i].runs):
        r._r.getparent().remove(r._r)
    P[i].alignment = WD_ALIGN_PARAGRAPH.CENTER
    run(P[i], text, size, bold=bold, color=color)

# ---- 1. Model logic -----------------------------------------------------------------------------
drop(3, 4)
c = Cur(P[2])
c.label("Chosen model (summary)")
c.par("I would build a **regularised logistic regression** (L2 / elastic-net, scorecard style) that outputs the probability that a customer's account "
      "becomes delinquent, and benchmark it against a **gradient-boosted tree model** as a challenger. The logistic model is the recommended "
      "production candidate because every input has a visible, signed weight, which suits a regulated lending setting and a small sample of 500 customers "
      "with only 80 delinquent.")
c.label("Top 5 input features")
c.table(["#", "Feature", "How it should contribute", "Expected effect"],
        [["1", "**Missed_Payments** (plus counts of Late / Missed months from Month_1-6)", "Most direct sign of repayment stress; recent months weighted most", "Higher = riskier"],
         ["2", "**Credit_Utilization**", "Heavy use of available credit signals liquidity stress", "Higher = riskier"],
         ["3", "**Debt_to_Income_Ratio**", "Little income headroom to absorb a shock", "Higher = riskier"],
         ["4", "**Credit_Score**", "Summarises past repayment behaviour across lenders", "Higher = safer"],
         ["5", "**Account_Tenure**", "Longer relationships mean a longer repayment record", "Longer = safer"]],
        [0.8, 5.4, 6.6, 2.6])
c.par("__Supporting inputs:__ Income and Loan_Balance (through ratios), Employment_Status and Credit_Card_Type. **Excluded from the inputs:** Age and Location, "
      "which are protected or proxy attributes and are used only in the fairness audit (section 3).", after=3)
c.par("**Important caveat from the EDA (Task 1):** these five are chosen on credit-risk logic, not on evidence in this sample. The EDA found no statistically "
      "significant relationship between any field and delinquency (all correlations below 0.05; cross-validated ROC-AUC about 0.41-0.47, no better than chance) "
      "and several contradictions (e.g. Missed_Payments conflicting with the monthly history for 141 customers). The plan therefore starts with a data-validation gate, "
      "and the features must earn their place in cross-validation.", after=3)
c.label("How the model turns customer data into a risk prediction (workflow)")
for s in ["**Validate the data (gate):** resolve the contradictions found in the EDA and confirm the definition of Delinquent_Account and the Missed_Payments window; stop if unresolved.",
          "**Ingest and clean:** standardise Employment_Status labels, convert Month_1-6 to codes (0 on-time, 1 late, 2 missed), median-impute Income / Loan_Balance / Credit_Score with missing-value flags.",
          "**Engineer features:** number of late and missed months, trend over the last 3 months, utilization bands, loan-to-income, tenure bands.",
          "**Split and prevent leakage:** stratified train / test split with repeated stratified cross-validation (only 80 positives); all scaling and encoding fitted inside the training folds.",
          "**Train:** logistic regression with class weighting for the 16% delinquency rate; tune the regularisation strength by cross-validation. Train the gradient-boosted challenger the same way.",
          "**Calibrate:** map scores to reliable probabilities (Platt / isotonic) so that '30%' really means about 30%.",
          "**Output:** a delinquency probability (0-100%), a risk tier (Low / Medium / High) set from the business cost of each error, and the top 3 reason codes (largest coefficient x value).",
          "**Monitor:** track drift (population stability index), calibration and fairness monthly or quarterly; retrain when they degrade."]:
    c.num(s)
c.label("Pseudocode")
c.code(["df = clean(load('Delinquency_prediction_dataset.xlsx'))    # labels, imputation + flags",
        "X  = engineer(df)      # late/missed counts, recent trend, utilization bands, loan-to-income",
        "X  = drop(X, ['Age', 'Location', 'Customer_ID'])            # protected / proxy / identifier",
        "y  = df['Delinquent_Account']",
        "pipe = Pipeline([impute_median, scale_numeric, one_hot_categorical,",
        "                 LogisticRegression(penalty='elasticnet', class_weight='balanced')])",
        "cv   = RepeatedStratifiedKFold(n_splits=5, n_repeats=5)",
        "best = GridSearchCV(pipe, {'C': [.01, .1, 1, 10]}, cv=cv, scoring='roc_auc').fit(X_train, y_train)",
        "model = CalibratedClassifierCV(best.best_estimator_, method='isotonic').fit(X_train, y_train)",
        "risk = model.predict_proba(X_new)[:, 1]                     # probability of delinquency",
        "tier = cut(risk, bins=[0, t_low, t_high, 1], labels=['Low', 'Medium', 'High'])"])

# ---- 2. Justification ---------------------------------------------------------------------------
drop(7)
c = Cur(P[6])
c.par("I chose regularised logistic regression because it best balances accuracy, transparency and practicality for Geldium. In financial services a lender "
      "must be able to explain a risk decision to regulators (for example adverse-action reasons under US fair-lending rules) and to customers; logistic regression "
      "gives each feature a signed, auditable weight and simple reason codes, which a neural network or large ensemble cannot offer without extra tooling. It is "
      "robust on small, noisy samples such as this one (500 customers, 80 delinquent), where a complex model would mostly learn noise, and it is fast and cheap to "
      "deploy, monitor and retrain, which suits Geldium's goal of earlier, targeted interventions for at-risk customers. Its main trade-off is that it captures only "
      "linear effects, so some predictive power may be lost against tree ensembles; I would therefore keep a gradient-boosted model as a challenger and adopt it only "
      "if it improves cross-validated AUC materially (for example by more than 0.03-0.05) and can be explained with SHAP-style reason codes.", after=5)
c.table(["Criterion", "Logistic regression (recommended)", "Decision tree / gradient boosting", "Neural network"],
        [["Interpretability", "High: one signed weight per feature", "Medium (single tree) to low (ensemble); needs SHAP", "Low"],
         ["Accuracy on small data", "Good, stable", "Good, but overfits easily with 80 positives", "Poor without much more data"],
         ["Non-linear effects", "Only if engineered", "Captured automatically", "Captured automatically"],
         ["Regulatory fit", "Strong: standard scorecard approach", "Acceptable with controls", "Hardest to justify"],
         ["Deployment and monitoring", "Trivial; easy to monitor", "Moderate", "Heavy"]],
        [3.4, 4.4, 4.7, 2.9])

# ---- 3. Evaluation ------------------------------------------------------------------------------
drop(10)
c = Cur(P[9])
c.label("Validation design")
c.bullet("Repeated stratified 5-fold cross-validation (only 80 delinquent cases), then a held-out test set used once; if dated data become available, add an out-of-time test.")
c.bullet("Always compare with two baselines: predicting the base rate (16%) and a shuffled-label model. In the EDA the features scored about 0.41-0.47 ROC-AUC, so any real model must clearly beat that.")
c.label("Accuracy metrics and how to interpret them")
c.table(["Metric", "Why it is used", "How to interpret (illustrative targets for Geldium to confirm)"],
        [["**ROC-AUC**", "Ranks risky vs safe customers regardless of threshold", "0.5 = chance; below 0.60 = no usable signal, stop; 0.70+ acceptable; 0.80+ strong"],
         ["**PR-AUC**", "Focuses on the rare delinquent class (16%)", "Compare with the 0.16 base rate; it should be well above it"],
         ["**Recall (sensitivity)**", "Share of truly delinquent customers caught", "Missed delinquents are costly; set the tier thresholds to reach the recall the intervention team can act on"],
         ["**Precision**", "Share of flagged customers who really become delinquent", "Low precision wastes outreach and may annoy good customers"],
         ["**F1 score**", "Single balance of precision and recall", "Use to compare models at the chosen threshold, not as the only criterion"],
         ["**Accuracy**", "Overall share correct", "Secondary only: predicting 'no delinquency' for everyone is already about 84% accurate"],
         ["**Calibration (Brier, curve)**", "Checks that predicted probabilities are trustworthy", "A predicted 20% should match about 20% observed in each risk band"],
         ["**KS / lift**", "Standard credit-risk separation measures", "Check that the top risk decile captures a multiple of the average delinquency rate"]],
        [3.2, 5.0, 7.2])
c.label("Bias and fairness checks")
c.bullet("**Groups:** Age bands (especially 62+), Location, Employment_Status (Retired, Unemployed) and Credit_Card_Type. Age and Location are not model inputs, but other fields can act as proxies, so they are still audited.")
c.bullet("**Metrics per group:** selection (flag) rate and disparate-impact ratio (flag a ratio below 0.80, the 'four-fifths' rule of thumb), true-positive-rate gap (equal opportunity), false-positive-rate gap, and calibration within each group. Tools such as Fairlearn or AIF360 can automate this.")
c.bullet("**Mitigation if gaps appear:** remove or transform proxy features, reweight or resample the training data, add fairness constraints during training, and review thresholds with compliance (group-specific thresholds may be restricted by law).")
c.label("When the model needs improvement")
c.bullet("ROC-AUC below the agreed target or not clearly above the shuffled baseline; recall or precision outside the range the business can act on.")
c.bullet("Calibration error in any risk band, a fairness gap beyond tolerance, or data drift (population stability index above about 0.25) in production.")
c.bullet("First fix data quality and add richer features (days past due, payment amounts, dated history), then try the challenger model, and only then tune thresholds.")

# ---- GenAI usage note ---------------------------------------------------------------------------
c = Cur(P[11])
c.label("GenAI usage note")
c.par("Claude (Anthropic) was used to structure this plan, guided by prompts such as: __'Outline a predictive modeling pipeline to forecast credit delinquency, from feature "
      "selection to model evaluation'__; __'Suggest 2 modeling options (simple and complex) for predicting delinquency, and recommend one'__; __'Explain the pros and cons of using "
      "logistic regression vs. decision trees for financial risk prediction'__; and __'Suggest a set of metrics to evaluate a financial risk prediction model for fairness, "
      "bias, and accuracy'__. The output was adapted to the findings of the Task 1 EDA; the numbers quoted come from that EDA, and the targets and thresholds above are "
      "illustrative values for Geldium to confirm.", size=9.5)
drop(5, 8, 11)

doc.core_properties.title = "Geldium Predictive Model Plan"
doc.core_properties.author = "Manthan Vijay Sankpal"
doc.save(HERE / "Geldium_Model_Plan.docx")
print("saved")
