"""
events app — Stub views with rich dummy context data.

These views serve all three roles (Dean, Committee Head, Student)
and render templates with realistic placeholder data for UI design.
Each view passes enough context to fully design the template layout.
"""

from django.shortcuts import render


# =============================================================================
# Shared dummy data — realistic event/committee data for all views
# =============================================================================

DUMMY_EVENTS = [
    {
        'id': 1,
        'name': 'Rajagiri Tech Fest 2026',
        'description': (
            'Annual technology festival featuring workshops, hackathons, and '
            'tech talks by industry experts. Join us for three days of '
            'innovation and learning.'
        ),
        'venue': 'Main Auditorium & Tech Block',
        'start_date': 'July 25, 2026',
        'end_date': 'July 27, 2026',
        'registration_deadline': 'July 20, 2026',
        'max_volunteers': 120,
        'total_applications': 87,
        'assigned_volunteers': 65,
        'status': 'Open',
        'banner': None,
        'main_student_coordinator': 'Arjun Menon',
        'committees': [
            {'id': 1, 'name': 'Registration & Reception', 'required': 15,
             'assigned': 12, 'head': 'Dr. Priya Sharma', 'student_coordinator': 'Anika Sharma'},
            {'id': 2, 'name': 'Technical Events', 'required': 20,
             'assigned': 18, 'head': 'Prof. Rahul Nair', 'student_coordinator': None},
            {'id': 3, 'name': 'Media & Publicity', 'required': 10,
             'assigned': 8, 'head': 'Dr. Anita Joseph', 'student_coordinator': None},
            {'id': 4, 'name': 'Logistics & Venue', 'required': 15,
             'assigned': 12, 'head': 'Prof. Suresh Kumar', 'student_coordinator': None},
            {'id': 5, 'name': 'Food & Hospitality', 'required': 10,
             'assigned': 8, 'head': 'Dr. Meera Krishnan', 'student_coordinator': None},
        ],
    },
    {
        'id': 2,
        'name': 'Annual Sports Day',
        'description': (
            'Inter-department sports competition with track events, team '
            'sports, and cultural performances.'
        ),
        'venue': 'Sports Ground & Indoor Stadium',
        'start_date': 'August 10, 2026',
        'end_date': 'August 12, 2026',
        'registration_deadline': 'August 5, 2026',
        'max_volunteers': 80,
        'total_applications': 45,
        'assigned_volunteers': 0,
        'status': 'Open',
        'banner': None,
        'main_student_coordinator': None,
        'committees': [
            {'id': 6, 'name': 'Event Coordination', 'required': 20,
             'assigned': 0, 'head': 'Prof. Deepak Menon', 'student_coordinator': None},
            {'id': 7, 'name': 'Scoring & Results', 'required': 10,
             'assigned': 0, 'head': 'Dr. Kavitha Raj', 'student_coordinator': None},
            {'id': 8, 'name': 'First Aid & Safety', 'required': 8,
             'assigned': 0, 'head': 'Dr. Anil Thomas', 'student_coordinator': None},
        ],
    },
    {
        'id': 3,
        'name': 'Cultural Fest - Dhwani 2026',
        'description': (
            'Three-day cultural extravaganza with music, dance, drama, '
            'and art exhibitions.'
        ),
        'venue': 'Open Air Theatre & Seminar Hall',
        'start_date': 'September 15, 2026',
        'end_date': 'September 17, 2026',
        'registration_deadline': 'September 10, 2026',
        'max_volunteers': 100,
        'total_applications': 0,
        'assigned_volunteers': 0,
        'status': 'Upcoming',
        'banner': None,
        'committees': [],
    },
    {
        'id': 4,
        'name': 'NSS Social Service Camp',
        'description': (
            'Week-long social service camp at adopted village for community '
            'development activities.'
        ),
        'venue': 'Adopted Village - Kottayam',
        'start_date': 'June 5, 2026',
        'end_date': 'June 10, 2026',
        'registration_deadline': 'May 30, 2026',
        'max_volunteers': 50,
        'total_applications': 50,
        'assigned_volunteers': 48,
        'status': 'Completed',
        'banner': None,
        'committees': [
            {'id': 9, 'name': 'Health Camp', 'required': 15,
             'assigned': 15, 'head': 'Dr. Lakshmi Nair'},
            {'id': 10, 'name': 'Education Drive', 'required': 15,
             'assigned': 15, 'head': 'Prof. Vineeth Mohan'},
            {'id': 11, 'name': 'Infrastructure', 'required': 10,
             'assigned': 10, 'head': 'Prof. Sanjay Das'},
            {'id': 12, 'name': 'Documentation', 'required': 8,
             'assigned': 8, 'head': 'Dr. Reshma Philip'},
        ],
    },
]


