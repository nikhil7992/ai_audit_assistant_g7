"""
src/data/generate_policies.py
Generates 12 realistic corporate expense policy documents as plain-text .txt files.

Runtime role
────────────
Called once at application startup (or via POST /admin/seed-policies) to produce
the policy knowledge base on the local filesystem.  After the .txt files exist,
seed_opensearch.py reads them, splits each into overlapping 300-word chunks,
embeds each chunk via Amazon Bedrock Titan Embed Text v2, and upserts the vectors
into the Amazon OpenSearch Service k-NN index.

At validation time the ValidationAgent builds a query string from the expense
(category + vendor + amount + description), retrieves the top-5 most similar
policy chunks from OpenSearch, and passes them as context to the Bedrock Claude
LLM call (or falls back to deterministic rule-based checks if Bedrock is
unavailable).

Output layout (matches v1 exactly — see images)
─────────────────────────────────────────────────
  app/data/policies/
    ├── PP-001_Vendor_Gifts.txt
    ├── PP-002_Office_Supplies.txt
    ├── TP-001_Air_Travel.txt
    ├── TP-002_Hotel_Accommodation.txt
    ├── TP-003_Meals_Entertainment.txt
    ├── TP-004_Ground_Transportation.txt
    ├── TP-005_Technology_Equipment.txt
    ├── TP-006_Submission_Deadlines.txt
    ├── TP-007_Prohibited_Expenses.txt
    ├── TP-008_Approval_Thresholds.txt
    ├── TP-009_Duplicate_Fraud_Prevention.txt
    └── TP-010_International_Travel.txt

Usage
─────
    from src.data.generate_policies import generate_policy_files
    count = generate_policy_files(Path("app/data/policies"))   # returns 12
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Policy content dict — keys match exact filenames seen in the images ────────
POLICIES: dict[str, str] = {

    "TP-001_Air_Travel.txt": """
POLICY TP-001: AIR TRAVEL POLICY
Effective Date: January 1, 2024  |  Version: 3.2  |  Owner: Finance & Compliance

1. SCOPE
This policy governs all business air travel for employees of RetailCorp Inc.

2. BOOKING REQUIREMENTS
2.1 All domestic flights must be booked at least 14 days in advance to qualify for reimbursement.
2.2 Flights booked within 7 days require VP-level approval prior to purchase.
2.3 All bookings must be made through the corporate travel portal (TravelDesk Pro) or an approved travel agent.
2.4 Economy class is required for all domestic flights and international flights under 6 hours.
2.5 Business class is permitted for international flights exceeding 6 hours with Director-level approval.

3. SPENDING LIMITS
3.1 Domestic one-way airfare cap: $800 per segment.
3.2 International airfare cap: $3,500 economy / $7,000 business class (pre-approved).
3.3 Baggage: One checked bag is reimbursable. Additional bags require documented business justification.
3.4 Seat upgrades, lounge passes, and premium economy are NOT reimbursable unless pre-approved.

4. RECEIPTS
4.1 Original e-ticket confirmation and boarding pass required for all claims.
4.2 Receipts must clearly show airline, flight number, date, route, and amount paid.

5. PROHIBITED
5.1 First-class travel is prohibited under all circumstances.
5.2 Mileage redemption tickets must be declared but are not eligible for cash reimbursement.
5.3 Personal travel extensions — only the business-leg fare is reimbursable.
""",

    "TP-002_Hotel_Accommodation.txt": """
POLICY TP-002: HOTEL & ACCOMMODATION POLICY
Effective Date: January 1, 2024  |  Version: 2.8  |  Owner: Finance & Compliance

1. SCOPE
Covers hotel bookings for all domestic and international business travel.

2. STANDARD RATE LIMITS
2.1 Standard cities (domestic): $250 per night (room rate + taxes, excluding resort fees).
2.2 High-cost cities (NYC, SF, Boston, DC, Chicago, LA): $350 per night.
2.3 International: $300 per night equivalent in local currency.
2.4 Rates above these limits require pre-approval from the employee's direct manager.

3. BOOKING REQUIREMENTS
3.1 Book through TravelDesk Pro for negotiated corporate rates.
3.2 Hotel stays exceeding 5 consecutive nights require VP approval.
3.3 Extended stays (14+ nights) require CFO approval.

