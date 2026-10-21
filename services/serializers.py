from rest_framework import serializers

from .models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem

# Set by the data pipeline only, never through the API.
SOURCE_FIELDS = ("source_system", "external_id", "last_synced_at")


class OutletSerializer(serializers.ModelSerializer):
    business_type_display = serializers.CharField(
        source="get_business_type_display", read_only=True
    )

    class Meta:
        model = Outlet
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class DailySalesSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)

    class Meta:
        model = DailySales
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class StockItemSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)
    business_type_display = serializers.CharField(
        source="outlet.get_business_type_display", read_only=True
    )
    stock_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = StockItem
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS

    def get_status_display(self, obj) -> str:
        return StockItem.Status(obj.status).label


class OutletBudgetSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)

    class Meta:
        model = OutletBudget
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class OutletExpenseSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)

    class Meta:
        model = OutletExpense
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


# --- Sales dashboard ----------------------------------------------------------------

class SalesDashboardQuerySerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    outlet = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if attrs.get("start") and attrs.get("end") and attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("start must be on or before end.")
        return attrs


class SalesSummarySerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=16, decimal_places=2)
    gross_profit = serializers.DecimalField(max_digits=16, decimal_places=2)
    gross_margin = serializers.FloatField(allow_null=True)
    transactions = serializers.IntegerField()
    average_sale = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)


class MonthlySalesSerializer(serializers.Serializer):
    month = serializers.CharField()  # "2026-02"
    label = serializers.CharField()  # "Feb"
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)


class OutletSalesSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    business_type = serializers.CharField()
    business_type_display = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)
    gross_margin = serializers.FloatField(allow_null=True)
    transactions = serializers.IntegerField()
    average_sale = serializers.DecimalField(max_digits=16, decimal_places=2, allow_null=True)


class SalesDashboardSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    summary = SalesSummarySerializer()
    monthly_trend = MonthlySalesSerializer(many=True)
    outlets = OutletSalesSerializer(many=True)


# --- Inventory dashboard ------------------------------------------------------------

class InventoryDashboardQuerySerializer(serializers.Serializer):
    outlet = serializers.IntegerField(required=False)
    status = serializers.ChoiceField(choices=StockItem.Status.choices, required=False)


class InventorySummarySerializer(serializers.Serializer):
    stock_value = serializers.DecimalField(max_digits=16, decimal_places=2)
    below_minimum = serializers.IntegerField()
    critical = serializers.IntegerField()
    outlets = serializers.IntegerField()


class InventoryDashboardSerializer(serializers.Serializer):
    summary = InventorySummarySerializer()
    items = StockItemSerializer(many=True)


# --- Budget utilisation dashboard ---------------------------------------------------

class BudgetDashboardQuerySerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)
    outlet = serializers.IntegerField(required=False)


class BudgetSummarySerializer(serializers.Serializer):
    operating_budget = serializers.DecimalField(max_digits=16, decimal_places=2)
    spent = serializers.DecimalField(max_digits=16, decimal_places=2)
    budget_used = serializers.FloatField(allow_null=True)
    time_elapsed = serializers.FloatField()


class OutletBudgetUseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    business_type_display = serializers.CharField()
    allocated = serializers.DecimalField(max_digits=16, decimal_places=2)
    spent = serializers.DecimalField(max_digits=16, decimal_places=2)
    used = serializers.FloatField(allow_null=True)
    status = serializers.CharField()
    status_display = serializers.CharField()


class BudgetDashboardSerializer(serializers.Serializer):
    financial_year = serializers.IntegerField()
    as_of = serializers.DateField()
    summary = BudgetSummarySerializer()
    outlets = OutletBudgetUseSerializer(many=True)
