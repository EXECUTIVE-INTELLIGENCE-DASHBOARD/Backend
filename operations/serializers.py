from rest_framework import serializers

from .models import Asset, Employee, Facility, StaffAttendance, WorkforceUnit


class WorkforceUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkforceUnit
        fields = '__all__'


class EmployeeSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'


class StaffAttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = '__all__'


# Query parameters accepted by the HR dashboard endpoint.
class HRDashboardQuerySerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    campus = serializers.ChoiceField(choices=WorkforceUnit.Campus.choices, required=False)
    unit = serializers.IntegerField(required=False)

    def validate(self, attrs):
        start, end = attrs.get("start"), attrs.get("end")
        if start and end and start > end:
            raise serializers.ValidationError("start must be on or before end.")
        return attrs


class HRDashboardUnitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    staff_category = serializers.CharField()
    staff_category_display = serializers.CharField()
    campus = serializers.CharField()
    location = serializers.CharField()
    headcount = serializers.IntegerField()
    attendance_rate = serializers.FloatField(allow_null=True)
    absences = serializers.DictField(child=serializers.IntegerField())


class HRDashboardSummarySerializer(serializers.Serializer):
    total_staff = serializers.IntegerField()
    teaching_staff = serializers.IntegerField()
    non_teaching_staff = serializers.IntegerField()
    staffing_ratio = serializers.FloatField(allow_null=True)
    staffing_ratio_display = serializers.CharField(allow_null=True)
    workforce_attendance_rate = serializers.FloatField(allow_null=True)


class HRDashboardSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    summary = HRDashboardSummarySerializer()
    units = HRDashboardUnitSerializer(many=True)


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'


class AssetSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    condition_display = serializers.CharField(source="get_condition_display", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    campus = serializers.CharField(source="facility.campus", read_only=True)
    campus_display = serializers.CharField(source="facility.get_campus_display", read_only=True)
    total_value = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = Asset
        fields = '__all__'


# Query parameters accepted by the asset register dashboard endpoint.
class AssetDashboardQuerySerializer(serializers.Serializer):
    campus = serializers.ChoiceField(choices=Facility.Campus.choices, required=False)
    category = serializers.ChoiceField(choices=Asset.Category.choices, required=False)
    facility = serializers.IntegerField(required=False)


class AssetDashboardSummarySerializer(serializers.Serializer):
    total_assets = serializers.IntegerField()
    total_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    operational_rate = serializers.FloatField(allow_null=True)
    capital_risk = serializers.FloatField(allow_null=True)
    capital_at_risk_value = serializers.DecimalField(max_digits=20, decimal_places=2)
    units_by_condition = serializers.DictField(child=serializers.IntegerField())


class AssetDashboardSerializer(serializers.Serializer):
    summary = AssetDashboardSummarySerializer()
    assets = AssetSerializer(many=True)
