"""Generate SD Worx-style sample PDFs for the demo (all content is fictional).

    venv/bin/pip install reportlab
    venv/bin/python samples/generate_samples.py

The set is built to exercise the app: a current procedure vs. a legacy FAQ that contradicts it,
a country-scoped NL guide, and a client-specific annex that overrides the general BE calendar.
"""
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

OUT = os.path.dirname(os.path.abspath(__file__))

BRAND = colors.HexColor("#E4003A")
INK = colors.HexColor("#1F2430")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#D9DCE3")
TINT = colors.HexColor("#F4F5F8")
NOTE_BG = colors.HexColor("#FFF4E5")
NOTE_EDGE = colors.HexColor("#F0A43A")

S = {
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=19, leading=23,
                            textColor=INK, spaceAfter=3),
    "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=10.5, leading=14,
                               textColor=MUTED, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK,
                         spaceBefore=12, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5,
                           textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, leading=13.5,
                             textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.8, leading=11.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5,
                            textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5,
                            textColor=colors.white),
    "note": ParagraphStyle("note", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK),
    "q": ParagraphStyle("q", fontName="Helvetica-Bold", fontSize=10, leading=13.5, textColor=INK,
                        spaceBefore=8, spaceAfter=3),
}


# --- page furniture ---------------------------------------------------------------------------

def _furniture(meta):
    def draw(canvas, doc):
        w, h = A4
        canvas.saveState()
        # header: wordmark + document type
        canvas.setFillColor(BRAND)
        canvas.rect(0, h - 6 * mm, w, 6 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 15)
        canvas.setFillColor(INK)
        canvas.drawString(18 * mm, h - 17 * mm, "SD")
        canvas.setFillColor(BRAND)
        canvas.drawString(18 * mm + canvas.stringWidth("SD ", "Helvetica-Bold", 15), h - 17 * mm,
                          "Worx")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 18 * mm, h - 14 * mm, meta["doc_type"].upper())
        canvas.drawRightString(w - 18 * mm, h - 18 * mm, f"{meta['doc_id']}  ·  v{meta['version']}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, h - 22 * mm, w - 18 * mm, h - 22 * mm)
        # footer
        canvas.line(18 * mm, 16 * mm, w - 18 * mm, 16 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 11 * mm,
                          f"{meta['classification']}  ·  Fictional sample for the Tectonic hackathon")
        canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {doc.page}")
        if meta.get("watermark"):
            canvas.setFont("Helvetica-Bold", 60)
            canvas.setFillColor(colors.Color(0.85, 0.1, 0.2, alpha=0.08))
            canvas.translate(w / 2, h / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, meta["watermark"])
        canvas.restoreState()
    return draw


def _control_block(meta):
    rows = [(k, v) for k, v in meta["control"]]
    data = []
    for i in range(0, len(rows), 2):
        pair = rows[i:i + 2]
        line = []
        for k, v in pair:
            line += [Paragraph(k, S["cellb"]), Paragraph(v, S["cell"])]
        while len(line) < 4:
            line.append("")
        data.append(line)
    t = Table(data, colWidths=[30 * mm, 55 * mm, 30 * mm, 59 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBEFORE", (2, 0), (2, -1), 0.6, RULE),
    ]))
    return t


