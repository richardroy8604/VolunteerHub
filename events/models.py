"""
Event and Committee models for the events app.

Event represents a campus event (e.g. 'Rajagiri Tech Fest 2026') with
volunteer management capabilities.

Committee represents a sub-unit of an event (e.g. 'Registration & Reception')
with its own faculty head, student coordinator, and volunteer quota.
"""

from django.db import models
from django.contrib.auth.models import User


class Venue(models.Model):
    """Saved location / venue registry for quick dropdown selection."""
    name = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Event(models.Model):
    """
    A campus event that requires volunteer management.

    Status lifecycle: draft → open → upcoming → ongoing → completed
    (or cancelled at any point).

    The main_student_coordinator is the lead student coordinator for
    the entire event. Each committee also has its own student_coordinator.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    ALLOCATION_CHOICES = [
        ('pool', 'General Pool with Preferences'),
        ('manual', 'Manual'),
        ('auto', 'Auto'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=200, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_deadline = models.DateField()
    max_volunteers = models.PositiveIntegerField(default=100)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    banner = models.ImageField(
        upload_to='event_banners/',
        blank=True,
        null=True
    )
    allocation_mode = models.CharField(
        max_length=10,
        choices=ALLOCATION_CHOICES,
        default='pool'
    )

    # Main Student Coordinator for the entire event
    main_student_coordinator = models.ForeignKey(
        'accounts.UserProfile',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='led_events',
        help_text="Lead student coordinator for this event"
    )

    # Dean who created the event
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_events'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    # ---- Computed Properties ----

    @property
    def dynamic_status(self):
        """
        Dynamically computes the event status based on today's date vs start_date, end_date,
        and registration_deadline.
        """
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date()

        if self.status in ['cancelled', 'draft']:
            return self.status

        if today > self.end_date:
            return 'completed'
        elif self.start_date <= today <= self.end_date:
            return 'ongoing'
        elif today < self.start_date:
            if today <= self.registration_deadline:
                return 'open'
            else:
                return 'upcoming'
        return self.status

    @property
    def dynamic_status_display(self):
        """User-facing status display text based on dynamic status."""
        status_map = {
            'draft': 'Draft',
            'open': 'Open for Registration',
            'upcoming': 'Registration Closed',
            'ongoing': 'Ongoing',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
        }
        return status_map.get(self.dynamic_status, self.get_status_display())

    @property
    def total_applications(self):
        """Total number of volunteer applications for this event."""
        return self.applications.count()

    @property
    def assigned_volunteers(self):
        """Number of volunteers who have been assigned to a committee."""
        return self.applications.filter(status='assigned').count()

    @property
    def pending_applications(self):
        """Number of applications still pending allocation."""
        return self.applications.filter(status='pending').count()

    @property
    def total_required_volunteers(self):
        """Sum of required volunteers across all committees."""
        return self.committees.aggregate(
            total=models.Sum('required_volunteers')
        )['total'] or 0

    @property
    def event_dates(self):
        """List of date strings between start_date and end_date (inclusive)."""
        from datetime import timedelta
        dates = []
        current = self.start_date
        while current <= self.end_date:
            dates.append(current.strftime('%B %d, %Y'))
            current += timedelta(days=1)
        return dates


class Committee(models.Model):
    """
    A committee (sub-unit) within an event.

    Each committee has a faculty head (who manages attendance),
    an optional student coordinator, and a required volunteer quota.

    Examples: 'Registration & Reception', 'Stage & Decorations',
              'Food & Hospitality', 'Technical Support'.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='committees'
    )
    name = models.CharField(max_length=200)
    required_volunteers = models.PositiveIntegerField(default=10)

    # Faculty head who manages this committee
    faculty_head = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_committees',
        help_text="Faculty member in charge of this committee"
    )

    # Student coordinator for this committee
    student_coordinator = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='coordinated_committees',
        help_text="Student lead for this committee"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event', 'name']

    def __str__(self):
        return f"{self.name} — {self.event.name}"

    # ---- Computed Properties ----

    @property
    def assigned_count(self):
        """Number of volunteers assigned to this committee."""
        return self.assigned_volunteers.count()

    @property
    def open_slots(self):
        """Number of unfilled volunteer slots."""
        return max(0, self.required_volunteers - self.assigned_count)

    @property
    def fill_percentage(self):
        """Percentage of volunteer slots filled (0–100)."""
        if self.required_volunteers == 0:
            return 100
        return min(100, int(
            (self.assigned_count / self.required_volunteers) * 100
        ))
