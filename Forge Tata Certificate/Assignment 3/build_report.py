"""Builds Geldium_Business_Summary_Report.docx (two pages) from the Forage Task 3 template."""
import copy
import math
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.text.paragraph import Paragraph

HERE = Path(__file__).parent
doc = Document(HERE / "Updated_Business_Summary_Report_Template.docx")
P = list(doc.paragraphs)
FONT, BODY = "Arial", 9.5

sec = doc.sections[0]                      # slightly tighter margins so the report fits two pages
sec.left_margin = sec.right_margin = Cm(2.2)
sec.top_margin = sec.bottom_margin = Cm(1.9)


def run(par, text, size=BODY, bold=None, italic=None, color=None):
    r = par.add_run(text)
    r.font.name = FONT
    r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
    r.font.size = Pt(size)
    r.bold, r.italic = bold, italic
    if color:
        r.font.color.rgb = RGBColor.from_string(color)


def rich(par, text, size=BODY):
    for part in re.split(r"(\*\*.+?\*\*|__.+?__)", text):
        if part.startswith("**"):
            run(par, part[2:-2], size, bold=True)
        elif part.startswith("__"):
            run(par, part[2:-2], size, italic=True)
        elif part:
            run(par, part, size)


def setp(par, text, after=3, before=0, size=BODY):
    for r in list(par.runs):
        r._r.getparent().remove(r._r)
    par.paragraph_format.space_after, par.paragraph_format.space_before = Pt(after), Pt(before)
    par.paragraph_format.line_spacing = 1.05
    rich(par, text, size)
    return par


def after(par_or_el, style, text, **kw):
    el = par_or_el._p if hasattr(par_or_el, "_p") else par_or_el
    p = OxmlElement("w:p")
    el.addnext(p)
    par = Paragraph(p, doc._body)
    par.style = doc.styles[style]
    return setp(par, text, **kw)


def drop(*idx):
    for i in idx:
        P[i]._p.getparent().remove(P[i]._p)


words = 0

# ---- Title ---------------------------------------------------------------------------------------
P[0].paragraph_format.space_after = Pt(2)
byline = after(P[0], "Normal", "Prepared for: Head of Collections, Geldium  |  Prepared by: Manthan Vijay Sankpal  |  22 October 2026", after=4, size=8.5)
for r in byline.runs:
    r.font.color.rgb = RGBColor.from_string("595959")

# ---- 1. Summary of predictive insights ----------------------------------------------------------
setp(P[2], "The Task 1 analysis of 500 customers (16% delinquent) and the Task 2 model plan point to payment history, credit utilization, debt-to-income, "
           "credit score and account tenure as the variables that should drive a delinquency model. **Important:** in this sample none of them is yet "
           "statistically confirmed (correlations with delinquency are all below 0.05, and a model built on all fields scored about chance, ROC-AUC 0.41-0.47), "
           "and the data contain contradictions that must be fixed first. The patterns below are therefore **directional leads to test, not proven rules**.")
top3 = after(P[2], "Normal", "**Top 3 Risk Factors** (largest observed gaps in delinquency rate)", before=2, after=1)
b = after(top3, "List Bullet", "**High debt burden:** customers with debt-to-income above 40% were delinquent 18.9% of the time vs 9.8% below 20%.", after=1)
b = after(b, "List Bullet", "**Newer accounts:** tenure of 4 years or less shows 19.5% delinquency vs 14.9% for longer relationships.", after=1)
b = after(b, "List Bullet", "**Heavy credit use:** utilization above 70% shows 15.9% vs 12.0% below 30%.", after=2)
seg = after(b, "Normal", "**Highest-risk segments observed:** business-card holders (21.3% vs 14.5% for other cards), unemployed customers (19.4%) and accounts with a missing "
                        "Loan_Balance (24.1%, only 29 customers). Surprisingly, missed payments and credit score did **not** separate good from bad accounts in this data.", after=3)
drop(3)                                                   # template's "Optional: ..." hint line
tbl = doc.tables[0]
rows = [["Debt burden drives risk: 18.9% vs 9.8% delinquent", "Customers with debt-to-income above 40% (n=74)", "Debt_to_Income_Ratio, Income, Loan_Balance", "Early affordability outreach before a payment is missed"],
        ["New accounts are riskier: 19.5% vs 14.9%", "Account tenure 4 years or less (n=123)", "Account_Tenure, Credit_Card_Type", "Onboarding reminders and auto-pay prompts"],
        ["Heavy credit use: 15.9% vs 12.0%", "Utilization above 70% (n=69)", "Credit_Utilization, Credit_Score", "Early-warning flag for the collections queue"],
        ["Business cards are riskier: 21.3% vs 14.5%", "Business-card holders (n=108)", "Credit_Card_Type, Income", "Segment-specific monitoring; test cash-flow causes"]]
while len(tbl.rows) < 1 + len(rows):
    tbl._tbl.append(copy.deepcopy(tbl.rows[-1]._tr))
