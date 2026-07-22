"""Admin registrations for events app models."""

from django.contrib import admin
from .models import Event, Committee


class CommitteeInline(admin.TabularInline):
    """Inline committee editor shown within the Event admin page."""
    model = Committee
    extra = 1
    fields = ('name', 'required_volunteers', 'faculty_head', 'student_coordinator')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin for Event model."""
    list_display = (
        'name', 'status', 'venue', 'start_date', 'end_date',
        'max_volunteers', 'total_applications', 'assigned_volunteers',
    )
    list_filter = ('status', 'allocation_mode')
    search_fields = ('name', 'venue', 'description')
    date_hierarchy = 'start_date'
    inlines = [CommitteeInline]
    readonly_fields = ('created_at', 'updated_at')

    def total_applications(self, obj):
        return obj.total_applications
    total_applications.short_description = 'Applications'

    def assigned_volunteers(self, obj):
        return obj.assigned_volunteers
    assigned_volunteers.short_description = 'Assigned'


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    """Admin for Committee model."""
    list_display = (
        'name', 'event', 'required_volunteers',
        'faculty_head', 'student_coordinator', 'assigned_count',
    )
    list_filter = ('event',)
    search_fields = ('name', 'event__name')

    def assigned_count(self, obj):
        return obj.assigned_count
    assigned_count.short_description = 'Assigned'
