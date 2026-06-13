"""
tests/test_agents.py
Unit tests for all agents and the complete data layer.
Run: pytest app/tests/ -v
No AWS services required — all tests run fully offline.
"""
import hashlib
import json
import re
import pytest
from pathlib import Path


# ─── FakeGen ──────────────────────────────────────────────────────────────────
class TestFakeGen:
    def _gen(self):
        from app.src.data.fake_gen import FakeGen
        return FakeGen()

    def test_name_has_space(self):
        assert " " in self._gen().name()

    def test_email_has_at_and_domain(self):
        email = self._gen().company_email()
        assert "@" in email
        assert "." in email.split("@")[1]

    def test_pyfloat_stays_in_range(self):
        g = self._gen()
        for _ in range(50):
            v = g.pyfloat(10.0, 200.0)
            assert 10.0 <= v <= 200.0

    def test_numerify_replaces_hashes(self):
        result = self._gen().numerify("INV-####")
        assert result.startswith("INV-")
        assert result[4:].isdigit()

    def test_hotel_vendor_nonempty(self):
        assert len(self._gen().hotel_vendor()) > 3

    def test_airline_vendor_nonempty(self):
        assert len(self._gen().airline_vendor()) > 3

    def test_date_recent_within_window(self):
        from datetime import datetime
        d = datetime.strptime(self._gen().date_recent(7), "%Y-%m-%d")
        assert (datetime.now() - d).days <= 7

    def test_emp_id_format(self):
        assert self._gen().emp_id().startswith("EMP-")

    def test_cost_centre_format(self):
        assert self._gen().cost_centre().startswith("CC-")


