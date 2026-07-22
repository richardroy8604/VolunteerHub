"""Admin registrations for volunteers app models."""

from django.contrib import admin
from .models import VolunteerApplication, AttendanceSheet, AttendanceRecord


class AttendanceRecordInline(admin.TabularInline):
    """Inline attendance record editor within AttendanceSheet admin."""
    model = AttendanceRecord
    extra = 0
    fields = ('student', 'hours', 'total_hours')
    readonly_fields = ('total_hours',)


@admin.register(VolunteerApplication)
class VolunteerApplicationAdmin(admin.ModelAdmin):
    """Admin for VolunteerApplication model."""
    list_display = (
        'student', 'event', 'status',
        'preference_1', 'assigned_committee', 'applied_at',
    )
    list_filter = ('status', 'event')
    search_fields = (
        'student__user__first_name', 'student__user__last_name',
        'event__name',
    )
    readonly_fields = ('applied_at', 'updated_at')


@admin.register(AttendanceSheet)
class AttendanceSheetAdmin(admin.ModelAdmin):
    """Admin for AttendanceSheet model."""
    list_display = (
        'committee', 'date', 'num_hours', 'status',
        'student_count', 'total_hours_logged',
        'submitted_by', 'submitted_at',
    )
    list_filter = ('status', 'committee__event', 'date')
    search_fields = ('committee__name', 'committee__event__name')
    inlines = [AttendanceRecordInline]
    readonly_fields = ('created_at',)

    def student_count(self, obj):
        return obj.student_count
    student_count.short_description = 'Students'

    def total_hours_logged(self, obj):
        return obj.total_hours_logged
    total_hours_logged.short_description = 'Total Hours'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Admin for AttendanceRecord model."""
    list_display = ('student', 'sheet', 'total_hours')
    list_filter = ('sheet__committee__event', 'sheet__date')
    search_fields = (
        'student__user__first_name', 'student__user__last_name',
    )
    readonly_fields = ('total_hours',)
