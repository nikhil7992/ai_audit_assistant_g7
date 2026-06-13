"""
src/data/generate_synthetic_data.py
Generates realistic synthetic invoices and reimbursement forms as PDFs
(via reportlab) plus matching JSON sidecars and OCR output stubs.

Data folder layout produced (matches v1 images exactly)
─────────────────────────────────────────────────────────
  app/data/
    ├── generate_synthetic_data.py    ← this file
    ├── generate_policies.py
    ├── forms/
    │   ├── FORM-001-ALICE.json       ground-truth sidecar
    │   ├── FORM-001-ALICE.pdf        rendered reimbursement form
    │   ├── FORM-002-BOB.json / .pdf
    │   ├── FORM-003-CAROL.json / .pdf
    │   └── FORM-004-DAVID.json / .pdf
    ├── invoices/
    │   ├── INV-AIR-001.json / .pdf
    │   ├── INV-DUP-COPY-001.json / .pdf
    │   ├── INV-DUP-NEAR-001.json / .pdf
    │   ├── INV-DUP-ORIG-001.json / .pdf
    │   ├── INV-HIGH-VALUE-001.json / .pdf
    │   ├── INV-HOTEL-001.json / .pdf
    │   ├── INV-HOTEL-VIOL-001.json / .pdf
    │   ├── INV-LATE-001.json / .pdf
    │   ├── INV-MEAL-001.json / .pdf
    │   ├── INV-MEAL-VIOL-001.json / .pdf
    │   ├── INV-PROHIBIT-001.json / .pdf
    │   ├── INV-SUPPLY-001.json / .pdf
    │   ├── INV-TECH-001.json / .pdf
    │   └── INV-TRANS-001.json / .pdf   (14 invoices x 2 files = 28)
    ├── ocr_output/
    │   ├── FORM-001-ALICE_ocr.json   pre-populated OCR stub
    │   ├── FORM-002-BOB_ocr.json
    │   ├── FORM-003-CAROL_ocr.json
    │   ├── FORM-004-DAVID_ocr.json
    │   ├── INV-AIR-001_ocr.json
    │   ├── INV-DUP-COPY-001_ocr.json
    │   ├── INV-DUP-NEAR-001_ocr.json
    │   ├── INV-DUP-ORIG-001_ocr.json
    │   ├── INV-HIGH-VALUE-001_ocr.json
    │   ├── INV-HOTEL-001_ocr.json
    │   ├── INV-HOTEL-VIOL-001_ocr.json
    │   ├── INV-LATE-001_ocr.json
    │   ├── INV-MEAL-001_ocr.json
    │   ├── INV-MEAL-VIOL-001_ocr.json
    │   ├── INV-PROHIBIT-001_ocr.json
    │   ├── INV-SUPPLY-001_ocr.json
    │   ├── INV-TECH-001_ocr.json
    │   └── INV-TRANS-001_ocr.json    (18 _ocr.json files total)
    └── policies/
        └── PP-001_Vendor_Gifts.txt ... TP-010_International_Travel.txt (12 files)

How the data folder is used at runtime
────────────────────────────────────────
  Path A — POST /audit/sample  (no upload, no OCR call)
  ───────────────────────────────────────────────────────
  generate_all_samples()
      returns pre-structured list[dict]  (confidence = 1.0)
          │
          ▼
  ValidationAgent.validate(expense)
      builds query  →  OpenSearch k-NN  →  top-5 policy chunks
      Bedrock Claude validates  →  compliance_status + confidence_score
          │
          ▼
  DuplicateAgent.detect(expenses)
      SHA-256 exact match  +  Bedrock Titan cosine similarity
          │
          ▼
  AuditAgent.generate_report(...)
      Bedrock synthesises executive summary  →  persists to S3

  Path B — POST /audit/upload  with .json sidecar files
  ───────────────────────────────────────────────────────
  Client uploads INV-HOTEL-001.json
          │
          ▼
  OcrAgent.extract_bytes(content, "INV-HOTEL-001.json")
      detects .json extension
      calls _parse_sidecar(raw_dict)   →  confidence = 1.0  (no Textract)
      writes INV-HOTEL-001_ocr.json to ocr_output/
          │
          ▼
  ValidationAgent  →  DuplicateAgent  →  AuditAgent  (identical to Path A)

  Path C — POST /audit/upload  with .pdf files
  ─────────────────────────────────────────────
  Client uploads INV-HOTEL-001.pdf
          │
          ▼
  OcrAgent.extract_bytes(content, "INV-HOTEL-001.pdf")
      uploads to S3  →  AWS Textract AnalyzeDocument (FORMS + TABLES)
      parses key-value pairs + table cells  →  confidence 0.8-0.95
      writes INV-HOTEL-001_ocr.json to ocr_output/
          │
          ▼
  ValidationAgent  →  DuplicateAgent  →  AuditAgent  (identical to Path A)

  The ocr_output/_ocr.json files are pre-seeded from ground-truth so the
  complete data folder is ready for inspection and CI without needing live
  AWS services.

Four named employees (exact same records as v1)
────────────────────────────────────────────────
  Alice Johnson   EMP-1001   Sales        manager: Sarah Chen
  Bob Martinez    EMP-1002   Marketing    manager: Tom Wilson
  Carol Lee       EMP-1003   Engineering  manager: Jake Peters
  David Kim       EMP-1004   Finance      manager: Lisa Nguyen

14 invoice scenarios
─────────────────────
  Clean:      INV-HOTEL-001, INV-AIR-001, INV-MEAL-001, INV-TRANS-001,
              INV-TECH-001, INV-SUPPLY-001
  Violations: INV-HOTEL-VIOL-001, INV-MEAL-VIOL-001, INV-PROHIBIT-001,
              INV-HIGH-VALUE-001, INV-LATE-001
  Duplicates: INV-DUP-ORIG-001, INV-DUP-COPY-001, INV-DUP-NEAR-001

4 reimbursement forms
──────────────────────
  FORM-001-ALICE  clean trip
  FORM-002-BOB    hotel + meal violations
  FORM-003-CAROL  duplicate hotel claims
  FORM-004-DAVID  high-value tech + prohibited spa
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from src.data.fake_gen import fake

logger = logging.getLogger(__name__)

# ── reportlab is optional — PDFs are skipped gracefully if not installed ──────
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    _RL = True
except ImportError:
    _RL = False
    logger.warning(
        "reportlab not installed — PDFs will be skipped. "
        "Install with: pip install reportlab"
    )

# ── Colour palette ─────────────────────────────────────────────────────────────
if _RL:
    _DARK_BLUE   = colors.HexColor("#1a3a5c")
    _MID_BLUE    = colors.HexColor("#2e6da4")
    _LIGHT_BLUE  = colors.HexColor("#d6eaf8")
    _LIGHT_GREY  = colors.HexColor("#f2f3f4")
    _MID_GREY    = colors.HexColor("#aab7b8")


def _styles() -> dict:
    s = getSampleStyleSheet()
    return {
        "title":    ParagraphStyle("title",    fontSize=20, textColor=_DARK_BLUE,
                                   spaceAfter=4,  fontName="Helvetica-Bold",
                                   alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", fontSize=10, textColor=_MID_BLUE,
                                   spaceAfter=2,  alignment=TA_CENTER),
        "header":   ParagraphStyle("header",   fontSize=11, textColor=_DARK_BLUE,
                                   fontName="Helvetica-Bold", spaceAfter=2),
        "normal":   ParagraphStyle("normal",   fontSize=9,  spaceAfter=2),
        "small":    ParagraphStyle("small",    fontSize=8,  textColor=_MID_GREY),
        "warning":  ParagraphStyle("warning",  fontSize=9,  textColor=colors.red,
                                   fontName="Helvetica-Bold"),
    }


def _table_style(header_row: bool = True) -> "TableStyle":
    cmds = [
        ("FONTNAME",       (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",       (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
        ("GRID",           (0, 0), (-1, -1), 0.3, _MID_GREY),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
    ]
    if header_row:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), _DARK_BLUE),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ]
    return TableStyle(cmds)


# ── Invoice PDF + JSON sidecar ─────────────────────────────────────────────────
def _make_invoice(
    inv_id: str, category: str, vendor: str,
    amount: float, date: datetime, employee: dict,
    description: str, line_items: list[dict],
    output_dir: Path,
) -> dict:
    """
    Write {inv_id}.json sidecar and (if reportlab available) {inv_id}.pdf.

    line_items format: [{"desc": str, "qty": int, "unit": float}, ...]
    The JSON sidecar is what OcrAgent reads directly (Path B upload).
    The PDF is what AWS Textract processes in an end-to-end test (Path C).
    Returns the complete metadata dict.
    """
    subtotal = sum(li["qty"] * li["unit"] for li in line_items)
    tax      = round(subtotal * 0.08, 2)
    total    = round(subtotal + tax, 2)

    metadata = {
        "invoice_id":  inv_id,
        "category":    category,
        "vendor":      vendor,
        "amount":      total,
        "subtotal":    subtotal,
        "tax":         tax,
        "date":        date.strftime("%Y-%m-%d"),
        "employee":    employee,
        "description": description,
        "line_items":  line_items,
    }
    (output_dir / f"{inv_id}.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    if _RL:
        _render_invoice_pdf(inv_id, vendor, date, employee, description,
                            line_items, subtotal, tax, total, output_dir)
    return metadata


def _render_invoice_pdf(
    inv_id: str, vendor: str, date: datetime, employee: dict,
    description: str, line_items: list, subtotal: float,
    tax: float, total: float, output_dir: Path,
) -> None:
    st    = _styles()
    doc   = SimpleDocTemplate(
        str(output_dir / f"{inv_id}.pdf"), pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch,  bottomMargin=0.75*inch,
    )
    elems = []

    elems.append(Paragraph(vendor.upper(), st["title"]))
    elems.append(Paragraph("Tax Invoice / Receipt", st["subtitle"]))
    elems.append(Spacer(1, 4))
    elems.append(HRFlowable(width="100%", thickness=2, color=_DARK_BLUE))
    elems.append(Spacer(1, 8))

    meta_data = [
        ["Invoice #:", inv_id,           "Date:",         date.strftime("%B %d, %Y")],
        ["Category:", employee.get("dept",""), "Employee:", employee["name"]],
        ["Dept:",     employee["dept"],   "Employee ID:",  employee["emp_id"]],
        ["Project Code:", employee.get("project","GENERAL"),
         "Cost Centre:", employee.get("cc","CC-001")],
    ]
    mt = Table(meta_data, colWidths=[1.2*inch, 2.2*inch, 1.2*inch, 2.2*inch])
    mt.setStyle(TableStyle([
        ("FONTNAME",       (0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",       (0,0),(-1,-1),9),
        ("FONTNAME",       (0,0),(0,-1),"Helvetica-Bold"),
        ("FONTNAME",       (2,0),(2,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",      (0,0),(0,-1),_DARK_BLUE),
        ("TEXTCOLOR",      (2,0),(2,-1),_DARK_BLUE),
        ("ROWBACKGROUNDS", (0,0),(-1,-1),[colors.white,_LIGHT_GREY]),
        ("GRID",           (0,0),(-1,-1),0.3,_MID_GREY),
        ("LEFTPADDING",    (0,0),(-1,-1),6),
        ("TOPPADDING",     (0,0),(-1,-1),4),
        ("BOTTOMPADDING",  (0,0),(-1,-1),4),
    ]))
    elems.append(mt)
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Description of Service / Purchase", st["header"]))
    elems.append(Paragraph(description, st["normal"]))
    elems.append(Spacer(1, 8))

    rows = [["#", "Description", "Qty", "Unit Price", "Amount"]]
    for i, li in enumerate(line_items, 1):
        rows.append([str(i), li["desc"], str(li["qty"]),
                     f"${li['unit']:.2f}", f"${li['qty']*li['unit']:.2f}"])
    lt = Table(rows, colWidths=[0.3*inch,3.2*inch,0.5*inch,1.0*inch,1.0*inch])
    lt.setStyle(_table_style())
    elems.append(lt)
    elems.append(Spacer(1, 6))

    for label, val in [("Subtotal:", f"${subtotal:.2f}"),
                        ("Tax (8%):", f"${tax:.2f}"),
                        ("TOTAL DUE:", f"${total:.2f}")]:
        is_total = "TOTAL" in label
        tt = Table([[label, val]], colWidths=[5.5*inch, 1.5*inch])
        tt.setStyle(TableStyle([
            ("FONTNAME",    (0,0),(-1,-1),"Helvetica-Bold" if is_total else "Helvetica"),
            ("FONTSIZE",    (0,0),(-1,-1),10 if is_total else 9),
            ("TEXTCOLOR",   (0,0),(-1,-1),_DARK_BLUE if is_total else colors.black),
            ("ALIGN",       (1,0),(1,0),"RIGHT"),
            ("BACKGROUND",  (0,0),(-1,0),_LIGHT_BLUE if is_total else colors.white),
            ("TOPPADDING",  (0,0),(-1,0),4),
            ("BOTTOMPADDING",(0,0),(-1,0),4),
        ]))
        elems.append(tt)

    elems.append(Spacer(1, 12))
    elems.append(HRFlowable(width="100%", thickness=1, color=_MID_GREY))
    elems.append(Spacer(1, 4))
    elems.append(Paragraph(
        f"Vendor Address: {fake.street_address()}, {fake.city()}, "
        f"{fake.state_abbr()} {fake.zipcode()}", st["small"]))
    elems.append(Paragraph(
        f"Contact: billing@{vendor.lower().replace(' ','')[:12]}.com  |  "
        f"Phone: (555) {fake.numerify('###-####')}", st["small"]))
    elems.append(Paragraph(
        "This document is a computer-generated receipt. No signature required.",
        st["small"]))
    doc.build(elems)


# ── Reimbursement form PDF + JSON sidecar ──────────────────────────────────────
def _make_reimbursement_form(
    form_id: str, employee: dict,
    expenses: list[dict], output_dir: Path,
) -> dict:
    """
    Write {form_id}.json sidecar and (if reportlab available) {form_id}.pdf.
    expenses format: [{"date":str, "category":str, "vendor":str,
                        "amount":float, "has_receipt":bool}, ...]
    Returns the complete metadata dict.
    """
    total = sum(ex["amount"] for ex in expenses)
    meta  = {
        "form_id":         form_id,
        "employee":        employee,
        "expenses":        expenses,
        "total_claimed":   total,
        "submission_date": datetime.now().strftime("%Y-%m-%d"),
    }
    (output_dir / f"{form_id}.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    if _RL:
        _render_form_pdf(form_id, employee, expenses, total, output_dir)
    return meta


def _render_form_pdf(
    form_id: str, employee: dict, expenses: list[dict],
    total: float, output_dir: Path,
) -> None:
    st  = _styles()
    doc = SimpleDocTemplate(
        str(output_dir / f"{form_id}.pdf"), pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch,  bottomMargin=0.75*inch,
    )
    elems = []

    elems.append(Paragraph("RetailCorp Inc.", st["title"]))
    elems.append(Paragraph("EMPLOYEE EXPENSE REIMBURSEMENT REQUEST", st["subtitle"]))
    elems.append(Spacer(1, 4))
    elems.append(HRFlowable(width="100%", thickness=2, color=_DARK_BLUE))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Employee Information", st["header"]))
    info = [
        ["Name:",       employee["name"],           "Employee ID:", employee["emp_id"]],
        ["Department:", employee["dept"],            "Manager:",     employee.get("manager","N/A")],
        ["Email:",      employee.get("email",""),   "Submission Date:", datetime.now().strftime("%B %d, %Y")],
        ["Form ID:",    form_id,                    "Period:",       employee.get("period","")],
    ]
    it = Table(info, colWidths=[1.2*inch,2.2*inch,1.2*inch,2.2*inch])
    it.setStyle(TableStyle([
        ("FONTNAME",       (0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",       (0,0),(-1,-1),9),
        ("FONTNAME",       (0,0),(0,-1),"Helvetica-Bold"),
        ("FONTNAME",       (2,0),(2,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",      (0,0),(0,-1),_DARK_BLUE),
        ("TEXTCOLOR",      (2,0),(2,-1),_DARK_BLUE),
        ("ROWBACKGROUNDS", (0,0),(-1,-1),[colors.white,_LIGHT_GREY]),
        ("GRID",           (0,0),(-1,-1),0.3,_MID_GREY),
        ("LEFTPADDING",    (0,0),(-1,-1),6),
        ("TOPPADDING",     (0,0),(-1,-1),4),
        ("BOTTOMPADDING",  (0,0),(-1,-1),4),
    ]))
    elems.append(it)
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Expense Details", st["header"]))
    rows = [["#","Date","Category","Vendor / Description","Receipt?","Amount (USD)"]]
    for i, ex in enumerate(expenses, 1):
        rows.append([str(i), ex["date"], ex["category"], ex["vendor"],
                     "Yes" if ex.get("has_receipt",True) else "No",
                     f"${ex['amount']:.2f}"])
    rows.append(["","","","","TOTAL:", f"${total:.2f}"])
    et = Table(rows, colWidths=[0.3*inch,0.9*inch,1.1*inch,2.8*inch,0.7*inch,1.2*inch])
    et.setStyle(TableStyle([
        ("FONTNAME",       (0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",       (0,0),(-1,-1),9),
        ("BACKGROUND",     (0,0),(-1,0),_DARK_BLUE),
        ("FONTNAME",       (0,0),(-1,0),"Helvetica-Bold"),
        ("TEXTCOLOR",      (0,0),(-1,0),colors.white),
        ("ROWBACKGROUNDS", (0,1),(-1,-2),[colors.white,_LIGHT_GREY]),
        ("BACKGROUND",     (0,-1),(-1,-1),_LIGHT_BLUE),
        ("FONTNAME",       (0,-1),(-1,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",      (0,-1),(-1,-1),_DARK_BLUE),
        ("GRID",           (0,0),(-1,-1),0.3,_MID_GREY),
        ("ALIGN",          (5,0),(5,-1),"RIGHT"),
        ("LEFTPADDING",    (0,0),(-1,-1),6),
        ("TOPPADDING",     (0,0),(-1,-1),4),
        ("BOTTOMPADDING",  (0,0),(-1,-1),4),
    ]))
    elems.append(et)
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Business Purpose / Justification", st["header"]))
    elems.append(Paragraph(
        employee.get("purpose",
            "Expenses incurred in the ordinary course of business travel and client meetings."),
        st["normal"]))
    elems.append(Spacer(1, 12))

    elems.append(HRFlowable(width="100%", thickness=1, color=_MID_GREY))
    elems.append(Spacer(1, 6))
    sig = [
        ["Employee Signature:", "_____________________", "Date:", "_____________"],
        ["Manager Approval:",   "_____________________", "Date:", "_____________"],
    ]
    sig_t = Table(sig, colWidths=[1.5*inch,2.5*inch,0.6*inch,2.0*inch])
    sig_t.setStyle(TableStyle([
        ("FONTNAME",   (0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",   (0,0),(-1,-1),9),
        ("FONTNAME",   (0,0),(0,-1),"Helvetica-Bold"),
        ("TOPPADDING", (0,0),(-1,-1),6),
    ]))
    elems.append(sig_t)
    doc.build(elems)


# ── OCR output stub ────────────────────────────────────────────────────────────
def _write_ocr_stub(doc_id: str, metadata: dict, ocr_dir: Path) -> None:
    """
    Write {doc_id}_ocr.json to ocr_output/.

    In production the OcrAgent writes this after AWS Textract returns.
    Here we pre-populate it from the ground-truth JSON sidecar so the
    complete data folder is ready for CI/inspection without needing AWS.

    Naming convention: {DOCUMENT-ID}_ocr.json  (underscore before ocr,
    matching the filenames visible in the images).
    """
    emp = metadata.get("employee") or {}
    stub = {
        "document_id":         metadata.get("invoice_id") or metadata.get("form_id") or doc_id,
        "document_type":       "invoice" if "invoice_id" in metadata else "reimbursement_form",
        "vendor":              metadata.get("vendor", ""),
        "category":            metadata.get("category", "multiple"),
        "amount":              float(metadata.get("amount") or metadata.get("total_claimed") or 0),
        "date":                metadata.get("date") or metadata.get("submission_date") or "",
        "employee_name":       emp.get("name", ""),
        "employee_id":         emp.get("emp_id", ""),
        "department":          emp.get("dept", ""),
        "project_code":        emp.get("project", ""),
        "cost_centre":         emp.get("cc", ""),
        "description":         metadata.get("description") or emp.get("purpose", ""),
        "line_items":          metadata.get("line_items") or metadata.get("expenses") or [],
        "raw_text":            "",
        "extraction_method":   "sidecar_json",   # replaced by "aws_textract" in live runs
        "confidence":          1.0,
        "textract_confidence": 1.0,
    }
    (ocr_dir / f"{doc_id}_ocr.json").write_text(
        json.dumps(stub, indent=2), encoding="utf-8"
    )


# ── Main dataset builder ───────────────────────────────────────────────────────
def generate_all_samples(
    invoices_dir:   Path | None = None,
    forms_dir:      Path | None = None,
    ocr_output_dir: Path | None = None,
) -> dict:
    """
    Generate the complete synthetic dataset.

    When directory arguments are supplied the function writes files to disk
    (invoices/, forms/, ocr_output/) exactly matching the layout in the
    reference images.  When called without arguments (e.g. from routes.py
    for the /audit/sample endpoint) it still returns the normalised expense
    list; no disk writes occur.

    Returns
    ───────
    {
      "expenses":           list[dict],   # flat normalised expense list
      "invoices_generated": int,
      "forms_generated":    int,
      "pdfs_generated":     bool,
      "invoice_ids":        list[str],
      "form_ids":           list[str],
    }
    """
    if invoices_dir:
        Path(invoices_dir).mkdir(parents=True, exist_ok=True)
    if forms_dir:
        Path(forms_dir).mkdir(parents=True, exist_ok=True)
    if ocr_output_dir:
        Path(ocr_output_dir).mkdir(parents=True, exist_ok=True)

    today      = datetime(2026, 5, 31)         # deterministic for CI reproducibility
    last_month = today - timedelta(days=30)

    def rand_date() -> datetime:
        return fake.date_between(last_month, today)

    # ── Four named employees (exact same records as v1) ───────────────────────
    employees = [
        {"name": "Alice Johnson", "emp_id": "EMP-1001", "dept": "Sales",
         "manager": "Sarah Chen",   "email": "alice.johnson@retailcorp.com",
         "project": "PROJ-2024-Q4", "cc": "CC-101"},
        {"name": "Bob Martinez",  "emp_id": "EMP-1002", "dept": "Marketing",
         "manager": "Tom Wilson",   "email": "bob.martinez@retailcorp.com",
         "project": "PROJ-2024-MKT","cc": "CC-102"},
        {"name": "Carol Lee",     "emp_id": "EMP-1003", "dept": "Engineering",
         "manager": "Jake Peters",  "email": "carol.lee@retailcorp.com",
         "project": "PROJ-2024-TECH","cc":"CC-103"},
        {"name": "David Kim",     "emp_id": "EMP-1004", "dept": "Finance",
         "manager": "Lisa Nguyen", "email": "david.kim@retailcorp.com",
         "project": "PROJ-2024-FIN","cc": "CC-104"},
    ]
    alice, bob, carol, david = employees

    invoices_raw: list[dict] = []
    forms_raw:    list[dict] = []
    idir = Path(invoices_dir) if invoices_dir else None
    fdir = Path(forms_dir)    if forms_dir    else None
    odir = Path(ocr_output_dir) if ocr_output_dir else None

    def _inv(inv_id, category, vendor, amount, date, emp, desc, items):
        """Helper: make invoice dict (writes files only if idir is set)."""
        if idir:
            return _make_invoice(inv_id, category, vendor, amount,
                                 date, emp, desc, items, idir)
        subtotal = sum(li["qty"]*li["unit"] for li in items)
        tax      = round(subtotal*0.08, 2)
        total    = round(subtotal+tax, 2)
        return {"invoice_id": inv_id, "category": category, "vendor": vendor,
                "amount": total, "date": date.strftime("%Y-%m-%d"),
                "employee": emp, "description": desc, "line_items": items}

    def _form(form_id, emp, expenses):
        """Helper: make form dict (writes files only if fdir is set)."""
        if fdir:
            return _make_reimbursement_form(form_id, emp, expenses, fdir)
        return {"form_id": form_id, "employee": emp, "expenses": expenses,
                "total_claimed": sum(e["amount"] for e in expenses),
                "submission_date": datetime.now().strftime("%Y-%m-%d")}

    # ── Clean invoices ────────────────────────────────────────────────────────
    d = rand_date()
    inv = _inv("INV-HOTEL-001","Hotel","Marriott Hotels",220.00, d, alice,
        f"3-night business stay in Chicago for Q4 sales conference. "
        f"Checkout {(d+timedelta(3)).strftime('%B %d')}.",
        [{"desc":"Standard King Room x 3 nights","qty":3,"unit":203.70}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-HOTEL-001", inv, odir)

    inv = _inv("INV-AIR-001","Airfare","Delta Air Lines",485.00,rand_date(),bob,
        "Round-trip economy fare: Chicago to New York for client pitch meeting.",
        [{"desc":"Economy Fare ORD-JFK","qty":1,"unit":430.00},
         {"desc":"Checked Baggage Fee","qty":1,"unit":35.00}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-AIR-001", inv, odir)

    inv = _inv("INV-MEAL-001","Meal","The Capital Grille",89.50,rand_date(),carol,
        "Business dinner with 2 client prospects from Apex Retail. "
        "Discussion: Q1 partnership proposal.",
        [{"desc":"Dinner - 3 covers","qty":3,"unit":27.80},
         {"desc":"Beverages (non-alcoholic)","qty":3,"unit":4.50}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-MEAL-001", inv, odir)

    inv = _inv("INV-TRANS-001","Transport","Uber Technologies",34.20,rand_date(),david,
        "Uber from O'Hare Airport to hotel. Arrived after redeye for 8am client meeting.",
        [{"desc":"UberX Airport Transfer (ORD to Hotel)","qty":1,"unit":31.67}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-TRANS-001", inv, odir)

    inv = _inv("INV-TECH-001","Technology","Adobe Systems",54.99,rand_date(),alice,
        "Adobe Acrobat Pro monthly subscription - used for contract review and PDF generation.",
        [{"desc":"Adobe Acrobat Pro - 1 month","qty":1,"unit":50.92}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-TECH-001", inv, odir)

    inv = _inv("INV-SUPPLY-001","Office Supplies","OfficeMax",42.75,rand_date(),bob,
        "Office supplies for Q4 planning sessions: notebooks, pens, whiteboard markers.",
        [{"desc":"Moleskine Notebooks x 3","qty":3,"unit":8.99},
         {"desc":"Whiteboard Markers (set)","qty":1,"unit":12.99},
         {"desc":"Ballpoint Pens (box)","qty":1,"unit":6.78}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-SUPPLY-001", inv, odir)

    # ── Policy-violating invoices ─────────────────────────────────────────────
    inv = _inv("INV-HOTEL-VIOL-001","Hotel","The Ritz-Carlton",650.00,rand_date(),bob,
        "Luxury accommodation in New York for 2 nights. Suite upgrade included.",
        [{"desc":"Deluxe Suite x 2 nights (NYC)","qty":2,"unit":555.56},
         {"desc":"Resort and Amenity Fee","qty":2,"unit":45.00}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-HOTEL-VIOL-001", inv, odir)

    inv = _inv("INV-MEAL-VIOL-001","Meal","Nobu Restaurant",845.00,rand_date(),alice,
        "Client dinner at Nobu for Q3 deal closing celebration. 4 attendees.",
        [{"desc":"Tasting Menu x 4 covers","qty":4,"unit":175.00},
         {"desc":"Sake and Cocktails","qty":4,"unit":36.25}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-MEAL-VIOL-001", inv, odir)

    inv = _inv("INV-PROHIBIT-001","Spa & Wellness","Four Seasons Spa",320.00,rand_date(),carol,
        "Relaxation and recovery after conference travel. Deep tissue massage + steam.",
        [{"desc":"90-min Deep Tissue Massage","qty":1,"unit":250.00},
         {"desc":"Steam Room Day Pass","qty":1,"unit":46.30}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-PROHIBIT-001", inv, odir)

    inv = _inv("INV-HIGH-VALUE-001","Technology","Apple Store",6499.00,rand_date(),david,
        "MacBook Pro 16-inch M3 Max for data analysis work. Purchased without PO.",
        [{"desc":"MacBook Pro 16in M3 Max 36GB","qty":1,"unit":5499.00},
         {"desc":"AppleCare+ 3-Year Plan","qty":1,"unit":399.00},
         {"desc":"USB-C Hub Accessory","qty":1,"unit":89.00}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-HIGH-VALUE-001", inv, odir)

    old_date = today - timedelta(days=55)
    inv = _inv("INV-LATE-001","Airfare","American Airlines",399.00,old_date,alice,
        "Domestic economy fare: Chicago to Denver for supplier meeting 55 days ago.",
        [{"desc":"Economy Fare ORD-DEN","qty":1,"unit":369.44}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-LATE-001", inv, odir)

    # ── Duplicate invoices ────────────────────────────────────────────────────
    dup_date   = rand_date()
    dup_vendor = "Hilton Hotels"
    dup_amount = 245.00

    inv = _inv("INV-DUP-ORIG-001","Hotel",dup_vendor,dup_amount,dup_date,carol,
        "Business stay - original submission.",
        [{"desc":"Standard Queen Room x 1 night","qty":1,"unit":226.85}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-DUP-ORIG-001", inv, odir)

    inv = _inv("INV-DUP-COPY-001","Hotel",dup_vendor,dup_amount,dup_date,carol,
        "Business stay - duplicate submission (same receipt resubmitted).",
        [{"desc":"Standard Queen Room x 1 night","qty":1,"unit":226.85}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-DUP-COPY-001", inv, odir)

    inv = _inv("INV-DUP-NEAR-001","Hotel",dup_vendor,
        dup_amount+12.50, dup_date+timedelta(days=1), carol,
        "Business stay - possible near-duplicate (late check-out fee added).",
        [{"desc":"Standard Queen Room x 1 night","qty":1,"unit":226.85},
         {"desc":"Late Check-out Fee","qty":1,"unit":11.57}])
    invoices_raw.append(inv)
    if odir: _write_ocr_stub("INV-DUP-NEAR-001", inv, odir)

    # ── Reimbursement forms ───────────────────────────────────────────────────
    # FORM-001-ALICE: all clean
    _alice = alice.copy()
    _alice["period"]  = f"{last_month.strftime('%b %d')}-{today.strftime('%b %d, %Y')}"
    _alice["purpose"] = ("Q4 Sales Conference travel to Chicago and New York. "
                         "Expenses cover hotel, airfare, client meals, and transport "
                         "per policy TP-001/002/003.")
    alice_expenses = [
        {"date":(last_month+timedelta(2)).strftime("%Y-%m-%d"),
         "category":"Airfare","vendor":"Delta - CHI to NYC","amount":485.00,"has_receipt":True},
        {"date":(last_month+timedelta(3)).strftime("%Y-%m-%d"),
         "category":"Hotel","vendor":"Marriott Chicago","amount":220.00,"has_receipt":True},
        {"date":(last_month+timedelta(4)).strftime("%Y-%m-%d"),
         "category":"Meal","vendor":"The Capital Grille","amount":89.50,"has_receipt":True},
        {"date":(last_month+timedelta(5)).strftime("%Y-%m-%d"),
         "category":"Transport","vendor":"Uber","amount":34.20,"has_receipt":True},
    ]
    form = _form("FORM-001-ALICE", _alice, alice_expenses)
    forms_raw.append(form)
    if odir: _write_ocr_stub("FORM-001-ALICE", form, odir)

    # FORM-002-BOB: violations (hotel + meal over limit)
    _bob = bob.copy()
    _bob["period"]  = f"{last_month.strftime('%b %d')}-{today.strftime('%b %d, %Y')}"
    _bob["purpose"] = "New York client meetings Q4. Hotel and meal expenses."
    bob_expenses = [
        {"date":(last_month+timedelta(5)).strftime("%Y-%m-%d"),
         "category":"Hotel","vendor":"The Ritz-Carlton NYC","amount":650.00,"has_receipt":True},
        {"date":(last_month+timedelta(6)).strftime("%Y-%m-%d"),
         "category":"Meal","vendor":"Nobu Restaurant","amount":845.00,"has_receipt":True},
        {"date":(last_month+timedelta(7)).strftime("%Y-%m-%d"),
         "category":"Airfare","vendor":"Delta Air Lines","amount":485.00,"has_receipt":True},
    ]
    form = _form("FORM-002-BOB", _bob, bob_expenses)
    forms_raw.append(form)
    if odir: _write_ocr_stub("FORM-002-BOB", form, odir)

    # FORM-003-CAROL: duplicate claims
    _carol = carol.copy()
    _carol["period"]  = f"{last_month.strftime('%b %d')}-{today.strftime('%b %d, %Y')}"
    _carol["purpose"] = "Engineering conference travel. Multiple hotel nights."
    carol_expenses = [
        {"date":dup_date.strftime("%Y-%m-%d"),
         "category":"Hotel","vendor":"Hilton Hotels","amount":245.00,"has_receipt":True},
        {"date":dup_date.strftime("%Y-%m-%d"),
         "category":"Hotel","vendor":"Hilton Hotels","amount":245.00,"has_receipt":True},
        {"date":(dup_date+timedelta(1)).strftime("%Y-%m-%d"),
         "category":"Hotel","vendor":"Hilton Hotels","amount":257.50,"has_receipt":True},
        {"date":(dup_date+timedelta(2)).strftime("%Y-%m-%d"),
         "category":"Meal","vendor":"Local Bistro","amount":68.00,"has_receipt":True},
    ]
    form = _form("FORM-003-CAROL", _carol, carol_expenses)
    forms_raw.append(form)
    if odir: _write_ocr_stub("FORM-003-CAROL", form, odir)

    # FORM-004-DAVID: high-value tech + prohibited spa
    _david = david.copy()
    _david["period"]  = f"{last_month.strftime('%b %d')}-{today.strftime('%b %d, %Y')}"
    _david["purpose"] = "Equipment purchase and travel expenses for fiscal year-end audit."
    david_expenses = [
        {"date":(last_month+timedelta(3)).strftime("%Y-%m-%d"),
         "category":"Technology","vendor":"Apple Store","amount":6499.00,"has_receipt":True},
        {"date":(last_month+timedelta(4)).strftime("%Y-%m-%d"),
         "category":"Spa","vendor":"Four Seasons Spa","amount":320.00,"has_receipt":True},
        {"date":(last_month+timedelta(5)).strftime("%Y-%m-%d"),
         "category":"Transport","vendor":"Enterprise Rent-A-Car","amount":189.00,"has_receipt":True},
    ]
    form = _form("FORM-004-DAVID", _david, david_expenses)
    forms_raw.append(form)
    if odir: _write_ocr_stub("FORM-004-DAVID", form, odir)

    # ── Normalise to flat expense list for the audit pipeline ─────────────────
    all_expenses: list[dict] = []

    for inv in invoices_raw:
        emp = inv.get("employee", {})
        all_expenses.append({
            "document_id":       inv["invoice_id"],
            "document_type":     "invoice",
            "vendor":            inv["vendor"],
            "category":          inv["category"],
            "amount":            float(inv["amount"]),
            "date":              inv["date"],
            "employee_name":     emp.get("name",""),
            "employee_id":       emp.get("emp_id",""),
            "department":        emp.get("dept",""),
            "project_code":      emp.get("project",""),
            "cost_centre":       emp.get("cc",""),
            "description":       inv.get("description",""),
            "line_items":        inv.get("line_items",[]),
            "extraction_method": "synthetic",
            "confidence":        1.0,
        })

    for form in forms_raw:
        emp = form.get("employee", {})
        for exp in form.get("expenses", []):
            all_expenses.append({
                "document_id":       f"{form['form_id']}-{exp.get('category','').upper()[:3]}",
                "document_type":     "reimbursement_form_item",
                "vendor":            exp["vendor"],
                "category":          exp["category"],
                "amount":            float(exp["amount"]),
                "date":              exp["date"],
                "employee_name":     emp.get("name",""),
                "employee_id":       emp.get("emp_id",""),
                "department":        emp.get("dept",""),
                "project_code":      emp.get("project",""),
                "cost_centre":       emp.get("cc",""),
                "description":       exp.get("description",""),
                "line_items":        [],
                "extraction_method": "synthetic",
                "confidence":        1.0,
            })

    summary = {
        "expenses":           all_expenses,
        "invoices_generated": len(invoices_raw),
        "forms_generated":    len(forms_raw),
        "pdfs_generated":     _RL,
        "invoice_ids":        [i["invoice_id"] for i in invoices_raw],
        "form_ids":           [f["form_id"]    for f in forms_raw],
    }
    logger.info(
        "Generated %d invoices and %d forms (%d total expenses, PDFs: %s)",
        len(invoices_raw), len(forms_raw), len(all_expenses),
        "yes" if _RL else "no — install reportlab",
    )
    return summary


def get_scenario_summary() -> list[dict]:
    """
    Human-readable metadata for all 18 synthetic test cases.
    Consumed by GET /audit/scenarios.
    """
    return [
        # Clean
        {"id":"INV-HOTEL-001",      "employee":"Alice Johnson","scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-002",
         "note":"Marriott Hotels $220/night within $250 standard limit"},
        {"id":"INV-AIR-001",        "employee":"Bob Martinez", "scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-001",
         "note":"Delta Air Lines economy round-trip $485"},
        {"id":"INV-MEAL-001",       "employee":"Carol Lee",    "scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-003",
         "note":"Capital Grille 3-cover dinner $89.50 < $100/person cap"},
        {"id":"INV-TRANS-001",      "employee":"David Kim",    "scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-004",
         "note":"Uber airport transfer $34.20"},
        {"id":"INV-TECH-001",       "employee":"Alice Johnson","scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-005",
         "note":"Adobe SaaS $54.99/month within self-approval threshold"},
        {"id":"INV-SUPPLY-001",     "employee":"Bob Martinez", "scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"PP-002",
         "note":"OfficeMax supplies $42.75 < $50 quarterly self-approval"},
        # Violations
        {"id":"INV-HOTEL-VIOL-001", "employee":"Bob Martinez", "scenario":"violation",
         "expected_status":"VIOLATION",       "policy":"TP-002",
         "note":"Ritz-Carlton NYC $650/night > $350 high-cost-city limit"},
        {"id":"INV-MEAL-VIOL-001",  "employee":"Alice Johnson","scenario":"violation",
         "expected_status":"VIOLATION",       "policy":"TP-003",
         "note":"Nobu $845 / 4 attendees = $211/person > $100 cap"},
        {"id":"INV-PROHIBIT-001",   "employee":"Carol Lee",    "scenario":"violation",
         "expected_status":"CRITICAL",        "policy":"TP-007",
         "note":"Four Seasons Spa — massage is an absolute prohibition"},
        {"id":"INV-HIGH-VALUE-001", "employee":"David Kim",    "scenario":"violation",
         "expected_status":"VIOLATION",       "policy":"TP-008",
         "note":"Apple MacBook $6,499 > $5,000 CFO-approval threshold"},
        {"id":"INV-LATE-001",       "employee":"Alice Johnson","scenario":"violation",
         "expected_status":"PENDING_REVIEW",  "policy":"TP-006",
         "note":"American Airlines submitted 55 days after expense date"},
        # Duplicates
        {"id":"INV-DUP-ORIG-001",   "employee":"Carol Lee",    "scenario":"duplicate",
         "expected_status":"COMPLIANT",       "policy":"TP-009",
         "note":"Hilton Hotels $245 — original legitimate claim"},
        {"id":"INV-DUP-COPY-001",   "employee":"Carol Lee",    "scenario":"duplicate",
         "expected_status":"EXACT_DUPLICATE", "policy":"TP-009",
         "note":"Identical SHA-256 fingerprint to INV-DUP-ORIG-001"},
        {"id":"INV-DUP-NEAR-001",   "employee":"Carol Lee",    "scenario":"duplicate",
         "expected_status":"NEAR_DUPLICATE",  "policy":"TP-009",
         "note":"Hilton Hotels $257.50 / +1 day — near-duplicate"},
        # Forms
        {"id":"FORM-001-ALICE",     "employee":"Alice Johnson","scenario":"clean",
         "expected_status":"COMPLIANT",       "policy":"TP-001,TP-002,TP-003,TP-004",
         "note":"All four expense lines within policy limits"},
        {"id":"FORM-002-BOB",       "employee":"Bob Martinez", "scenario":"violation",
         "expected_status":"VIOLATION",       "policy":"TP-002,TP-003",
         "note":"Ritz-Carlton $650 + Nobu $845 both exceed limits"},
        {"id":"FORM-003-CAROL",     "employee":"Carol Lee",    "scenario":"duplicate",
         "expected_status":"NEAR_DUPLICATE",  "policy":"TP-009",
         "note":"Hilton $245 submitted twice + near-dup $257.50"},
        {"id":"FORM-004-DAVID",     "employee":"David Kim",    "scenario":"violation",
         "expected_status":"VIOLATION",       "policy":"TP-007,TP-008",
         "note":"Apple $6,499 CFO required + Four Seasons Spa prohibited"},
    ]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/data")
    result = generate_all_samples(
        invoices_dir   = base / "invoices",
        forms_dir      = base / "forms",
        ocr_output_dir = base / "ocr_output",
    )
    print(f"OK  {result['invoices_generated']} invoices, "
          f"{result['forms_generated']} forms, "
          f"PDFs: {'yes' if result['pdfs_generated'] else 'no'}")
    print("    Invoice IDs:", result["invoice_ids"])
    print("    Form IDs:   ", result["form_ids"])
