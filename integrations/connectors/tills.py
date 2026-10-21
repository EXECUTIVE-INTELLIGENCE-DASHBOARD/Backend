"""Mock till and stock system for GSL's outlets: daily sales, stock, budgets, spending.

Stands in for the outlets' point-of-sale and stock system until the real source is
known, producing what the Sales, Inventory and Budget Utilisation screens need. Volumes
follow the screen designs: about UGX 681M of sales from February to mid-October, sixteen
stock items, and UGX 570M of budgets. Shops A to D are all uniform shops. Like the other
mocks it is messy on purpose: money written as "UGX 1,500,000", outlet names in
capitals, mixed dates, a duplicate end-of-day report, and a few broken rows (sales for an
unknown outlet, a negative amount, a stock count written in words, an unknown business
type).
"""
import random
from datetime import date, timedelta

from . import Connector

# code, name as the till writes it, business type as written, sales Feb to mid-Oct (UGX),
# gross margin, transactions, budget (UGX), spent by mid-Oct (UGX)
OUTLETS = [
    ("SHOP-A", "Shop A", "Uniform shop", 148_000_000, 0.34, 2_900, 120_000_000, 102_000_000),
    ("SHOP-B", "SHOP B", "Uniforms", 96_000_000, 0.31, 11_200, 80_000_000, 58_000_000),
    ("SHOP-C", "Shop C", "UNIFORM SHOP", 74_000_000, 0.29, 8_400, 62_000_000, 49_000_000),
    ("SHOP-D", "shop d", "School uniforms", 68_000_000, 0.28, 7_600, 58_000_000, 52_000_000),
    ("CAFE", "Café", "Cafe", 132_000_000, 0.42, 24_000, 110_000_000, 98_000_000),
    ("MINIMART", "Minimart", "Mini-mart", 163_000_000, 0.24, 38_000, 140_000_000, 121_000_000),
]
# share of the year's sales in each month, following the screen's monthly trend
MONTH_WEIGHTS = {2: 112, 3: 74, 4: 58, 5: 88, 6: 79, 7: 52, 8: 96, 9: 70, 10: 52}
SALES_START, SALES_END = date(2026, 2, 1), date(2026, 10, 17)
# item, outlet, on hand, minimum level, unit cost
STOCK = [
    ("Boys' shirt (M)", "SHOP-A", 64, 80, 28_000),
    ("Girls' skirt (L)", "SHOP-A", 12, 40, 32_000),
    ("School sweater", "SHOP-A", 55, 50, 45_000),
    ("School socks (pair)", "SHOP-B", 900, 500, 1_800),
    ("Sports T-shirt", "SHOP-B", 18, 30, 22_000),
    ("School tie", "SHOP-C", 60, 40, 9_500),
    ("Tracksuit", "SHOP-D", 22, 30, 34_000),
    ("Coffee beans (1kg)", "CAFE", 14, 10, 48_000),
    ("Fresh milk (1L)", "CAFE", 20, 60, 3_200),
    ("Bottled water (24 pack)", "MINIMART", 35, 50, 17_000),
    ("Sugar (1kg)", "MINIMART", 210, 150, 4_800),
    ("Bread loaf", "MINIMART", 25, 40, 4_500),
    # everyday goods the minimart sells, not the uniform shops
    ("Exercise books (96pg)", "MINIMART", 900, 500, 1_800),
    ("Pens (box of 50)", "MINIMART", 18, 30, 22_000),
    ("Toiletry pack", "MINIMART", 60, 40, 9_500),
    ("Snacks carton", "MINIMART", 22, 30, 34_000),
]
EXPENSE_LINES = ["Stock purchase", "Utilities", "Staff allowances", "Repairs", "Packaging"]


