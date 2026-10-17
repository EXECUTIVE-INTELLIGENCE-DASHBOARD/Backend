from rest_framework import serializers

from .models import Employee, StaffAttendance, WorkforceUnit


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
