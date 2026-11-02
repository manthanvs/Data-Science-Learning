"""Builds Geldium_AI_Collections_Strategy.pptx from the Forage Task 4 template (high-level strategy deck)."""
import copy
import math
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Cm, Pt

HERE = Path(__file__).parent
prs = Presentation(HERE / "Presentation_Template.pptx")
S = list(prs.slides)

CARD, BLUE, GREEN, YELLOW, LIGHT, WHITE = (RGBColor.from_string(c) for c in ("004065", "039BE5", "8BC34A", "FFEB38", "CFD8DC", "FFFFFF"))
warnings = []


def rgb(c):
    return c


def est_height_cm(paras, width_cm, size):
    """Rough text height: Arial averages about 0.52 em per character, line height 1.2 em."""
    cpl = max(1, int(width_cm / (size * 0.52 * 0.03528)))
    lines = sum(max(1, math.ceil(len(t) / cpl)) for t in paras)
    return lines * size * 1.2 * 0.03528 + len(paras) * 0.12


def set_bullet(par, char="•", color=None):
    pPr = par._p.get_or_add_pPr()
    pPr.set("marL", "228600")
    pPr.set("indent", "-228600")
    for tag in ("a:buNone", "a:buChar", "a:buClr"):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    if color is not None:
        clr = pPr.makeelement(qn("a:buClr"), {})
        srgb = clr.makeelement(qn("a:srgbClr"), {"val": str(color)})
        clr.append(srgb)
        pPr.append(clr)
    pPr.append(pPr.makeelement(qn("a:buChar"), {"char": char}))


def add_text(slide, x, y, w, h, paras, size=12, bold=False, color=WHITE, bullets=False, bullet_color=None, align=None,
             anchor=MSO_ANCHOR.TOP, space_after=3, name=None):
    tb = slide.shapes.add_textbox(Cm(x), Cm(y), Cm(w), Cm(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Cm(0.15)
    tf.margin_top = tf.margin_bottom = Cm(0.08)
    for i, text in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(space_after)
        if align:
            p.alignment = align
        if isinstance(text, tuple):                       # (bold lead-in, rest)
            r = p.add_run()
            r.text = text[0]
            r.font.bold, r.font.size, r.font.color.rgb, r.font.name = True, Pt(size), color, "Arial"
            r2 = p.add_run()
            r2.text = text[1]
            r2.font.size, r2.font.color.rgb, r2.font.name = Pt(size), color, "Arial"
        else:
            r = p.add_run()
            r.text = text
            r.font.bold, r.font.size, r.font.color.rgb, r.font.name = bold, Pt(size), color, "Arial"
        if bullets:
            set_bullet(p, color=bullet_color)
    flat = ["".join(t) if isinstance(t, tuple) else t for t in paras]
    need = est_height_cm(flat, w - 0.3 - (0.6 if bullets else 0), size)
    if need > h:
        warnings.append(f"text may overflow ({need:.1f} cm needed > {h:.1f} cm): {flat[0][:40]}")
    if name:
        tb.name = name
    return tb


def card(slide, x, y, w, h, title, bullets, accent=BLUE, size=11, badge=None):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Cm(x), Cm(y), Cm(w), Cm(h))
    box.adjustments[0] = 0.04
    box.fill.solid()
    box.fill.fore_color.rgb = CARD
    box.line.color.rgb = accent
    box.line.width = Pt(1.5)
    box.shadow.inherit = False
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Cm(x + 0.06), Cm(y + 0.06), Cm(w - 0.12), Cm(1.15))
    band.fill.solid()
    band.fill.fore_color.rgb = accent
    band.line.fill.background()
    band.shadow.inherit = False
    tf = band.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Cm(0.25)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = (f"{badge}  " if badge else "") + title
    r.font.bold, r.font.size, r.font.name = True, Pt(14), "Arial"
    r.font.color.rgb = RGBColor.from_string("00314D") if accent in (GREEN, YELLOW) else WHITE
    add_text(slide, x + 0.15, y + 1.4, w - 0.3, h - 1.55, bullets, size=size, bullets=True, bullet_color=accent, space_after=4)


def arrow(slide, x, y, w=0.7, h=1.0, color=GREEN):
    a = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Cm(x), Cm(y), Cm(w), Cm(h))
    a.fill.solid()
    a.fill.fore_color.rgb = color
    a.line.fill.background()
    a.shadow.inherit = False


def drop_body(slide):
    for sh in list(slide.placeholders):
        if sh.placeholder_format.idx != 0:
            sh._element.getparent().remove(sh._element)