# =============================================================================
# Dean views — /dean/ prefix
# =============================================================================

def dean_dashboard_view(request):
    """Dean's main dashboard with overview stats and recent activity."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'stats': {
            'total_events': 12,
            'active_events': 3,
            'total_volunteers': 342,
            'pending_applications': 45,
            'total_committees': 18,
            'total_hours': 1580,
        },
        'recent_events': DUMMY_EVENTS[:3],
        'pending_apps': [
            {'student': 'Anika Sharma', 'event': 'Rajagiri Tech Fest 2026',
             'date': 'Jul 12, 2026', 'dept': 'Computer Science'},
            {'student': 'Vishnu Prasad', 'event': 'Rajagiri Tech Fest 2026',
             'date': 'Jul 12, 2026', 'dept': 'Electronics'},
            {'student': 'Nandita Krishnan', 'event': 'Annual Sports Day',
             'date': 'Jul 13, 2026', 'dept': 'Commerce'},
            {'student': 'Rohit Menon', 'event': 'Annual Sports Day',
             'date': 'Jul 13, 2026', 'dept': 'Mathematics'},
            {'student': 'Sneha Thomas', 'event': 'Rajagiri Tech Fest 2026',
             'date': 'Jul 14, 2026', 'dept': 'Computer Science'},
        ],
    }
    return render(request, 'dashboards/dean_dashboard.html', context)


def event_list_view(request):
    """List all events (Dean view with full management controls)."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'events': DUMMY_EVENTS,
    }
    return render(request, 'events/event_list.html', context)