4. REIMBURSABLE ITEMS
4.1 Room rate, applicable taxes, and a daily parking fee up to $30 are reimbursable.
4.2 In-room internet ($15/night cap) is reimbursable with business justification.
4.3 One reasonable breakfast per day ($25 cap) may be claimed when not covered by per diem.

5. NON-REIMBURSABLE ITEMS
5.1 Minibar charges, in-room movies, spa/wellness services.
5.2 Room service above $40 per meal (excess must be deducted).
5.3 Laundry for stays under 5 days.
5.4 Resort fees at leisure properties.

6. CANCELLATION
6.1 Employees are responsible for cancelling reservations within the policy window.
6.2 No-show charges are not reimbursable unless documented emergency.
""",

    "TP-003_Meals_Entertainment.txt": """
POLICY TP-003: MEALS & BUSINESS ENTERTAINMENT
Effective Date: January 1, 2024  |  Version: 4.1  |  Owner: Finance & Compliance

1. SCOPE
Governs meal expenses and client/team entertainment while on approved business travel or hosting business meetings.

2. PER DIEM RATES (DOMESTIC)
2.1 Breakfast: $20 per day
2.2 Lunch: $20 per day
2.3 Dinner: $35 per day
2.4 Total daily per diem: $75 per day (all meals combined)
2.5 Per diem is reduced proportionally for partial travel days.

3. BUSINESS MEALS WITH CLIENTS / PROSPECTS
3.1 Business meal cap: $100 per person (including tax, tip, and beverages).
3.2 Alcohol: maximum $25 per person is reimbursable at business meals.
3.3 The business purpose, names, titles, and company of all attendees must be documented.
3.4 Manager approval required for meals exceeding $75 per person.

4. TEAM MEALS
4.1 Team lunches: $25 per person, maximum 12 attendees without pre-approval.
4.2 Team dinners during multi-day offsites: $60 per person.

5. NON-REIMBURSABLE
5.1 Meals with family members or personal guests not on company business.
5.2 Tips exceeding 20% of the pre-tax bill.
5.3 Club memberships, subscriptions to dining services.
5.4 Meals claimed under per diem AND as business meal (double-dipping is prohibited).

6. RECEIPTS
6.1 Itemized receipts required for all meal claims over $25.
6.2 Credit card summaries are NOT acceptable as sole documentation.
""",

    "TP-004_Ground_Transportation.txt": """
POLICY TP-004: GROUND TRANSPORTATION POLICY
Effective Date: January 1, 2024  |  Version: 2.5  |  Owner: Finance & Compliance

1. SCOPE
All ground transportation expenses during approved business travel.

2. RIDE-SHARING & TAXIS
2.1 Uber, Lyft, and licensed taxis are reimbursable for business travel between airport/hotel/client.
2.2 UberX or Lyft Standard (economy tier) is required unless unavailable.
2.3 UberXL / Lyft XL permitted when travelling with 3+ colleagues sharing the ride.
2.4 Surge pricing: reimbursable with a note in the expense report; avoid where feasible.

3. RENTAL CARS
3.1 Economy or compact class required; mid-size permitted with business justification.
3.2 Rental car duration must match documented travel dates.
3.3 Fuel: reimbursable with receipt; premium/super-premium fuel is not reimbursable.
3.4 Collision Damage Waiver (CDW) insurance is reimbursable through the corporate card.
3.5 GPS/navigation add-ons at rental agencies are NOT reimbursable (use phone).

4. PERSONAL VEHICLE
4.1 Mileage rate: $0.67/mile (IRS 2024 standard rate).
4.2 Commute miles (home to primary office) must be deducted from total mileage.
4.3 Mileage log (date, origin, destination, purpose, miles) is mandatory.
4.4 Parking and tolls are reimbursable with receipts.

5. PROHIBITED
5.1 Limousine, black car, or luxury vehicle services without VP pre-approval.
5.2 Airport valet parking (use economy parking unless fully booked).
""",

    "TP-005_Technology_Equipment.txt": """
POLICY TP-005: TECHNOLOGY & EQUIPMENT EXPENSES
Effective Date: January 1, 2024  |  Version: 1.9  |  Owner: IT & Finance

