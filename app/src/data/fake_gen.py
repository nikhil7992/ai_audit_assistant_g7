"""
src/data/fake_gen.py
Minimal stdlib-only fake data generator.
No external Faker dependency — works inside the Docker container without PyPI access.
Ported from v1 utils/data_gen.py and extended with additional vendor categories.
"""
import random
import string
from datetime import datetime, timedelta

_FIRST = [
    "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
    "Iris", "James", "Karen", "Leo", "Maria", "Nathan", "Olivia", "Paul",
    "Quinn", "Rachel", "Samuel", "Tina", "Uma", "Victor", "Wendy", "Xavier",
]
_LAST = [
    "Johnson", "Martinez", "Lee", "Kim", "Williams", "Brown", "Davis",
    "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris",
    "Martin", "Thompson", "Garcia", "Rodriguez", "Lewis", "Walker",
]
_CITIES = [
    "New York", "Chicago", "Seattle", "Austin", "Denver", "Boston", "Miami",
    "Atlanta", "Portland", "Phoenix", "Dallas", "San Diego", "Nashville",
]
_STATES = [
    "NY", "IL", "WA", "TX", "CO", "MA", "FL", "GA", "OR", "AZ", "CA", "TN", "MI",
]
_STREETS = [
    "Main St", "Oak Ave", "Elm Blvd", "Maple Dr", "Cedar Ln",
    "Pine Rd", "Lake Way", "River Rd", "Valley Dr", "Summit Ave",
]
_COMPANIES = [
    "Acme Corp", "Nexus Inc", "Vertex LLC", "Pinnacle Co", "Summit Ltd",
    "Apex Systems", "CoreTech Inc", "Synergy Ltd", "Global Dynamics",
    "Horizon Ventures", "Delta Solutions", "Zenith Partners",
]
_HOTEL_VENDORS = [
    "Marriott", "Hilton", "Hyatt", "Sheraton", "Holiday Inn",
    "Westin", "Ritz-Carlton", "Courtyard", "Hampton Inn", "Radisson",
]
_AIRLINE_VENDORS = [
    "United Airlines", "Delta Air Lines", "American Airlines",
    "Southwest Airlines", "JetBlue", "Alaska Airlines",
]
_MEAL_VENDORS = [
    "The Capital Grille", "Olive Garden", "Cheesecake Factory",
    "Nobu Restaurant", "Local Bistro", "City Diner", "The Steakhouse",
    "Trattoria Roma", "Sushi Palace", "The Grand Cafe",
]
_TRANSPORT_VENDORS = [
    "Uber", "Lyft", "Yellow Cab", "Enterprise Rent-A-Car",
    "Hertz", "Avis", "National Car Rental",
]
_TECH_VENDORS = [
    "Apple Store", "Best Buy", "Microsoft", "Adobe", "Salesforce",
    "Amazon Web Services", "Google Workspace", "Zoom", "Slack",
]
_SUPPLY_VENDORS = [
    "OfficeMax", "Staples", "Office Depot", "Amazon Business", "W.B. Mason",
]
_PROHIBITED_VENDORS = [
    "Four Seasons Spa", "Canyon Ranch Spa", "Bliss Spa",
    "Pure Barre", "SoulCycle", "Lucky Strike Bowling",
]
_DEPT_CODES = ["ENG", "FIN", "MKT", "OPS", "SAL", "LGL", "HR", "EXEC"]
_PROJECT_CODES = [
    "PROJ-2024-ALPHA", "PROJ-2024-BETA", "PROJ-2025-Q1",
    "PROJ-2025-Q2", "PROJ-2025-CORE", "PROJ-2025-TECH",
]


class FakeGen:
    """Minimal stdlib-only fake data generator."""

    def name(self) -> str:
        return f"{random.choice(_FIRST)} {random.choice(_LAST)}"

    def first_name(self) -> str:
        return random.choice(_FIRST)

    def last_name(self) -> str:
        return random.choice(_LAST)

    def company(self) -> str:
        return random.choice(_COMPANIES)

    def company_email(self, first: str = "", last: str = "") -> str:
        domain = random.choice(["retailcorp", "globaltech", "nexusfirm", "apexco", "vertexsys"])
        f = first.lower() or random.choice(_FIRST).lower()
        l = last.lower()  or random.choice(_LAST).lower()
        return f"{f}.{l}@{domain}.com"

    def city(self) -> str:
        return random.choice(_CITIES)

    def state_abbr(self) -> str:
        return random.choice(_STATES)

    def street_address(self) -> str:
        return f"{random.randint(100, 9999)} {random.choice(_STREETS)}"

    def zipcode(self) -> str:
        return f"{random.randint(10000, 99999)}"

    def hotel_vendor(self) -> str:
        return random.choice(_HOTEL_VENDORS)

    def airline_vendor(self) -> str:
        return random.choice(_AIRLINE_VENDORS)

    def meal_vendor(self) -> str:
        return random.choice(_MEAL_VENDORS)

    def transport_vendor(self) -> str:
        return random.choice(_TRANSPORT_VENDORS)

    def tech_vendor(self) -> str:
        return random.choice(_TECH_VENDORS)

    def supply_vendor(self) -> str:
        return random.choice(_SUPPLY_VENDORS)

    def prohibited_vendor(self) -> str:
        return random.choice(_PROHIBITED_VENDORS)

    def dept_code(self) -> str:
        return random.choice(_DEPT_CODES)

    def project_code(self) -> str:
        return random.choice(_PROJECT_CODES)

    def emp_id(self) -> str:
        return f"EMP-{random.randint(1000, 9999)}"

    def cost_centre(self) -> str:
        return f"CC-{random.randint(100, 999)}"

    def random_vendor_for_category(self, category: str) -> str:
        mapping: dict = {
            "hotel":         self.hotel_vendor,
            "accommodation": self.hotel_vendor,
            "airfare":       self.airline_vendor,
            "travel":        self.airline_vendor,
            "meal":          self.meal_vendor,
            "meals":         self.meal_vendor,
            "transport":     self.transport_vendor,
            "transportation":self.transport_vendor,
            "technology":    self.tech_vendor,
            "supplies":      self.supply_vendor,
            "wellness":      self.prohibited_vendor,
        }
        return mapping.get(category.lower(), self.company)()

    def date_between(self, start_date: datetime, end_date: datetime) -> datetime:
        delta = max((end_date - start_date).days, 0)
        return start_date + timedelta(days=random.randint(0, delta))

    def date_recent(self, days: int = 30) -> str:
        end   = datetime.now()
        start = end - timedelta(days=days)
        return self.date_between(start, end).strftime("%Y-%m-%d")

    def numerify(self, template: str) -> str:
        return "".join(str(random.randint(0, 9)) if c == "#" else c for c in template)

    def bothify(self, template: str) -> str:
        result = []
        for c in template:
            if c == "#":   result.append(str(random.randint(0, 9)))
            elif c == "?": result.append(random.choice(string.ascii_uppercase))
            else:          result.append(c)
        return "".join(result)

    def random_number(self, digits: int = 6) -> int:
        return random.randint(10 ** (digits - 1), 10 ** digits - 1)

    def pyfloat(self, min_value: float = 10.0, max_value: float = 500.0,
                right_digits: int = 2) -> float:
        return round(random.uniform(min_value, max_value), right_digits)

    def random_element(self, elements) -> object:
        return random.choice(list(elements))

    def random_int(self, min: int = 0, max: int = 100) -> int:
        return random.randint(min, max)


# Module-level singleton — import and use as `from src.data.fake_gen import fake`
fake = FakeGen()
