
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academics.models import Application, Enrolment, School, StudentProfile, Term
from finance.models import (
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
from integrations.models import SourceSystem
from operations.models import (
    Asset,
    Employee,
    Facility,
    StaffAttendance,
    WorkforceUnit,
)
from procurement.models import ProcurementTransaction, Vendor
from services.models import (
    DailySales,
    Outlet,
    OutletBudget,
    OutletExpense,
    StockItem,
)


class Command(BaseCommand):
    help = "Create repeatable sample data for GreenHill dashboards."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        year = today.year
        month_start = today.replace(day=1)
        source, _ = SourceSystem.objects.get_or_create(
            code="sample-data",
            defaults={"name": "Sample Data", "mode": SourceSystem.Mode.MOCK},
        )

        self.stdout.write("Creating academic records...")

        school_data = [
            ("Kibuli Campus", "kibuli", 1200),
            ("Buwaate Campus", "buwaate", 900),
            ("Annex Campus", "annex", 500),
        ]
        schools = []
        for name, campus, capacity in school_data:
            school = School.objects.filter(campus=campus).first()
            if school is None:
                school, _ = School.objects.get_or_create(
                    name=name,
                    defaults={
                        "campus": campus,
                        "capacity": capacity,
                        "minimum_enrolment": 100,
                    },
                )
            schools.append(school)

        term, _ = Term.objects.get_or_create(
            academic_year=f"{year}/{year + 1}",
            number=1,
            defaults={
                "start_date": date(year, 1, 1),
                "end_date": date(year, 12, 31),
            },
        )

        for i in range(1, 31):
            student, _ = StudentProfile.objects.update_or_create(
                student_number=f"STU-{i:04d}",
                defaults={
                    "gender": "female" if i % 2 == 0 else "male",
                    "nationality": "Ugandan",
                    "date_of_birth": date(
                        2008 + i % 5, 1 + i % 12, 1 + i % 27
                    ),
                    "source_system": source,
                    "external_id": f"student-{i:04d}",
                    "last_synced_at": timezone.now(),
                },
            )

            Enrolment.objects.update_or_create(
                student=student,
                term=term,
                defaults={
                    "school": schools[(i - 1) % len(schools)],
                    "class_level": f"Senior {1 + i % 6}",
                    "status": "active",
                    "withdrawal_date": None,
                    "withdrawal_reason": "",
                    "at_risk": i % 10 == 0,
                    "source_system": source,
                    "external_id": f"enrol-{i:04d}",
                    "last_synced_at": timezone.now(),
                },
            )

            Application.objects.update_or_create(
                reference=f"APP-{i:04d}",
                defaults={
                    "school": schools[(i - 1) % len(schools)],
                    "term": term,
                    "stage": [
                        "applied", "qualified", "interviewed",
                        "accepted", "enrolled",
                    ][i % 5],
                    "applied_on": today - timedelta(days=i * 2),
                    "source_system": source,
                    "external_id": f"application-{i:04d}",
                    "last_synced_at": timezone.now(),
                },
            )

        self.stdout.write("Creating finance records...")

        fiscal_year, _ = FiscalYear.objects.get_or_create(
            year=year,
            quarter=(today.month - 1) // 3 + 1,
        )

        departments = []
        for name in [
            "Academics", "Administration", "ICT",
            "Transport", "Facilities",
        ]:
            department, _ = Department.objects.get_or_create(name=name)
            departments.append(department)

        for i, department in enumerate(departments):
            DepartmentBudget.objects.update_or_create(
                department=department,
                fiscal_year=fiscal_year,
                defaults={
                    "budget_amount": Decimal("100000000") + Decimal(i * 10000000),
                    "currency": "UGX",
                },
            )
            MonthlyDepartmentBudget.objects.update_or_create(
                department=department,
                fiscal_year=fiscal_year,
                month=month_start,
                defaults={
                    "budget_amount": Decimal("10000000") + Decimal(i * 1000000),
                    "currency": "UGX",
                },
            )

        creditor_data = [
            ("Utility Provider", "utility"),
            ("Fuel Supplier", "fleet_fuel"),
            ("ICT Supplier", "it_comms"),
            ("School Lender", "lender"),
        ]
        creditors = []
        for i, (name, creditor_type) in enumerate(creditor_data, start=1):
            creditor, _ = Creditor.objects.update_or_create(
                reference_number=f"CRED-{i:03d}",
                defaults={
                    "name": name,
                    "creditor_type": creditor_type,
                },
            )
            creditors.append(creditor)

        liability_statuses = ["current", "due_soon", "overdue", "paid"]
        liability_categories = [
            "current_payables", "accrued_expenses_tax", "long_term_debt",
        ]
        for i, creditor in enumerate(creditors):
            amount = Decimal("5000000") + Decimal(i * 1500000)
            Liability.objects.update_or_create(
                creditor=creditor,
                description=f"School liability {i + 1}",
                defaults={
                    "category": liability_categories[i % 3],
                    "status": liability_statuses[i],
                    "amount": amount,
                    "paid_amount": amount if i == 3 else Decimal("0"),
                    "currency": "UGX",
                    "issued_date": today - timedelta(days=60),
                    "due_date": today + timedelta(days=(i - 1) * 10),
                    "paid_date": today if i == 3 else None,
                },
            )

        for i, school in enumerate(schools, start=1):
            amount = Decimal("20000000") + Decimal(i * 5000000)
            RevenueRecord.objects.update_or_create(
                fiscal_year=fiscal_year,
                school=school,
                stream="tuition",
                billing_date=month_start,
                defaults={
                    "billed_amount": amount,
                    "realized_amount": amount * Decimal("0.8"),
                    "currency": "UGX",
                },
            )
            MonthlyRevenueTarget.objects.update_or_create(
                fiscal_year=fiscal_year,
                school=school,
                month=month_start,
                defaults={
                    "target_amount": amount,
                    "realized_amount": amount * Decimal("0.8"),
                    "currency": "UGX",
                },
            )

            invoice, _ = FeeInvoice.objects.update_or_create(
                invoice_number=f"INV-{i:04d}",
                defaults={
                    "school": school,
                    "fiscal_year": fiscal_year,
                    "student_reference": f"STU-{i:04d}",
                    "stream": "tuition",
                    "issue_date": today - timedelta(days=20),
                    "due_date": today + timedelta(days=10),
                    "amount": Decimal("1500000"),
                    "currency": "UGX",
                    "description": "School tuition fees",
                    "status": "part_paid",
                },
            )
            FeePayment.objects.update_or_create(
                payment_reference=f"PAY-{i:04d}",
                defaults={
                    "invoice": invoice,
                    "payment_date": today,
                    "amount": Decimal("500000"),
                    "currency": "UGX",
                },
            )

        expense_categories = [
            "salaries",
            "utilities_maintenance",
            "instructional_materials",
            "cocurricular_ops",
        ]
        for i, department in enumerate(departments):
            ExpenseTransaction.objects.update_or_create(
                reference_number=f"EXP-{i + 1:04d}",
                defaults={
                    "department": department,
                    "school": schools[i % len(schools)],
                    "category": expense_categories[i % len(expense_categories)],
                    "expense_date": today,
                    "description": f"{department.name} operating expense",
                    "amount": Decimal("2500000") + Decimal(i * 500000),
                    "currency": "UGX",
                },
            )

        for i, school in enumerate(schools, start=1):
            account, _ = BankAccount.objects.update_or_create(
                account_reference=f"BANK-{i:03d}",
                defaults={
                    "school": school,
                    "account_name": f"School Account {i}",
                    "bank_name": "Sample Bank",
                    "account_type": "bank",
                    "balance": Decimal("50000000") + Decimal(i * 10000000),
                    "currency": "UGX",
                    "as_of_date": today,
                    "is_active": True,
                },
            )
            CashMovement.objects.update_or_create(
                reference_number=f"CASH-{i:04d}",
                defaults={
                    "account": account,
                    "movement_date": today,
                    "description": "Tuition receipt",
                    "category": "tuition",
                    "direction": "inflow",
                    "amount": Decimal("1000000"),
                },
            )
            CashForecast.objects.update_or_create(
                school=school,
                forecast_date=today + timedelta(days=7),
                currency="UGX",
                defaults={
                    "forecast_balance": Decimal("45000000") + Decimal(i * 5000000),
                    "actual_balance": account.balance,
                    "notes": "Weekly cash forecast",
                },
            )

        loan, _ = Loan.objects.update_or_create(
            loan_reference="LOAN-001",
            defaults={
                "school": schools[0],
                "creditor": creditors[3],
                "principal_amount": Decimal("50000000"),
                "outstanding_balance": Decimal("40000000"),
                "annual_interest_rate": Decimal("12.00"),
                "currency": "UGX",
                "start_date": today - timedelta(days=90),
                "maturity_date": today + timedelta(days=365),
                "next_installment_date": today + timedelta(days=30),
                "status": "active",
                "description": "School development loan",
            },
        )
        LoanRepayment.objects.update_or_create(
            loan=loan,
            installment_number=1,
            defaults={
                "due_date": today + timedelta(days=30),
                "principal_due": Decimal("5000000"),
                "interest_due": Decimal("500000"),
                "principal_paid": Decimal("0"),
                "interest_paid": Decimal("0"),
                "balance_after_payment": Decimal("40000000"),
                "paid_date": None,
                "status": "scheduled",
            },
        )

        self.stdout.write("Creating procurement records...")

        vendor_data = [
            ("Scholastic Publishers", "goods"),
            ("Building Contractors", "works"),
            ("Catering Services", "services"),
            ("ICT Equipment Supplier", "goods"),
        ]
        vendors = []
        for name, category in vendor_data:
            vendor, _ = Vendor.objects.get_or_create(
                name=name,
                defaults={"primary_category": category},
            )
            vendors.append(vendor)

        for i, vendor in enumerate(vendors):
            ProcurementTransaction.objects.update_or_create(
                vendor=vendor,
                fiscal_year=fiscal_year,
                reference_number=f"PROC-{i + 1:04d}",
                defaults={
                    "category": ["goods", "works", "services", "goods"][i],
                    "status": ["paid", "committed", "outstanding", "paid"][i],
                    "amount": Decimal("10000000") + Decimal(i * 2500000),
                    "currency": "UGX",
                    "transaction_date": today - timedelta(days=i * 7),
                    "description": "School procurement purchase",
                },
            )

        self.stdout.write("Creating operations records...")

        facilities = []
        for i, school in enumerate(schools, start=1):
            facility, _ = Facility.objects.get_or_create(
                name=f"Classroom Block {i}",
                defaults={
                    "campus": school.campus,
                    "facility_type": "classroom",
                    "status": "operational",
                },
            )
            facilities.append(facility)

        for i, facility in enumerate(facilities, start=1):
            Asset.objects.get_or_create(
                name=f"Computer Equipment {i}",
                facility=facility,
                defaults={
                    "category": "computer_equipment",
                    "quantity": 10,
                    "unit_value": Decimal("1500000"),
                    "condition": "operational",
                    "acquired_date": today - timedelta(days=180),
                },
            )

        units = []
        for i, school in enumerate(schools, start=1):
            unit, _ = WorkforceUnit.objects.get_or_create(
                name=f"Teaching Unit {i}",
                defaults={
                    "staff_category": "teaching",
                    "campus": school.campus,
                    "location": school.name,
                },
            )
            units.append(unit)

        for i, unit in enumerate(units, start=1):
            employee, _ = Employee.objects.get_or_create(
                staff_number=f"STAFF-{i:04d}",
                defaults={
                    "full_name": ["Sarah Namusoke", "Peter Okello", "Grace Nanyonga"][i - 1],
                    "unit": unit,
                    "job_title": "Teacher",
                    "employment_type": "full_time",
                    "hire_date": today - timedelta(days=365),
                    "is_active": True,
                },
            )
            StaffAttendance.objects.update_or_create(
                employee=employee,
                date=today,
                defaults={
                    "status": "present",
                    "note": "Present for duty",
                },
            )

        self.stdout.write("Creating commercial outlet records...")

        outlet_data = [
            ("gh-uniform", "Uniform Shop", "uniform_shop"),
            ("gh-cafe", "School Cafe", "cafe"),
            ("gh-minimart", "School Minimart", "minimart"),
        ]
        for code, name, business_type in outlet_data:
            outlet, _ = Outlet.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "business_type": business_type,
                    "source_system": source,
                    "external_id": code,
                    "last_synced_at": timezone.now(),
                },
            )

            DailySales.objects.update_or_create(
                outlet=outlet,
                date=today,
                defaults={
                    "revenue": Decimal("1500000"),
                    "cost_of_sales": Decimal("900000"),
                    "transactions": 45,
                    "source_system": source,
                    "external_id": f"{code}-sales",
                    "last_synced_at": timezone.now(),
                },
            )
            StockItem.objects.update_or_create(
                outlet=outlet,
                name="Stock Item",
                defaults={
                    "on_hand": 100,
                    "minimum_level": 20,
                    "unit_cost": Decimal("10000"),
                    "source_system": source,
                    "external_id": f"{code}-stock",
                    "last_synced_at": timezone.now(),
                },
            )
            OutletBudget.objects.update_or_create(
                outlet=outlet,
                financial_year=year,
                defaults={
                    "allocated": Decimal("30000000"),
                    "source_system": source,
                    "external_id": f"{code}-budget-{year}",
                    "last_synced_at": timezone.now(),
                },
            )
            OutletExpense.objects.update_or_create(
                outlet=outlet,
                date=today,
                description="Operating supplies",
                defaults={
                    "amount": Decimal("250000"),
                    "source_system": source,
                    "external_id": f"{code}-expense",
                    "last_synced_at": timezone.now(),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            "Sample records created or updated successfully."
        ))