def event_create_view(request):
    """Event creation form with committee setup."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'is_edit': False,
        'committee_heads': [
            {'id': 1, 'name': 'Dr. Priya Sharma'},
            {'id': 2, 'name': 'Prof. Rahul Nair'},
            {'id': 3, 'name': 'Dr. Anita Joseph'},
            {'id': 4, 'name': 'Prof. Suresh Kumar'},
            {'id': 5, 'name': 'Dr. Meera Krishnan'},
            {'id': 6, 'name': 'Prof. Deepak Menon'},
        ],
        'students_pool': [
            {'id': 1, 'name': 'Arjun Menon'},
            {'id': 2, 'name': 'Anika Sharma'},
            {'id': 3, 'name': 'Rohit Menon'},
            {'id': 4, 'name': 'Vishnu Prasad'},
            {'id': 5, 'name': 'Sneha Thomas'},
        ],
    }
    return render(request, 'events/event_form.html', context)


def event_detail_view(request, pk):
    """Detailed event view with committee breakdown (Dean view)."""
    event = DUMMY_EVENTS[0]  # Always show first dummy event for design
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'event': event,
    }
    return render(request, 'events/event_detail.html', context)


def event_edit_view(request, pk):
    """Event edit form pre-filled with existing data."""
    event = DUMMY_EVENTS[0]
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'is_edit': True,
        'event': event,
        'committee_heads': [
            {'id': 1, 'name': 'Dr. Priya Sharma'},
            {'id': 2, 'name': 'Prof. Rahul Nair'},
            {'id': 3, 'name': 'Dr. Anita Joseph'},
            {'id': 4, 'name': 'Prof. Suresh Kumar'},
            {'id': 5, 'name': 'Dr. Meera Krishnan'},
        ],
        'students_pool': [
            {'id': 1, 'name': 'Arjun Menon'},
            {'id': 2, 'name': 'Anika Sharma'},
            {'id': 3, 'name': 'Rohit Menon'},
            {'id': 4, 'name': 'Vishnu Prasad'},
            {'id': 5, 'name': 'Sneha Thomas'},
        ],
    }
    return render(request, 'events/event_form.html', context)


def committee_list_view(request):
    """List all committees across all events, with optional event filtering."""
    selected_event_id = request.GET.get('event_id', '')
    
    all_committees = []
    for event in DUMMY_EVENTS:
        if not selected_event_id or str(event['id']) == selected_event_id:
            for c in event.get('committees', []):
                committee_copy = dict(c)
                committee_copy['event_name'] = event['name']
                all_committees.append(committee_copy)
                
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'committees': all_committees,
        'events': [{'id': e['id'], 'name': e['name']} for e in DUMMY_EVENTS],
        'selected_event_id': selected_event_id,
    }
    return render(request, 'events/committee_list.html', context)


def user_management_view(request):
    """User management page for Dean to manage all system users."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Jaya Vijayan',
        'departments': [
            'Computer Science',
            'Business Administration',
            'Commerce',
            'Psychology',
            'Social Work',
        ],
        'designations': [
            'Assistant Professor',
            'Associate Professor',
            'Professor',
            'Teaching Associate',
            'Dean',
        ],
        'users': [
            {
                'id': 1,
                'name': 'Dr. Jaya Vijayan',
                'email': 'jayad@rajagiri.edu',
                'role': 'Dean', # System Admin
                'is_admin': True,
                'designation': 'Dean of Student Affairs',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 22, 2026'
            },
            {
                'id': 2,
                'name': 'Dr. Bindiya M Varghese',
                'email': 'bindiyad@rajagiri.edu',
                'role': 'Committee Head',
                'is_admin': False,
                'designation': 'Dean',
                'department': 'Computer Science',
                'is_hod': True, # Dept Dean / HOD
                'status': 'Active',
                'last_login': 'Jul 21, 2026'
            },
            {
                'id': 3,
                'name': 'Mr. Diljith K Benny',
                'email': 'diljithd@rajagiri.edu',
                'role': 'Committee Head',
                'is_admin': False,
                'designation': 'Assistant Professor',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 20, 2026'
            },
            {
                'id': 4,
                'name': 'Dr. Ann Baby',
                'email': 'annd@rajagiri.edu',
                'role': 'Committee Head',
                'is_admin': False,
                'designation': 'Assistant Professor',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 19, 2026'
            },
            {
                'id': 5,
                'name': 'Jobin Jaison K',
                'email': 'jobinjaisond@rajagiri.edu',
                'role': 'Committee Head',
                'is_admin': False,
                'designation': 'Teaching Associate',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 18, 2026'
            },
            {
                'id': 6,
                'name': 'Arjun Menon',
                'email': 'arjun.menon@rajagiri.edu',
                'role': 'Student',
                'is_admin': False,
                'designation': 'Student',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 22, 2026'
            },
            {
                'id': 7,
                'name': 'Anika Sharma',
                'email': 'anika.sharma@rajagiri.edu',
                'role': 'Student',
                'is_admin': False,
                'designation': 'Student',
                'department': 'Computer Science',
                'is_hod': False,
                'status': 'Active',
                'last_login': 'Jul 21, 2026'
            },
        ],
    }
    return render(request, 'accounts/user_management.html', context)