1. SCOPE
Covers purchase of hardware, software, SaaS subscriptions, and accessories.

2. HARDWARE PURCHASES
2.1 Laptop, tablet, phone: must be approved by IT and ordered through the company procurement portal.
2.2 Peripherals (keyboards, mice, monitors, headsets): up to $150 self-approved; $151-$500 requires manager approval.
2.3 No hardware purchase above $500 is reimbursable as an out-of-pocket expense; use PO process.

3. SOFTWARE & SAAS SUBSCRIPTIONS
3.1 Monthly SaaS expense: up to $50/month self-approved.
3.2 $51-$200/month: manager approval required.
3.3 Annual SaaS contracts: must go through IT procurement regardless of amount.

4. MOBILE PHONE & INTERNET
4.1 Mobile phone plan: up to $80/month reimbursable.
4.2 Home internet for remote work: up to $50/month with manager approval.
4.3 International data plans during travel: reimbursable with receipts.

5. NON-REIMBURSABLE
5.1 Personal software, gaming applications, streaming services.
5.2 Smart TVs, home entertainment equipment even if occasionally used for work.
5.3 Any device bought outside the procurement portal above $500.
""",

    "TP-006_Submission_Deadlines.txt": """
POLICY TP-006: EXPENSE SUBMISSION & REIMBURSEMENT TIMELINE
Effective Date: January 1, 2024  |  Version: 2.0  |  Owner: Accounts Payable

1. SUBMISSION DEADLINES
1.1 Expenses must be submitted within 30 calendar days of the date the expense was incurred.
1.2 Expenses submitted 31-60 days after the transaction date require written justification and CFO approval.
1.3 Expenses submitted more than 60 days after the transaction date will NOT be reimbursed under any circumstance.

2. DOCUMENTATION REQUIREMENTS
2.1 All claims must include: original receipt (PDF or clear photo), business purpose, project code, and attendee list (for meals/entertainment).
2.2 Receipts must be legible and clearly show vendor name, date, itemized amounts, and total.
2.3 Missing receipts: a Missing Receipt Affidavit (Form AP-07) may substitute for lost receipts up to $50; above $50 the expense is denied.

3. APPROVAL WORKFLOW
3.1 Employee submits expense in ExpenseFlow system.
3.2 Automated policy check flags violations before manager review.
3.3 Manager approves/rejects within 5 business days.
3.4 Accounts Payable processes reimbursement within 10 business days of manager approval.
3.5 Reimbursements are paid via direct deposit with the biweekly payroll cycle.

4. DISPUTES
4.1 Employees may raise disputes within 15 days of reimbursement decision.
4.2 Disputes are reviewed by the Finance Compliance team within 10 business days.
""",

    "TP-007_Prohibited_Expenses.txt": """
POLICY TP-007: PROHIBITED EXPENSE CATEGORIES
Effective Date: January 1, 2024  |  Version: 3.0  |  Owner: Finance & Compliance

1. ABSOLUTE PROHIBITIONS (will NEVER be reimbursed)

The following categories are strictly prohibited and will result in expense denial and potential disciplinary action:

1.1 Personal entertainment: spa treatments, massage therapy, personal grooming, hair salons, nail salons.
1.2 Gambling or casino expenses of any kind.
1.3 Adult entertainment: adult clubs, adult content, escort services.
1.4 Tobacco and cannabis products.
1.5 Personal fines, traffic tickets, parking violations (except meters during meetings).
1.6 Political donations or contributions.
1.7 Gifts to government officials (any amount).
1.8 Gym memberships, fitness equipment, personal wellness (unless covered under Wellness Benefit Program separately).
1.9 Pet care, pet boarding, pet supplies.
1.10 Personal clothing, dry cleaning for stays under 5 days.
1.11 Non-business reading materials, personal subscriptions.

2. CONDITIONAL PROHIBITIONS (reimbursable only with documented exception)
2.1 Alcohol: reimbursable ONLY as part of an approved business meal (max $25/person limit — see TP-003).
2.2 First-class flights: never reimbursable (see TP-001).
2.3 Luxury hotel upgrades: not reimbursable (room must be at standard rate — see TP-002).

