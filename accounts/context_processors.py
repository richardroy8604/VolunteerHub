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

            # Notifications
            from accounts.models import Notification
            from events.models import Event
            
            unread_notifications = profile.notifications.filter(is_read=False)
            unread_notifications_count = unread_notifications.count()
            recent_notifications = profile.notifications.all()[:8]

            active_events_for_broadcast = []
            if profile.role == 'dean' or request.user.is_staff:
                active_events_for_broadcast = Event.objects.prefetch_related('committees').all().order_by('-created_at')

            student_assigned_committee_id = None
            student_assigned_committee_name = ''
            if profile.role == 'student':
                from volunteers.models import VolunteerApplication
                active_app = VolunteerApplication.objects.filter(
                    student=profile,
                    status='assigned',
                    event__status__in=['open', 'upcoming', 'ongoing']
                ).select_related('assigned_committee').first()
                if active_app and active_app.assigned_committee:
                    student_assigned_committee_id = active_app.assigned_committee.id
                    student_assigned_committee_name = active_app.assigned_committee.name

            context.update({
                'user_role': profile.role,
                'user_name': request.user.get_full_name() or request.user.username,
                'user_department': profile.department,
                'user_designation': profile.display_role,
                'user_profile': profile,
                'is_student_coordinator': profile.is_student_coordinator,
                'pending_approvals_count': pending_approvals,
                'user_committee_id': user_committee_id,
                'student_assigned_committee_id': student_assigned_committee_id,
                'student_assigned_committee_name': student_assigned_committee_name,
                'unread_notifications_count': unread_notifications_count,
                'recent_notifications': recent_notifications,
                'active_events_for_broadcast': active_events_for_broadcast,
            })
        except Exception:
            # Profile may not exist yet (e.g. during superuser creation)
            context['user_name'] = request.user.username

    return context
