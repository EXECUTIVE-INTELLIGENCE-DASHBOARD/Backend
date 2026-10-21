from rest_framework import serializers

from .models import (
    Academic,
    Application,
    Assessment,
    AssessmentResult,
    Attendance,
    Curricular,
    Enrolment,
    Events,
    GradeResult,
    Homework,
    NationalExamResult,
    School,
    Section,
    Staff,
    Student,
    StudentProfile,
    Subject,
    SyllabusCoverage,
    Term,
    grade_for,
)


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'

class AcademicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Academic
        fields = '__all__'

class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = '__all__'

class GradeResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeResult
        fields = '__all__'

class HomeworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = '__all__'

class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'

class CurricularSerializer(serializers.ModelSerializer):
    class Meta:
        model = Curricular
        fields = '__all__'

class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = '__all__'

class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = '__all__'


# --- Enrolment & retention ------------------------------------------------------

# Set by the data pipeline only, never through the API.
SOURCE_FIELDS = ("source_system", "external_id", "last_synced_at")

class SchoolSerializer(serializers.ModelSerializer):
    campus_display = serializers.CharField(source="get_campus_display", read_only=True)

    class Meta:
        model = School
        fields = '__all__'


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = '__all__'

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and start > end:
            raise serializers.ValidationError("start_date must be on or before end_date.")
        return attrs


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class EnrolmentSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    withdrawal_reason_display = serializers.CharField(
        source="get_withdrawal_reason_display", read_only=True
    )

    class Meta:
        model = Enrolment
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", Enrolment.Status.ACTIVE))
        reason = attrs.get("withdrawal_reason", getattr(self.instance, "withdrawal_reason", ""))
        if status == Enrolment.Status.WITHDRAWN and not reason:
            raise serializers.ValidationError(
                {"withdrawal_reason": "A withdrawn enrolment needs a reason."}
            )
        if status != Enrolment.Status.WITHDRAWN and reason:
            raise serializers.ValidationError(
                {"withdrawal_reason": "Only withdrawn enrolments have a reason."}
            )
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


# Query parameters shared by the enrolment and retention dashboards.
class AcademicDashboardQuerySerializer(serializers.Serializer):
    term = serializers.IntegerField(required=False)
    campus = serializers.ChoiceField(choices=School.Campus.choices, required=False)
    school = serializers.IntegerField(required=False)


class TermSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()


class EnrollmentSummarySerializer(serializers.Serializer):
    total_active_enrolment = serializers.IntegerField()
    admissions_conversion = serializers.FloatField(allow_null=True)
    capacity = serializers.IntegerField()
    capacity_utilisation = serializers.FloatField(allow_null=True)


class GenderSplitSerializer(serializers.Serializer):
    boys = serializers.IntegerField()
    girls = serializers.IntegerField()
    boys_pct = serializers.FloatField(allow_null=True)
    girls_pct = serializers.FloatField(allow_null=True)


class CampusEnrolmentSerializer(serializers.Serializer):
    campus = serializers.CharField()
    campus_display = serializers.CharField()
    boys = serializers.IntegerField()
    girls = serializers.IntegerField()
    total = serializers.IntegerField()


class SchoolEnrolmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    campus = serializers.CharField()
    enrolled = serializers.IntegerField()
    capacity = serializers.IntegerField()
    minimum_enrolment = serializers.IntegerField()
    below_minimum = serializers.BooleanField()


class PipelineStageSerializer(serializers.Serializer):
    stage = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    rate = serializers.FloatField(allow_null=True)


class EnrollmentDashboardSerializer(serializers.Serializer):
    term = TermSummarySerializer()
    summary = EnrollmentSummarySerializer()
    gender = GenderSplitSerializer()
    campuses = CampusEnrolmentSerializer(many=True)
    schools = SchoolEnrolmentSerializer(many=True)
    pipeline = PipelineStageSerializer(many=True)


class RetentionSummarySerializer(serializers.Serializer):
    eligible_to_return = serializers.IntegerField()
    total_re_enrolled = serializers.IntegerField()
    re_enrolment_rate = serializers.FloatField(allow_null=True)
    at_risk = serializers.IntegerField()


class NationalityRetentionSerializer(serializers.Serializer):
    nationality = serializers.CharField()
    campus = serializers.CharField()
    campus_display = serializers.CharField()
    eligible = serializers.IntegerField()
    re_enrolled = serializers.IntegerField()
    retention_rate = serializers.FloatField(allow_null=True)


class WithdrawalReasonSerializer(serializers.Serializer):
    reason = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    share = serializers.FloatField(allow_null=True)