def course_dept_management_view(request):
    """Course and Department management page for Dean."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Jaya Vijayan',
        'courses': [
            {'id': 1, 'name': 'BBA F&B', 'code': 'bba', 'years': 3, 'dept': 'Business Administration'},
            {'id': 2, 'name': 'IMBA (Integrated MBA)', 'code': 'imba', 'years': 5, 'dept': 'Business Administration'},
            {'id': 3, 'name': 'BCA', 'code': 'bca', 'years': 3, 'dept': 'Computer Science'},
            {'id': 4, 'name': 'BSc Computer Science', 'code': 'bsccs', 'years': 3, 'dept': 'Computer Science'},
            {'id': 5, 'name': 'IMCA (Integrated MCA)', 'code': 'imca', 'years': 5, 'dept': 'Computer Science'},
            {'id': 6, 'name': 'MCA (Master of Computer Applications)', 'code': 'mca', 'years': 2, 'dept': 'Computer Science'},
            {'id': 7, 'name': 'MSc Computer Science', 'code': 'msccs', 'years': 2, 'dept': 'Computer Science'},
            {'id': 8, 'name': 'BSc Psychology', 'code': 'psy', 'years': 3, 'dept': 'Psychology'},
            {'id': 9, 'name': 'MSc Counselling Psychology', 'code': 'msycp', 'years': 2, 'dept': 'Psychology'},
            {'id': 10, 'name': 'MSW', 'code': 'msw', 'years': 2, 'dept': 'Social Work'},
            {'id': 11, 'name': 'PGDCSW', 'code': 'pgd', 'years': 1, 'dept': 'Social Work'},
        ],
        'departments': [
            {'id': 1, 'name': 'Computer Science', 'hod': 'Dr. Bindiya M Varghese', 'faculty_count': 21, 'courses_count': 5},
            {'id': 2, 'name': 'Business Administration', 'hod': 'Unassigned', 'faculty_count': 0, 'courses_count': 2},
            {'id': 3, 'name': 'Commerce', 'hod': 'Unassigned', 'faculty_count': 0, 'courses_count': 0},
            {'id': 4, 'name': 'Psychology', 'hod': 'Unassigned', 'faculty_count': 0, 'courses_count': 2},
            {'id': 5, 'name': 'Social Work', 'hod': 'Dr. Kiran Thampi', 'faculty_count': 1, 'courses_count': 2},
        ],
        'faculty_members': [
            {'id': 1, 'name': 'Dr. Bindiya M Varghese', 'dept': 'Computer Science'},
            {'id': 2, 'name': 'Dr. Kiran Thampi', 'dept': 'Social Work'},
            {'id': 3, 'name': 'Dr. Jaya Vijayan', 'dept': 'Computer Science'},
            {'id': 4, 'name': 'Mr. Diljith K Benny', 'dept': 'Computer Science'},
        ]
    }
    return render(request, 'events/course_dept_management.html', context)



def reports_view(request):
    """Reports dashboard with summary statistics and leaderboards."""
    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'summary': {
            'total_events': 12,
            'total_volunteers': 342,
            'total_hours': 1580,
            'avg_attendance': 89,
        },
        'event_stats': [
            {'event': 'NSS Social Service Camp', 'volunteers': 48,
             'hours': 480, 'attendance': 95},
            {'event': 'Rajagiri Tech Fest 2026', 'volunteers': 65,
             'hours': 390, 'attendance': 88},
            {'event': 'Annual Sports Day', 'volunteers': 0,
             'hours': 0, 'attendance': 0},
        ],
        'top_volunteers': [
            {'name': 'Arjun Menon', 'dept': 'Computer Science',
             'hours': 47.5, 'events': 8},
            {'name': 'Anika Sharma', 'dept': 'Computer Science',
             'hours': 42.0, 'events': 7},
            {'name': 'Vishnu Prasad', 'dept': 'Electronics',
             'hours': 38.5, 'events': 6},
            {'name': 'Nandita Krishnan', 'dept': 'Commerce',
             'hours': 35.0, 'events': 5},
            {'name': 'Sneha Thomas', 'dept': 'Computer Science',
             'hours': 32.0, 'events': 5},
        ],
    }
    return render(request, 'volunteers/reports.html', context)


# =============================================================================
# Student-facing views — /events/ prefix
# =============================================================================

def browse_events_view(request):
    """Browse available events (student-facing, filters open/upcoming)."""
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'is_student_coordinator': True,
        'events': [e for e in DUMMY_EVENTS
                   if e['status'] in ('Open', 'Upcoming')],
    }
    return render(request, 'events/event_list.html', context)


def event_public_detail_view(request, pk):
    """Public event detail page with apply button for students."""
    event = DUMMY_EVENTS[0]
    context = {
        'user_role': 'student',
        'user_name': 'Arjun Menon',
        'is_student_coordinator': True,
        'event': event,
        'has_applied': False,
    }
    return render(request, 'events/event_detail.html', context)


# =============================================================================
# Committee Head views — /committee/ prefix
# =============================================================================

def committee_dashboard_view(request):
    """Committee Head's dashboard with their committee overview and history tracking."""
    context = {
        'user_role': 'committee_head',
        'user_name': 'Dr. Priya Sharma',
        'committee': {
            'id': 1,
            'name': 'Registration & Reception',
            'event': 'Rajagiri Tech Fest 2026',
            'required': 15,
            'assigned': 12,
            'attendance_pct': 92,
            'total_hours_logged': 133,
            'open_slots': 3,
            'student_coordinator': 'Anika Sharma',
        },
        'submission_history': [
            {
                'date': 'July 25, 2026',
                'day': 'Day 1',
                'status': 'Approved',
                'status_color': 'success',
                'student_count': 12,
                'hours_logged': 66,
                'feedback': ''
            },
            {
                'date': 'July 26, 2026',
                'day': 'Day 2',
                'status': 'Sent Back',
                'status_color': 'danger',
                'student_count': 12,
                'hours_logged': 67,
                'feedback': 'Arjun Menon left early. Please adjust his hours to 3.0.'
            },
            {
                'date': 'July 27, 2026',
                'day': 'Day 3',
                'status': 'Not Submitted',
                'status_color': 'secondary',
                'student_count': 0,
                'hours_logged': 0,
                'feedback': ''
            }
        ],
        'volunteers': [
            {'name': 'Arjun Menon', 'class': 'CS-B',
             'dept': 'Computer Science', 'phone': '+91 98765 43210',
             'status': 'Active', 'attendance': 'Present'},
            {'name': 'Anika Sharma', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 87654 32109',
             'status': 'Active', 'attendance': 'Present'},
            {'name': 'Rohit Menon', 'class': 'MA-A',
             'dept': 'Mathematics', 'phone': '+91 76543 21098',
             'status': 'Active', 'attendance': 'Absent'},
            {'name': 'Vishnu Prasad', 'class': 'EC-B',
             'dept': 'Electronics', 'phone': '+91 65432 10987',
             'status': 'Active', 'attendance': 'Present'},
            {'name': 'Sneha Thomas', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 54321 09876',
             'status': 'Active', 'attendance': 'Present'},
        ],
    }
    return render(request, 'dashboards/committee_dashboard.html', context)