def _table(rows, widths):
    data = [[Paragraph(c, S["cellh"]) for c in rows[0]]]
    data += [[Paragraph(c, S["cell"]) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TINT]),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _note(text, label="Note"):
    t = Table([[Paragraph(f"<b>{label}.</b> {text}", S["note"])]], colWidths=[174 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NOTE_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, NOTE_EDGE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def build(filename, meta, blocks):
    """blocks: list of (kind, payload) — h2, p, bullets, table, note, qa."""
    story = [Paragraph(meta["title"], S["title"]), Paragraph(meta["subtitle"], S["subtitle"]),
             _control_block(meta), Spacer(1, 6)]
    for kind, payload in blocks:
        if kind == "h2":
            story.append(Paragraph(payload, S["h2"]))
        elif kind == "p":
            story.append(Paragraph(payload, S["body"]))
        elif kind == "bullets":
            story += [Paragraph(b, S["bullet"], bulletText="•") for b in payload]
            story.append(Spacer(1, 4))
        elif kind == "table":
            rows, widths = payload
            story += [_table(rows, widths), Spacer(1, 8)]
        elif kind == "note":
            story += [Spacer(1, 2), _note(*payload) if isinstance(payload, tuple) else _note(payload),
                      Spacer(1, 8)]
        elif kind == "qa":
            q, a = payload
            story.append(KeepTogether([Paragraph(q, S["q"]), Paragraph(a, S["body"])]))
    doc = SimpleDocTemplate(os.path.join(OUT, filename), pagesize=A4, leftMargin=18 * mm,
                            rightMargin=18 * mm, topMargin=28 * mm, bottomMargin=22 * mm,
                            title=meta["title"], author="SD Worx (fictional sample)",
                            subject=meta["subtitle"])
    furniture = _furniture(meta)
    doc.build(story, onFirstPage=furniture, onLaterPages=furniture)
    print("wrote", filename)


# --- documents --------------------------------------------------------------------------------

def be_departure_holiday_pay():
    meta = {
        "title": "Departure Holiday Pay — Belgium",
        "subtitle": "Payroll procedure for calculating holiday pay when a white-collar employee "
                    "leaves the company",
        "doc_type": "Payroll procedure", "doc_id": "PAY-BE-PRC-014", "version": "4.2",
        "classification": "Internal",
        "control": [
            ("Country", "Belgium (BE)"), ("Applies to", "All BE clients, white-collar statute"),
            ("Product", "Payroll"), ("Effective from", "1 January 2026"),
            ("Owner", "Payroll Expertise Centre BE"), ("Supersedes", "PAY-BE-PRC-014 v4.1; "
                                                       "Payroll FAQ 2021 Q7"),
        ],
    }
    blocks = [
        ("h2", "1. Purpose"),
        ("p", "This procedure describes how payroll consultants calculate the <b>departure holiday "
              "pay</b> (<i>vertrekvakantiegeld / pécule de vacances de sortie</i>) owed to a "
              "white-collar employee whose contract ends. It replaces all earlier guidance, "
              "including question 7 of the 2021 Payroll FAQ, which is no longer correct."),
        ("h2", "2. Principle"),
        ("p", "On leaving, the employer settles the holiday pay the employee has earned but not "
              "yet received. Two periods are always taken into account:"),
        ("bullets", [
            "<b>Previous calendar year (N-1)</b> — rights vested through work in the prior year "
            "and not yet paid out through holidays taken in the current year.",
            "<b>Current calendar year (N)</b> — rights accrued from 1 January up to and including "
            "the last day of employment.",
        ]),
        ("p", "Each period is settled at <b>15.34%</b> of the gross earnings of that period: "
              "7.67% simple holiday pay plus 7.67% double holiday pay. Holiday pay already paid for "
              "days taken in year N is deducted from the N-1 amount."),
        ("h2", "3. Rates and bases"),
        ("table", ([
            ["Component", "Rate", "Basis", "Remarks"],
            ["Simple departure holiday pay", "7.67%", "Gross earnings of the period, incl. "
             "variable pay", "Paid with the final salary"],
            ["Double departure holiday pay", "7.67%", "Same basis as above",
             "Subject to the special holiday-pay withholding tax scale"],
            ["Total per period", "15.34%", "Per period (N-1 and N)", "Pro-rated automatically "
             "for part-time work via the earnings basis"],
        ], [44, 18, 56, 56])),
        ("h2", "4. Worked example"),
        ("p", "An employee earns € 3,600 gross per month, full-time, and leaves on 30 April 2026. "
              "In 2026 the employee already took 5 holiday days, paid as normal salary."),
        ("table", ([
            ["Step", "Calculation", "Amount"],
            ["Earnings N-1 (2025)", "12 × € 3,600", "€ 43,200.00"],
            ["Departure holiday pay N-1", "€ 43,200 × 15.34%", "€ 6,626.88"],
            ["Less: holiday pay for 5 days taken in 2026", "per payroll records", "− € 1,080.00"],
            ["Earnings N (Jan–Apr 2026)", "4 × € 3,600", "€ 14,400.00"],
            ["Departure holiday pay N", "€ 14,400 × 15.34%", "€ 2,208.96"],
            ["<b>Total departure holiday pay</b>", "", "<b>€ 7,755.84</b>"],
        ], [70, 64, 40])),
        ("note", ("Consultants regularly calculate only year N (\"rights reset each January\"). "
                  "This is wrong and leads to underpayment. Always include N-1.", "Common mistake")),
        ("h2", "5. Holiday certificate"),
        ("p", "Together with the final pay slip the employer issues the <b>holiday certificate</b> "
              "(<i>vakantieattest</i>) for years N-1 and N. The next employer uses it to avoid paying "
              "the same holiday days twice. The certificate is generated automatically in the payroll "
              "engine once the leaving date is registered."),
        ("h2", "6. Blue-collar employees"),
        ("p", "Blue-collar holiday pay is paid by the holiday fund (RJV/ONVA or a sector fund), not "
              "by the employer. This procedure does not apply to them."),
        ("h2", "7. Change history"),
        ("table", ([
            ["Version", "Date", "Change"],
            ["4.2", "January 2026", "Clarified deduction of holiday days already taken in year N."],
            ["4.1", "March 2024", "Added worked example; aligned with holiday certificate flow."],
            ["4.0", "June 2022", "Corrected rule: N-1 must be included (FAQ 2021 Q7 withdrawn)."],
        ], [20, 30, 124])),
    ]
    build("sdworx-be-departure-holiday-pay.pdf", meta, blocks)


def payroll_faq_2021():
    meta = {
        "title": "Payroll FAQ — Belgium",
        "subtitle": "Frequently asked questions from client helpdesk tickets, compiled for new "
                    "payroll consultants",
        "doc_type": "FAQ", "doc_id": "KB-BE-FAQ-003", "version": "1.3",
        "classification": "Internal",
        "control": [
            ("Country", "Belgium (BE)"), ("Applies to", "All clients"),
            ("Product", "Payroll"), ("Published", "September 2021"),
            ("Owner", "—"), ("Status", "Not reviewed since publication"),
        ],
    }
    blocks = [
        ("p", "This FAQ collects the questions our helpdesk receives most often. Answers are kept "
              "short on purpose; check the relevant procedure for details."),
        ("qa", ("Q1. When is the payroll cut-off for monthly paid employees?",
                "Variable data (overtime, absences, new hires) must reach us by the <b>25th of the "
                "month</b> at the latest. Data received later is processed in the next month.")),
        ("qa", ("Q2. When is double holiday pay paid?",
                "Double holiday pay for white-collar employees is paid in May or June and equals "
                "92% of one month's gross salary.")),
        ("qa", ("Q3. Are meal vouchers subject to social security?",
                "No, provided the legal conditions are met (maximum employer contribution, employee "
                "contribution of at least € 1.09, one voucher per day worked).")),
        ("qa", ("Q4. How do we register an employee on sick leave?",
                "Enter the absence with code 'ZK' in the portal. A medical certificate must be "
                "received within two working days, unless the work regulations say otherwise.")),
        ("qa", ("Q5. Can a client change the pay date?",
                "Yes, via a change request to the account manager, at least one month in advance.")),
        ("qa", ("Q6. What happens with company car benefits when an employee leaves?",
                "The benefit in kind is calculated up to the last day on which the car was available "
                "to the employee.")),
        ("qa", ("Q7. How is holiday pay calculated when someone leaves?",
                "It is calculated on the <b>current calendar year's earnings only</b>. Take the gross "
                "earnings from January up to the leaving date and apply the <b>7.67%</b> rate. The "
                "previous year is not relevant because holiday rights reset each January.")),
        ("qa", ("Q8. Who do I contact for questions not in this FAQ?",
                "Post the question in the Payroll BE Teams channel.")),
    ]
    build("sdworx-be-payroll-faq-2021.pdf", meta, blocks)


def nl_holiday_allowance():
    meta = {
        "title": "Holiday Allowance (Vakantiegeld) — Netherlands",
        "subtitle": "Guide for payroll consultants handling Dutch employment contracts",
        "doc_type": "Guideline", "doc_id": "PAY-NL-GDL-007", "version": "2.0",
        "classification": "Internal",
        "control": [
            ("Country", "Netherlands (NL)"), ("Applies to", "All NL clients"),
            ("Product", "Payroll"), ("Effective from", "1 June 2025"),
            ("Owner", "Payroll Expertise Centre NL"), ("Next review", "June 2026"),
        ],
    }
    blocks = [
        ("note", ("This guide applies to Dutch employment contracts only. Belgian holiday pay "
                  "(enkel/dubbel vakantiegeld) follows completely different rules — see "
                  "PAY-BE-PRC-014.", "Scope")),
        ("h2", "1. Statutory rule"),
        ("p", "Every employee in the Netherlands is entitled to a holiday allowance of at least "
              "<b>8% of gross annual salary</b> (Wet minimumloon en minimumvakantiebijslag). A "
              "collective labour agreement (CAO) or the employment contract may grant more, never "
              "less."),
        ("h2", "2. Accrual and payment"),
        ("bullets", [
            "The allowance accrues over the reference period <b>1 June to 31 May</b>.",
            "It is paid out <b>once a year, in May or June</b>, unless the contract provides for "
            "monthly payment.",
            "On termination, the accrued but unpaid allowance is paid with the final salary.",
        ]),
        ("h2", "3. Basis"),
        ("table", ([
            ["Element", "Included in basis?", "Remarks"],
            ["Fixed monthly salary", "Yes", ""],
            ["Structural overtime", "Yes", "If agreed in contract or CAO"],
            ["Incidental overtime", "No", "Unless the CAO says otherwise"],
            ["Bonus / 13th month", "No", "Unless the CAO says otherwise"],
            ["Salary above 3× minimum wage", "Optional", "Employer may cap the basis"],
        ], [56, 36, 82])),
        ("h2", "4. Example"),
        ("p", "An employee earns € 4,000 gross per month. Annual basis: 12 × € 4,000 = € 48,000. "
              "Holiday allowance: € 48,000 × 8% = <b>€ 3,840</b>, paid in May."),
    ]
    build("sdworx-nl-holiday-allowance.pdf", meta, blocks)


def be_payroll_calendar_2026():
    meta = {
        "title": "Payroll Calendar 2026 — Belgium",
        "subtitle": "Standard cut-off and pay dates for monthly payroll, standard service level",
        "doc_type": "Service calendar", "doc_id": "OPS-BE-CAL-2026", "version": "1.0",
        "classification": "Client-facing",
        "control": [
            ("Country", "Belgium (BE)"), ("Applies to", "Clients on the standard service level"),
            ("Product", "Payroll"), ("Valid for", "Calendar year 2026"),
            ("Owner", "Client Operations BE"), ("Published", "November 2025"),
        ],
    }
    months = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
    cutoff = ["20 Jan", "20 Feb", "20 Mar", "20 Apr", "20 May", "19 Jun", "20 Jul", "20 Aug",
              "18 Sep", "20 Oct", "20 Nov", "15 Dec"]
    pay = ["30 Jan", "27 Feb", "31 Mar", "30 Apr", "29 May", "30 Jun", "31 Jul", "31 Aug",
           "30 Sep", "30 Oct", "30 Nov", "23 Dec"]
    blocks = [
        ("h2", "1. Standard rule"),
        ("p", "For clients on the standard service level, variable payroll data (hours, absences, "
              "new hires, leavers, bonuses) must be submitted in the portal by the <b>20th of the "
              "month, 17:00 CET</b>. When the 20th falls on a weekend or public holiday, the cut-off "
              "is the last working day before it. December has an early cut-off because of the "
              "holiday period."),
        ("p", "Client-specific agreements in a signed service annex take precedence over this "
              "calendar."),
        ("h2", "2. Calendar"),
        ("table", ([["Month", "Data cut-off (17:00)", "Pay date"]] +
                   [[m, c, p] for m, c, p in zip(months, cutoff, pay)], [60, 57, 57])),
        ("h2", "3. Late data"),
        ("p", "Data received after the cut-off is processed in the next monthly run. An off-cycle "
              "run can be requested at the rate in the client's price list."),
    ]
    build("sdworx-be-payroll-calendar-2026.pdf", meta, blocks)


def be_client_annex_northwind():
    meta = {
        "title": "Service Annex — Northwind Logistics NV",
        "subtitle": "Client-specific payroll arrangements (annex 3 to the service agreement)",
        "doc_type": "Client annex", "doc_id": "CLI-BE-NWL-A3", "version": "1.1",
        "classification": "Confidential — client specific",
        "control": [
            ("Client", "Northwind Logistics NV (fictional)"), ("Country", "Belgium (BE)"),
            ("Product", "Payroll"), ("Effective from", "1 March 2026"),
            ("Owner", "Account team Northwind"), ("Signed", "12 February 2026"),
        ],
    }
    blocks = [
        ("p", "This annex records the arrangements agreed with Northwind Logistics NV that deviate "
              "from SD Worx standard service levels. Where this annex and a general procedure or "
              "calendar differ, <b>this annex prevails for Northwind only</b>."),
        ("h2", "1. Payroll cut-off"),
        ("p", "Because Northwind runs a 24/7 warehouse operation with shift premiums calculated at "
              "month end, the variable-data cut-off is <b>the 25th of the month, 12:00 CET</b>, "
              "instead of the standard 20th. Pay date remains the last working day of the month."),
        ("h2", "2. Shift premiums"),
        ("table", ([
            ["Shift", "Hours", "Premium"],
            ["Early", "06:00 – 14:00", "4% of hourly wage"],
            ["Late", "14:00 – 22:00", "8% of hourly wage"],
            ["Night", "22:00 – 06:00", "18% of hourly wage"],
            ["Sunday", "Any", "100% (paid as overtime)"],
        ], [40, 50, 84])),
        ("h2", "3. Reporting"),
        ("bullets", [
            "Monthly payroll journal delivered to Northwind Finance by the 3rd working day.",
            "Quarterly absence report per site (Antwerp, Liège, Genk).",
        ]),
        ("h2", "4. Contacts"),
        ("p", "Questions about this annex go to the Northwind account team. The client-side "
              "contact is the HR Operations Manager."),
    ]
    build("sdworx-be-northwind-service-annex.pdf", meta, blocks)


if __name__ == "__main__":
    be_departure_holiday_pay()
    payroll_faq_2021()
    nl_holiday_allowance()
    be_payroll_calendar_2026()
    be_client_annex_northwind()
