"""
Role-based access decorators for VolunteerHub views.

These decorators wrap views to enforce role-based access control.
They check the user's UserProfile.role and redirect unauthorized users
with an appropriate error message.

Usage:
    @dean_required
    def dean_dashboard(request):
        ...

    @faculty_required
    def faculty_dashboard(request):
        ...

    @student_required
    def student_dashboard(request):
        ...

    @login_required_with_role('dean', 'faculty')
    def shared_view(request):
        ...
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def login_required_with_role(*allowed_roles):
    """
    Decorator that requires login AND one of the specified roles.

    Args:
        *allowed_roles: One or more role strings ('dean', 'faculty', 'student').

    Redirects to login if not authenticated, or to the user's own dashboard
    if authenticated but with the wrong role.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            try:
                profile = request.user.profile
            except Exception:
                messages.error(request, 'User profile not found. Please contact an administrator.')
                return redirect('accounts:login')

            if profile.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # Redirect to the user's own dashboard with an error message
            messages.error(request, 'You do not have permission to access that page.')
            dashboard_map = {
                'dean': 'events:dean_dashboard',
                'faculty': 'events:faculty_dashboard',
                'student': 'events:student_dashboard',
            }
            redirect_url = dashboard_map.get(profile.role, 'accounts:login')
            return redirect(redirect_url)

        return wrapper
    return decorator


def dean_required(view_func):
    """Decorator that requires the user to be a Dean (system admin)."""
    return login_required_with_role('dean')(view_func)


def faculty_required(view_func):
    """Decorator that requires the user to be Faculty or Dean."""
    return login_required_with_role('dean', 'faculty')(view_func)


def student_required(view_func):
    """Decorator that requires the user to be a Student."""
    return login_required_with_role('student')(view_func)


def coordinator_or_dean_required(view_func):
    """
    Decorator for views accessible by Deans or Student Coordinators.
    Student coordinators are students who are Main Student Coordinator
    or Committee Student Coordinator on an active event.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        try:
            profile = request.user.profile
        except Exception:
            messages.error(request, 'User profile not found.')
            return redirect('accounts:login')

        if profile.role == 'dean':
            return view_func(request, *args, **kwargs)

        if profile.role == 'student' and profile.is_student_coordinator:
            return view_func(request, *args, **kwargs)

        messages.error(request, 'You do not have permission to access that page.')
        dashboard_map = {
            'dean': 'events:dean_dashboard',
            'faculty': 'events:faculty_dashboard',
            'student': 'events:student_dashboard',
        }
        redirect_url = dashboard_map.get(profile.role, 'accounts:login')
        return redirect(redirect_url)

    return wrapper
