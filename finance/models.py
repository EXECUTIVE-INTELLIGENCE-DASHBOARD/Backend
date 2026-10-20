from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class FiscalYear(models.Model):
    # A financial reporting year and its quarter.

    year = models.CharField(max_length=9)
    quarter = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )

    class Meta:
        ordering = ["-year", "quarter"]
        constraints = [
            models.UniqueConstraint(fields=["year", "quarter"], name="unique_fiscal_year_quarter"),
            models.CheckConstraint(
                condition=Q(quarter__gte=1, quarter__lte=4), name="fiscal_quarter_between_1_and_4"
            ),
        ]

    def __str__(self):
        return f"FY {self.year} Q{self.quarter}"


class Department(models.Model):
    # A department responsible for an allocated budget.

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ExpenseCategory(models.TextChoices):
    SALARIES = "salaries", "Salaries"
    UTILITIES_MAINTENANCE = "utilities_maintenance", "Utilities and Maintenance"
    INSTRUCTIONAL_MATERIALS = "instructional_materials", "Instructional Materials"
    COCURRICULAR_OPS = "cocurricular_ops", "Co-curricular Operations"


class DepartmentBudget(models.Model):
    # The total budget allocated to a department for a fiscal year.

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="annual_budgets"
    )
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="department_budgets"
    )
    budget_amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["fiscal_year", "department"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "fiscal_year"], name="unique_department_annual_budget"
            ),
            models.CheckConstraint(
                condition=Q(budget_amount__gte=0), name="department_budget_nonnegative"
            ),
        ]

    def __str__(self):
        return f"{self.department} - {self.fiscal_year}"


class MonthlyDepartmentBudget(models.Model):
    # The budget allocated to a department for a particular month.

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="monthly_budgets"
    )
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="monthly_department_budgets"
    )
    month = models.DateField(help_text="Use the first day of the month.")
    budget_amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["month", "department"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "fiscal_year", "month"],
                name="unique_department_monthly_budget",
            ),
            models.CheckConstraint(
                condition=Q(budget_amount__gte=0), name="monthly_department_budget_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["fiscal_year", "month"]),
            models.Index(fields=["department", "month"]),
        ]

    def __str__(self):
        return f"{self.department} - {self.month:%Y-%m}"


class ExpenseTransaction(models.Model):
    # An expense incurred by a department, optionally linked to a school.

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="expenses")
    school = models.ForeignKey(
        "academics.School",
        on_delete=models.PROTECT,
        related_name="expense_transactions",
        null=True,
        blank=True,
    )
    category = models.CharField(max_length=40, choices=ExpenseCategory.choices)
    expense_date = models.DateField()
    description = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["-expense_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="expense_amount_nonnegative"),
        ]
        indexes = [
            models.Index(fields=["expense_date", "category"]),
            models.Index(fields=["department", "expense_date"]),
            models.Index(fields=["school", "expense_date"]),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.amount} {self.currency}"


class CreditorType(models.TextChoices):
    LENDER = "lender", "Lender"
    STATUTORY_TAX = "statutory_tax", "Statutory Tax"
    TRADE_PAYABLE = "trade_payable", "Trade Payable"
    INSURER = "insurer", "Insurer"
    UTILITY = "utility", "Utility"
    STATUTORY_REMITTANCE = "statutory_remittance", "Statutory Remittance"
    FLEET_FUEL = "fleet_fuel", "Fleet and Fuel"
    IT_COMMS = "it_comms", "IT and Communications"


class LiabilityCategory(models.TextChoices):
    CURRENT_PAYABLES = "current_payables", "Current Payables"
    ACCRUED_EXPENSES_TAX = "accrued_expenses_tax", "Accrued Expenses and Tax"
    LONG_TERM_DEBT = "long_term_debt", "Long-term Debt and Commitments"


class LiabilityStatus(models.TextChoices):
    CURRENT = "current", "Current"
    DUE_SOON = "due_soon", "Due Soon"
    OVERDUE = "overdue", "Overdue"
    PAID = "paid", "Paid"


class Creditor(models.Model):
    # A lender, supplier, statutory body, or other party owed money.

    name = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=100, unique=True)
    creditor_type = models.CharField(max_length=30, choices=CreditorType.choices)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Liability(models.Model):
    # A financial obligation, including its original and paid amounts.

    creditor = models.ForeignKey(Creditor, on_delete=models.PROTECT, related_name="liabilities")
    category = models.CharField(max_length=30, choices=LiabilityCategory.choices)
    status = models.CharField(
        max_length=20, choices=LiabilityStatus.choices, default=LiabilityStatus.CURRENT
    )
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="UGX")
    due_date = models.DateField()
    issued_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["due_date", "creditor"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="liability_amount_nonnegative"),
            models.CheckConstraint(
                condition=Q(paid_amount__gte=0), name="liability_paid_amount_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(paid_amount__lte=F("amount")), name="liability_paid_not_above_amount"
            ),
        ]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["creditor", "due_date"]),
        ]

    @property
    def outstanding_amount(self):
        # Return the unpaid portion of this liability.
        return self.amount - self.paid_amount

    def __str__(self):
        return f"{self.creditor} - {self.amount} {self.currency}"


