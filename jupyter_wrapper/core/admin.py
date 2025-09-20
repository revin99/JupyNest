from django.contrib import admin
from .models import Project, Notebook , BusinessGroup, CustomUser , Schedule , ScheduleStep , NotebookRun
from django.contrib.auth.admin import UserAdmin

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Business Group", {"fields": ("group",)}),
    )

admin.site.register(BusinessGroup)
admin.site.register(Project)
admin.site.register(Notebook)
admin.site.register(Schedule)
admin.site.register(ScheduleStep)
admin.site.register(NotebookRun)
# Register your models here.
