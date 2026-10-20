
from django.db.models import Sum
from rest_framework import serializers

from .models import (
    BankAccount,
    CashForecast,
    CashMovement,
    Creditor,
    Department,
    DepartmentBudget,
    ExpenseTransaction,
    FeeInvoice,
    FeePayment,
    FiscalYear,
    Liability,
    Loan,
    LoanRepayment,
    MonthlyDepartmentBudget,
    MonthlyRevenueTarget,
    RevenueRecord,
)


class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = "__all__"

    def validate_quarter(self, value):
        if value not in range(1, 5):
            raise serializers.ValidationError("Quarter must be between 1 and 4.")
        return value


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class DepartmentBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentBudget
        fields = "__all__"

    def validate_budget_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Budget amount cannot be negative.")
        return value


class MonthlyDepartmentBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyDepartmentBudget
        fields = "__all__"

    def validate_budget_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Budget amount cannot be negative.")
        return value

    def validate_month(self, value):
        if value.day != 1:
            raise serializers.ValidationError(
                "Month must be represented by its first day."
            )
        return value


class ExpenseTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseTransaction
        fields = "__all__"

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Expense amount cannot be negative.")
        return value


class CreditorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Creditor
        fields = "__all__"


class LiabilitySerializer(serializers.ModelSerializer):
    outstanding_amount = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = Liability
        fields = "__all__"

    def validate(self, attrs):
        amount = attrs.get(
            "amount",
            getattr(self.instance, "amount", None),
        )
        paid_amount = attrs.get(
            "paid_amount",
            getattr(self.instance, "paid_amount", None),
        )

        if amount is not None and amount < 0:
            raise serializers.ValidationError(
                {"amount": "Liability amount cannot be negative."}
            )

        if paid_amount is not None and paid_amount < 0:
            raise serializers.ValidationError(
                {"paid_amount": "Paid amount cannot be negative."}
            )

        if amount is not None and paid_amount is not None and paid_amount > amount:
            raise serializers.ValidationError(
                {"paid_amount": "Paid amount cannot exceed the liability amount."}
            )

        return attrs


class RevenueRecordSerializer(serializers.ModelSerializer):
    arrears_amount = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = RevenueRecord
        fields = "__all__"

    def validate(self, attrs):
        billed_amount = attrs.get(
            "billed_amount",
            getattr(self.instance, "billed_amount", None),
        )
        realized_amount = attrs.get(
            "realized_amount",
            getattr(self.instance, "realized_amount", None),
        )

        if billed_amount is not None and billed_amount < 0:
            raise serializers.ValidationError(
                {"billed_amount": "Billed amount cannot be negative."}
            )

        if realized_amount is not None and realized_amount < 0:
            raise serializers.ValidationError(
                {"realized_amount": "Realized amount cannot be negative."}
            )

        return attrs


class MonthlyRevenueTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyRevenueTarget
        fields = "__all__"

    def validate(self, attrs):
        target_amount = attrs.get(
            "target_amount",
            getattr(self.instance, "target_amount", None),
        )
        realized_amount = attrs.get(
            "realized_amount",
            getattr(self.instance, "realized_amount", None),
        )
        month = attrs.get("month", getattr(self.instance, "month", None))

        if target_amount is not None and target_amount < 0:
            raise serializers.ValidationError(
                {"target_amount": "Target amount cannot be negative."}
            )

        if realized_amount is not None and realized_amount < 0:
            raise serializers.ValidationError(
                {"realized_amount": "Realized amount cannot be negative."}
            )

        if month is not None and month.day != 1:
            raise serializers.ValidationError(
                {"month": "Month must be represented by its first day."}
            )

        return attrs


class FeeInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInvoice
        fields = "__all__"

    def validate(self, attrs):
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        issue_date = attrs.get(
            "issue_date",
            getattr(self.instance, "issue_date", None),
        )
        due_date = attrs.get(
            "due_date",
            getattr(self.instance, "due_date", None),
        )

        if amount is not None and amount < 0:
            raise serializers.ValidationError(
                {"amount": "Invoice amount cannot be negative."}
            )

        if issue_date and due_date and due_date < issue_date:
            raise serializers.ValidationError(
                {"due_date": "Due date cannot be before the issue date."}
            )

        return attrs


class FeePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeePayment
        fields = "__all__"

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero."
            )
        return value

    def validate(self, attrs):
        invoice = attrs.get("invoice", getattr(self.instance, "invoice", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", None))
        currency = attrs.get("currency", getattr(self.instance, "currency", None))

        if invoice is None or amount is None:
            return attrs

        if invoice.status == FeeInvoice.Status.VOID:
            raise serializers.ValidationError(
                {"invoice": "Payments cannot be recorded against a void invoice."}
            )

        if currency != invoice.currency:
            raise serializers.ValidationError(
                {"currency": "Payment currency must match the invoice currency."}
            )

        existing_payments = invoice.payments.all()

        if self.instance:
            existing_payments = existing_payments.exclude(pk=self.instance.pk)

        already_paid = existing_payments.aggregate(total=Sum("amount"))["total"] or 0
        remaining = invoice.amount - already_paid

        if amount > remaining:
            raise serializers.ValidationError(
                {
                    "amount": (
                        f"Payment exceeds the remaining invoice balance of "
                        f"{remaining} {invoice.currency}."
                    )
                }
            )

        return attrs


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = "__all__"

    def validate_balance(self, value):
        if value < 0:
            raise serializers.ValidationError("Account balance cannot be negative.")
        return value


class CashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = "__all__"

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Movement amount cannot be negative.")
        return value


class CashForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashForecast
        fields = "__all__"

    def validate(self, attrs):
        forecast_balance = attrs.get(
            "forecast_balance",
            getattr(self.instance, "forecast_balance", None),
        )
        actual_balance = attrs.get(
            "actual_balance",
            getattr(self.instance, "actual_balance", None),
        )

        if forecast_balance is not None and forecast_balance < 0:
            raise serializers.ValidationError(
                {"forecast_balance": "Forecast balance cannot be negative."}
            )

        if actual_balance is not None and actual_balance < 0:
            raise serializers.ValidationError(
                {"actual_balance": "Actual balance cannot be negative."}
            )

        return attrs


class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = "__all__"

    def validate(self, attrs):
        principal_amount = attrs.get(
            "principal_amount",
            getattr(self.instance, "principal_amount", None),
        )
        outstanding_balance = attrs.get(
            "outstanding_balance",
            getattr(self.instance, "outstanding_balance", None),
        )
        annual_interest_rate = attrs.get(
            "annual_interest_rate",
            getattr(self.instance, "annual_interest_rate", None),
        )
        start_date = attrs.get(
            "start_date",
            getattr(self.instance, "start_date", None),
        )
        maturity_date = attrs.get(
            "maturity_date",
            getattr(self.instance, "maturity_date", None),
        )

        if principal_amount is not None and principal_amount < 0:
            raise serializers.ValidationError(
                {"principal_amount": "Principal amount cannot be negative."}
            )

        if outstanding_balance is not None and outstanding_balance < 0:
            raise serializers.ValidationError(
                {"outstanding_balance": "Outstanding balance cannot be negative."}
            )

        if (
            principal_amount is not None
            and outstanding_balance is not None
            and outstanding_balance > principal_amount
        ):
            raise serializers.ValidationError(
                {
                    "outstanding_balance": (
                        "Outstanding balance cannot exceed the principal amount."
                    )
                }
            )

        if annual_interest_rate is not None and not 0 <= annual_interest_rate <= 100:
            raise serializers.ValidationError(
                {"annual_interest_rate": "Interest rate must be between 0 and 100."}
            )

        if start_date and maturity_date and maturity_date < start_date:
            raise serializers.ValidationError(
                {"maturity_date": "Maturity date cannot be before the start date."}
            )

        return attrs


class LoanRepaymentSerializer(serializers.ModelSerializer):
    installment_total = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )
    installment_paid = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )
    installment_outstanding = serializers.DecimalField(
        max_digits=16, decimal_places=2, read_only=True
    )

    class Meta:
        model = LoanRepayment
        fields = "__all__"

    def validate(self, attrs):
        fields_to_check = (
            "principal_due",
            "interest_due",
            "principal_paid",
            "interest_paid",
        )

        values = {
            field: attrs.get(field, getattr(self.instance, field, None))
            for field in fields_to_check
        }

        for field, value in values.items():
            if value is not None and value < 0:
                raise serializers.ValidationError(
                    {field: "Amount cannot be negative."}
                )

        principal_due = values["principal_due"]
        interest_due = values["interest_due"]
        principal_paid = values["principal_paid"]
        interest_paid = values["interest_paid"]

        if (
            principal_due is not None
            and principal_paid is not None
            and principal_paid > principal_due
        ):
            raise serializers.ValidationError(
                {"principal_paid": "Principal paid cannot exceed principal due."}
            )

        if (
            interest_due is not None
            and interest_paid is not None
            and interest_paid > interest_due
        ):
            raise serializers.ValidationError(
                {"interest_paid": "Interest paid cannot exceed interest due."}
            )

        balance_after_payment = attrs.get(
            "balance_after_payment",
            getattr(self.instance, "balance_after_payment", None),
        )

        if balance_after_payment is not None and balance_after_payment < 0:
            raise serializers.ValidationError(
                {"balance_after_payment": "Balance cannot be negative."}
            )

        return attrs
