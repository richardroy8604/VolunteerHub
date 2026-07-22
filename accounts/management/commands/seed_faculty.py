"""
Management command to seed faculty and admin accounts.

Usage: py manage.py seed_faculty

Creates the initial faculty roster for the Computer Science department
plus the two Dean of Student Affairs (system admin) accounts.
All accounts use demo-marked emails (with 'd' before @rajagiri.edu).
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import UserProfile


# (first_name, last_name, email, role, designation, department, is_hod)
FACULTY_DATA = [
    # ---- System Admins (Dean of Student Affairs) ----
    ('Jaya', 'Vijayan', 'jayad@rajagiri.edu', 'dean', 'assistant_professor', 'Computer Science', False),
    ('Kiran', 'Thampi', 'kirand@rajagiri.edu', 'dean', '', 'Social Work', False),

    # ---- CS Department Faculty ----
    ('Diljith K', 'Benny', 'diljithd@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Ann', 'Baby', 'annd@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Shiju Thomas', 'M Y', 'shijud@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Sabeen', 'Govind', 'sabeend@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Keerthy', 'A S', 'keerthid@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Neethu', 'Narayanan', 'neethud@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Priyanka E', 'Thambi', 'priyankad@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Ann', 'Rija', 'rijad@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Shoby', 'Sunny', 'shobyd@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Sunu', 'Fathima', 'sunufathiad@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Sunu Mary', 'Abraham', 'sunud@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Bindiya M', 'Varghese', 'bindiyad@rajagiri.edu', 'faculty', 'professor', 'Computer Science', True),  # HOD
    ('Ajay Antony', 'Joseph', 'ajayantonyd@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
    ('Jobin Jaison', 'K', 'jobinjaisond@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Jonath Shibu', 'Pullorkudiyil', 'jonathd@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Ananthakrishnan', 'K V', 'ananthakrishnand@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Ajay Das', 'M', 'ajaydasd@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Aadarsh R', 'Warrier', 'aadarshwarrierd@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Gracen K', 'Shaji', 'gracend@rajagiri.edu', 'faculty', 'teaching_associate', 'Computer Science', False),
    ('Vivek', 'M V', 'vivekd@rajagiri.edu', 'faculty', 'assistant_professor', 'Computer Science', False),
]


class Command(BaseCommand):
    help = 'Seed faculty and admin accounts for the CS department.'

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for first_name, last_name, email, role, designation, department, is_hod in FACULTY_DATA:
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.WARNING(
                    f'  SKIP: {first_name} {last_name} ({email}) -- already exists'
                ))
                skipped_count += 1
                continue

            # Create the Django User
            username = email.split('@')[0]
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password='VolunteerHub@2026',  # Default password for dev
                is_staff=(role == 'dean'),      # Admins get staff access
                is_superuser=(role == 'dean'),  # System admins get full superuser permissions in Django admin
            )

            # Update the auto-created UserProfile
            profile = user.profile
            profile.role = role
            profile.designation = designation
            profile.department = department
            profile.is_hod = is_hod
            profile.is_first_login = False  # Faculty accounts are pre-configured
            profile.save()

            self.stdout.write(self.style.SUCCESS(
                f'  OK: Created {first_name} {last_name} ({email}) -- {role}'
            ))
            created_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created: {created_count} | Skipped: {skipped_count}'
        ))