# ─── Policy generation ────────────────────────────────────────────────────────
class TestGeneratePolicies:
    def test_writes_twelve_files(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        count = generate_policy_files(tmp_path)
        assert count == 12
        assert len(list(tmp_path.glob("*.txt"))) == 12

    def test_exact_filenames_match_images(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        generate_policy_files(tmp_path)
        expected = {
            "PP-001_Vendor_Gifts.txt",
            "PP-002_Office_Supplies.txt",
            "TP-001_Air_Travel.txt",
            "TP-002_Hotel_Accommodation.txt",
            "TP-003_Meals_Entertainment.txt",
            "TP-004_Ground_Transportation.txt",
            "TP-005_Technology_Equipment.txt",
            "TP-006_Submission_Deadlines.txt",
            "TP-007_Prohibited_Expenses.txt",
            "TP-008_Approval_Thresholds.txt",
            "TP-009_Duplicate_Fraud_Prevention.txt",
            "TP-010_International_Travel.txt",
        }
        actual = {f.name for f in tmp_path.glob("*.txt")}
        assert actual == expected

    def test_tp007_contains_prohibited_keywords(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        generate_policy_files(tmp_path)
        content = (tmp_path / "TP-007_Prohibited_Expenses.txt").read_text()
        for kw in ["spa", "massage", "gambling", "casino", "tobacco"]:
            assert kw in content.lower(), f"Expected '{kw}' in TP-007"

    def test_tp002_contains_hotel_limits(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        generate_policy_files(tmp_path)
        content = (tmp_path / "TP-002_Hotel_Accommodation.txt").read_text()
        assert "$250" in content
        assert "$350" in content

    def test_tp008_contains_cfo_threshold(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        generate_policy_files(tmp_path)
        content = (tmp_path / "TP-008_Approval_Thresholds.txt").read_text()
        assert "CFO" in content
        assert "5,000" in content

    def test_idempotent(self, tmp_path):
        from app.src.data.generate_policies import generate_policy_files
        generate_policy_files(tmp_path)
        generate_policy_files(tmp_path)  # second call must not raise
        assert len(list(tmp_path.glob("*.txt"))) == 12


# ─── Synthetic data generation ────────────────────────────────────────────────
class TestGenerateSyntheticData:

    def _run(self, tmp_path=None):
        from app.src.data.generate_synthetic_data import generate_all_samples
        if tmp_path:
            return generate_all_samples(
                invoices_dir   = tmp_path / "invoices",
                forms_dir      = tmp_path / "forms",
                ocr_output_dir = tmp_path / "ocr_output",
            )
        return generate_all_samples()

    # ── Summary dict shape ────────────────────────────────────────────────────
    def test_returns_summary_dict(self):
        result = self._run()
        assert isinstance(result, dict)
        for key in ("expenses","invoices_generated","forms_generated",
                    "pdfs_generated","invoice_ids","form_ids"):
            assert key in result, f"Missing key: {key}"

    def test_invoice_count_is_14(self):
        assert self._run()["invoices_generated"] == 14

    def test_form_count_is_4(self):
        assert self._run()["forms_generated"] == 4

    def test_exact_invoice_ids(self):
        expected = {
            "INV-HOTEL-001","INV-AIR-001","INV-MEAL-001","INV-TRANS-001",
            "INV-TECH-001","INV-SUPPLY-001","INV-HOTEL-VIOL-001",
            "INV-MEAL-VIOL-001","INV-PROHIBIT-001","INV-HIGH-VALUE-001",
            "INV-LATE-001","INV-DUP-ORIG-001","INV-DUP-COPY-001","INV-DUP-NEAR-001",
        }
        assert set(self._run()["invoice_ids"]) == expected

    def test_exact_form_ids(self):
        expected = {"FORM-001-ALICE","FORM-002-BOB","FORM-003-CAROL","FORM-004-DAVID"}
        assert set(self._run()["form_ids"]) == expected

    # ── Expense list content ──────────────────────────────────────────────────
    def test_all_expenses_have_required_fields(self):
        required = {"document_id","vendor","category","amount",
                    "date","employee_name","confidence"}
        for exp in self._run()["expenses"]:
            missing = required - exp.keys()
            assert not missing, f"{exp['document_id']} missing: {missing}"

    def test_all_amounts_are_positive_floats(self):
        for exp in self._run()["expenses"]:
            assert isinstance(exp["amount"], float), f"{exp['document_id']} amount not float"
            assert exp["amount"] > 0, f"{exp['document_id']} amount not positive"

    def test_all_confidence_is_1_0(self):
        for exp in self._run()["expenses"]:
            assert exp["confidence"] == 1.0

    def test_extraction_method_is_synthetic(self):
        for exp in self._run()["expenses"]:
            assert exp["extraction_method"] == "synthetic"

    # ── Specific scenarios ────────────────────────────────────────────────────
    def test_prohibited_invoice_present(self):
        expenses = self._run()["expenses"]
        spa = [e for e in expenses if e["document_id"] == "INV-PROHIBIT-001"]
        assert len(spa) == 1
        assert "spa" in spa[0].get("category","").lower() or \
               "spa" in spa[0].get("description","").lower()

    def test_high_value_invoice_exceeds_5000(self):
        expenses = self._run()["expenses"]
        hv = [e for e in expenses if e["document_id"] == "INV-HIGH-VALUE-001"]
        assert len(hv) == 1
        assert hv[0]["amount"] > 5000

    def test_late_invoice_date_is_old(self):
        from datetime import datetime
        expenses = self._run()["expenses"]
        late = [e for e in expenses if e["document_id"] == "INV-LATE-001"]
        assert len(late) == 1
        expense_date = datetime.strptime(late[0]["date"], "%Y-%m-%d")
        days_old = (datetime.now() - expense_date).days
        assert days_old > 45, f"Expected >45 days old, got {days_old}"

    def test_exact_duplicate_pair_shares_fingerprint(self):
        def fp(e):
            v = re.sub(r"\s+", " ",
                (e["vendor"] or "").lower()
                .replace(" inc","").replace(" llc",""))
            return f"{v}|{e['amount']:.2f}|{str(e['date'])[:10]}|{(e['category'] or '').lower()}"

        expenses = self._run()["expenses"]
        hashes: dict[str, list] = {}
        for e in expenses:
            h = hashlib.sha256(fp(e).encode()).hexdigest()
            hashes.setdefault(h, []).append(e["document_id"])

        dups = [ids for ids in hashes.values() if len(ids) >= 2]
        assert len(dups) >= 1, "Expected at least one exact-duplicate pair"
        flat = [doc_id for group in dups for doc_id in group]
        assert "INV-DUP-ORIG-001" in flat
        assert "INV-DUP-COPY-001" in flat

    def test_four_named_employees_present(self):
        employees = {e["employee_name"] for e in self._run()["expenses"]}
        assert "Alice Johnson" in employees
        assert "Bob Martinez"  in employees
        assert "Carol Lee"     in employees
        assert "David Kim"     in employees

    # ── Disk output layout ────────────────────────────────────────────────────
    def test_invoices_dir_has_json_per_invoice(self, tmp_path):
        result = self._run(tmp_path)
        inv_dir = tmp_path / "invoices"
        json_files = list(inv_dir.glob("*.json"))
        assert len(json_files) == 14

    def test_forms_dir_has_json_per_form(self, tmp_path):
        result = self._run(tmp_path)
        form_dir = tmp_path / "forms"
        json_files = list(form_dir.glob("*.json"))
        assert len(json_files) == 4

    def test_ocr_output_has_18_stubs(self, tmp_path):
        self._run(tmp_path)
        ocr_dir = tmp_path / "ocr_output"
        ocr_files = list(ocr_dir.glob("*_ocr.json"))
        assert len(ocr_files) == 18

    def test_ocr_stub_filenames_match_images(self, tmp_path):
        self._run(tmp_path)
        ocr_dir = tmp_path / "ocr_output"
        names = {f.name for f in ocr_dir.glob("*_ocr.json")}
        expected = {
            "FORM-001-ALICE_ocr.json","FORM-002-BOB_ocr.json",
            "FORM-003-CAROL_ocr.json","FORM-004-DAVID_ocr.json",
            "INV-AIR-001_ocr.json","INV-DUP-COPY-001_ocr.json",
            "INV-DUP-NEAR-001_ocr.json","INV-DUP-ORIG-001_ocr.json",
            "INV-HIGH-VALUE-001_ocr.json","INV-HOTEL-001_ocr.json",
            "INV-HOTEL-VIOL-001_ocr.json","INV-LATE-001_ocr.json",
            "INV-MEAL-001_ocr.json","INV-MEAL-VIOL-001_ocr.json",
            "INV-PROHIBIT-001_ocr.json","INV-SUPPLY-001_ocr.json",
            "INV-TECH-001_ocr.json","INV-TRANS-001_ocr.json",
        }
        assert names == expected

    def test_ocr_stub_structure(self, tmp_path):
        self._run(tmp_path)
        stub = json.loads((tmp_path / "ocr_output" / "INV-HOTEL-001_ocr.json").read_text())
        for field in ("document_id","vendor","amount","date",
                      "employee_name","confidence","extraction_method"):
            assert field in stub, f"Missing field '{field}' in OCR stub"
        assert stub["confidence"] == 1.0
        assert stub["extraction_method"] == "sidecar_json"

    def test_invoice_json_sidecar_parseable(self, tmp_path):
        self._run(tmp_path)
        sidecar = json.loads((tmp_path / "invoices" / "INV-HOTEL-001.json").read_text())
        assert sidecar["invoice_id"] == "INV-HOTEL-001"
        assert sidecar["vendor"] == "Marriott Hotels"
        assert isinstance(sidecar["amount"], float)
        assert len(sidecar["line_items"]) >= 1

    def test_form_json_sidecar_parseable(self, tmp_path):
        self._run(tmp_path)
        sidecar = json.loads((tmp_path / "forms" / "FORM-001-ALICE.json").read_text())
        assert sidecar["form_id"] == "FORM-001-ALICE"
        assert sidecar["employee"]["name"] == "Alice Johnson"
        assert sidecar["employee"]["emp_id"] == "EMP-1001"
        assert len(sidecar["expenses"]) == 4

    def test_duplicate_sidecar_same_amount_and_date(self, tmp_path):
        self._run(tmp_path)
        orig = json.loads((tmp_path / "invoices" / "INV-DUP-ORIG-001.json").read_text())
        copy = json.loads((tmp_path / "invoices" / "INV-DUP-COPY-001.json").read_text())
        assert orig["amount"] == copy["amount"]
        assert orig["date"]   == copy["date"]
        assert orig["vendor"] == copy["vendor"]

    # ── Scenario metadata ─────────────────────────────────────────────────────
    def test_scenario_summary_is_18(self):
        from app.src.data.generate_synthetic_data import get_scenario_summary
        assert len(get_scenario_summary()) == 18

    def test_scenario_summary_has_all_categories(self):
        from app.src.data.generate_synthetic_data import get_scenario_summary
        cats = {s["scenario"] for s in get_scenario_summary()}
        assert cats == {"clean","violation","duplicate"}

    def test_scenario_summary_employee_names_match_v1(self):
        from app.src.data.generate_synthetic_data import get_scenario_summary
        employees = {s["employee"] for s in get_scenario_summary()}
        assert employees == {"Alice Johnson","Bob Martinez","Carol Lee","David Kim"}


# ─── OCR agent ────────────────────────────────────────────────────────────────
class TestOcrAgent:
    def _agent(self):
        from app.src.agents.ocr_agent import OcrAgent
        return OcrAgent.__new__(OcrAgent)

    def test_sidecar_invoice_parse(self):
        agent = self._agent()
        raw = {
            "invoice_id":"INV-HOTEL-001","vendor":"Marriott Hotels",
            "amount":220.0,"category":"Hotel","date":"2026-05-01",
            "description":"Hotel stay","employee":{"name":"Alice Johnson","emp_id":"EMP-1001","dept":"Sales"},
        }
        result = agent._parse_sidecar(raw, "INV-HOTEL-001")
        assert result["vendor"] == "Marriott Hotels"
        assert result["amount"] == 220.0
        assert result["confidence"] == 1.0
        assert result["extraction_method"] == "sidecar_json"

    def test_sidecar_form_parse(self):
        agent = self._agent()
        raw = {
            "form_id":"FORM-001-ALICE","total_claimed":828.70,
            "submission_date":"2026-06-01",
            "employee":{"name":"Alice Johnson","emp_id":"EMP-1001","dept":"Sales"},
            "expenses":[],
        }
        result = agent._parse_sidecar(raw, "FORM-001-ALICE")
        assert result["document_type"] == "reimbursement_form"
        assert result["confidence"] == 1.0

    def test_heuristic_category_hotel(self):
        assert self._agent()._heuristic_category("Marriott hotel lodging") == "accommodation"

    def test_heuristic_category_travel(self):
        assert self._agent()._heuristic_category("United Airlines economy flight") == "travel"

    def test_heuristic_category_wellness(self):
        assert self._agent()._heuristic_category("Deep tissue spa massage") == "wellness"

    def test_heuristic_category_fallback(self):
        assert self._agent()._heuristic_category("Miscellaneous purchase") == "other"

    def test_extract_amount_from_kv(self):
        result = self._agent()._extract_amount({"total": "$250.00"}, "")
        assert result == 250.0

    def test_extract_amount_fallback_regex(self):
        result = self._agent()._extract_amount({}, "Invoice total: $189.99")
        assert result == 189.99


# ─── Validation agent ─────────────────────────────────────────────────────────
class TestValidationAgent:
    def _agent(self):
        from app.src.agents.validation_agent import ValidationAgent
        return ValidationAgent.__new__(ValidationAgent)

    def _validate(self, expense):
        return self._agent()._validate_rule_based(expense, [])

    def test_compliant_transport(self):
        r = self._validate({"document_id":"T1","vendor":"Uber",
                            "category":"transportation","amount":35.0,"description":"Airport ride"})
        assert r["compliance_status"] == "COMPLIANT"
        assert r["confidence_score"] >= 0.8

    def test_spa_is_critical(self):
        r = self._validate({"document_id":"T2","vendor":"Four Seasons Spa",
                            "category":"wellness","amount":200.0,"description":"Spa treatment"})
        assert r["compliance_status"] == "CRITICAL"
        assert r["confidence_score"] >= 0.9

    def test_hotel_over_limit_is_violation(self):
        r = self._validate({"document_id":"T3","vendor":"Marriott",
                            "category":"accommodation","amount":400.0,"description":"Hotel stay"})
        assert r["compliance_status"] == "VIOLATION"

    def test_cfo_approval_above_5000(self):
        r = self._validate({"document_id":"T4","vendor":"Apple Store",
                            "category":"technology","amount":6000.0,"description":"Laptop"})
        assert r["requires_approval_from"] == "CFO"

    def test_manager_approval_between_100_and_1000(self):
        r = self._validate({"document_id":"T5","vendor":"United Airlines",
                            "category":"travel","amount":500.0,"description":"Flight"})
        assert r["requires_approval_from"] == "MANAGER"

    def test_self_approval_under_100(self):
        r = self._validate({"document_id":"T6","vendor":"Uber",
                            "category":"transportation","amount":50.0,"description":"Ride"})
        assert r["requires_approval_from"] == "SELF"

    def test_result_always_has_confidence_score(self):
        r = self._validate({"document_id":"T7","amount":50.0,"category":"meals"})
        assert "confidence_score" in r
        assert 0.0 <= r["confidence_score"] <= 1.0

    def test_result_has_all_required_keys(self):
        r = self._validate({"document_id":"T8","amount":200.0,"category":"accommodation"})
        for k in ("compliance_status","risk_level","confidence_score",
                  "violations","recommendations","requires_approval_from","reasoning"):
            assert k in r, f"Missing key: {k}"


# ─── Duplicate detection agent ────────────────────────────────────────────────
class TestDuplicateAgent:
    def _agent(self):
        from app.src.agents.duplicate_agent import DuplicateAgent
        return DuplicateAgent.__new__(DuplicateAgent)

    def _fp(self, e):
        v = re.sub(r"\s+", " ",
            (e.get("vendor") or "").lower()
            .replace(" inc","").replace(" llc",""))
        return f"{v}|{float(e.get('amount',0)):.2f}|{str(e.get('date',''))[:10]}|{(e.get('category') or '').lower()}"

    def test_identical_expenses_share_hash(self):
        e1 = {"document_id":"E1","vendor":"Marriott","amount":250.0,"date":"2026-05-01","category":"hotel"}
        e2 = {"document_id":"E2","vendor":"Marriott","amount":250.0,"date":"2026-05-01","category":"hotel"}
        h1 = hashlib.sha256(self._fp(e1).encode()).hexdigest()
        h2 = hashlib.sha256(self._fp(e2).encode()).hexdigest()
        assert h1 == h2

    def test_different_expenses_have_different_hashes(self):
        e1 = {"document_id":"E3","vendor":"Marriott","amount":250.0,"date":"2026-05-01","category":"hotel"}
        e2 = {"document_id":"E4","vendor":"Delta Air Lines","amount":380.0,"date":"2026-05-10","category":"travel"}
        h1 = hashlib.sha256(self._fp(e1).encode()).hexdigest()
        h2 = hashlib.sha256(self._fp(e2).encode()).hexdigest()
        assert h1 != h2

    def test_amount_sim_identical(self):
        assert self._agent()._amount_sim(250.0, 250.0) == 1.0

    def test_amount_sim_zero_case(self):
        assert self._agent()._amount_sim(0.0, 0.0) == 1.0

    def test_amount_sim_partial(self):
        sim = self._agent()._amount_sim(245.0, 257.50)
        assert 0.0 < sim < 1.0

    def test_date_proximity_same_date(self):
        assert self._agent()._date_proximity("2026-05-10","2026-05-10") is True

    def test_date_proximity_within_3_days(self):
        assert self._agent()._date_proximity("2026-05-10","2026-05-12") is True

    def test_date_proximity_beyond_3_days(self):
        assert self._agent()._date_proximity("2026-05-01","2026-05-10") is False


# ─── Audit agent ──────────────────────────────────────────────────────────────
class TestAuditAgent:
    def _agent(self):
        from app.src.agents.audit_agent import AuditAgent
        return AuditAgent.__new__(AuditAgent)

    def _val(self, status, conf=0.9, req="SELF"):
        return {"compliance_status":status,"confidence_score":conf,"violations":[],
                "recommendations":[],"requires_approval_from":req,"risk_level":"LOW"}

    def _dup(self, pairs=None):
        return {"duplicate_pairs": pairs or [], "flagged_ids": [],
                "summary": {"total_checked":0,"exact":0,"near":0,"suspected":0}}

    def test_all_compliant_gives_approved(self):
        expenses = [{"document_id":f"E{i}","amount":50.0} for i in range(3)]
        vals     = [self._val("COMPLIANT") for _ in expenses]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T001")
        assert report["overall_verdict"]  == "APPROVED"
        assert report["compliance_score"] == 100

    def test_violations_reduce_score(self):
        expenses = [{"document_id":"E1","amount":200.0},
                    {"document_id":"E2","amount":100.0}]
        vals     = [self._val("VIOLATION",0.88), self._val("COMPLIANT")]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T002")
        assert report["compliance_score"] < 100

    def test_critical_reduces_by_15(self):
        expenses = [{"document_id":"E1","amount":300.0}]
        vals     = [self._val("CRITICAL",0.95)]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T003")
        assert report["compliance_score"] == 85

    def test_duplicate_pair_reduces_score(self):
        expenses = [{"document_id":"E1","amount":245.0},
                    {"document_id":"E2","amount":245.0}]
        vals     = [self._val("COMPLIANT"), self._val("COMPLIANT")]
        pairs    = [{"type":"EXACT_DUPLICATE","expense_id_1":"E1","expense_id_2":"E2",
                     "amount_at_risk":245.0,"confidence_score":1.0,
                     "recommendation":"REJECT"}]
        report   = self._agent()._rule_based(expenses, vals, self._dup(pairs), "T004")
        assert report["compliance_score"] < 100

    def test_aggregate_confidence_is_weighted_mean(self):
        expenses = [{"document_id":f"E{i}","amount":50.0} for i in range(4)]
        vals     = [self._val("COMPLIANT", c) for c in [0.9, 0.8, 1.0, 0.7]]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T005")
        assert report["aggregate_confidence"] == pytest.approx(0.85, abs=0.01)

    def test_report_has_all_required_top_level_keys(self):
        expenses = [{"document_id":"E1","amount":50.0}]
        vals     = [self._val("COMPLIANT")]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T006")
        for k in ("audit_report_id","overall_verdict","compliance_score",
                  "aggregate_confidence","executive_summary","financial_breakdown",
                  "key_findings","duplicate_findings","action_items",
                  "approval_chain","expense_details","generated_at"):
            assert k in report, f"Missing key: {k}"

    def test_financial_totals_are_accurate(self):
        expenses = [{"document_id":"E1","amount":200.0},
                    {"document_id":"E2","amount":300.0}]
        vals     = [self._val("COMPLIANT"), self._val("COMPLIANT")]
        report   = self._agent()._rule_based(expenses, vals, self._dup(), "T007")
        assert report["financial_breakdown"]["total_claimed"] == pytest.approx(500.0, abs=0.01)