def committee_volunteers_view(request, pk):
    """View all volunteers assigned to a specific committee."""
    context = {
        'user_role': 'committee_head',
        'user_name': 'Dr. Priya Sharma',
        'committee': {
            'name': 'Registration & Reception',
            'event': 'Rajagiri Tech Fest 2026',
        },
        'volunteers': [
            {'id': 1, 'name': 'Arjun Menon', 'class': 'CS-B',
             'dept': 'Computer Science', 'phone': '+91 98765 43210',
             'email': 'arjun.menon@rajagiri.edu', 'status': 'Active'},
            {'id': 2, 'name': 'Anika Sharma', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 87654 32109',
             'email': 'anika.sharma@rajagiri.edu', 'status': 'Active'},
            {'id': 3, 'name': 'Rohit Menon', 'class': 'MA-A',
             'dept': 'Mathematics', 'phone': '+91 76543 21098',
             'email': 'rohit.menon@rajagiri.edu', 'status': 'Active'},
            {'id': 4, 'name': 'Vishnu Prasad', 'class': 'EC-B',
             'dept': 'Electronics', 'phone': '+91 65432 10987',
             'email': 'vishnu.p@rajagiri.edu', 'status': 'Active'},
            {'id': 5, 'name': 'Sneha Thomas', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 54321 09876',
             'email': 'sneha.t@rajagiri.edu', 'status': 'Active'},
        ],
    }
    return render(request, 'events/committee_volunteers.html', context)


