"""
volunteers app — Stub views with dummy context data.

Handles student-facing volunteer features (dashboard, applications,
volunteering history) and dean-facing volunteer pool management.
"""

from django.shortcuts import render


# =============================================================================
# Student views — /student/ prefix
# =============================================================================

def student_dashboard_view(request):
    """Student's main dashboard with active assignments and stats."""
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'stats': {
            'active_events': 2,
            'total_applications': 5,
            'total_hours': 47.5,
            'upcoming_events': 3,
        },
        'active_assignments': [
            {'event': 'Rajagiri Tech Fest 2026',
             'committee': 'Registration & Reception',
             'date': 'Jul 25-27, 2026', 'status': 'Assigned'},
            {'event': 'Annual Sports Day',
             'committee': 'Pending Assignment',
             'date': 'Aug 10-12, 2026', 'status': 'Pending'},
        ],
        'recent_events': [
            {'name': 'Rajagiri Tech Fest 2026', 'date': 'Jul 25, 2026',
             'status': 'Open'},
            {'name': 'Annual Sports Day', 'date': 'Aug 10, 2026',
             'status': 'Open'},
            {'name': 'Cultural Fest - Dhwani 2026', 'date': 'Sep 15, 2026',
             'status': 'Upcoming'},
        ],
    }
    return render(request, 'dashboards/student_dashboard.html', context)


def my_applications_view(request):
    """List all volunteer applications submitted by the student."""
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'applications': [
            {'id': 1, 'event': 'Rajagiri Tech Fest 2026',
             'pref1': 'Registration & Reception',
             'pref2': 'Technical Events',
             'pref3': 'Media & Publicity',
             'status': 'Assigned',
             'assigned_committee': 'Registration & Reception',
             'date': 'Jul 10, 2026'},
            {'id': 2, 'event': 'Annual Sports Day',
             'pref1': 'Event Coordination',
             'pref2': 'Scoring & Results',
             'pref3': 'First Aid & Safety',
             'status': 'Pending',
             'assigned_committee': None,
             'date': 'Jul 13, 2026'},
            {'id': 3, 'event': 'NSS Social Service Camp',
             'pref1': 'Education Drive',
             'pref2': 'Health Camp',
             'pref3': 'Documentation',
             'status': 'Assigned',
             'assigned_committee': 'Education Drive',
             'date': 'May 28, 2026'},
        ],
    }
    return render(request, 'volunteers/my_applications.html', context)


def my_volunteering_view(request):
    """View the student's complete volunteering history and hours."""
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'total_hours': 47.5,
        'total_events': 8,
        'history': [
            {'event': 'NSS Social Service Camp',
             'committee': 'Education Drive',
             'dates': 'Jun 5-10, 2026', 'hours': 30.0,
             'attendance': 100, 'status': 'Completed'},
            {'event': 'College Open Day',
             'committee': 'Campus Tour',
             'dates': 'May 15, 2026', 'hours': 6.5,
             'attendance': 100, 'status': 'Completed'},
            {'event': 'Blood Donation Drive',
             'committee': 'Registration',
             'dates': 'Apr 20, 2026', 'hours': 5.0,
             'attendance': 100, 'status': 'Completed'},
            {'event': 'Literary Fest 2026',
             'committee': 'Stage Management',
             'dates': 'Mar 10-12, 2026', 'hours': 6.0,
             'attendance': 83, 'status': 'Completed'},
        ],
    }
    return render(request, 'volunteers/my_volunteering.html', context)


# =============================================================================
# Student apply view — used in /events/<id>/apply/
# =============================================================================

def apply_view(request, event_id):
    """Volunteer application form with committee preference selection."""
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'event': {
            'id': 2,
            'name': 'Annual Sports Day',
            'committees': [
                {'id': 6, 'name': 'Event Coordination'},
                {'id': 7, 'name': 'Scoring & Results'},
                {'id': 8, 'name': 'First Aid & Safety'},
            ],
        },
        'student': {
            'name': 'Arjun Menon',
            'department': 'Computer Science',
            'semester': '6th Semester',
            'student_class': 'CS-B',
            'email': 'arjun.menon@rajagiri.edu',
            'phone': '+91 98765 43210',
        },
    }
    return render(request, 'volunteers/apply.html', context)


# =============================================================================
# Dean views — /dean/events/ prefix (volunteer pool management)
# =============================================================================

def volunteer_pool_view(request, event_id):
    """Dean's view of all applications for an event with allocation controls."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'event': {
            'id': 1,
            'name': 'Rajagiri Tech Fest 2026',
            'committees': [
                {'id': 1, 'name': 'Registration & Reception',
                 'required': 15, 'assigned': 12},
                {'id': 2, 'name': 'Technical Events',
                 'required': 20, 'assigned': 18},
                {'id': 3, 'name': 'Media & Publicity',
                 'required': 10, 'assigned': 8},
                {'id': 4, 'name': 'Logistics & Venue',
                 'required': 15, 'assigned': 12},
                {'id': 5, 'name': 'Food & Hospitality',
                 'required': 10, 'assigned': 8},
            ],
        },
        'applications': [
            {'id': 1, 'student': 'Arjun Menon', 'class': 'CS-B',
             'dept': 'Computer Science',
             'pref1': 'Registration & Reception',
             'pref2': 'Technical Events',
             'pref3': 'Media & Publicity',
             'status': 'Assigned',
             'assigned': 'Registration & Reception'},
            {'id': 2, 'student': 'Anika Sharma', 'class': 'CS-A',
             'dept': 'Computer Science',
             'pref1': 'Technical Events',
             'pref2': 'Media & Publicity',
             'pref3': 'Registration & Reception',
             'status': 'Assigned',
             'assigned': 'Technical Events'},
            {'id': 3, 'student': 'Vishnu Prasad', 'class': 'EC-B',
             'dept': 'Electronics',
             'pref1': 'Technical Events',
             'pref2': 'Logistics & Venue',
             'pref3': 'Registration & Reception',
             'status': 'Pending',
             'assigned': None},
            {'id': 4, 'student': 'Nandita Krishnan', 'class': 'CO-A',
             'dept': 'Commerce',
             'pref1': 'Registration & Reception',
             'pref2': 'Food & Hospitality',
             'pref3': 'Media & Publicity',
             'status': 'Pending',
             'assigned': None},
            {'id': 5, 'student': 'Rohit Menon', 'class': 'MA-A',
             'dept': 'Mathematics',
             'pref1': 'Logistics & Venue',
             'pref2': 'Registration & Reception',
             'pref3': 'Food & Hospitality',
             'status': 'Pending',
             'assigned': None},
            {'id': 6, 'student': 'Sneha Thomas', 'class': 'CS-A',
             'dept': 'Computer Science',
             'pref1': 'Media & Publicity',
             'pref2': 'Registration & Reception',
             'pref3': 'Technical Events',
             'status': 'Assigned',
             'assigned': 'Media & Publicity'},
            {'id': 7, 'student': 'Deepa Nair', 'class': 'EC-A',
             'dept': 'Electronics',
             'pref1': 'Technical Events',
             'pref2': 'Logistics & Venue',
             'pref3': 'Media & Publicity',
             'status': 'Rejected',
             'assigned': None},
        ],
    }
    return render(request, 'volunteers/volunteer_pool.html', context)


def auto_allocate_view(request, event_id):
    """Auto-allocate volunteers to committees (stub — just redirects)."""
    # This will just render the pool page for now
    return render(request, 'volunteers/volunteer_pool.html', {})
