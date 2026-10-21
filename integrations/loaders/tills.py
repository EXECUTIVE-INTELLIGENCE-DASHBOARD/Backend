"""Loads staged till and stock records into the Services tables.

Rows are matched by their ID in the till system (source-tracked), so a re-run updates
rather than duplicates: outlets by outlet code, daily sales by report ID, stock items by
SKU, budgets by budget ID and expenses by expense ID.
"""
from services.models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem

from ..cleaning import CleaningError, clean_text, map_choice, parse_date, parse_money
from .base import BaseLoad

BUSINESS_TYPES = {
    "uniform_shop": ["uniform shop", "uniforms", "uniform", "school uniforms"],
    "cafe": ["café", "cafe", "coffee shop"],
    "minimart": ["minimart", "mini-mart", "mini mart"],
}


def _count(value, field):
    text = clean_text(value).replace(",", "")
    if not text.isdigit():
        raise CleaningError(f"{field} '{clean_text(value)}' is not a whole number")
    return int(text)


class TillLoad(BaseLoad):
    record_order = ["outlet", "daily_sales", "stock_item", "budget", "expense"]

    def _existing(self, model):
        return {row.external_id: row for row in model.objects.filter(source_system=self.source)}

    def _upsert(self, model, existing, record, values, to_create, to_update):
        row = existing.get(record.external_id)
        if row is None:
            row = model(external_id=record.external_id, **values)
            to_create.append(row)
        else:
            for field, value in values.items():
                setattr(row, field, value)
            to_update.append(row)
        self.track(row)
        self.loaded(record)
        return row

    def _outlet_of(self, payload, errors):
        outlet = self.outlet_by_code.get(clean_text(payload.get("OutletCode")).upper())
        if outlet is None:
            errors.append(f"outlet '{clean_text(payload.get('OutletCode'))}' is not known")
        return outlet

    def outlets(self):
        existing = self._existing(Outlet)
        by_code = {o.code: o for o in Outlet.objects.all()}
        self.outlet_by_code = {}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["outlet"]):
            p = record.payload
            try:
                code = clean_text(p.get("OutletCode")).upper()
                name = clean_text(p.get("OutletName"))
                if not code or not name:
                    raise CleaningError("outlet code or name is missing")
                kind = map_choice(p.get("Business"), BUSINESS_TYPES, "business type")
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            values = {"code": code.lower(), "name": name.title() if name.isupper() or
                      name.islower() else name, "business_type": kind}
            if record.external_id not in existing and code.lower() in by_code:
                existing[record.external_id] = by_code[code.lower()]  # take over a hand-made one
            outlet = self._upsert(Outlet, existing, record, values, to_create, to_update)
            self.outlet_by_code[code] = outlet
        self.save(Outlet, to_create, to_update,
                  ["code", "name", "business_type", "source_system", "external_id",
                   "last_synced_at"])

    def daily_sales(self):
        existing = self._existing(DailySales)
        by_day = {(s.outlet_id, s.date): s for s in DailySales.objects.all()}
        seen = set()
        to_create, to_update = [], []
        for record in self.unique(self.by_type["daily_sales"]):
            p, errors = record.payload, []
            outlet = self._outlet_of(p, errors)
            try:
                day = parse_date(p.get("Date"), "sales date")
                revenue = parse_money(p.get("Takings"), "takings")
                cost = parse_money(p.get("CostOfSales"), "cost of sales")
                transactions = _count(p.get("Receipts"), "receipts")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            if (outlet.pk, day) in seen:
                self.reject(record, "this outlet already has sales for that day in this sync")
                continue
            seen.add((outlet.pk, day))
            if record.external_id not in existing and (outlet.pk, day) in by_day:
                existing[record.external_id] = by_day[(outlet.pk, day)]
            self._upsert(DailySales, existing, record,
                         {"outlet": outlet, "date": day, "revenue": revenue,
                          "cost_of_sales": cost, "transactions": transactions},
                         to_create, to_update)
        self.save(DailySales, to_create, to_update,
                  ["outlet", "date", "revenue", "cost_of_sales", "transactions",
                   "source_system", "external_id", "last_synced_at"])

    def stock_items(self):
        existing = self._existing(StockItem)
        by_name = {(s.outlet_id, s.name): s for s in StockItem.objects.all()}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["stock_item"]):
            p, errors = record.payload, []
            outlet = self._outlet_of(p, errors)
            name = clean_text(p.get("Item"))
            if not name:
                errors.append("item name is missing")
            try:
                on_hand = _count(p.get("OnHand"), "stock on hand")
                minimum = _count(p.get("ReorderLevel"), "reorder level")
                cost = parse_money(p.get("UnitCost"), "unit cost")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            if record.external_id not in existing and (outlet.pk, name) in by_name:
                existing[record.external_id] = by_name[(outlet.pk, name)]
            self._upsert(StockItem, existing, record,
                         {"outlet": outlet, "name": name[:150], "on_hand": on_hand,
                          "minimum_level": minimum, "unit_cost": cost},
                         to_create, to_update)
        self.save(StockItem, to_create, to_update,
                  ["outlet", "name", "on_hand", "minimum_level", "unit_cost",
                   "source_system", "external_id", "last_synced_at"])

    def budgets(self):
        existing = self._existing(OutletBudget)
        by_year = {(b.outlet_id, b.financial_year): b for b in OutletBudget.objects.all()}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["budget"]):
            p, errors = record.payload, []
            outlet = self._outlet_of(p, errors)
            try:
                year = _count(p.get("Year"), "financial year")
                allocated = parse_money(p.get("Allocated"), "allocated amount")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            if record.external_id not in existing and (outlet.pk, year) in by_year:
                existing[record.external_id] = by_year[(outlet.pk, year)]
            self._upsert(OutletBudget, existing, record,
                         {"outlet": outlet, "financial_year": year, "allocated": allocated},
                         to_create, to_update)
        self.save(OutletBudget, to_create, to_update,
                  ["outlet", "financial_year", "allocated", "source_system", "external_id",
                   "last_synced_at"])

    def expenses(self):
        existing = self._existing(OutletExpense)
        to_create, to_update = [], []
        for record in self.unique(self.by_type["expense"]):
            p, errors = record.payload, []
            outlet = self._outlet_of(p, errors)
            try:
                day = parse_date(p.get("Date"), "expense date")
                amount = parse_money(p.get("Amount"), "amount")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            self._upsert(OutletExpense, existing, record,
                         {"outlet": outlet, "date": day, "amount": amount,
                          "description": clean_text(p.get("Description"))[:200]},
                         to_create, to_update)
        self.save(OutletExpense, to_create, to_update,
                  ["outlet", "date", "amount", "description", "source_system", "external_id",
                   "last_synced_at"])


def load_tills(source, records):
    """Loader for the till and stock system; see integrations.pipeline for the contract."""
    load = TillLoad(source, records)
    load.outlets()
    load.daily_sales()
    load.stock_items()
    load.budgets()
    load.expenses()
    return load.created, load.updated
