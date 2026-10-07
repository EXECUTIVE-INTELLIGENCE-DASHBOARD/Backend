from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.
User = get_user_model()
# Create your models here.
class Student(models.Model):
    sname = models.CharField(max_length=100)
    sgender = models.CharField(max_length=10)
    sclass = models.CharField(max_length=10)
    sparentname = models.CharField(max_length=100)
    