def committee_attendance_view(request, pk):
    """Mark/view attendance for volunteers on a specific date, supporting locking and feedback states."""
    selected_date = request.GET.get('date', 'July 26, 2026')
    
    # Mock different states and hour counts based on date selected
    sheet_status = "Not Submitted"
    feedback = ""
    num_hours = 3
    
    if selected_date == 'July 25, 2026':
        sheet_status = "Approved"
        num_hours = 6
    elif selected_date == 'July 26, 2026':
        sheet_status = "Sent Back"
        feedback = "Arjun Menon left early. Please adjust his hours to 3.0."
        num_hours = 4
    elif selected_date == 'July 27, 2026':
        sheet_status = "Not Submitted"
        num_hours = 3

    # Generate student mock hourly status records (OD leave specific periods)
    if selected_date == 'July 25, 2026':
        volunteers_data = [
            {'id': 1, 'name': 'Arjun Menon', 'class': 'CS-B', 'hours': [True, True, True, True, True, True]},
            {'id': 2, 'name': 'Anika Sharma', 'class': 'CS-A', 'hours': [True, True, True, True, True, True]},
            {'id': 3, 'name': 'Rohit Menon', 'class': 'MA-A', 'hours': [False, False, False, False, False, False]},
            {'id': 4, 'name': 'Vishnu Prasad', 'class': 'EC-B', 'hours': [True, True, True, True, True, False]},
            {'id': 5, 'name': 'Sneha Thomas', 'class': 'CS-A', 'hours': [True, True, True, True, True, True]},
        ]
    elif selected_date == 'July 26, 2026':
        volunteers_data = [
            {'id': 1, 'name': 'Arjun Menon', 'class': 'CS-B', 'hours': [True, True, False, False]},
            {'id': 2, 'name': 'Anika Sharma', 'class': 'CS-A', 'hours': [True, True, True, True]},
            {'id': 3, 'name': 'Rohit Menon', 'class': 'MA-A', 'hours': [False, False, False, False]},
            {'id': 4, 'name': 'Vishnu Prasad', 'class': 'EC-B', 'hours': [True, True, True, False]},
            {'id': 5, 'name': 'Sneha Thomas', 'class': 'CS-A', 'hours': [True, True, True, True]},
        ]
    else: # July 27, 2026
        volunteers_data = [
            {'id': 1, 'name': 'Arjun Menon', 'class': 'CS-B', 'hours': [True, True, True]},
            {'id': 2, 'name': 'Anika Sharma', 'class': 'CS-A', 'hours': [True, True, True]},
            {'id': 3, 'name': 'Rohit Menon', 'class': 'MA-A', 'hours': [True, True, True]},
            {'id': 4, 'name': 'Vishnu Prasad', 'class': 'EC-B', 'hours': [True, True, True]},
            {'id': 5, 'name': 'Sneha Thomas', 'class': 'CS-A', 'hours': [True, True, True]},
        ]

    # Calculate initial totals for each volunteer to display in context
    for vol in volunteers_data:
        vol['total_hours'] = sum(1 for h in vol['hours'] if h)

    context = {
        'user_role': 'committee_head',
        'user_name': 'Dr. Priya Sharma',
        'committee': {
            'name': 'Registration & Reception',
            'event': 'Rajagiri Tech Fest 2026',
        },
        'event_dates': ['July 25, 2026', 'July 26, 2026', 'July 27, 2026'],
        'selected_date': selected_date,
        'sheet_status': sheet_status,
        'feedback': feedback,
        'num_hours': num_hours,
        'hours_range': range(1, num_hours + 1),
        'volunteers': volunteers_data,
    }
    return render(request, 'volunteers/attendance.html', context)


