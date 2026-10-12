
from django.db import models


# Define the available fiscal years and quarters.
class FiscalYear(models.Model):
    year = models.CharField(max_length=9)
    quarter = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["-year", "quarter"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "quarter"],
                name="unique_fiscal_year_quarter",
            ),
            models.CheckConstraint(
                condition=models.Q(quarter__gte=1, quarter__lte=4),
                name="valid_fiscal_year_quarter",
            ),
        ]

    def __str__(self):
        return f"{self.year} / Q{self.quarter}"


# Store departments within the institution.
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Define expense categories.
class ExpenseCategory(models.TextChoices):
    SALARIES = "salaries", "Salaries & Allowances"
    UTILITIES_MAINTENANCE = (
        "utilities_maintenance",
        "Utilities & Maintenance",
    )
    INSTRUCTIONAL_MATERIALS = (
        "instructional_materials",
        "Instructional Materials",
    )
    COCURRICULAR_OPS = "cocurricular_ops", "Co-curricular & Ops"


# Store departmental budgets by fiscal year.
class DepartmentBudget(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.CASCADE,
        related_name="department_budgets",
    )
    budget_amount = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["department__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "fiscal_year"],
                name="unique_department_fiscal_year_budget",
            ),
        ]

    def __str__(self):
        return f"{self.department.name} - {self.fiscal_year}"


# Define the supported creditor types.
class CreditorType(models.TextChoices):
    LENDER = "lender", "Lender / Term Loan"
    STATUTORY_TAX = "statutory_tax", "Statutory Tax"
    TRADE_PAYABLE = "trade_payable", "Trade Invoices Payable"
    INSURER = "insurer", "Service / Insurer"
    UTILITY = "utility", "Utility Creditor"
    STATUTORY_REMITTANCE = "statutory_remittance", "Statutory Remittance"
    FLEET_FUEL = "fleet_fuel", "Fleet & Generator Fuel"
    IT_COMMS = "it_comms", "IT & Communication"


# Classify liabilities by their financial nature.
class LiabilityCategory(models.TextChoices):
    CURRENT_PAYABLES = "current_payables", "Current Payables"
    ACCRUED_EXPENSES_TAX = "accrued_expenses_tax", "Accrued Expenses & Tax"
    LONG_TERM_DEBT = "long_term_debt", "Long-Term Debt & Commitments"


# Define liability payment statuses.
class LiabilityStatus(models.TextChoices):
    CURRENT = "current", "Current"
    DUE_SOON = "due_soon", "Due in Next 30 Days"
    OVERDUE = "overdue", "Overdue"
    PAID = "paid", "Paid"


# Store creditor details.
class Creditor(models.Model):
    name = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)
    creditor_type = models.CharField(
        max_length=30,
        choices=CreditorType.choices,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Track liabilities without a campus relationship for now.
class Liability(models.Model):
    creditor = models.ForeignKey(
        Creditor,
        on_delete=models.PROTECT,
        related_name="liabilities",
    )
    category = models.CharField(
        max_length=30,
        choices=LiabilityCategory.choices,
    )
    status = models.CharField(
        max_length=20,
        choices=LiabilityStatus.choices,
        default=LiabilityStatus.CURRENT,
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    due_date = models.DateField()
    issued_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-amount"]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self):
        return f"{self.creditor.name} - {self.amount} {self.currency}"


# Define the school's revenue streams.
class RevenueStream(models.TextChoices):
    TUITION = "tuition", "Tuition"
    EXTRACURRICULAR = "extracurricular", "Extracurricular & Clubs"
    ADMISSION_REGISTRATION = (
        "admission_registration",
        "Admission & Registration",
    )
    TRANSPORT = "transport", "Transport & Shuttle Services"
    DONATIONS = "donations", "Donations"
    ALUMNI = "alumni", "Alumni Contributions"


# Track billed and collected revenue by fiscal year.
class RevenueRecord(models.Model):
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="revenue_records",
    )
    stream = models.CharField(
        max_length=30,
        choices=RevenueStream.choices,
    )
    billed_amount = models.DecimalField(max_digits=16, decimal_places=2)
    realized_amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    billing_date = models.DateField()

    class Meta:
        ordering = ["-billed_amount"]
        indexes = [
            models.Index(fields=["fiscal_year", "stream"]),
        ]

    @property
    def arrears_amount(self):
        # Calculate the outstanding amount.
        return self.billed_amount - self.realized_amount

    def __str__(self):
        return f"{self.stream} - {self.billed_amount} {self.currency}"


# Store monthly revenue targets and actual collections.
class MonthlyRevenueTarget(models.Model):
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name="monthly_targets",
    )
    month = models.DateField()
    target_amount = models.DecimalField(max_digits=16, decimal_places=2)
    realized_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["month"]
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_year", "month"],
                name="unique_monthly_revenue_target",
            ),
        ]

    def __str__(self):
        return f"{self.month:%b %Y} - {self.target_amount} {self.currency}"
