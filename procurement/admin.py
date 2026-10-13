from django.contrib import admin

from .models import (
    Vendor,
    ProcurementTransaction,
)

admin.site.register([
    Vendor,
    ProcurementTransaction,
])
