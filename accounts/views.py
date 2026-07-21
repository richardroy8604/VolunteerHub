"""
accounts app — Stub views with dummy context data.

These views render templates with realistic placeholder data
for UI design and development. Authentication logic will be
added once templates are finalized.
"""

from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout


def login_view(request):
    """Render the login page."""
    return render(request, 'accounts/login.html')


def logout_view(request):
    """Log the user out and redirect to the login page."""
    auth_logout(request)
    return redirect('accounts:login')


def first_login_view(request):
    """Render the first-login setup page (phone verification, etc.)."""
    return render(request, 'accounts/first_login.html')


def profile_view(request):
    """Render the user profile page with volunteer statistics."""
    role = request.GET.get('role', 'student')
    
    if role == 'dean':
        context = {
            'user_role': 'dean',
            'profile_user': {
                'name': 'Dr. Thomas Mathew',
                'email': 'thomas.mathew@rajagiri.edu',
                'role': 'Dean',
                'department': 'Administration',
                'semester': 'N/A',
                'student_class': 'N/A',
                'phone': '+91 94470 12345',
                'phone_verified': True,
                'total_hours': 'N/A',
                'events_participated': 'N/A',
                'profile_pic': None,
            }
        }
    elif role == 'committee_head':
        context = {
            'user_role': 'committee_head',
            'profile_user': {
                'name': 'Dr. Priya Sharma',
                'email': 'priya.sharma@rajagiri.edu',
                'role': 'Committee Head',
                'department': 'Computer Applications',
                'semester': 'N/A',
                'student_class': 'N/A',
                'phone': '+91 98460 54321',
                'phone_verified': True,
                'total_hours': 'N/A',
                'events_participated': 'N/A',
                'profile_pic': None,
            }
        }
    else:
        context = {
            'user_role': 'student',
            'profile_user': {
                'name': 'Arjun Menon',
                'email': 'arjun.menon@rajagiri.edu',
                'role': 'Student',
                'department': 'Computer Science',
                'semester': '6th Semester',
                'student_class': 'CS-B',
                'phone': '+91 98765 43210',
                'phone_verified': True,
                'total_hours': 47.5,
                'events_participated': 8,
                'profile_pic': None,
            }
        }
    return render(request, 'accounts/profile.html', context)


def profile_edit_view(request):
    """Render the profile edit form."""
    role = request.GET.get('role', 'student')
    
    if role == 'dean':
        context = {
            'user_role': 'dean',
            'profile_user': {
                'name': 'Dr. Thomas Mathew',
                'email': 'thomas.mathew@rajagiri.edu',
                'role': 'Dean',
                'department': 'Administration',
                'semester': 'N/A',
                'student_class': 'N/A',
                'phone': '+91 94470 12345',
                'phone_verified': True,
            }
        }
    elif role == 'committee_head':
        context = {
            'user_role': 'committee_head',
            'profile_user': {
                'name': 'Dr. Priya Sharma',
                'email': 'priya.sharma@rajagiri.edu',
                'role': 'Committee Head',
                'department': 'Computer Applications',
                'semester': 'N/A',
                'student_class': 'N/A',
                'phone': '+91 98460 54321',
                'phone_verified': True,
            }
        }
    else:
        context = {
            'user_role': 'student',
            'profile_user': {
                'name': 'Arjun Menon',
                'email': 'arjun.menon@rajagiri.edu',
                'role': 'Student',
                'department': 'Computer Science',
                'semester': '6th Semester',
                'student_class': 'CS-B',
                'phone': '+91 98765 43210',
                'phone_verified': True,
            }
        }
    return render(request, 'accounts/profile_edit.html', context)
