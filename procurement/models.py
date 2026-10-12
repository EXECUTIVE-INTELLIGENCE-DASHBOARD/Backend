from django.db import models

# Create your models here.

# Define procurement categories.
class ProcurementCategory(models.TextChoices):
    WORKS = "works", "Works (Capital)"
    SERVICES = "services", "Services (Operations)"
    GOODS = "goods", "Goods"


# Define procurement settlement statuses.
class SettlementStatus(models.TextChoices):
    PAID = "paid", "Paid (Disbursed)"
    COMMITTED = "committed", "Committed Budget"
    OUTSTANDING = "outstanding", "Outstanding AP (Unpaid)"


# Store vendor information.
class Vendor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    primary_category = models.CharField(
        max_length=20,
        choices=ProcurementCategory.choices,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Record procurement transactions without a campus link.
class ProcurementTransaction(models.Model):
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    fiscal_year = models.ForeignKey(
        "finance.FiscalYear",
        on_delete=models.PROTECT,
        related_name="procurement_transactions",
    )
    category = models.CharField(
        max_length=20,
        choices=ProcurementCategory.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=SettlementStatus.choices,
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    transaction_date = models.DateField()
    reference_number = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-amount"]
        indexes = [
            models.Index(fields=["vendor", "fiscal_year"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.vendor.name} - {self.amount} "
            f"{self.currency} ({self.status})"
        )