class RevenueStream(models.TextChoices):
    TUITION = "tuition", "Tuition"
    EXTRACURRICULAR = "extracurricular", "Extracurricular"
    ADMISSION_REGISTRATION = "admission_registration", "Admission and Registration"
    TRANSPORT = "transport", "Transport"
    MINIMART = "minimart", "Minimart"
    DONATIONS = "donations", "Donations"
    ALUMNI = "alumni", "Alumni"


class RevenueRecord(models.Model):
    # A record of revenue billed and collected for a fiscal year.

    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="revenue_records"
    )
    school = models.ForeignKey(
        "academics.School",
        on_delete=models.PROTECT,
        related_name="revenue_records",
        null=True,
        blank=True,
    )
    stream = models.CharField(max_length=30, choices=RevenueStream.choices)
    billed_amount = models.DecimalField(max_digits=16, decimal_places=2)
    realized_amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    billing_date = models.DateField()

    class Meta:
        ordering = ["-billing_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(billed_amount__gte=0), name="revenue_billed_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(realized_amount__gte=0), name="revenue_realized_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["fiscal_year", "stream"]),
            models.Index(fields=["school", "billing_date"]),
            models.Index(fields=["billing_date", "currency"]),
        ]

    @property
    def arrears_amount(self):
        # Return the unpaid billed amount, never below zero.
        return max(self.billed_amount - self.realized_amount, 0)

    def __str__(self):
        return f"{self.get_stream_display()} - {self.billed_amount}"


class MonthlyRevenueTarget(models.Model):
    # A monthly revenue target and its recorded collections.

    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="monthly_revenue_targets"
    )
    school = models.ForeignKey(
        "academics.School",
        on_delete=models.PROTECT,
        related_name="monthly_revenue_targets",
        null=True,
        blank=True,
    )
    month = models.DateField(help_text="Use the first day of the month.")
    target_amount = models.DecimalField(max_digits=16, decimal_places=2)
    realized_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["month", "school"]
        constraints = [
            models.UniqueConstraint(
                fields=["fiscal_year", "school", "month"],
                name="unique_school_monthly_revenue_target",
            ),
            models.CheckConstraint(
                condition=Q(target_amount__gte=0), name="monthly_revenue_target_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(realized_amount__gte=0) | Q(realized_amount__isnull=True),
                name="monthly_revenue_realized_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["fiscal_year", "month"]),
            models.Index(fields=["school", "month"]),
        ]

    def __str__(self):
        return f"{self.school or 'All schools'} - {self.month:%Y-%m}"


class FeeInvoice(models.Model):
    # An invoice issued for a student's school fees or other charges.

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        PART_PAID = "part_paid", "Part Paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    school = models.ForeignKey(
        "academics.School", on_delete=models.PROTECT, related_name="fee_invoices"
    )
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, related_name="fee_invoices"
    )
    student_reference = models.CharField(max_length=100)
    invoice_number = models.CharField(max_length=100, unique=True)
    stream = models.CharField(max_length=30, choices=RevenueStream.choices)
    issue_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)

    class Meta:
        ordering = ["-issue_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="fee_invoice_amount_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(due_date__gte=F("issue_date")), name="fee_invoice_due_after_issue"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "due_date"]),
            models.Index(fields=["fiscal_year", "status"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self):
        return self.invoice_number


class FeePayment(models.Model):
    # A payment received against a fee invoice.

    invoice = models.ForeignKey(FeeInvoice, on_delete=models.PROTECT, related_name="payments")
    payment_reference = models.CharField(max_length=100, unique=True)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")

    class Meta:
        ordering = ["-payment_date"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="fee_payment_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["payment_date"]),
            models.Index(fields=["invoice", "payment_date"]),
        ]

    def __str__(self):
        return f"{self.payment_reference} - {self.amount} {self.currency}"


class BankAccount(models.Model):
    # A bank or cash account and its reported balance.

    class AccountType(models.TextChoices):
        BANK = "bank", "Bank"
        CASH = "cash", "Cash"

    school = models.ForeignKey(
        "academics.School",
        on_delete=models.PROTECT,
        related_name="bank_accounts",
        null=True,
        blank=True,
    )
    account_name = models.CharField(max_length=150)
    bank_name = models.CharField(max_length=150, blank=True)
    account_reference = models.CharField(max_length=100, unique=True)
    account_type = models.CharField(max_length=10, choices=AccountType.choices)
    balance = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    as_of_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["account_name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(balance__gte=0), name="bank_account_balance_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "is_active"]),
            models.Index(fields=["as_of_date", "currency"]),
        ]

    def __str__(self):
        return self.account_name


