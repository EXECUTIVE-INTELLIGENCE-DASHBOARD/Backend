from rest_framework import serializers

from .models import (
    Creditor,
    Department,
    DepartmentBudget,
    ExpenseCategory,
    FiscalYear,
    Liability,
    MonthlyRevenueTarget,
    RevenueRecord,
)


class CreditorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Creditor
        fields = '__all__'
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
class DepartmentBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentBudget
        fields = '__all__'
class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'
class FiscalYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalYear
        fields = '__all__'
class LiabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Liability
        fields = '__all__'
class MonthlyRevenueTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyRevenueTarget
        fields = '__all__'
class RevenueRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevenueRecord
        fields = '__all__'