for ri, row in enumerate(rows, 1):
    for ci, text in enumerate(row):
        cell = tbl.cell(ri, ci)
        par = cell.paragraphs[0]
        for r in list(par.runs):
            r._r.getparent().remove(r._r)
        par.paragraph_format.space_after = Pt(0)
        run(par, text, 8)
for ci in range(4):                                       # header row: keep template styling, make it compact
    for r in tbl.cell(0, ci).paragraphs[0].runs:
        r.font.size = Pt(8.5)
note = after(tbl._tbl, "Normal", "__Rates compare each group with its reference group; no difference reaches statistical significance (Fisher exact p = 0.10-0.66), so treat them as hypotheses.__", before=2, after=2, size=8)

# ---- 2. Recommendation framework ------------------------------------------------------------------
drop(6, 7)
rec = {
    8: "**Restated Insight:** customers whose debt-to-income ratio exceeds 40% are delinquent far more often (18.9% vs 9.8% below 20%), and debt burden is something Collections can act on early.",
    9: "**Proposed Recommendation:** run a controlled pilot of proactive early contact for high-DTI accounts, offering a payment reminder, an affordability check and flexible due dates **before** a payment is missed.",
    10: "**Specific:** contact customers with debt-to-income above 40% who have no missed payment yet; a randomly chosen half receives outreach, the other half is the control group.",
    11: "**Measurable:** cut the delinquency rate of contacted customers from about 19% to 14% or lower (5 points) versus the control group; about 850 customers per group are needed, so the pilot runs on the live portfolio, not the 500-customer sample.",
    12: "**Actionable:** uses current collections staff and existing SMS, e-mail and call channels; no new system is required beyond a list of flagged accounts.",
    13: "**Relevant:** targets the largest observed risk gap, lowers delinquency and collection cost, and supports customers before they fall behind.",
    14: "**Time-bound:** launch by 30 November 2026, run 90 days, review by 28 February 2027; scale up only if the reduction is at least 5 points and statistically significant (p < 0.05).",
    15: "**Justification and Business Rationale:** early, supportive contact is cheaper than recovering a delinquent account and protects the customer relationship. Because our data cannot yet prove that DTI causes delinquency, a controlled pilot is the safe way to confirm the effect before changing policy.",
}
for i, text in rec.items():
    setp(P[i], text, after=1.5)
P[8].paragraph_format.space_before = Pt(2)

# ---- 3. Ethical and responsible AI considerations ----------------------------------------------------
setp(P[17], "**Plain-language explanation for non-technical readers:** the model works like a points checklist. Each factor (for example, high debt relative to income) "
            "adds or removes risk points, and each flagged customer comes with the top three reasons, such as \"debt is above 40% of income\". It estimates likelihood, "
            "not certainty, and a person always makes the final decision.", after=2)
setp(P[18], "**Fairness risk 1 - proxy bias:** income, employment status, card type or location can stand in for age or other protected traits, so some groups (e.g. retired or unemployed customers) "
            "may be flagged more often. **Mitigation:** keep Age and Location out of the model, audit flag rates and error rates by group (four-fifths rule), and review results with compliance.", after=1.5)
setp(P[19], "**Fairness risk 2 - unreliable data:** employment status contradicts income and age for many records, and 141 customers have missed-payment counts that conflict with their monthly history, "
            "so customers could be wrongly labelled high-risk. **Mitigation:** validate the data with Geldium first, require human review of flagged accounts, and start with the pilot.", after=1.5)
setp(P[20], "**Responsible decision-making:** the recommendation is supportive (earlier help and flexible options), not punitive; it must never be used to reduce credit limits or refuse service without separate review.", after=1.5)
setp(P[21], "**Transparency and accountability:** publish the model's limits (currently weak predictive power), name an owner, monitor calibration, drift and fairness every quarter, "
            "and use only the data needed, with access controls (privacy).", after=1.5)
drop(22)

# ---- rough length check (no renderer available): estimate lines on a Letter page --------------------------
chars_per_line = 17.2 / 0.165                              # 9.5 pt Arial, 17.2 cm text width
lines = 0
for p in doc.paragraphs:
    t = p.text
    if p.style.name.startswith("Heading"):
        lines += 2.4
    elif p.style.name == "Title":
        lines += 2.6
    elif t:
        lines += math.ceil(len(t) / (chars_per_line - (4 if "List" in p.style.name else 0))) + 0.25
tbl_lines = sum(max(math.ceil(len(c.text) / 24) for c in r.cells) * 0.85 + 0.3 for r in tbl.rows)
page_lines = (27.9 - 3.8) / 0.43
print(f"estimated length: {(lines + tbl_lines) / page_lines:.2f} pages")

doc.core_properties.title = "Business Summary Report - Predictive Insights for Collections Strategy"
doc.core_properties.author = "Manthan Vijay Sankpal"
doc.save(HERE / "Geldium_Business_Summary_Report.docx")
print("saved")
