from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()
# Create your models here.
class Student(models.Model):
	name = models.CharField(max_length = 255, default="")
	date_of_birth = models.CharField(max_length = 255, default="")
	gender = models.CharField(max_length = 255, default="")
	created_on = models.DateTimeField(auto_now_add = True, null = True)
	#photo
	nationality = models.CharField(max_length = 255, default="")
	lin= models.CharField(max_length = 255, default="")
	email = models.CharField(max_length = 255, default = "")
	address = models.CharField(max_length = 255, default="")
	phone = models.CharField(max_length = 255, default="")
	guardian_name = models.CharField(max_length = 255, default="")
	relation = models.CharField(max_length = 255, default="")
	guardian_contact = models.CharField(max_length = 255, default="")

class Academic(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	subjects = models.CharField(max_length = 255, default="")
	syllabus = models.CharField(max_length = 255, default="")
	created_on = models.DateTimeField(auto_now_add = True, null = True)
	outcome = models.CharField(max_length = 255, default="")

class Section(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	grade_levels = models.CharField(max_length = 255, default="")
	streams = models.CharField(max_length = 255, default="")
	allocation = models.CharField(max_length = 255, default="")

class GradeResult(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	marks = models.CharField(max_length = 255, default="")
	rankings = models.CharField(max_length = 255, default="")
	transcript = models.CharField(max_length = 255, default="")
	report_cards = models.CharField(max_length = 255, default="")

class Homework(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	task = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	submission = models.CharField(max_length = 255, default="")

class Attendance(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	student_attendance = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	staff_attendance = models.CharField(max_length = 255, default="")
	period = models.CharField(max_length = 255, default="")

class Curricular(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	club = models.CharField(max_length = 255, default="")
	society = models.CharField(max_length = 255, default="")

class Events(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	competition = models.CharField(max_length = 255, default="")
	achievement = models.CharField(max_length = 255, default="")
	total_female = models.IntegerField(default=0)
	total_male = models.IntegerField(default=0)