3. REPORTING FRAUD
3.1 Employees who submit prohibited or falsified expenses face immediate disciplinary review.
3.2 Violations may result in termination and referral to legal for recovery.
3.3 Employees are encouraged to report suspected fraud anonymously via the Ethics Hotline: 1-800-555-ETHICS.
""",

    "TP-008_Approval_Thresholds.txt": """
POLICY TP-008: EXPENSE APPROVAL THRESHOLDS & AUTHORITY MATRIX
Effective Date: January 1, 2024  |  Version: 2.3  |  Owner: Finance & Compliance

1. APPROVAL AUTHORITY MATRIX

| Expense Amount       | Approval Required             |
|----------------------|-------------------------------|
| $0.01 - $100.00      | Self-approved (employee)      |
| $100.01 - $1,000.00  | Direct Manager                |
| $1,000.01 - $5,000   | VP or Senior Director         |
| $5,000.01 and above  | CFO (Chief Financial Officer) |

2. CUMULATIVE SPENDING LIMITS
2.1 An employee's total expense submissions in any calendar month must not exceed $10,000 without CFO notification.
2.2 Project-coded expenses (client entertainment, trade shows) follow the project budget approval, not individual thresholds.

3. ESCALATION RULES
3.1 If a manager is not available within 3 business days, escalate to skip-level manager.
3.2 Approvers may NOT approve their own expenses (self-approval only for sub-$100 claims).
3.3 Approvers must review and either approve or reject within 5 business days; silence is NOT approval.

4. RETROACTIVE APPROVAL
4.1 Retroactive approvals are only valid when documented with a written business justification.
4.2 Retroactive approval beyond 30 days from submission requires CFO signature.
""",

    "TP-009_Duplicate_Fraud_Prevention.txt": """
POLICY TP-009: DUPLICATE & FRAUD PREVENTION POLICY
Effective Date: January 1, 2024  |  Version: 1.6  |  Owner: Internal Audit

1. DUPLICATE CLAIM PREVENTION
1.1 Submitting the same expense more than once — whether identical or slightly modified — constitutes expense fraud.
1.2 The ExpenseFlow system runs automated duplicate detection on every submission.
1.3 Suspected duplicates are flagged for manual review by Internal Audit before any reimbursement is issued.
1.4 Duplicate detection checks: same vendor + same amount + same date (exact duplicate), or same vendor + within 10% amount + within 3-day window (near-duplicate).

2. WHAT CONSTITUTES A DUPLICATE
2.1 Same receipt submitted in multiple expense reports.
2.2 Same vendor, same date, same amount — even across different employees (split billing must be documented).
2.3 Corporate card transaction also submitted as out-of-pocket expense.

3. FRAUD INDICATORS
3.1 Round-number amounts (e.g., exactly $100.00 repeatedly) with no itemized receipts.
3.2 Recurring vendor claims on weekends/holidays without business justification.
3.3 Cluster of expenses just below approval thresholds (structuring).
3.4 Receipts with inconsistent fonts, altered dates, or edited totals.

4. INVESTIGATION PROCESS
4.1 Flagged expenses are frozen pending Internal Audit review (5 business days).
4.2 Employees must respond to audit queries within 3 business days.
4.3 Substantiated fraud is escalated to HR and Legal.

5. WHISTLEBLOWER PROTECTION
5.1 Employees reporting fraud in good faith are protected under RetailCorp's Whistleblower Policy.
""",

    "TP-010_International_Travel.txt": """
POLICY TP-010: INTERNATIONAL TRAVEL POLICY
Effective Date: January 1, 2024  |  Version: 2.1  |  Owner: Finance & Compliance

1. PRE-TRAVEL REQUIREMENTS
1.1 VP approval required for all international travel at least 5 business days prior to departure.
1.2 Employee must register travel with Global Security (travel@retailcorp.com) before departure.
1.3 Travel insurance through the corporate broker is mandatory; receipts reimbursable.

2. CURRENCY & EXCHANGE
2.1 All expenses must be reported in USD at the exchange rate on the date of the transaction.
2.2 Use the corporate Amex card for international purchases to avoid personal exchange-rate fees.
2.3 Cash withdrawals: up to $500 equivalent per trip reimbursable with receipts.

3. PER DIEM (INTERNATIONAL)
3.1 Per diems follow the US State Department foreign per diem rates for the destination country/city.
3.2 Employees must look up the applicable rate at travel.state.gov prior to departure.

