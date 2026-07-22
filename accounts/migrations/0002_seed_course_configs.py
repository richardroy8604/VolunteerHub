"""
Data migration to seed the CourseConfig table with initial courses.

These course codes power the automated student email parsing pipeline:
e.g. msccs2524@rajagiri.edu → MSc Computer Science, Batch MSCCS - 25-27.
"""

from django.db import migrations


INITIAL_COURSES = [
    # (code, full_name, short_name, duration_years, department)
    ('bba', 'BBA F&B', 'BBA', 3, 'Business Administration'),
    ('imba', 'IMBA (Integrated MBA)', 'IMBA', 5, 'Business Administration'),
    ('bca', 'BCA', 'BCA', 3, 'Computer Science'),
    ('bsccs', 'BSc Computer Science', 'BSCCS', 3, 'Computer Science'),
    ('imca', 'IMCA (Integrated MCA)', 'IMCA', 5, 'Computer Science'),
    ('mca', 'MCA (Master of Computer Applications)', 'MCA', 2, 'Computer Science'),
    ('msccs', 'MSc Computer Science', 'MSCCS', 2, 'Computer Science'),
    ('psy', 'BSc Psychology', 'PSY', 3, 'Psychology'),
    ('msycp', 'MSc Counselling Psychology', 'MSYCP', 2, 'Psychology'),
    ('msw', 'MSW', 'MSW', 2, 'Social Work'),
    ('pgd', 'PGDCSW', 'PGD', 1, 'Social Work'),
]


def seed_courses(apps, schema_editor):
    """Create initial CourseConfig entries."""
    CourseConfig = apps.get_model('accounts', 'CourseConfig')
    for code, full_name, short_name, duration, dept in INITIAL_COURSES:
        CourseConfig.objects.get_or_create(
            code=code,
            defaults={
                'full_name': full_name,
                'short_name': short_name,
                'duration_years': duration,
                'department': dept,
            }
        )


def reverse_seed(apps, schema_editor):
    """Remove seeded courses."""
    CourseConfig = apps.get_model('accounts', 'CourseConfig')
    codes = [c[0] for c in INITIAL_COURSES]
    CourseConfig.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_courses, reverse_seed),
    ]