def title(slide, text):
    tf = slide.shapes.title.text_frame
    tf.text = text
    for r in tf.paragraphs[0].runs:                       # fixed size so every title stays on one line (about 45 characters max)
        r.font.size = Pt(26)
    assert len(text) <= 46, text


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def style_cell(cell, text, size, bold=False, fill=CARD, color=WHITE, bullets=False):
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.margin_left = cell.margin_right = Cm(0.25)
    cell.margin_top = cell.margin_bottom = Cm(0.12)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = cell.text_frame
    tf.word_wrap = True
    items = text if isinstance(text, list) else [text]
    for i, t in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run()
        r.text = t
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(size), bold, color, "Arial"
        p.space_after = Pt(2)
        if bullets:
            set_bullet(p)


def table(slide, x, y, w, col_w, header, rows, size=11, header_fill=BLUE, row_h=1.5, first_col_bold=False):
    gf = slide.shapes.add_table(len(rows) + 1, len(header), Cm(x), Cm(y), Cm(w), Cm(row_h * (len(rows) + 1)))
    t = gf.table
    tblPr = t._tbl.tblPr
    for a in ("firstRow", "bandRow"):
        tblPr.set(a, "0")
    for i, cw in enumerate(col_w):
        t.columns[i].width = Cm(cw)
    for ci, htext in enumerate(header):
        style_cell(t.cell(0, ci), htext, size + 1, bold=True, fill=header_fill,
                   color=RGBColor.from_string("00314D") if header_fill in (GREEN, YELLOW) else WHITE)
    t.rows[0].height = Cm(1.0)
    for ri, row in enumerate(rows, 1):
        t.rows[ri].height = Cm(row_h)
        for ci, text in enumerate(row):
            style_cell(t.cell(ri, ci), text, size, bold=(first_col_bold and ci == 0),
                       fill=CARD if ri % 2 else RGBColor.from_string("00496F"))
            flat = " ".join(text) if isinstance(text, list) else text
            if est_height_cm([flat], col_w[ci] - 0.5, size) > row_h + 0.6:
                warnings.append(f"table cell may be tall: {flat[:40]}")
    return gf


# ================================================================================================
# Slide 1 - title
# ================================================================================================
s = S[0]
add_text(s, 4.7, 11.6, 16.1, 1.2, ["Prepared by Manthan Vijay Sankpal  |  Tata iQ Data Analytics Job Simulation  |  October 2026"],
         size=10, color=LIGHT, align=PP_ALIGN.CENTER)
notes(s, "Purpose: a high-level concept for an autonomous but responsible AI-powered collections system for Geldium. It builds on the EDA (Task 1), the "
         "predictive model plan (Task 2) and the stakeholder recommendation (Task 3). This is a strategy, not a technical architecture.")

# ================================================================================================
# Slide 2 - how the system works (4-part flow)
# ================================================================================================
s = S[1]
title(s, "How It Works: Data, Decision, Action, Learning")
drop_body(s)
cw, gap, y0, ch = 5.2, 0.8, 4.0, 8.7
cards = [("DATA", BLUE, ["Repayment history: late and missed payments (Month_1-6)",
                         "Credit utilization and debt-to-income",
                         "Credit score, account tenure, loan balance",
                         "Cleaned and validated first; age and location held out and used only for fairness audits"]),
         ("DECISION", GREEN, ["Calibrated logistic regression scores each account: probability of delinquency",
                              "Score maps to a risk tier: Low, Medium, High",
                              "Top 3 plain-language reason codes per customer",
                              "A challenger model runs in the background"]),
         ("ACTION", BLUE, ["Low: automated friendly reminder",
                           "Medium: early outreach with flexible due date or payment plan",
                           "High: case routed to a human specialist",
                           "Channel and timing follow customer preference"]),
         ("LEARNING", GREEN, ["Log every outcome: paid, promise kept, delinquent",
                              "Random hold-out group measures true impact",
                              "Retrain on schedule; monitor drift and fairness",
                              "People approve any model or policy change"])]
for i, (name, col, bl) in enumerate(cards):
    x = 1.1 + i * (cw + gap)
    card(s, x, y0, cw, ch, name, bl, accent=col, size=11, badge=str(i + 1))
    if i < 3:
        arrow(s, x + cw + 0.05, y0 + ch / 2 - 0.5, w=0.7, h=1.0, color=YELLOW)
notes(s, "Walk left to right. Data: the five predictors from the Task 2 plan, validated before use. Decision: a simple, explainable model gives a calibrated risk "
         "probability and reason codes. Action: the tier decides the treatment, and the Task 3 pilot (early outreach to customers with debt-to-income above 40%) is "
         "the first Medium-tier action. Learning: a random hold-out group lets us measure what actually works, and the loop feeds the next retraining.")