4. VISAS & ENTRY FEES
4.1 Visa fees, ESTA fees, and government entry fees are fully reimbursable with receipts.
4.2 Expedited passport fees are reimbursable when travel is confirmed within 6 weeks.

5. PROHIBITED
5.1 Stopovers for personal tourism longer than 24 hours without vacation days logged.
5.2 Upgrading flights mid-trip without pre-approval (see TP-001).
""",

    "PP-001_Vendor_Gifts.txt": """
POLICY PP-001: VENDOR GIFTS & HOSPITALITY
Effective Date: January 1, 2024  |  Version: 1.4  |  Owner: Legal & Compliance

1. RECEIVING GIFTS
1.1 Employees may accept gifts from vendors/clients up to $50 per occasion.
1.2 Annual cumulative gift limit per vendor: $150.
1.3 Gifts exceeding these limits must be reported to Legal and either returned or donated to charity.

2. GIVING GIFTS TO CLIENTS / VENDORS
2.1 Client gifts: up to $75 per recipient per year (company-branded items preferred).
2.2 Gifts must be expensed with recipient name, company, and business purpose.
2.3 Cash gifts, gift cards, and prepaid debit cards are PROHIBITED.
2.4 Government official gifts: PROHIBITED regardless of value.

3. HOSPITALITY (MEALS, EVENTS, SPORTS TICKETS)
3.1 Hospitality events must have a bona fide business purpose and be attended by the host.
3.2 Sports/entertainment tickets: up to $200 per person per event, VP approval for anything above.
3.3 Hospitality that could influence a procurement decision must be pre-cleared by Legal.

4. DISCLOSURE
4.1 All gifts received above $25 must be logged in the Gift Register within 5 business days.
4.2 Failure to disclose may constitute a conflict of interest.
""",

    "PP-002_Office_Supplies.txt": """
POLICY PP-002: OFFICE SUPPLIES & MISCELLANEOUS
Effective Date: January 1, 2024  |  Version: 1.2  |  Owner: Operations & Finance

1. STANDARD OFFICE SUPPLIES
1.1 Routine supplies (pens, paper, notebooks, staples, etc.): up to $50 self-approved per quarter.
1.2 $51-$200: manager approval required; must order via preferred vendor (OfficeMax corporate account).
1.3 Over $200: use the PO (Purchase Order) process through Procurement.

2. HOME OFFICE SETUP (REMOTE EMPLOYEES)
2.1 One-time home office setup allowance: $500 (new hire or relocation).
2.2 Ergonomic chair or standing desk: up to $300 with manager approval and medical note (if ergonomic).
2.3 Annual home office supply replenishment: $150 without approval.

3. PRINTING & SHIPPING
3.1 Business printing and shipping fully reimbursable with receipts and project code.
3.2 Overnight/express shipping requires manager approval unless client-deadline-driven.

4. MISCELLANEOUS BUSINESS EXPENSES
4.1 Professional association memberships: fully reimbursable with manager approval (one per year).
4.2 Business books and online courses: up to $200/year self-approved; $201-$1,000 manager approval.
4.3 Conference registration fees: reimbursable with pre-approval, subject to travel policy TP-001/TP-002.
""",
}


def generate_policy_files(policies_dir: Path) -> int:
    """
    Write all 12 policy .txt files to policies_dir.

    Runtime behaviour
    ─────────────────
    Called by seed_opensearch.py before it chunks and indexes the policies.
    After writing, each .txt file is read back, split into overlapping 300-word
    chunks, embedded via Bedrock Titan Embed Text v2, and upserted into the
    Amazon OpenSearch k-NN index so the ValidationAgent can retrieve relevant
    clauses at query time.

    Returns count of files written (always 12).
    """
    policies_dir = Path(policies_dir)
    policies_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for filename, content in POLICIES.items():
        path = policies_dir / filename
        path.write_text(content.strip(), encoding="utf-8")
        logger.debug("Wrote policy: %s", filename)
        count += 1
    logger.info("Generated %d policy files in %s", count, policies_dir)
    return count


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/data/policies")
    n = generate_policy_files(out)
    print(f"OK  {n} policy files written to {out}")