class RetentionDashboardSerializer(serializers.Serializer):
    term = TermSummarySerializer()
    academic_year = serializers.CharField()
    # last term of the previous academic year, which retention is measured against
    compared_with = TermSummarySerializer(allow_null=True)
    summary = RetentionSummarySerializer()
    by_nationality = NationalityRetentionSerializer(many=True)
    withdrawals_total = serializers.IntegerField()
    withdrawal_reasons = WithdrawalReasonSerializer(many=True)


# --- Academic performance ---------------------------------------------------------

class SubjectSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Subject
        fields = '__all__'


class AssessmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Assessment
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class AssessmentResultSerializer(serializers.ModelSerializer):
    passed = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssessmentResult
        fields = '__all__'
        # the grade always follows from the mark, on the subject level's scale
        read_only_fields = SOURCE_FIELDS + ("grade",)

    def validate(self, attrs):
        assessment = attrs.get("assessment", getattr(self.instance, "assessment", None))
        mark = attrs.get("mark", getattr(self.instance, "mark", None))
        if assessment is not None and mark is not None:
            attrs["grade"] = grade_for(assessment.subject.level, mark)
        return attrs


class SyllabusCoverageSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = SyllabusCoverage
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS

    def validate(self, attrs):
        planned = attrs.get("topics_planned", getattr(self.instance, "topics_planned", None))
        covered = attrs.get("topics_covered", getattr(self.instance, "topics_covered", None))
        if planned is not None and covered is not None and covered > planned:
            raise serializers.ValidationError(
                {"topics_covered": "Topics covered can't be more than topics planned."}
            )
        return attrs


class NationalExamResultSerializer(serializers.ModelSerializer):
    exam_display = serializers.CharField(source="get_exam_display", read_only=True)
    division_display = serializers.CharField(source="get_division_display", read_only=True)

    class Meta:
        model = NationalExamResult
        fields = '__all__'
        read_only_fields = SOURCE_FIELDS


class PerformanceDashboardQuerySerializer(serializers.Serializer):
    term = serializers.IntegerField(required=False)
    campus = serializers.ChoiceField(choices=School.Campus.choices, required=False)
    level = serializers.ChoiceField(choices=School.Level.choices, required=False)
    school = serializers.IntegerField(required=False)


class PerformanceSummarySerializer(serializers.Serializer):
    syllabus_coverage = serializers.FloatField(allow_null=True)
    topics_covered = serializers.IntegerField()
    topics_planned = serializers.IntegerField()
    student_performance = serializers.FloatField(allow_null=True)
    students_passing = serializers.IntegerField()
    students_assessed = serializers.IntegerField()
    average_mark = serializers.FloatField(allow_null=True)
    average_grade = serializers.CharField(allow_null=True)


class GradeCountSerializer(serializers.Serializer):
    grade = serializers.CharField()
    students = serializers.IntegerField()
    share = serializers.FloatField(allow_null=True)


class GradeDistributionSerializer(serializers.Serializer):
    level = serializers.CharField()
    level_display = serializers.CharField()
    students = serializers.IntegerField()
    grades = GradeCountSerializer(many=True)


class DivisionCountSerializer(serializers.Serializer):
    division = serializers.CharField()
    label = serializers.CharField()
    candidates = serializers.IntegerField()


class NationalExamSummarySerializer(serializers.Serializer):
    exam = serializers.CharField()
    label = serializers.CharField()
    year = serializers.IntegerField()
    sat = serializers.IntegerField()
    passed = serializers.IntegerField()
    pass_rate = serializers.FloatField(allow_null=True)
    divisions = DivisionCountSerializer(many=True)


class SubjectPerformanceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject = serializers.CharField()
    code = serializers.CharField()
    level = serializers.CharField()
    level_display = serializers.CharField()
    category = serializers.CharField()
    average_mark = serializers.FloatField(allow_null=True)
    pass_rate = serializers.FloatField(allow_null=True)
    previous_pass_rate = serializers.FloatField(allow_null=True)
    results = serializers.IntegerField()


class TestResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject = serializers.CharField()
    level = serializers.CharField()
    level_display = serializers.CharField()
    test_1_average = serializers.FloatField(allow_null=True)
    test_2_average = serializers.FloatField(allow_null=True)
    test_1_pass_rate = serializers.FloatField(allow_null=True)
    test_2_pass_rate = serializers.FloatField(allow_null=True)
    students_assessed = serializers.IntegerField()


class PerformanceDashboardSerializer(serializers.Serializer):
    term = TermSummarySerializer()
    compared_with = TermSummarySerializer(allow_null=True)
    summary = PerformanceSummarySerializer()
    grade_distribution = GradeDistributionSerializer(many=True)
    national_exams = NationalExamSummarySerializer(many=True)
    subjects = SubjectPerformanceSerializer(many=True)
    tests = TestResultSerializer(many=True)
