"""
UserProfile and CourseConfig models for the accounts app.

UserProfile extends Django's built-in User model via a OneToOne relationship,
adding role-based access control, institutional data, and profile fields.

CourseConfig is an admin-managed lookup table that powers the automated student
email parsing pipeline (e.g. msccs2524@rajagiri.edu → MSc Computer Science,
Batch MSCCS - 25-27, Semester 3).
"""

import re
from datetime import date

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class CourseConfig(models.Model):
    """
    Lookup table for student email parsing.

    When a student signs in with e.g. msccs2524@rajagiri.edu, the system
    extracts the last 4 digits (YYRR) and everything before them as the
    course code. That code is matched against this table to resolve the
    student's course name, department, and batch duration.

    Fields:
        code: Email prefix code (e.g. 'msccs', 'mca', 'bca', 'm1ca')
        full_name: Full course name (e.g. 'MSc Computer Science')
        short_name: Uppercase short name for batch labels (e.g. 'MSCCS')
        duration_years: Course duration in years (e.g. 2)
        department: Department this course belongs to (e.g. 'Computer Science')
    """

    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Lowercase email prefix before the 4-digit year+roll (e.g. 'msccs')"
    )
    full_name = models.CharField(
        max_length=150,
        help_text="Full course name (e.g. 'MSc Computer Science')"
    )
    short_name = models.CharField(
        max_length=20,
        help_text="Uppercase short label for batch names (e.g. 'MSCCS')"
    )
    duration_years = models.PositiveIntegerField(
        help_text="Course duration in years (e.g. 2)"
    )
    department = models.CharField(
        max_length=100,
        help_text="Department name (e.g. 'Computer Science')"
    )

    class Meta:
        verbose_name = "Course Configuration"
        verbose_name_plural = "Course Configurations"
        ordering = ['department', 'full_name']

    def __str__(self):
        return f"{self.short_name} ({self.full_name}) — {self.duration_years}yr"


class UserProfile(models.Model):
    """
    Extends Django User with role, institutional, and profile data.

    Role hierarchy:
        - 'dean': System Admin (Dean of Student Affairs) — full admin access
        - 'faculty': Faculty / Committee Head — can manage committees, attendance
        - 'student': Student Volunteer — can browse events, apply, view hours

    For faculty users:
        - designation: Academic title (Assistant Professor, Professor, etc.)
        - is_hod: True if this faculty is the Department Dean/HOD
          (displayed as "Dean of [Department]" but retains faculty-level access)

    For student users:
        - class_batch, department, admission_year are auto-populated from
          email parsing on first Google Auth login.
        - semester is computed dynamically (never stored).
    """

    ROLE_CHOICES = [
        ('dean', 'Dean of Student Affairs'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
    ]

    DESIGNATION_CHOICES = [
        ('assistant_professor', 'Assistant Professor'),
        ('associate_professor', 'Associate Professor'),
        ('professor', 'Professor'),
        ('teaching_associate', 'Teaching Associate'),
    ]

    # --- Core relationship ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # --- Role & Access ---
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    # --- Contact & Profile ---
    phone = models.CharField(max_length=20, blank=True)
    phone_verified = models.BooleanField(default=False)
    profile_pic = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True
    )

    # --- Faculty-specific fields ---
    designation = models.CharField(
        max_length=30,
        choices=DESIGNATION_CHOICES,
        blank=True,
        help_text="Academic designation (faculty only)"
    )
    is_hod = models.BooleanField(
        default=False,
        help_text="True if this user is Department Dean/HOD"
    )

    # --- Student-specific fields (auto-populated from email parsing) ---
    class_batch = models.CharField(
        max_length=50,
        blank=True,
        help_text="Auto-generated batch label (e.g. 'MSCCS - 25-27')"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Department name (e.g. 'Computer Science')"
    )
    admission_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="2-digit admission year extracted from email (e.g. 25)"
    )
    roll_number = models.CharField(
        max_length=10,
        blank=True,
        help_text="Roll number extracted from email (e.g. '24')"
    )

    # --- Onboarding state ---
    is_first_login = models.BooleanField(default=True)

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    # ---- Computed Properties ----

    @property
    def semester(self):
        """
        Auto-calculate current semester from admission_year.

        Indian academic calendar:
            Odd semesters (1, 3, 5...): June–November
            Even semesters (2, 4, 6...): December–May

        Returns None for non-students or if admission_year is not set.
        """
        if self.role != 'student' or not self.admission_year:
            return None

        today = date.today()
        start_year = 2000 + self.admission_year
        years_diff = today.year - start_year

        if today.month >= 6:  # June onwards = odd semester
            sem = years_diff * 2 + 1
        else:  # Jan–May = even semester
            sem = years_diff * 2

        return max(sem, 1)

    @property
    def is_student_coordinator(self):
        """
        True if this student is Main Student Coordinator on any active event
        OR is Student Coordinator on any committee of an active event.
        """
        if self.role != 'student':
            return False

        # Import here to avoid circular imports
        from events.models import Event, Committee

        active_statuses = ['open', 'upcoming', 'ongoing']

        is_main = Event.objects.filter(
            main_student_coordinator=self,
            status__in=active_statuses
        ).exists()

        if is_main:
            return True

        is_committee_coord = Committee.objects.filter(
            student_coordinator=self,
            event__status__in=active_statuses
        ).exists()

        return is_committee_coord

    @property
    def display_role(self):
        """Human-readable role string for templates."""
        if self.role == 'dean':
            return 'Dean of Student Affairs'
        elif self.role == 'faculty':
            if self.is_hod:
                return f'Dean of {self.department}'
            return self.get_designation_display() or 'Faculty'
        return 'Student Volunteer'

    # ---- Email Parsing Utility ----

    @staticmethod
    def parse_student_email(email):
        """
        Parse a Rajagiri student email to extract course, batch, and department.

        Email format: [course_code][YYRR]@rajagiri.edu
        Examples:
            msccs2524@rajagiri.edu → course='msccs', year=25, roll='24'
            m1ca2530@rajagiri.edu  → course='m1ca',  year=25, roll='30'

        Returns dict with keys: course_code, admission_year, roll_number,
        class_batch, department, full_name. Returns None if parsing fails.
        """
        if not email or '@' not in email:
            return None

        username = email.split('@')[0].lower()

        # Extract last 4 digits as YYRR, everything before is course code
        match = re.match(r'^(.+?)(\d{4})$', username)
        if not match:
            return None

        course_code = match.group(1)
        digits = match.group(2)
        admission_year = int(digits[:2])
        roll_number = digits[2:]

        # Lookup course in CourseConfig
        try:
            config = CourseConfig.objects.get(code=course_code)
        except CourseConfig.DoesNotExist:
            return None

        end_year = admission_year + config.duration_years
        class_batch = f"{config.short_name} - {admission_year}-{end_year}"

        return {
            'course_code': course_code,
            'admission_year': admission_year,
            'roll_number': roll_number,
            'class_batch': class_batch,
            'department': config.department,
            'full_name': config.full_name,
        }


# ---- Signal: Auto-create UserProfile when User is created ----

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile automatically when a new User is created."""
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # Ensure profile exists for existing users
        UserProfile.objects.get_or_create(user=instance)