# ================================================================================================
# Slide 3 - decision logic (re-using the template's spare slide), moved to position 3
# ================================================================================================
s = S[5]
title(s, "Decision Logic: From Risk Score to Action")
drop_body(s)
table(s, 1.1, 3.9, 23.2, [2.6, 7.0, 8.2, 5.4],
      ["Risk tier", "Example trigger (illustrative)", "Automated action", "Escalation"],
      [["Low", "Probability below about 10%", "Friendly reminder before the due date (SMS or e-mail)", "Only if the customer replies or asks for help"],
       ["Medium", "About 10-30%, e.g. debt-to-income above 40% and no missed payment yet", "Early outreach: affordability check, flexible due date, payment-plan offer",
        "Specialist call if no response within 7 days"],
       ["High", "Above about 30%, or a payment already missed", "Automated messages paused; case opened for a human specialist",
        "Specialist agrees the plan; manager approves exceptions"]],
      size=11, row_h=2.0, first_col_bold=True)
add_text(s, 1.1, 10.8, 11.4, 2.4,
         [("Learning loop: ", "each contact is logged, outcomes are compared with a random hold-out group, and results feed the monthly model and policy review.")],
         size=11, color=WHITE)
add_text(s, 12.9, 10.8, 11.4, 2.4,
         [("Go-live gates: ", "(1) resolve the data contradictions found in the EDA; (2) pass a 90-day controlled pilot. Thresholds are set from the cost of each error and a fairness review.")],
         size=11, color=WHITE)
notes(s, "Tier thresholds are illustrative; Geldium would set them from the cost of a missed delinquent versus an unnecessary contact, and after a fairness review. "
         "Two gates protect the business: the Task 1 EDA found contradictions and no statistical signal in the sample, so the data must be validated and the pilot must "
         "prove the effect before the system acts at scale.")
# move this slide to position 3 (index 2)
lst = prs.slides._sldIdLst
ids = list(lst)
lst.remove(ids[5])
lst.insert(2, ids[5])

# ================================================================================================
# Slide 4 - role of agentic AI
# ================================================================================================
s = S[2]
title(s, "Agentic AI: Autonomous vs. Human Oversight")
drop_body(s)
table(s, 1.1, 3.9, 23.2, [11.6, 11.6], ["Autonomous (AI agent acts on its own)", "Human Oversight (people decide or approve)"],
      [["Score all accounts daily and assign risk tiers", "Approve the model, thresholds and policy changes"],
       ["Send standard reminders and due-date nudges", "Handle High-risk and potentially vulnerable customers"],
       ["Choose contact channel and timing from customer preference", "Approve exceptions: fee waivers, settlements, write-offs"],
       ["Offer pre-approved options: flexible due date, payment plan", "Resolve disputes and complaints; review flagged explanations"],
       ["Log outcomes and run controlled A/B tests", "Review fairness audits and sign off on retraining"]],
      size=11.5, row_h=1.35)
bar = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Cm(1.1), Cm(11.7), Cm(23.2), Cm(1.5))
bar.fill.solid()
bar.fill.fore_color.rgb = YELLOW
bar.line.fill.background()
bar.shadow.inherit = False
tf = bar.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
r = p.add_run()
r.text = "Rule: the AI never takes irreversible or adverse actions on its own (legal action, credit reporting, limit cuts)."
r.font.bold, r.font.size, r.font.name, r.font.color.rgb = True, Pt(12), "Arial", RGBColor.from_string("00314D")
notes(s, "Agentic AI handles the high-volume, low-risk, reversible work: scoring, reminders, channel and timing, and logging. People stay in control of anything "
         "that is high-stakes, exceptional or irreversible, and of changes to the system itself. This keeps the speed of automation without losing accountability.")

# ================================================================================================
# Slide 5 - responsible AI guardrails
# ================================================================================================
s = S[3]
title(s, "Responsible AI Guardrails")
drop_body(s)
cw, gap, ch = 11.2, 0.8, 4.2
g = [("Fairness", BLUE, ["Age and location excluded from the model; audited every month by age band, location, employment and card type",
                         "Flag-rate ratio at least 0.80 and similar error rates across groups; mitigation plan if breached"]),
     ("Explainability", GREEN, ["Top 3 plain-language reasons for every decision",
                                "Simple, auditable model; any customer can ask why they were contacted"]),
     ("Compliance and privacy", GREEN, ["Follows applicable fair-lending and debt-collection rules (e.g. ECOA, FDCPA in the US), including contact limits",
                                        "Minimum data, access controls and a full audit trail of every action"]),
     ("Oversight and monitoring", BLUE, ["Human review of High-risk cases; kill switch to pause automation",
                                         "Track drift, calibration and complaints; named owner; quarterly review"])]