def committee_coordinators_view(request, pk):
    """View fellow committee coordinators of the same event."""
    context = {
        'user_role': 'committee_head',
        'user_name': 'Dr. Priya Sharma',
        'active_committee_id': pk,
        'committee': {
            'name': 'Registration & Reception',
            'event': 'Rajagiri Tech Fest 2026',
        },
        'coordinators': [
            {
                'name': 'Dr. Priya Sharma',
                'committee': 'Registration & Reception',
                'phone': '+91 94471 23456',
                'email': 'priya.sharma@rajagiri.edu',
                'role': 'Faculty Head',
                'is_me': True
            },
            {
                'name': 'Prof. Rahul Nair',
                'committee': 'Technical Events',
                'phone': '+91 98765 01234',
                'email': 'rahul.nair@rajagiri.edu',
                'role': 'Faculty Head',
                'is_me': False
            },
            {
                'name': 'Dr. Anita Joseph',
                'committee': 'Media & Publicity',
                'phone': '+91 87654 32109',
                'email': 'anita.joseph@rajagiri.edu',
                'role': 'Faculty Head',
                'is_me': False
            },
            {
                'name': 'Prof. Suresh Kumar',
                'committee': 'Logistics & Venue',
                'phone': '+91 76543 21098',
                'email': 'suresh.kumar@rajagiri.edu',
                'role': 'Faculty Head',
                'is_me': False
            },
            {
                'name': 'Dr. Meera Krishnan',
                'committee': 'Food & Hospitality',
                'phone': '+91 65432 10987',
                'email': 'meera.krishnan@rajagiri.edu',
                'role': 'Faculty Head',
                'is_me': False
            }
        ]
    }
    return render(request, 'events/committee_coordinators.html', context)


def dean_committee_detail_view(request, pk):
    """Dean view of all volunteers and coordinators assigned to a specific committee."""
    # Find matching committee from our dummy structure
    committee_data = None
    event_name = ""
    for event in DUMMY_EVENTS:
        for c in event.get('committees', []):
            if c['id'] == pk:
                committee_data = c
                event_name = event['name']
                break
        if committee_data:
            break
            
    # Fallback if id not found in dummy
    if not committee_data:
        committee_data = {
            'name': 'Registration & Reception',
            'head': 'Dr. Priya Sharma',
            'required': 15,
            'assigned': 12
        }
        event_name = 'Rajagiri Tech Fest 2026'

    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'committee': {
            'id': pk,
            'name': committee_data['name'],
            'event': event_name,
            'faculty_head': committee_data['head'],
            'student_head': committee_data.get('student_coordinator', None),
            'required': committee_data['required'],
            'assigned': committee_data['assigned'] if committee_data['assigned'] > 0 else 12,
        },
        'volunteers': [
            {'id': 1, 'name': 'Arjun Menon', 'class': 'CS-B',
             'dept': 'Computer Science', 'phone': '+91 98765 43210',
             'email': 'arjun.menon@rajagiri.edu', 'status': 'Active'},
            {'id': 2, 'name': 'Anika Sharma', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 87654 32109',
             'email': 'anika.sharma@rajagiri.edu', 'status': 'Active'},
            {'id': 3, 'name': 'Vishnu Prasad', 'class': 'EC-B',
             'dept': 'Electronics', 'phone': '+91 65432 10987',
             'email': 'vishnu.p@rajagiri.edu', 'status': 'Active'},
            {'id': 4, 'name': 'Sneha Thomas', 'class': 'CS-A',
             'dept': 'Computer Science', 'phone': '+91 54321 09876',
             'email': 'sneha.t@rajagiri.edu', 'status': 'Active'},
            {'id': 5, 'name': 'Rohit Menon', 'class': 'MA-A',
             'dept': 'Mathematics', 'phone': '+91 76543 21098',
             'email': 'rohit.menon@rajagiri.edu', 'status': 'Active'},
            {'id': 6, 'name': 'Nandita Krishnan', 'class': 'CO-A',
             'dept': 'Commerce', 'phone': '+91 91234 56789',
             'email': 'nandita.k@rajagiri.edu', 'status': 'Active'},
        ]
    }
    return render(request, 'events/committee_detail.html', context)


