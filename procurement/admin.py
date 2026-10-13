from django.contrib import admin

from .models import (
    ProcurementTransaction,
    Vendor,
)

admin.site.register([
    Vendor,
    ProcurementTransaction,
])