for i, (name, col, bl) in enumerate(g):
    x = 1.1 + (i % 2) * (cw + gap)
    y = 3.9 + (i // 2) * (ch + 0.5)
    card(s, x, y, cw, ch, name, bl, accent=col, size=11)
notes(s, "Four guardrails. Fairness: protected attributes are not inputs but are audited, because other fields can act as proxies. Explainability: reason codes and a "
         "simple model make every decision traceable. Compliance and privacy: rules are applied in code and logged. Oversight: people can always pause the system. "
         "The exact regulations depend on Geldium's jurisdiction and should be confirmed with compliance.")

# ================================================================================================
# Slide 6 - expected business impact
# ================================================================================================
s = S[4]
title(s, "Expected Business Impact")
drop_body(s)
card(s, 1.1, 3.9, 11.2, 7.9, "Business KPIs", [
    "Delinquency rate: pilot goal of 5 points lower in contacted customers (about 19% to 14%)",
    "Roll rate into delinquency: lower",
    "Cost to collect per account: lower, with fewer late-stage calls",
    "Promise-to-pay kept and contact success: higher",
    "Share of low and medium-risk accounts handled automatically: higher",
    "Model quality: ROC-AUC of at least 0.70 on validated data; fairness ratio at least 0.80"], accent=BLUE, size=11)
card(s, 13.1, 3.9, 11.2, 7.9, "Customer outcomes", [
    "Help arrives earlier, before a payment is missed",
    "Relevant, respectful, less intrusive contact",
    "Clear plain-language reasons for every contact",
    "Consistent, fair treatment across customer groups",
    "Easier access to flexible payment options",
    "Fewer complaints and stronger trust in Geldium"], accent=GREEN, size=11)
add_text(s, 1.1, 12.0, 23.2, 1.2,
         ["Figures are pilot goals, not forecasts: the sample data showed weak predictive signal (Task 1), so impact must be proven in the controlled pilot."],
         size=10, color=LIGHT)
notes(s, "Left: the measurable business outcomes, each with a baseline from the pilot's control group. Right: what customers experience. The headline goal is the Task 3 "
         "target of a 5-point reduction in delinquency among contacted customers. These are goals to validate, not promises, because the Task 1 data could not yet confirm the predictors.")

# ================================================================================================
# Slide 7 - roadmap (new slide)
# ================================================================================================
s = prs.slides.add_slide(prs.slide_layouts.get_by_name("TITLE_AND_BODY"))
title(s, "Roadmap and Decision Gates")
drop_body(s)
phases = [("0  Validate data", "Oct-Nov 2026", ["Resolve data contradictions", "Confirm delinquency definition", "Fairness baseline"]),
          ("1  Controlled pilot", "Dec 2026-Feb 2027", ["Early outreach for debt-to-income above 40%", "Random control group", "Gate: 5-point reduction, p < 0.05"]),
          ("2  Limited rollout", "Mar-Jun 2027", ["Automate Low and Medium tiers", "Humans keep High tier", "Monthly fairness audit"]),
          ("3  Scale and improve", "From Jul 2027", ["Retrain and challenger tests", "Quarterly governance review", "Add richer data (days past due)"])]
cw, gap = 5.2, 0.8
for i, (name, when, bl) in enumerate(phases):
    x = 1.1 + i * (cw + gap)
    card(s, x, 3.9, cw, 6.2, name, [f"{when}"] + bl, accent=GREEN if i % 2 else BLUE, size=11)
    if i < 3:
        arrow(s, x + cw + 0.05, 6.5, w=0.7, h=1.0, color=YELLOW)
add_text(s, 1.1, 10.6, 23.2, 2.4,
         [("Decision requested: ", "approve the data-validation work and the 90-day controlled pilot. Scale-up is decided only at the gate, on measured results and a passed fairness review.")],
         size=13, color=WHITE)
notes(s, "Indicative timeline. Each phase ends at a gate: no automation scales until the data is validated, the pilot shows a real effect, and the fairness audit passes. "
         "The ask today is approval for phases 0 and 1.")

prs.core_properties.title = "AI-Powered Collections Strategy - Geldium"
prs.core_properties.author = "Manthan Vijay Sankpal"
out = HERE / "Geldium_AI_Collections_Strategy.pptx"
prs.save(out)
print("saved", out.name, "| slides:", len(prs.slides))
print("fit warnings:", warnings or "none")
