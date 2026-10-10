from django.contrib.auth import get_user_model
from django.db import models

"""
The following are the models picked from
the data categories document.
prepared by me and they are intended to be used 
for api development by Caroline
further adjustments and modifications are due
eg transforming this into postgres as done 
by the technical lead
"""
User = get_user_model()
# This model is created by the student data based from the data category meant for student retention
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

#This model is meant for academic performance under the academic domain
class Academic(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	subjects = models.CharField(max_length = 255, default="")
	syllabus = models.CharField(max_length = 255, default="")
	created_on = models.DateTimeField(auto_now_add = True, null = True)
	outcome = models.CharField(max_length = 255, default="")

#This model is meant for student mapping under the academic domain.
class Section(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	grade_levels = models.CharField(max_length = 255, default="")
	streams = models.CharField(max_length = 255, default="")
	allocation = models.CharField(max_length = 255, default="")

#this particular model is meant for student grading under the academic domain.
class GradeResult(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	marks = models.CharField(max_length = 255, default="")
	rankings = models.CharField(max_length = 255, default="")
	transcript = models.CharField(max_length = 255, default="")
	report_cards = models.CharField(max_length = 255, default="")

#this shows the homework done under the academic domain
class Homework(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	task = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	submission = models.CharField(max_length = 255, default="")

#this is meant for student attendance under the academic domain
class Attendance(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	student_attendance = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	staff_attendance = models.CharField(max_length = 255, default="")
	period = models.CharField(max_length = 255, default="")

#this is meant for non cirricular activities under the academic domain
class Curricular(models.Model):
	name = models.CharField(max_length = 255, default="")
	club = models.CharField(max_length = 255, default="")
	society = models.CharField(max_length = 255, default="")

#This is meant to work with cocirricular activities under the academic domain
class Events(models.Model):
    name = models.ForeignKey(Curricular, on_delete = models.CASCADE)
    competition = models.CharField(max_length = 255, default="")
    achievement = models.CharField(max_length = 255, default="")
    total_female = models.IntegerField(default=0)
    total_male = models.IntegerField(default=0)
    period = models.CharField(max_length = 255, default="")

#this is for staff under the academic domain
class Staff(models.Model):
    name = models.CharField(max_length = 255, default="")
    contact = models.CharField(max_length = 255, default="")
    email = models.CharField(max_length = 255, default="")

#TO DO: create subject model





