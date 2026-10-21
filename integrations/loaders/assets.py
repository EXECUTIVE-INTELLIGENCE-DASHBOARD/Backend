"""Loads staged asset-register records into the Asset Registry tables.

Like the HR loader, rows are matched on natural keys because the operations models
don't have source fields yet: sites by name and campus, assets by name and site.
"""
from operations.models import Asset, Facility

from ..cleaning import (
    CAMPUSES,
    CleaningError,
    clean_text,
    map_choice,
    parse_date,
    parse_money,
)
from .base import BaseLoad

SITE_TYPES = {
    "classroom": ["classroom", "classrooms"],
    "laboratory": ["laboratory", "lab"],
    "hostel": ["hostel", "dormitory"],
    "admin_block": ["admin block", "administration"],
    "sports": ["sports", "sports facility"],
    "dining": ["dining", "dining hall"],
    "other": ["other"],
}
CATEGORIES = {
    "computer_equipment": ["ict hardware", "ict", "computers"],
    "laboratory_equipment": ["science laboratory equipment", "lab equipment", "laboratory"],
    "furniture": ["administrative furniture", "furniture"],
    "machinery": ["power & facility machinery", "machinery", "plant"],
    "vehicle": ["fleet & vehicles", "vehicles", "fleet"],
    "other": ["other"],
}
CONDITIONS = {
    "operational": ["good", "operational", "operational (good)", "working"],
    "servicing_required": ["fair", "needs service", "service due", "servicing required"],
    "critical": ["critical", "repair queued", "critical / repair queued", "broken"],
    "decommissioned": ["disposed", "decommissioned", "retired"],
}


class AssetRegisterLoad(BaseLoad):
    record_order = ["site", "asset"]

    def sites(self):
        existing = {(f.name, f.campus): f for f in Facility.objects.all()}
        self.site_by_code = {}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["site"]):
            p = record.payload
            try:
                name = clean_text(p.get("SiteName"))
                if not name:
                    raise CleaningError("site name is missing")
                campus = map_choice(p.get("Campus"), CAMPUSES, "campus")
                site_type = map_choice(p.get("SiteType"), SITE_TYPES, "site type")
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            site = existing.get((name, campus))
            if site is None:
                site = Facility(name=name, campus=campus, facility_type=site_type)
                to_create.append(site)
                existing[(name, campus)] = site
            else:
                site.facility_type = site_type
                to_update.append(site)
            self.site_by_code[record.external_id] = site
            self.loaded(record)
        self.save(Facility, to_create, to_update, ["facility_type"])

    def assets(self):
        site_ids = [s.pk for s in self.site_by_code.values()]
        existing = {(a.name, a.facility_id): a
                    for a in Asset.objects.filter(facility_id__in=site_ids)}
        to_create, to_update = [], []
        fields = ["category", "quantity", "unit_value", "condition", "acquired_date"]
        for record in self.unique(self.by_type["asset"]):
            p = record.payload
            errors = []
            name = clean_text(p.get("Description"))
            site = self.site_by_code.get(clean_text(p.get("SiteCode")))
            if not name:
                errors.append("description is missing")
            if site is None:
                errors.append(f"site '{clean_text(p.get('SiteCode'))}' is not known")
            try:
                category = map_choice(p.get("Class"), CATEGORIES, "asset class")
                quantity_text = clean_text(p.get("Qty"))
                if not quantity_text.isdigit():
                    raise CleaningError(f"quantity '{quantity_text}' is not a whole number")
                unit_value = parse_money(p.get("UnitCost"), "unit cost")
                condition = map_choice(p.get("Condition"), CONDITIONS, "condition")
                acquired = (parse_date(p["AcquiredOn"], "acquired date")
                            if clean_text(p.get("AcquiredOn")) else None)
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            values = {"category": category, "quantity": int(quantity_text),
                      "unit_value": unit_value, "condition": condition,
                      "acquired_date": acquired}
            asset = existing.get((name, site.pk))
            if asset is None:
                asset = Asset(name=name[:150], facility=site, **values)
                to_create.append(asset)
                existing[(name, site.pk)] = asset
            else:
                for field, value in values.items():
                    setattr(asset, field, value)
                to_update.append(asset)
            self.loaded(record)
        self.save(Asset, to_create, to_update, fields)


def load_asset_register(source, records):
    """Loader for the asset register; see integrations.pipeline for the contract."""
    load = AssetRegisterLoad(source, records)
    load.sites()
    load.assets()
    return load.created, load.updated
