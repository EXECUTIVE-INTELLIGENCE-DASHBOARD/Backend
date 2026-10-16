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
        UNDER_MAINTENANCE = "under_maintenance", "Under Maintenance"  # temporarily out of service for repair/upkeep
        CLOSED = "closed", "Closed"                          # not in use, no active maintenance

    class Campus(models.TextChoices):
        KIBULI = "kibuli", "Kibuli"
        BUWAATE = "buwaate", "Buwaate"

    name = models.CharField(max_length=150)  # display name, e.g. "Science Block B"
    campus = models.CharField(max_length=20, choices=Campus.choices)  # which of the two campuses this facility sits on
    facility_type = models.CharField(max_length=20, choices=FacilityType.choices)  # category, used to group/filter on the dashboard
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPERATIONAL)  # current operating state, drives the facility-status KPI
    created_at = models.DateTimeField(auto_now_add=True)  # record creation timestamp, set once
    updated_at = models.DateTimeField(auto_now=True)      # last-modified timestamp, updates on every save

    def __str__(self):
        return self.name