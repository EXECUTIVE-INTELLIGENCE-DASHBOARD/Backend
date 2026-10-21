from django.db import models

from integrations.models import SourceTrackedModel, source_record_constraint


class Outlet(SourceTrackedModel):
    """One of GSL's six commercial outlets: uniform shops A to D, the café and the minimart."""

    class BusinessType(models.TextChoices):
        UNIFORM_SHOP = "uniform_shop", "Uniform shop"
        CAFE = "cafe", "Café"
        MINIMART = "minimart", "Minimart"

    code = models.SlugField(max_length=20, unique=True)  # e.g. "shop-a", "cafe"
    name = models.CharField(max_length=100)  # e.g. "Shop A"
    business_type = models.CharField(max_length=20, choices=BusinessType.choices)

    class Meta:
        ordering = ["name"]
        constraints = [source_record_constraint()]

    def __str__(self):
        return self.name


class DailySales(SourceTrackedModel):
    """One outlet's takings for one day, as a till's end-of-day report gives them."""

    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name="daily_sales")
    date = models.DateField()
    revenue = models.DecimalField(max_digits=14, decimal_places=2)  # UGX taken
    # UGX the goods sold cost the outlet; gross profit is revenue minus this
    cost_of_sales = models.DecimalField(max_digits=14, decimal_places=2)
    transactions = models.PositiveIntegerField()  # number of sales rung up

    class Meta:
        ordering = ["-date", "outlet"]
        verbose_name_plural = "daily sales"
        constraints = [
            models.UniqueConstraint(fields=["outlet", "date"], name="unique_daily_sales"),
            source_record_constraint(),
        ]

    def __str__(self):
        return f"{self.outlet} on {self.date}"


class StockItem(SourceTrackedModel):
    """An item an outlet stocks, with its current level and the level to reorder at."""

    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "In stock"
        REORDER_SOON = "reorder_soon", "Reorder soon"  # below the minimum level
        CRITICAL = "critical", "Critical"  # below half the minimum level

    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name="stock_items")
    name = models.CharField(max_length=150)  # e.g. "Boys' shirt (M)"
    on_hand = models.PositiveIntegerField(default=0)  # units in stock now
    minimum_level = models.PositiveIntegerField(default=0)  # reorder when stock falls below
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)  # UGX per unit
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["outlet", "name"]
        constraints = [
            models.UniqueConstraint(fields=["outlet", "name"], name="unique_stock_item"),
            source_record_constraint(),
        ]

    @property
    def stock_value(self):
        """UGX value of the units on hand."""
        return self.on_hand * self.unit_cost

    @property
    def status(self):
        if self.on_hand < self.minimum_level / 2:
            return self.Status.CRITICAL
        if self.on_hand < self.minimum_level:
            return self.Status.REORDER_SOON
        return self.Status.IN_STOCK

    def __str__(self):
        return f"{self.name} ({self.outlet})"


class OutletBudget(SourceTrackedModel):
    """The operating budget allocated to an outlet for one financial year."""

    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name="budgets")
    financial_year = models.PositiveSmallIntegerField()  # e.g. 2026 (January to December)
    allocated = models.DecimalField(max_digits=14, decimal_places=2)  # UGX

    class Meta:
        ordering = ["-financial_year", "outlet"]
        constraints = [
            models.UniqueConstraint(
                fields=["outlet", "financial_year"], name="unique_outlet_budget"
            ),
            source_record_constraint(),
        ]

    def __str__(self):
        return f"{self.outlet} {self.financial_year}"


class OutletExpense(SourceTrackedModel):
    """Money an outlet spent against its operating budget."""

    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name="expenses")
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # UGX
    description = models.CharField(max_length=200, blank=True)  # e.g. "Stock purchase"

    class Meta:
        ordering = ["-date", "outlet"]
        constraints = [source_record_constraint()]

    def __str__(self):
        return f"{self.outlet} {self.date}: {self.amount}"