def dean_approvals_view(request):
    """Dean view to manage and approve volunteering hour sheets submitted by coordinators (Event first hierarchy)."""
    selected_event_id = request.GET.get('event_id', '')
    
    all_submissions = [
        {
            'id': 1,
            'event_id': 1,
            'event_name': 'Rajagiri Tech Fest 2026',
            'committee_name': 'Registration & Reception',
            'coordinator': 'Dr. Priya Sharma',
            'submitted_date': 'Jul 15, 2026',
            'student_count': 12,
            'total_hours': 66.0,
            'students': [
                {'name': 'Arjun Menon', 'class': 'CS-B', 'status': 'Present', 'hours': 5.5},
                {'name': 'Anika Sharma', 'class': 'CS-A', 'status': 'Present', 'hours': 6.0},
                {'name': 'Vishnu Prasad', 'class': 'EC-B', 'status': 'Present', 'hours': 4.5},
                {'name': 'Sneha Thomas', 'class': 'CS-A', 'status': 'Present', 'hours': 6.0},
                {'name': 'Rohit Menon', 'class': 'MA-A', 'status': 'Absent', 'hours': 0.0},
                {'name': 'Deepa Nair', 'class': 'EC-A', 'status': 'Present', 'hours': 5.0},
            ]
        },
        {
            'id': 2,
            'event_id': 2,
            'event_name': 'NSS Social Service Camp',
            'committee_name': 'Health Camp',
            'coordinator': 'Dr. Lakshmi Nair',
            'submitted_date': 'Jul 14, 2026',
            'student_count': 15,
            'total_hours': 90.0,
            'students': [
                {'name': 'Rahul Nair', 'class': 'CS-B', 'status': 'Present', 'hours': 6.0},
                {'name': 'Devika S', 'class': 'CS-B', 'status': 'Present', 'hours': 6.0},
                {'name': 'Gautham K', 'class': 'EC-A', 'status': 'Present', 'hours': 6.0},
            ]
        }
    ]
    
    # Group unique events with pending approvals
    events_map = {}
    for sub in all_submissions:
        ev_id = sub['event_id']
        if ev_id not in events_map:
            events_map[ev_id] = {
                'id': ev_id,
                'name': sub['event_name'],
                'count': 0,
                'total_hours': 0.0,
                'student_count': 0
            }
        events_map[ev_id]['count'] += 1
        events_map[ev_id]['total_hours'] += sub['total_hours']
        events_map[ev_id]['student_count'] += sub['student_count']

    filtered_submissions = []
    selected_event_name = ""
    if selected_event_id:
        filtered_submissions = [s for s in all_submissions if str(s['event_id']) == selected_event_id]
        if filtered_submissions:
            selected_event_name = filtered_submissions[0]['event_name']

    context = {
        'user_role': 'dean',
        'user_name': 'Dr. Thomas Mathew',
        'events': list(events_map.values()),
        'selected_event_id': selected_event_id,
        'selected_event_name': selected_event_name,
        'pending_approvals': filtered_submissions,
    }
    return render(request, 'events/dean_approvals.html', context)
