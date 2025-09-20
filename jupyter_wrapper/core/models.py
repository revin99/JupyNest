from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUser(AbstractUser):
    group = models.ForeignKey('BusinessGroup', on_delete=models.SET_NULL, null=True, blank=True)

class BusinessGroup(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Project(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(BusinessGroup, on_delete=models.CASCADE, null=True, blank=True) #project belongs to this group
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Auto-assign project to the same group as the user
        if not self.group and hasattr(self.user, "group"):
            self.group = self.user.group
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('group','name') #ensures that within a given business group, project names are unique

    def __str__(self):     
        return self.name
    
class Notebook(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=1024)
    created_at = models.DateTimeField(auto_now_add=True)

    # Scheduling fields
    is_scheduled = models.BooleanField(default=False)
    schedule_seconds = models.IntegerField(default=0)
    schedule_minutes = models.IntegerField(default=0)
    schedule_hours = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    airflow_dag_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name
    

class NotebookRun(models.Model):
    notebook = models.ForeignKey(Notebook, on_delete=models.CASCADE, related_name='runs')
    status_choices = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAIL', 'Fail')
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='PENDING')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    log = models.TextField(blank=True)  # optional: store stdout or error messages

    def __str__(self):
        return f"{self.notebook.name} - {self.status} - {self.started_at}"