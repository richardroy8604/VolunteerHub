"""
Custom context processor for VolunteerHub.

Injects user profile data into every template context so that
base templates, sidebars, and navigation can access role, name,
department, and other profile fields without each view having to
pass them explicitly.
"""


def user_context(request):
    """
    Injects the authenticated user's profile data into template context.

    Available in templates as:
        {{ user_role }}         → 'dean', 'faculty', or 'student'
        {{ user_name }}         → Full name or username
        {{ user_department }}   → Department name
        {{ user_designation }}  → Display role string (e.g. 'Dean of Student Affairs')
        {{ user_profile }}      → Full UserProfile object
        {{ is_student_coordinator }} → True if student is coordinator on active event
    """
    context = {
        'user_role': None,
        'user_name': '',
        'user_department': '',
        'user_designation': '',
        'user_profile': None,
        'is_student_coordinator': False,
    }

    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            context.update({
                'user_role': profile.role,
                'user_name': request.user.get_full_name() or request.user.username,
                'user_department': profile.department,
                'user_designation': profile.display_role,
                'user_profile': profile,
                'is_student_coordinator': profile.is_student_coordinator,
            })
        except Exception:
            # Profile may not exist yet (e.g. during superuser creation)
            context['user_name'] = request.user.username

    return context
