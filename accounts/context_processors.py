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
        'pending_approvals_count': 0,
    }

    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            
            pending_approvals = 0
            user_committee_id = None

            if profile.role == 'dean' or request.user.is_staff:
                from volunteers.models import AttendanceSheet
                pending_approvals = AttendanceSheet.objects.filter(status='pending').count()
            elif profile.role == 'faculty':
                from events.models import Committee
                user_comm = Committee.objects.filter(
                    faculty_head=profile,
                    event__status__in=['open', 'upcoming', 'ongoing']
                ).first()
                if not user_comm:
                    user_comm = Committee.objects.filter(faculty_head=profile).first()
                if user_comm:
                    user_committee_id = user_comm.id

            context.update({
                'user_role': profile.role,
                'user_name': request.user.get_full_name() or request.user.username,
                'user_department': profile.department,
                'user_designation': profile.display_role,
                'user_profile': profile,
                'is_student_coordinator': profile.is_student_coordinator,
                'pending_approvals_count': pending_approvals,
                'user_committee_id': user_committee_id,
            })
        except Exception:
            # Profile may not exist yet (e.g. during superuser creation)
            context['user_name'] = request.user.username

    return context
