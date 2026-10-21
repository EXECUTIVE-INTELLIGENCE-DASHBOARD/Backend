from django.db import models


# Create your models here.
class Facility(models.Model):
    """Represents a physical facility on a campus (classroom, lab, hostel, etc.),
    tracked for maintenance completion rates and incident monitoring (OI-01, OI-02)."""

    class FacilityType(models.TextChoices):
        CLASSROOM = "classroom", "Classroom"
        LABORATORY = "laboratory", "Laboratory"
        HOSTEL = "hostel", "Hostel"
        ADMIN_BLOCK = "admin_block", "Admin Block"
        SPORTS = "sports", "Sports Facility"
        DINING = "dining", "Dining Hall"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPERATIONAL = "operational", "Operational"          # facility is in normal use
        # temporarily out of service for repair/upkeep
        UNDER_MAINTENANCE = "under_maintenance", "Under Maintenance"
        CLOSED = "closed", "Closed"                          # not in use, no active maintenance

    class Campus(models.TextChoices):
        KIBULI = "kibuli", "Kibuli"
        BUWAATE = "buwaate", "Buwaate"
        ANNEX = "annex", "Annex Preschool"

    name = models.CharField(max_length=150)  # display name, e.g. "Science Block B"
    # which of the two campuses this facility sits on
    campus = models.CharField(max_length=20, choices=Campus.choices)
    # category, used to group/filter on the dashboard
    facility_type = models.CharField(max_length=20, choices=FacilityType.choices)
    # current operating state, drives the facility-status KPI
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPERATIONAL
    )
    created_at = models.DateTimeField(auto_now_add=True)  # record creation timestamp, set once
    # last-modified timestamp, updates on every save
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Asset(models.Model):
    """Operations asset registry — vehicles, computers, and other tracked equipment,
    recorded by location (Facility), quantity and value. Each row is one line of the
    institutional asset register, e.g. "Dell Student Laboratory Workstations" x 120."""

    class Category(models.TextChoices):
        COMPUTER_EQUIPMENT = "computer_equipment", "ICT Hardware"
        LABORATORY_EQUIPMENT = "laboratory_equipment", "Science Laboratory Equipment"
        FURNITURE = "furniture", "Administrative Furniture"
        MACHINERY = "machinery", "Power & Facility Machinery"
        VEHICLE = "vehicle", "Fleet & Vehicles"
        OTHER = "other", "Other"

    class Condition(models.TextChoices):
        OPERATIONAL = "operational", "Operational (Good)"  # fully functional, no known issues
        # usable but showing wear; needs servicing soon
        SERVICING_REQUIRED = "servicing_required", "Servicing Required"
        CRITICAL = "critical", "Critical / Repair Queued"  # out of service, awaiting repair
        # retired from active use; left out of register totals
        DECOMMISSIONED = "decommissioned", "Decommissioned"

    name = models.CharField(max_length=150)  # e.g. "Toyota Hiace Bus", "Dell Latitude Laptop"
    # broad asset type, for filtering/grouping
    category = models.CharField(max_length=30, choices=Category.choices)
    # where this asset is located; PROTECT stops a facility being deleted
    # while assets still reference it
    facility = models.ForeignKey(
        Facility, on_delete=models.PROTECT, related_name="assets"
    )
    # count of identical units at this location (1 for a single serialized item like a car)
    quantity = models.PositiveIntegerField(default=1)
    # value of one unit in UGX; the register's total value is quantity x unit_value
    unit_value = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    # current state, for maintenance/replacement planning
    condition = models.CharField(
        max_length=20, choices=Condition.choices, default=Condition.OPERATIONAL
    )
    acquired_date = models.DateField(null=True, blank=True)  # when the asset was acquired, if known
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_value(self):
        """Register value of this line in UGX (quantity x unit value)."""
        return self.quantity * self.unit_value

    def __str__(self):
        return f"{self.name} ({self.facility})"

class WorkforceUnit(models.Model):
    """A department or unit of the HR workforce register (e.g. "Transport & Fleet
    Management"), grouped by staff category and campus on the HR dashboard."""

    class StaffCategory(models.TextChoices):
        TEACHING = "teaching", "Teaching Staff (Full-Time & Contract)"
        NON_TEACHING_SUPPORT = "non_teaching_support", "Non-Teaching Support"
        DRIVERS_TECHNICIANS = "drivers_technicians", "Drivers & Mechanical Technicians"
        ADMINISTRATIVE = "administrative", "Administrative & Clerical"
        TECHNICAL_SECURITY = "technical_security", "Technical, Security & Groundskeeping"

    class Campus(models.TextChoices):
        KIBULI = "kibuli", "Kibuli"
        BUWAATE = "buwaate", "Buwaate"
        ANNEX = "annex", "Annex Preschool"
        MULTI_CAMPUS = "multi_campus", "Multi-Campus"  # unit serves more than one campus

    name = models.CharField(max_length=150, unique=True)  # e.g. "Academic & Curriculum Instruction"
    # nature of staff; teaching vs the rest drives the staffing ratio
    staff_category = models.CharField(max_length=30, choices=StaffCategory.choices)
    campus = models.CharField(max_length=20, choices=Campus.choices)  # used by the campus filter
    location = models.CharField(max_length=150, blank=True)  # e.g. "Kibuli Main Dining Complex"
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    """A staff member on the workforce register; headcount is the count of active employees."""

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-Time"
        CONTRACT = "contract", "Contract"
        PART_TIME = "part_time", "Part-Time"

    staff_number = models.CharField(max_length=30, unique=True)  # HR reference number
    full_name = models.CharField(max_length=150)
    unit = models.ForeignKey(
        WorkforceUnit, on_delete=models.PROTECT, related_name="employees"
    )  # PROTECT stops a unit being deleted while staff still belong to it
    job_title = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(
        max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    hire_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # leavers stay on record, out of headcount
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.staff_number})"


class StaffAttendance(models.Model):
    """One employee's attendance status for one day; the source for attendance rates
    and the on-leave / on-training counts on the HR dashboard."""

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"            # unexplained absence
        ON_LEAVE = "on_leave", "On Leave"
        ON_TRAINING = "on_training", "On Training"
        ON_FIELD = "on_field", "On Field Duty"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="unique_staff_attendance_per_day"
            ),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date}: {self.get_status_display()}"
