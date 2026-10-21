"""Mock asset register connector: sites and asset lines.

The asset register is usually a spreadsheet kept by the bursar or estates office. This
mock stands in for it, producing what the Assets & Equipment screen needs: the five
lines from the screen design plus everyday items, sized so the dashboard shows about
4,250 units, 88% operational and a capital risk near 12%. Like the other mocks it is
messy on purpose: money written as "UGX 1,500,000", varied condition and category
words, mixed dates, a duplicate line, and a few broken rows (an unknown site, a
quantity written in words, an unknown condition, a site on an unknown campus).
"""
import random
from datetime import date

from . import Connector

# code, name, campus as written, site type
SITES = [
    ("KB-CSB", "Computer Suite B", "Kibuli Main Campus", "Laboratory"),
    ("BW-CL1", "Chemistry Lab 1", "Buwaate Campus", "Lab"),
    ("KB-ADM", "Admin Block", "KIBULI MAIN", "Administration"),
    ("AX-PWR", "Power House", "Annex / Preschool Branch", "Other"),
    ("KB-TPT", "Transport Depot", "Kibuli", "Other"),
    ("KB-CLA", "Classroom Block A", "Kibuli Main Campus", "Classroom"),
    ("BW-CLC", "Classroom Block C", "Buwaate", "Classroom"),
    ("KB-BDM", "Boys Dormitory", "Kibuli Main Campus", "Hostel"),
    ("BW-GDM", "Girls Dormitory", "Buwaate Campus", "Hostel"),
    ("KB-DIN", "Main Dining Hall", "Kibuli", "Dining"),
    ("KB-SPT", "Sports Complex", "Kibuli Main Campus", "Sports"),
    ("AX-CLS", "Annex Classrooms", "Annex Preschool", "Classroom"),
]
# name, category as written, site, quantity, unit cost (UGX), condition as written
LINES = [
    # the five lines on the screen design
    ("Dell Student Laboratory Workstations", "ICT Hardware", "KB-CSB", 120, 1_500_000, "Good"),
    ("Optics Spectrophotometers & Beakers", "Science Laboratory Equipment", "BW-CL1", 45,
     2_111_111, "Needs service"),
    ("Executive Ergonomic Office Desks & Chairs", "Administrative Furniture", "KB-ADM", 65,
     1_307_692, "Operational"),
    ("250kVA Heavy-Duty Backup Generator", "Power & Facility Machinery", "AX-PWR", 2,
     105_000_000, "Repair queued"),
    ("67-Seater Student Transport Buses", "Fleet & Vehicles", "KB-TPT", 6, 163_333_333,
     "Operational"),
    # everyday items
    ("Classroom Desks (Double)", "Furniture", "KB-CLA", 1400, 180_000, "Good"),
    ("Classroom Chairs", "Furniture", "BW-CLC", 1168, 60_000, "Good"),
    ("Classroom Chairs (Broken)", "Furniture", "BW-CLC", 60, 60_000, "Critical"),
    ("Boarding Beds (Double-Decker)", "Furniture", "KB-BDM", 394, 200_000, "Service due"),
    ("Mattresses", "Other", "BW-GDM", 300, 150_000, "Good"),
    ("Teacher Laptops", "ICT", "KB-ADM", 140, 3_500_000, "Working"),
    ("Classroom Projectors", "ICT Hardware", "KB-CLA", 60, 3_200_000, "Good"),
    ("Kitchen Cooking Ranges", "Machinery", "KB-DIN", 8, 25_000_000, "Good"),
    ("Sports Equipment Sets", "Other", "KB-SPT", 200, 500_000, "Good"),
    ("Annex Play Equipment", "Other", "AX-CLS", 150, 600_000, "Good"),
    ("Microscopes", "Lab Equipment", "BW-CL1", 132, 1_500_000, "Good"),
    ("Old Minibus", "Vehicles", "KB-TPT", 2, 40_000_000, "Disposed"),
]


class MockAssetRegisterConnector(Connector):
    """Generates asset-register records. The register is small, so `scale` is accepted
    for a common interface but not used."""

    source_code = "assets"

    def __init__(self, seed=2026, scale=1.0):
        self.seed = seed
        self.injected = {}

    def _money(self, amount):
        style = self.rng.randrange(3)
        if style == 0:
            return f"UGX {amount:,}"
        if style == 1:
            return f"{amount:,}"
        return f"{amount}.00"

    def _date(self, value):
        return value.strftime("%d/%m/%Y") if self.rng.random() < 0.5 else value.isoformat()

    def _note(self, problem):
        self.injected[problem] = self.injected.get(problem, 0) + 1

    def fetch(self):
        self.rng = random.Random(self.seed)
        self.injected = {}
        for code, name, campus, site_type in SITES:
            yield "site", code, {"SiteCode": code, "SiteName": name, "Campus": campus,
                                 "SiteType": site_type}
        yield "site", "EN-001", {"SiteCode": "EN-001", "SiteName": "Entebbe Store",
                                 "Campus": "Entebbe", "SiteType": "Other"}
        self._note("site_unknown_campus")

        lines = []
        for number, (name, category, site, qty, cost, condition) in enumerate(LINES, start=1):
            acquired = date(self.rng.randint(2014, 2025), self.rng.randint(1, 12), 1)
            payload = {"AssetCode": f"AST-{number:04d}", "Description": name,
                       "Class": category, "SiteCode": site, "Qty": str(qty),
                       "UnitCost": self._money(cost), "Condition": condition,
                       "AcquiredOn": self._date(acquired)}
            lines.append(payload)
            yield "asset", payload["AssetCode"], payload

        yield "asset", lines[0]["AssetCode"], dict(lines[0])  # the same line sent twice
        self._note("duplicate_asset")
        broken = [
            ("unknown_site", {"SiteCode": "ZZ-999"}),
            ("quantity_in_words", {"Qty": "two"}),
            ("unknown_condition", {"Condition": "Lost"}),
        ]
        for offset, (problem, change) in enumerate(broken, start=len(LINES) + 1):
            payload = {"AssetCode": f"AST-{offset:04d}", "Description": f"Broken line {offset}",
                       "Class": "Furniture", "SiteCode": "KB-ADM", "Qty": "1",
                       "UnitCost": "UGX 100,000", "Condition": "Good", "AcquiredOn": "2020-01-01",
                       **change}
            yield "asset", payload["AssetCode"], payload
            self._note(problem)