class CashMovement(models.Model):
    # An inflow or outflow recorded against a bank or cash account.

    class Direction(models.TextChoices):
        INFLOW = "inflow", "Inflow"
        OUTFLOW = "outflow", "Outflow"

    account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="movements")
    movement_date = models.DateField()
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    reference_number = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["-movement_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="cash_movement_amount_nonnegative"
            ),
        ]
        indexes = [
            models.Index(fields=["account", "movement_date"]),
            models.Index(fields=["direction", "movement_date"]),
        ]

    def __str__(self):
        return f"{self.reference_number} - {self.amount}"


class CashForecast(models.Model):
    # A forecast or actual cash balance for a particular date.

    school = models.ForeignKey(
        "academics.School",
        on_delete=models.PROTECT,
        related_name="cash_forecasts",
        null=True,
        blank=True,
    )
    forecast_date = models.DateField()
    forecast_balance = models.DecimalField(max_digits=16, decimal_places=2)
    actual_balance = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="UGX")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["forecast_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "forecast_date", "currency"],
                name="unique_school_cash_forecast_date_currency",
            ),
            models.CheckConstraint(
                condition=Q(forecast_balance__gte=0), name="cash_forecast_balance_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(actual_balance__gte=0) | Q(actual_balance__isnull=True),
                name="cash_actual_balance_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "forecast_date"]),
        ]

    def __str__(self):
        return f"Cash forecast - {self.forecast_date}"


class Loan(models.Model):
    # A loan and its current outstanding balance.

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SETTLED = "settled", "Settled"
        DEFAULTED = "defaulted", "Defaulted"

    school = models.ForeignKey(
        "academics.School", on_delete=models.PROTECT, related_name="loans", null=True, blank=True
    )
    creditor = models.ForeignKey(Creditor, on_delete=models.PROTECT, related_name="loans")
    loan_reference = models.CharField(max_length=100, unique=True)
    principal_amount = models.DecimalField(max_digits=16, decimal_places=2)
    outstanding_balance = models.DecimalField(max_digits=16, decimal_places=2)
    annual_interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    currency = models.CharField(max_length=3, default="UGX")
    start_date = models.DateField()
    maturity_date = models.DateField()
    next_installment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["maturity_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(principal_amount__gte=0), name="loan_principal_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(outstanding_balance__gte=0), name="loan_balance_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(outstanding_balance__lte=F("principal_amount")),
                name="loan_balance_not_above_principal",
            ),
            models.CheckConstraint(
                condition=Q(maturity_date__gte=F("start_date")), name="loan_maturity_after_start"
            ),
        ]
        indexes = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["status", "next_installment_date"]),
        ]

    def __str__(self):
        return self.loan_reference


class LoanRepayment(models.Model):
    # A scheduled loan installment and its repayment progress.

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        PART_PAID = "part_paid", "Part Paid"

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    principal_due = models.DecimalField(max_digits=16, decimal_places=2)
    interest_due = models.DecimalField(max_digits=16, decimal_places=2)
    principal_paid = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    interest_paid = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    balance_after_payment = models.DecimalField(max_digits=16, decimal_places=2)
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    class Meta:
        ordering = ["loan", "installment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_number"], name="unique_loan_installment_number"
            ),
            models.CheckConstraint(
                condition=Q(principal_due__gte=0), name="loan_principal_due_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(interest_due__gte=0), name="loan_interest_due_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(principal_paid__gte=0), name="loan_principal_paid_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(interest_paid__gte=0), name="loan_interest_paid_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(principal_paid__lte=F("principal_due")),
                name="loan_principal_paid_not_above_due",
            ),
            models.CheckConstraint(
                condition=Q(interest_paid__lte=F("interest_due")),
                name="loan_interest_paid_not_above_due",
            ),
            models.CheckConstraint(
                condition=Q(balance_after_payment__gte=0),
                name="loan_installment_balance_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["due_date", "status"]),
        ]

    @property
    def installment_total(self):
        # Return the scheduled principal plus interest.
        return self.principal_due + self.interest_due

    @property
    def installment_paid(self):
        # Return the principal and interest paid so far.
        return self.principal_paid + self.interest_paid

    @property
    def installment_outstanding(self):
        # Return the remaining amount due for this installment.
        return self.installment_total - self.installment_paid

    def __str__(self):
        return f"{self.loan.loan_reference} - Installment {self.installment_number}"