class MockTillConnector(Connector):
    """Generates till and stock records for the six GSL outlets. `scale` is accepted for a
    common interface; the volumes are already small."""

    source_code = "tills"

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
        style = self.rng.randrange(3)
        if style == 0:
            return value.strftime("%d/%m/%Y")
        if style == 1:
            return value.isoformat()
        return value.strftime("%d %b %Y")

    def _note(self, problem):
        self.injected[problem] = self.injected.get(problem, 0) + 1

    def _split(self, total, parts):
        """Split a whole-number total into `parts` uneven pieces that add up exactly."""
        weights = [self.rng.uniform(0.7, 1.3) for _ in range(parts)]
        pieces = [int(total * w / sum(weights)) for w in weights]
        pieces[-1] += total - sum(pieces)
        return pieces

    def fetch(self):
        self.rng = random.Random(self.seed)
        self.injected = {}
        for code, name, kind, *_ in OUTLETS:
            yield "outlet", code, {"OutletCode": code, "OutletName": name, "Business": kind}
        yield "outlet", "KIOSK", {"OutletCode": "KIOSK", "OutletName": "Kiosk",
                                  "Business": "Car wash"}
        self._note("outlet_unknown_business_type")

        yield from self._daily_sales()
        yield from self._stock()
        yield from self._budgets_and_spending()

    def _daily_sales(self):
        days = [SALES_START + timedelta(n) for n in range((SALES_END - SALES_START).days + 1)]
        by_month = {}
        for day in days:
            by_month.setdefault(day.month, []).append(day)
        weight_total = sum(MONTH_WEIGHTS.values())
        first = None
        for code, _name, _kind, sales, margin, transactions, *_ in OUTLETS:
            month_sales = [round(sales * MONTH_WEIGHTS[m] / weight_total) for m in by_month]
            month_sales[-1] += sales - sum(month_sales)
            month_txns = [round(transactions * MONTH_WEIGHTS[m] / weight_total) for m in by_month]
            month_txns[-1] += transactions - sum(month_txns)
            for (_month, month_days), revenue, txns in zip(
                by_month.items(), month_sales, month_txns, strict=True
            ):
                for day, day_revenue, day_txns in zip(
                    month_days, self._split(revenue, len(month_days)),
                    self._split(txns, len(month_days)), strict=True,
                ):
                    cost = round(day_revenue * (1 - margin))
                    payload = {"ReportID": f"Z-{code}-{day:%Y%m%d}", "OutletCode": code,
                               "Date": self._date(day), "Takings": self._money(day_revenue),
                               "CostOfSales": self._money(cost), "Receipts": str(day_txns)}
                    first = first or payload
                    yield "daily_sales", payload["ReportID"], payload
        # a till that sent its report twice, sales for an unknown outlet, a negative amount
        yield "daily_sales", first["ReportID"], dict(first)
        self._note("duplicate_daily_sales")
        yield "daily_sales", "Z-KIOSK-20260301", {
            "ReportID": "Z-KIOSK-20260301", "OutletCode": "KIOSK-9", "Date": "01/03/2026",
            "Takings": "UGX 50,000", "CostOfSales": "30,000", "Receipts": "12"}
        self._note("sales_unknown_outlet")
        yield "daily_sales", "Z-CAFE-REFUND", {
            "ReportID": "Z-CAFE-REFUND", "OutletCode": "CAFE", "Date": "2026-03-02",
            "Takings": "-25,000", "CostOfSales": "0", "Receipts": "1"}
        self._note("sales_negative_amount")

    def _stock(self):
        for number, (name, outlet, on_hand, minimum, cost) in enumerate(STOCK, start=1):
            yield "stock_item", f"SKU-{number:04d}", {
                "SKU": f"SKU-{number:04d}", "Item": name, "OutletCode": outlet,
                "OnHand": str(on_hand), "ReorderLevel": str(minimum),
                "UnitCost": self._money(cost)}
        yield "stock_item", "SKU-9999", {
            "SKU": "SKU-9999", "Item": "School belt", "OutletCode": "SHOP-B",
            "OnHand": "twenty", "ReorderLevel": "10", "UnitCost": "5,000"}
        self._note("stock_count_in_words")

    def _budgets_and_spending(self):
        for code, *_rest, budget, spent in OUTLETS:
            yield "budget", f"BUD-{code}-2026", {
                "BudgetID": f"BUD-{code}-2026", "OutletCode": code, "Year": "2026",
                "Allocated": self._money(budget)}
            # spending spread over the months to mid-October
            for month, amount in zip(range(1, 11), self._split(spent, 10), strict=True):
                day = date(2026, month, min(28, 15 + self.rng.randrange(10)))
                if day > SALES_END:
                    day = SALES_END
                yield "expense", f"EXP-{code}-{month:02d}", {
                    "ExpenseID": f"EXP-{code}-{month:02d}", "OutletCode": code,
                    "Date": self._date(day), "Amount": self._money(amount),
                    "Description": self.rng.choice(EXPENSE_LINES)}
