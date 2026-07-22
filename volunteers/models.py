"""
Volunteer management models for the volunteers app.

VolunteerApplication tracks student applications to events with 3 committee
preferences and allocation status.

AttendanceSheet is a daily attendance record per committee, managed by the
faculty head and approved/rejected by the Dean.

AttendanceRecord stores per-student hourly attendance within a sheet.
"""

from django.db import models


class VolunteerApplication(models.Model):
    """
    A student's application to volunteer at an event.

    Students select up to 3 committee preferences. The Dean (or auto-allocation
    algorithm) assigns them to one committee. Each student can only apply once
    per event (enforced by unique_together).

    Status lifecycle: pending → assigned / rejected / waitlisted
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('rejected', 'Rejected'),
        ('waitlisted', 'Waitlisted'),
    ]

    student = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='applications'
    )
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='applications'
    )

    # Committee preferences (1st is required, 2nd and 3rd are optional)
    preference_1 = models.ForeignKey(
        'events.Committee',
        on_delete=models.CASCADE,
        related_name='pref1_applications',
        help_text="1st choice committee"
    )
    preference_2 = models.ForeignKey(
        'events.Committee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pref2_applications',
        help_text="2nd choice committee"
    )
    preference_3 = models.ForeignKey(
        'events.Committee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pref3_applications',
        help_text="3rd choice committee"
    )

    # The committee this student was ultimately assigned to
    assigned_committee = models.ForeignKey(
        'events.Committee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_volunteers',
        help_text="Committee the student was assigned to"
    )

    # Optional application fields
    experience = models.TextField(
        blank=True,
        help_text="Past volunteering experience"
    )
    skills = models.TextField(
        blank=True,
        help_text="Relevant skills or certifications"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One application per student per event
        unique_together = ('student', 'event')
        ordering = ['-applied_at']
        verbose_name = "Volunteer Application"
        verbose_name_plural = "Volunteer Applications"

    def __str__(self):
        return f"{self.student} → {self.event.name} ({self.get_status_display()})"

    @property
    def assigned_to_preference(self):
        """
        Returns which preference the assignment matches (1, 2, 3, or None).
        Useful for templates showing 'Matched 1st Preference!' badges.
        """
        if not self.assigned_committee:
            return None
        if self.assigned_committee == self.preference_1:
            return 1
        if self.assigned_committee == self.preference_2:
            return 2
        if self.assigned_committee == self.preference_3:
            return 3
        return None


class AttendanceSheet(models.Model):
    """
    A daily attendance sheet for one committee on one date.

    Created by the faculty head when marking attendance. The sheet tracks
    the number of shift hours (periods) and goes through a review workflow:

    Status lifecycle: not_submitted → pending → approved / sent_back
    (sent_back → pending → approved after corrections)

    When approved, the hours are credited to the students' volunteering records.
    """

    STATUS_CHOICES = [
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('sent_back', 'Sent Back'),
    ]

    committee = models.ForeignKey(
        'events.Committee',
        on_delete=models.CASCADE,
        related_name='attendance_sheets'
    )
    date = models.DateField()
    num_hours = models.PositiveIntegerField(
        default=1,
        help_text="Number of shift periods for this day (1–12)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_submitted'
    )
    feedback = models.TextField(
        blank=True,
        help_text="Dean's feedback when sheet is sent back for corrections"
    )

    # Faculty head who submitted the sheet
    submitted_by = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_sheets'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Dean who reviewed the sheet
    reviewed_by = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_sheets'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # One sheet per committee per day
        unique_together = ('committee', 'date')
        ordering = ['-date']
        verbose_name = "Attendance Sheet"
        verbose_name_plural = "Attendance Sheets"

    def __str__(self):
        return f"{self.committee.name} — {self.date} ({self.get_status_display()})"

    @property
    def total_hours_logged(self):
        """Sum of all student hours in this sheet."""
        return self.records.aggregate(
            total=models.Sum('total_hours')
        )['total'] or 0

    @property
    def student_count(self):
        """Number of students with attendance records in this sheet."""
        return self.records.count()


class AttendanceRecord(models.Model):
    """
    Per-student attendance within an AttendanceSheet.

    The 'hours' field is a JSON list of booleans, one per shift period.
    E.g. [true, true, false, true] means present for hours 1, 2, 4
    and absent for hour 3.

    'total_hours' is pre-computed from the hours list for fast aggregation.
    """

    sheet = models.ForeignKey(
        AttendanceSheet,
        on_delete=models.CASCADE,
        related_name='records'
    )
    student = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    hours = models.JSONField(
        default=list,
        help_text="List of booleans, one per shift period (e.g. [true, true, false])"
    )
    total_hours = models.PositiveIntegerField(
        default=0,
        help_text="Pre-computed count of True values in hours list"
    )

    class Meta:
        unique_together = ('sheet', 'student')
        ordering = ['student__user__first_name']
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    def __str__(self):
        return f"{self.student} — {self.sheet.date} ({self.total_hours}h)"

    def save(self, *args, **kwargs):
        """Auto-compute total_hours from the hours list before saving."""
        if self.hours:
            self.total_hours = sum(1 for h in self.hours if h)
        else:
            self.total_hours = 0
        super().save(*args, **kwargs)
