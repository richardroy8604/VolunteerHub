"""
events app — Views powered by real database queries.

These views serve Dean, Faculty (Committee Head), and Student roles
with data from the Event, Committee, UserProfile, VolunteerApplication,
AttendanceSheet, and AttendanceRecord models.

Context processor (accounts.context_processors.user_context) automatically
injects user_role, user_name, user_department, user_designation, and
is_student_coordinator into every template context.
"""

from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.core.paginator import Paginator

from accounts.models import UserProfile, CourseConfig
from accounts.decorators import dean_required, faculty_required, student_required
from events.models import Event, Committee, Venue
from volunteers.models import VolunteerApplication, AttendanceSheet, AttendanceRecord
from .forms import EventForm


# =============================================================================
# Helper functions
# =============================================================================

def _format_date(d):
    """Format a date object as 'Month DD, YYYY'."""
    if d is None:
        return ''
    return d.strftime('%B %d, %Y')


def _format_date_short(d):
    """Format a date object as 'Mon DD, YYYY'."""
    if d is None:
        return ''
    return d.strftime('%b %d, %Y')


def _safe_parse_date(date_str, fallback_date):
    """
    Safely parse a date string in format '%B %d, %Y' (e.g. 'July 20, 2026').
    If invalid or malformed, returns (fallback_date, fallback_date.strftime('%B %d, %Y')).
    """
    if not date_str or not isinstance(date_str, str):
        return fallback_date, fallback_date.strftime('%B %d, %Y')
    from datetime import datetime
    try:
        parsed_obj = datetime.strptime(date_str.strip(), '%B %d, %Y').date()
        return parsed_obj, parsed_obj.strftime('%B %d, %Y')
    except (ValueError, TypeError):
        return fallback_date, fallback_date.strftime('%B %d, %Y')


def _event_to_dict(event):
    """
    Convert an Event model instance to a template-compatible dict.
    Matches the exact key structure templates expect from the old DUMMY_EVENTS.
    """
    committees = []
    has_overmanned = False
    for c in event.committees.select_related('faculty_head__user', 'student_coordinator__user').all():
        is_overmanned = (c.assigned_count > c.required_volunteers)
        if is_overmanned:
            has_overmanned = True
        committees.append({
            'id': c.id,
            'name': c.name,
            'required': c.required_volunteers,
            'assigned': c.assigned_count,
            'is_overmanned': is_overmanned,
            'head': c.faculty_head.user.get_full_name() if c.faculty_head else 'Unassigned',
            'head_id': c.faculty_head_id,
            'student_coordinator': (
                c.student_coordinator.user.get_full_name()
                if c.student_coordinator else None
            ),
            'student_coordinator_id': c.student_coordinator_id,
        })

    return {
        'id': event.id,
        'name': event.name,
        'description': event.description,
        'venue': event.venue,
        'start_date': _format_date(event.start_date),
        'end_date': _format_date(event.end_date),
        'registration_deadline': _format_date(event.registration_deadline),
        'raw_start_date': event.start_date.strftime('%Y-%m-%d') if event.start_date else '',
        'raw_end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else '',
        'raw_registration_deadline': event.registration_deadline.strftime('%Y-%m-%d') if event.registration_deadline else '',
        'max_volunteers': max(1, event.max_volunteers) if event.max_volunteers else 100,
        'total_applications': event.total_applications,
        'assigned_volunteers': event.assigned_volunteers,
        'status': event.dynamic_status_display,
        'raw_status': event.dynamic_status,
        'has_overmanned': has_overmanned,
        'banner': event.banner if event.banner else None,
        'main_student_coordinator': (
            event.main_student_coordinator.user.get_full_name()
            if event.main_student_coordinator else None
        ),
        'committees': committees,
    }


# =============================================================================
# DEAN VIEWS
# =============================================================================

@dean_required
def dean_dashboard_view(request):
    """Dean Dashboard: High-level overview of active events, volunteers, and quick actions."""
    events_qs = Event.objects.all()

    total_events = events_qs.count()
    active_events = events_qs.filter(status__in=['open', 'upcoming', 'ongoing']).count()

    total_volunteers_req = Committee.objects.aggregate(
        total=Sum('required_volunteers')
    )['total'] or 0

    assigned_volunteers = VolunteerApplication.objects.filter(
        status='assigned'
    ).count()

    hours_agg = AttendanceRecord.objects.filter(
        sheet__status='approved'
    ).aggregate(total=Sum('total_hours'))['total'] or 0

    # Recent events (last 3 by start_date)
    recent_qs = events_qs.prefetch_related(
        'committees__faculty_head__user',
        'committees__student_coordinator__user',
    ).order_by('-start_date')[:3]
    recent_events = [_event_to_dict(e) for e in recent_qs]

    # Pending applications (last 5)
    pending_apps_qs = VolunteerApplication.objects.filter(
        status='pending'
    ).select_related(
        'student__user', 'event'
    ).order_by('-applied_at')[:5]
    pending_apps = [{
        'student': app.student.user.get_full_name(),
        'event': app.event.name,
        'date': _format_date_short(app.applied_at),
        'dept': app.student.department,
    } for app in pending_apps_qs]

    context = {
        'stats': {
            'total_events': total_events,
            'active_events': active_events,
            'total_volunteers': assigned_volunteers,
            'pending_applications': VolunteerApplication.objects.filter(status='pending').count(),
            'total_committees': Committee.objects.count(),
            'total_hours': hours_agg,
        },
        'recent_events': recent_events,
        'pending_apps': pending_apps,
    }
    return render(request, 'dashboards/dean_dashboard.html', context)


@dean_required
def event_list_view(request):
    """List all events (Dean view with full management controls)."""
    raw_search_query = request.GET.get('search', '')
    search_query = raw_search_query.strip()
    status_filter = request.GET.get('status', '').strip()

    events_qs = Event.objects.prefetch_related(
        'committees__faculty_head__user',
        'committees__student_coordinator__user',
    ).all()

    if search_query:
        events_qs = events_qs.filter(
            Q(name__icontains=search_query) |
            Q(venue__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if status_filter:
        events_qs = events_qs.filter(status=status_filter)

    events = [_event_to_dict(e) for e in events_qs]

    context = {
        'events': events,
        'search_query': raw_search_query,
        'status_filter': status_filter,
    }
    return render(request, 'events/event_list.html', context)


@dean_required
def event_create_view(request):
    """Event creation form with committee setup and date timeline validations."""
    errors = {}
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.status = 'open'
            event.created_by = request.user
            event.save()

            msc_id = request.POST.get('main_student_coordinator')
            if msc_id:
                try:
                    event.main_student_coordinator = UserProfile.objects.get(id=msc_id, role='student')
                    event.save()
                except UserProfile.DoesNotExist:
                    pass

            committee_names = request.POST.getlist('committee_name[]')
            committee_required = request.POST.getlist('committee_required[]')
            committee_heads = request.POST.getlist('committee_head[]')
            committee_student_coords = request.POST.getlist('committee_student_coordinator[]')

            for i, name in enumerate(committee_names):
                if not name.strip():
                    continue
                committee = Committee.objects.create(
                    event=event,
                    name=name.strip(),
                    required_volunteers=int(committee_required[i]) if i < len(committee_required) and committee_required[i] else 10,
                )
                if i < len(committee_heads) and committee_heads[i]:
                    try:
                        committee.faculty_head = UserProfile.objects.get(id=committee_heads[i])
                        committee.save()
                    except UserProfile.DoesNotExist:
                        pass
                if i < len(committee_student_coords) and committee_student_coords[i]:
                    try:
                        committee.student_coordinator = UserProfile.objects.get(id=committee_student_coords[i], role='student')
                        committee.save()
                    except UserProfile.DoesNotExist:
                        pass

            messages.success(request, f'Event "{event.name}" created successfully!')
            return redirect('events_dean:event_detail', pk=event.id)
        else:
            errors = {field: err[0] for field, err in form.errors.items()}
            err_messages = [f"{field.replace('_', ' ').title()}: {err[0]}" for field, err in form.errors.items()]
            messages.error(request, 'Validation Error: ' + '; '.join(err_messages))

    faculty_profiles = UserProfile.objects.filter(
        role__in=['faculty', 'dean']
    ).select_related('user').order_by('user__first_name')
    committee_heads = [{'id': p.id, 'name': p.user.get_full_name()} for p in faculty_profiles]

    student_profiles = UserProfile.objects.filter(
        role='student'
    ).select_related('user').order_by('user__first_name')
    students_pool = [{'id': p.id, 'name': p.user.get_full_name()} for p in student_profiles]

    context = {
        'is_edit': False,
        'committee_heads': committee_heads,
        'students_pool': students_pool,
        'saved_venues': Venue.objects.all().order_by('name'),
        'errors': errors,
        'form_data': request.POST if request.method == 'POST' else {},
    }
    return render(request, 'events/event_form.html', context)


@dean_required
def event_detail_view(request, pk):
    """Detailed event view with committee breakdown (Dean view)."""
    event = get_object_or_404(
        Event.objects.prefetch_related(
            'committees__faculty_head__user',
            'committees__student_coordinator__user',
        ),
        pk=pk
    )
    context = {
        'event': _event_to_dict(event),
    }
    return render(request, 'events/event_detail.html', context)


@dean_required
def event_edit_view(request, pk):
    """Event edit form pre-filled with existing data and date timeline validations."""
    event = get_object_or_404(Event, pk=pk)
    errors = {}

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            event = form.save(commit=False)

            msc_id = request.POST.get('main_student_coordinator')
            if msc_id:
                try:
                    event.main_student_coordinator = UserProfile.objects.get(id=msc_id, role='student')
                except UserProfile.DoesNotExist:
                    pass
            else:
                event.main_student_coordinator = None

            event.save()

            # Update or create committees for this event
            committee_names = request.POST.getlist('committee_name[]')
            committee_required = request.POST.getlist('committee_count[]') or request.POST.getlist('committee_required[]')
            committee_heads = request.POST.getlist('committee_head[]')
            committee_student_coords = request.POST.getlist('committee_student_coordinator[]')

            existing_committees = list(event.committees.all())
            for i, name in enumerate(committee_names):
                if not name.strip():
                    continue
                req_val = int(committee_required[i]) if i < len(committee_required) and committee_required[i] else 10
                head_id = committee_heads[i] if i < len(committee_heads) and committee_heads[i] else None
                faculty_head = UserProfile.objects.filter(id=head_id).first() if head_id else None

                student_coord_id = committee_student_coords[i] if i < len(committee_student_coords) and committee_student_coords[i] else None
                student_coord = UserProfile.objects.filter(id=student_coord_id, role='student').first() if student_coord_id else None

                if i < len(existing_committees):
                    comm = existing_committees[i]
                    comm.name = name.strip()
                    comm.required_volunteers = req_val
                    comm.faculty_head = faculty_head
                    comm.student_coordinator = student_coord
                    comm.save()
                else:
                    Committee.objects.create(
                        event=event,
                        name=name.strip(),
                        required_volunteers=req_val,
                        faculty_head=faculty_head,
                        student_coordinator=student_coord
                    )

            messages.success(request, f'Event "{event.name}" updated successfully!')
            return redirect('events_dean:event_detail', pk=event.id)
        else:
            errors = {field: err[0] for field, err in form.errors.items()}
            err_messages = [f"{field.replace('_', ' ').title()}: {err[0]}" for field, err in form.errors.items()]
            messages.error(request, 'Validation Error: ' + '; '.join(err_messages))

    event_with_committees = Event.objects.prefetch_related(
        'committees__faculty_head__user',
        'committees__student_coordinator__user',
    ).get(pk=pk)

    faculty_profiles = UserProfile.objects.filter(
        role__in=['faculty', 'dean']
    ).select_related('user').order_by('user__first_name')
    committee_heads = [{'id': p.id, 'name': p.user.get_full_name()} for p in faculty_profiles]

    student_profiles = UserProfile.objects.filter(
        role='student'
    ).select_related('user').order_by('user__first_name')
    students_pool = [{'id': p.id, 'name': p.user.get_full_name()} for p in student_profiles]

    context = {
        'is_edit': True,
        'event': _event_to_dict(event_with_committees),
        'committee_heads': committee_heads,
        'students_pool': students_pool,
        'saved_venues': Venue.objects.all().order_by('name'),
        'errors': errors,
        'form_data': request.POST if request.method == 'POST' else {},
    }
    return render(request, 'events/event_form.html', context)


@dean_required
def event_delete_view(request, pk):
    """Delete an event (Dean only). Protects events with active attendance sheets."""
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        if AttendanceSheet.objects.filter(committee__event=event).exists():
            messages.error(request, f'Cannot delete event "{event.name}" because attendance sheets have already been logged for it.')
            return redirect('events_dean:event_detail', pk=event.id)
            
        event_name = event.name
        event.delete()
        messages.success(request, f'Event "{event_name}" deleted successfully.')
        return redirect('events_dean:event_list')
    return redirect('events_dean:event_detail', pk=pk)


@dean_required
def venue_delete_view(request, pk):
    """Delete a saved venue from the dropdown registry."""
    if request.method in ['POST', 'DELETE']:
        venue = get_object_or_404(Venue, pk=pk)
        venue.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@dean_required
def committee_list_view(request):
    """List all committees across all events, with optional event filtering."""
    selected_event_id = request.GET.get('event_id', '')

    committees_qs = Committee.objects.select_related(
        'event', 'faculty_head__user', 'student_coordinator__user'
    )
    if selected_event_id:
        committees_qs = committees_qs.filter(event_id=selected_event_id)

    committees = []
    for c in committees_qs:
        committees.append({
            'id': c.id,
            'name': c.name,
            'required': c.required_volunteers,
            'assigned': c.assigned_count,
            'head': c.faculty_head.user.get_full_name() if c.faculty_head else 'Unassigned',
            'student_coordinator': (
                c.student_coordinator.user.get_full_name()
                if c.student_coordinator else None
            ),
            'event_name': c.event.name,
        })

    events = [{'id': e.id, 'name': e.name} for e in Event.objects.all()]

    context = {
        'committees': committees,
        'events': events,
        'selected_event_id': selected_event_id,
    }
    return render(request, 'events/committee_list.html', context)


@dean_required
def user_management_view(request):
    """User management page for Dean to manage all system users."""
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_faculty':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            department = request.POST.get('department', '').strip()
            designation = request.POST.get('designation', '').strip()
            is_hod = request.POST.get('is_hod') == 'on'
            role = request.POST.get('role', 'faculty')

            if not email:
                messages.error(request, 'Email is required.')
                return redirect('events_dean:user_management')

            if User.objects.filter(email=email).exists():
                messages.error(request, f'A user with email {email} already exists.')
                return redirect('events_dean:user_management')

            username = email.split('@')[0]
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password='VolunteerHub@2026',
                is_staff=(role == 'dean'),
                is_superuser=(role == 'dean'),
            )
            profile = user.profile
            profile.role = role
            profile.department = department
            profile.designation = designation
            profile.is_hod = is_hod
            profile.is_first_login = False
            profile.save()

            messages.success(request, f'Faculty user {first_name} {last_name} created successfully!')
            return redirect('events_dean:user_management')

        elif action == 'edit_user':
            user_profile_id = request.POST.get('user_profile_id')
            department = request.POST.get('department', '').strip()
            designation = request.POST.get('designation', '').strip()
            is_hod = request.POST.get('is_hod') == 'on'
            role = request.POST.get('role', 'faculty')

            if user_profile_id:
                try:
                    profile = UserProfile.objects.get(id=user_profile_id)
                    profile.department = department
                    profile.designation = designation
                    profile.is_hod = is_hod
                    profile.role = role

                    # Update User flags if role is dean
                    user = profile.user
                    user.is_staff = (role == 'dean')
                    user.is_superuser = (role == 'dean')
                    user.save()
                    profile.save()

                    messages.success(request, f'User profile for "{user.get_full_name() or user.username}" updated successfully!')
                except UserProfile.DoesNotExist:
                    messages.error(request, 'User profile not found.')
            return redirect('events_dean:user_management')

        elif action == 'delete_user':
            user_profile_id = request.POST.get('user_profile_id')
            confirm_text = request.POST.get('confirm_delete', '').strip()

            if user_profile_id and confirm_text == 'DELETE':
                try:
                    profile = UserProfile.objects.get(id=user_profile_id)
                    user = profile.user
                    name = user.get_full_name() or user.username
                    user.delete()
                    messages.success(request, f'User account "{name}" deleted successfully.')
                except UserProfile.DoesNotExist:
                    messages.error(request, 'User profile not found.')
            else:
                messages.error(request, 'Deletion cancelled: Confirmation text did not match "DELETE".')
            return redirect('events_dean:user_management')

    # GET: build user list from database
    raw_search_query = request.GET.get('search', '')
    search_query = raw_search_query.strip()
    selected_role = request.GET.get('role', '').strip()

    # Departments: get unique departments from UserProfile
    departments = list(
        UserProfile.objects.exclude(department='').values_list('department', flat=True).distinct()
    )
    if not departments:
        departments = ['Computer Science', 'Business Administration', 'Commerce', 'Psychology', 'Social Work']

    designations = ['Assistant Professor', 'Associate Professor', 'Professor', 'Teaching Associate']

    # Filter profiles
    profiles = UserProfile.objects.select_related('user').annotate(
        full_name=Concat('user__first_name', Value(' '), 'user__last_name')
    ).order_by('role', 'user__first_name')

    if search_query:
        # Match combined full_name ("Jaya Vijayan"), first_name, last_name, email, or department
        profiles = profiles.filter(
            Q(full_name__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(department__icontains=search_query)
        )

    if selected_role:
        # map 'committee_head' -> 'faculty'
        role_db = 'faculty' if selected_role == 'committee_head' else selected_role
        profiles = profiles.filter(role=role_db)

    users = []
    for p in profiles:
        if p.role == 'dean':
            display_role = 'Dean'
            is_admin = True
        elif p.role == 'faculty':
            display_role = 'Committee Head'
            is_admin = False
        else:
            display_role = 'Student'
            is_admin = False

        users.append({
            'id': p.id,
            'name': p.user.get_full_name(),
            'email': p.user.email,
            'role': display_role,
            'is_admin': is_admin,
            'designation': p.display_role,
            'department': p.department,
            'is_hod': p.is_hod,
            'status': 'Active' if p.user.is_active else 'Inactive',
            'last_login': (
                _format_date_short(p.user.last_login)
                if p.user.last_login else 'Never'
            ),
        })

    # Paginate 15 users per page (Fix 5)
    paginator = Paginator(users, 15)
    page_number = request.GET.get('page', 1)
    users_page = paginator.get_page(page_number)

    context = {
        'departments': departments,
        'designations': designations,
        'users': users_page,
        'search_query': raw_search_query,
        'selected_role': selected_role,
        'total_user_count': len(users),
    }
    return render(request, 'accounts/user_management.html', context)


@dean_required
def course_dept_management_view(request):
    """Course and Department management page for Dean."""
    # Ensure custom_departments list exists in session
    if 'custom_departments' not in request.session:
        request.session['custom_departments'] = []

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_course':
            name = request.POST.get('course_name', '').strip()
            code = request.POST.get('course_code', '').strip().lower()
            years_str = request.POST.get('course_years', '3')
            years = int(years_str) if years_str and years_str.isdigit() else 3
            dept = request.POST.get('course_dept', '').strip()

            if not code and name:
                code = ''.join([w[0] for w in name.split()]).lower()

            if code and name:
                if CourseConfig.objects.filter(code=code).exists():
                    messages.error(request, f'Course short code "{code}" already exists.')
                else:
                    CourseConfig.objects.create(
                        code=code,
                        full_name=name,
                        short_name=code.upper(),
                        duration_years=years,
                        department=dept or 'General',
                    )
                    messages.success(request, f'Course "{name}" created successfully!')
            return redirect('events_dean:course_dept_management')

        elif action == 'edit_course':
            course_id = request.POST.get('course_id')
            name = request.POST.get('course_name', '').strip()
            code = request.POST.get('course_code', '').strip().lower()
            years_str = request.POST.get('course_years', '3')
            years = int(years_str) if years_str and years_str.isdigit() else 3
            dept = request.POST.get('course_dept', '').strip()

            if course_id:
                try:
                    course = CourseConfig.objects.get(id=course_id)
                    course.full_name = name or course.full_name
                    course.code = code or course.code
                    course.short_name = (code or course.code).upper()
                    course.duration_years = years
                    course.department = dept or course.department
                    course.save()
                    messages.success(request, f'Course "{course.full_name}" updated successfully!')
                except CourseConfig.DoesNotExist:
                    messages.error(request, 'Course not found.')
            return redirect('events_dean:course_dept_management')

        elif action == 'delete_course':
            course_id = request.POST.get('course_id')
            confirm_text = request.POST.get('confirm_delete', '').strip()

            if course_id and confirm_text == 'DELETE':
                try:
                    course = CourseConfig.objects.get(id=course_id)
                    c_name = course.full_name
                    course.delete()
                    messages.success(request, f'Course "{c_name}" deleted successfully.')
                except CourseConfig.DoesNotExist:
                    messages.error(request, 'Course not found.')
            else:
                messages.error(request, 'Deletion cancelled: Confirmation text did not match "DELETE".')
            return redirect('events_dean:course_dept_management')

        elif action == 'add_department':
            dept_name = request.POST.get('dept_name', '').strip()
            hod_id = request.POST.get('dept_hod')

            if dept_name:
                custom_depts = request.session.get('custom_departments', [])
                if dept_name not in custom_depts:
                    custom_depts.append(dept_name)
                    request.session['custom_departments'] = custom_depts
                    request.session.modified = True

                if hod_id:
                    try:
                        hod_profile = UserProfile.objects.get(id=hod_id)
                        hod_profile.department = dept_name
                        hod_profile.is_hod = True
                        hod_profile.save()
                    except UserProfile.DoesNotExist:
                        pass

                messages.success(request, f'Department "{dept_name}" created successfully!')
            return redirect('events_dean:course_dept_management')

        elif action == 'edit_department':
            old_dept = request.POST.get('old_dept_name', '').strip()
            new_dept = request.POST.get('dept_name', '').strip()
            hod_id = request.POST.get('dept_hod')

            if old_dept and new_dept:
                # Update custom departments list in session
                custom_depts = request.session.get('custom_departments', [])
                if old_dept in custom_depts:
                    custom_depts.remove(old_dept)
                if new_dept not in custom_depts:
                    custom_depts.append(new_dept)
                request.session['custom_departments'] = custom_depts
                request.session.modified = True

                # Update CourseConfigs
                CourseConfig.objects.filter(department=old_dept).update(department=new_dept)
                # Update Profiles
                UserProfile.objects.filter(department=old_dept).update(department=new_dept)

                if hod_id:
                    try:
                        # Reset previous HOD for this department
                        UserProfile.objects.filter(department=new_dept, is_hod=True).update(is_hod=False)
                        new_hod = UserProfile.objects.get(id=hod_id)
                        new_hod.department = new_dept
                        new_hod.is_hod = True
                        new_hod.save()
                    except UserProfile.DoesNotExist:
                        pass

                messages.success(request, f'Department updated to "{new_dept}".')
            return redirect('events_dean:course_dept_management')

        elif action == 'delete_department':
            dept_name = request.POST.get('dept_name', '').strip()
            confirm_text = request.POST.get('confirm_delete', '').strip()

            if dept_name and confirm_text == 'DELETE':
                custom_depts = request.session.get('custom_departments', [])
                if dept_name in custom_depts:
                    custom_depts.remove(dept_name)
                    request.session['custom_departments'] = custom_depts
                    request.session.modified = True

                # Reset HOD flag for department
                UserProfile.objects.filter(department=dept_name, is_hod=True).update(is_hod=False)
                messages.success(request, f'Department "{dept_name}" deleted.')
            else:
                messages.error(request, 'Deletion cancelled: Confirmation text did not match "DELETE".')
            return redirect('events_dean:course_dept_management')

    # GET: build course and department data from DB
    courses = []
    for c in CourseConfig.objects.all():
        courses.append({
            'id': c.id,
            'name': c.full_name,
            'code': c.code,
            'years': c.duration_years,
            'dept': c.department,
        })

    # Build departments from unique department names across CourseConfig, UserProfile, and session
    dept_names = set()
    dept_names.update(CourseConfig.objects.values_list('department', flat=True).distinct())
    dept_names.update(
        UserProfile.objects.exclude(department='').values_list('department', flat=True).distinct()
    )
    dept_names.update(request.session.get('custom_departments', []))

    departments = []
    for idx, dept_name in enumerate(sorted(dept_names), 1):
        if not dept_name:
            continue
        hod = UserProfile.objects.filter(
            department=dept_name, is_hod=True
        ).select_related('user').first()

        faculty_count = UserProfile.objects.filter(
            department=dept_name, role__in=['faculty', 'dean']
        ).count()

        courses_count = CourseConfig.objects.filter(department=dept_name).count()

        departments.append({
            'id': idx,
            'name': dept_name,
            'hod': hod.user.get_full_name() if hod else 'Unassigned',
            'hod_id': hod.id if hod else '',
            'faculty_count': faculty_count,
            'courses_count': courses_count,
        })

    faculty_qs = UserProfile.objects.filter(
        role__in=['faculty', 'dean']
    ).select_related('user').order_by('user__first_name')
    faculty_members = [
        {'id': p.id, 'name': p.user.get_full_name(), 'dept': p.department}
        for p in faculty_qs
    ]

    context = {
        'courses': courses,
        'departments': departments,
        'faculty_members': faculty_members,
    }
    return render(request, 'events/course_dept_management.html', context)


@dean_required
def reports_view(request):
    """Reports dashboard with summary statistics and leaderboards."""
    completed_events = sum(1 for e in Event.objects.all() if e.dynamic_status == 'completed')
    total_volunteers = VolunteerApplication.objects.filter(status='assigned').values('student').distinct().count()
    total_hours = AttendanceRecord.objects.filter(
        sheet__status='approved'
    ).aggregate(total=Sum('total_hours'))['total'] or 0

    # Average attendance across approved sheets
    approved_sheets = AttendanceSheet.objects.filter(status='approved')
    if approved_sheets.exists():
        total_records = AttendanceRecord.objects.filter(sheet__status='approved').count()
        present_records = AttendanceRecord.objects.filter(
            sheet__status='approved', total_hours__gt=0
        ).count()
        avg_attendance = int((present_records / total_records * 100)) if total_records > 0 else 0
    else:
        avg_attendance = 0

    # Per-event stats
    event_stats = []
    for event in Event.objects.all():
        vol_count = VolunteerApplication.objects.filter(
            event=event, status='assigned'
        ).count()
        hours = AttendanceRecord.objects.filter(
            sheet__committee__event=event,
            sheet__status='approved'
        ).aggregate(total=Sum('total_hours'))['total'] or 0

        # Event-specific attendance
        evt_total = AttendanceRecord.objects.filter(
            sheet__committee__event=event, sheet__status='approved'
        ).count()
        evt_present = AttendanceRecord.objects.filter(
            sheet__committee__event=event, sheet__status='approved', total_hours__gt=0
        ).count()
        evt_attendance = int((evt_present / evt_total * 100)) if evt_total > 0 else 0

        event_stats.append({
            'event': event.name,
            'volunteers': vol_count,
            'hours': hours,
            'attendance': evt_attendance,
        })

    # Top volunteers by approved hours
    top_volunteers_qs = AttendanceRecord.objects.filter(
        sheet__status='approved'
    ).values(
        'student__user__first_name', 'student__user__last_name', 'student__department'
    ).annotate(
        total=Sum('total_hours'),
        event_count=Count('sheet__committee__event', distinct=True)
    ).order_by('-total')[:5]

    top_volunteers = [{
        'name': f"{v['student__user__first_name']} {v['student__user__last_name']}",
        'dept': v['student__department'],
        'hours': v['total'],
        'events': v['event_count'],
    } for v in top_volunteers_qs]

    context = {
        'summary': {
            'total_events': completed_events,
            'total_volunteers': total_volunteers,
            'total_hours': total_hours,
            'avg_attendance': avg_attendance,
        },
        'event_stats': event_stats,
        'top_volunteers': top_volunteers,
    }
    return render(request, 'volunteers/reports.html', context)


# =============================================================================
# Student-facing views — /events/ prefix
# =============================================================================

@student_required
def browse_events_view(request):
    """Browse available events (student-facing, filters open/upcoming)."""
    raw_search_query = request.GET.get('search', '')
    search_query = raw_search_query.strip()
    status_filter = request.GET.get('status', '').strip()

    events_qs = Event.objects.filter(
        status__in=['open', 'upcoming']
    ).prefetch_related(
        'committees__faculty_head__user',
        'committees__student_coordinator__user',
    )

    if search_query:
        events_qs = events_qs.filter(
            Q(name__icontains=search_query) |
            Q(venue__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if status_filter:
        events_qs = events_qs.filter(status=status_filter)

    events = [_event_to_dict(e) for e in events_qs]

    context = {
        'events': events,
        'search_query': raw_search_query,
        'status_filter': status_filter,
    }
    return render(request, 'events/event_list.html', context)


@student_required
def event_public_detail_view(request, pk):
    """Public event detail page with apply button for students."""
    event = get_object_or_404(
        Event.objects.prefetch_related(
            'committees__faculty_head__user',
            'committees__student_coordinator__user',
        ),
        pk=pk
    )
    profile = request.user.profile
    has_applied = VolunteerApplication.objects.filter(
        student=profile, event=event
    ).exists()

    context = {
        'event': _event_to_dict(event),
        'has_applied': has_applied,
    }
    return render(request, 'events/event_detail.html', context)


# =============================================================================
# Committee Head (Faculty) views — /committee/ prefix
# =============================================================================

@faculty_required
def committee_dashboard_view(request):
    """Committee Head's dashboard with their committee overview and history."""
    profile = request.user.profile

    # Find the committee(s) this faculty heads on an active event
    headed_committees = Committee.objects.filter(
        faculty_head=profile,
        event__status__in=['open', 'upcoming', 'ongoing']
    ).select_related('event', 'student_coordinator__user')

    if not headed_committees.exists():
        # Fall back to any committee they head
        headed_committees = Committee.objects.filter(
            faculty_head=profile,
        ).select_related('event', 'student_coordinator__user')

    committee_obj = headed_committees.first()

    if not committee_obj:
        context = {
            'committee': None,
            'submission_history': [],
            'volunteers': [],
        }
        return render(request, 'dashboards/committee_dashboard.html', context)

    # Handle POST action: Assign / Change Student Lead
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign_lead':
            student_lead_id = request.POST.get('student_lead_id')
            if student_lead_id:
                student_profile = UserProfile.objects.filter(id=student_lead_id, role='student').first()
                if student_profile:
                    committee_obj.student_coordinator = student_profile
                    committee_obj.save()
                    messages.success(request, f"Assigned {student_profile.user.get_full_name()} as Student Coordinator for {committee_obj.name}.")
            else:
                committee_obj.student_coordinator = None
                committee_obj.save()
                messages.info(request, f"Removed Student Coordinator for {committee_obj.name}.")
            return redirect('events_committee:committee_dashboard')

    # Build committee dict matching template expectations
    # Calculate attendance percentage from approved sheets
    approved_records = AttendanceRecord.objects.filter(
        sheet__committee=committee_obj,
        sheet__status='approved',
    )
    total_records_count = approved_records.count()
    present_records_count = approved_records.filter(total_hours__gt=0).count()
    attendance_pct = (
        int((present_records_count / total_records_count * 100))
        if total_records_count > 0 else 0
    )

    total_hours_logged = approved_records.aggregate(
        total=Sum('total_hours')
    )['total'] or 0

    committee_dict = {
        'id': committee_obj.id,
        'name': committee_obj.name,
        'event': committee_obj.event.name,
        'required': committee_obj.required_volunteers,
        'assigned': committee_obj.assigned_count,
        'attendance_pct': attendance_pct,
        'total_hours_logged': total_hours_logged,
        'open_slots': committee_obj.open_slots,
        'student_coordinator': (
            committee_obj.student_coordinator.user.get_full_name()
            if committee_obj.student_coordinator else None
        ),
    }

    # Submission history — one row per event date
    event = committee_obj.event
    submission_history = []
    current_date = event.start_date
    day_num = 1
    while current_date <= event.end_date:
        try:
            sheet = AttendanceSheet.objects.get(
                committee=committee_obj, date=current_date
            )
            status = sheet.get_status_display()
            status_color_map = {
                'not_submitted': 'secondary',
                'pending': 'warning',
                'approved': 'success',
                'sent_back': 'danger',
            }
            submission_history.append({
                'date': _format_date(current_date),
                'day': f'Day {day_num}',
                'status': status,
                'status_color': status_color_map.get(sheet.status, 'secondary'),
                'student_count': sheet.student_count,
                'hours_logged': sheet.total_hours_logged,
                'feedback': sheet.feedback,
            })
        except AttendanceSheet.DoesNotExist:
            submission_history.append({
                'date': _format_date(current_date),
                'day': f'Day {day_num}',
                'status': 'Not Submitted',
                'status_color': 'secondary',
                'student_count': 0,
                'hours_logged': 0,
                'feedback': '',
            })
        current_date += timedelta(days=1)
        day_num += 1

    # Volunteers assigned to this committee
    assigned_apps = VolunteerApplication.objects.filter(
        assigned_committee=committee_obj,
        status='assigned'
    ).select_related('student__user')

    volunteers = []
    for app in assigned_apps:
        s = app.student
        # Get today's attendance if available
        today = timezone.now().date()
        try:
            today_record = AttendanceRecord.objects.get(
                sheet__committee=committee_obj,
                sheet__date=today,
                student=s
            )
            attendance = 'Present' if today_record.total_hours > 0 else 'Absent'
        except AttendanceRecord.DoesNotExist:
            attendance = 'Absent'

        volunteers.append({
            'id': s.id,
            'name': s.user.get_full_name(),
            'class': s.class_batch,
            'dept': s.department,
            'phone': s.phone,
            'status': 'Active',
            'attendance': attendance,
        })

    context = {
        'committee': committee_dict,
        'submission_history': submission_history,
        'volunteers': volunteers,
    }
    return render(request, 'dashboards/committee_dashboard.html', context)


@faculty_required
def committee_volunteers_view(request, pk):
    """View all volunteers assigned to a specific committee."""
    committee = get_object_or_404(
        Committee.objects.select_related('event', 'faculty_head'),
        pk=pk
    )
    profile = request.user.profile
    if profile.role != 'dean' and not request.user.is_staff and committee.faculty_head != profile:
        messages.error(request, f"Access Denied: You are not assigned as the Faculty Head of the '{committee.name}' committee.")
        return redirect('events_committee:committee_dashboard')

    assigned_apps = VolunteerApplication.objects.filter(
        assigned_committee=committee,
        status='assigned'
    ).select_related('student__user')

    volunteers = []
    for app in assigned_apps:
        s = app.student
        volunteers.append({
            'id': s.id,
            'name': s.user.get_full_name(),
            'class': s.class_batch,
            'dept': s.department,
            'phone': s.phone,
            'email': s.user.email,
            'status': 'Active',
        })

    context = {
        'committee': {
            'name': committee.name,
            'event': committee.event.name,
        },
        'volunteers': volunteers,
    }
    return render(request, 'events/committee_volunteers.html', context)


@faculty_required
def committee_attendance_view(request, pk):
    """Mark/view attendance for volunteers on a specific date."""
    committee = get_object_or_404(
        Committee.objects.select_related('event', 'faculty_head'),
        pk=pk
    )
    profile = request.user.profile
    if profile.role != 'dean' and not request.user.is_staff and committee.faculty_head != profile:
        messages.error(request, f"Access Denied: You are not assigned as the Faculty Head of the '{committee.name}' committee.")
        return redirect('events_committee:committee_dashboard')

    event = committee.event

    # Build event dates list
    event_dates_list = event.event_dates  # List of formatted date strings

    raw_date = request.GET.get('date', event_dates_list[0] if event_dates_list else '')
    selected_date_obj, selected_date = _safe_parse_date(raw_date, event.start_date)

    # Handle POST: save attendance data
    if request.method == 'POST':
        today = timezone.now().date()

        # Timeline Rule 1: Duty date must be within event duration
        if selected_date_obj < event.start_date or selected_date_obj > event.end_date:
            messages.error(
                request,
                f"Attendance duty date ({selected_date_obj.strftime('%b %d, %Y')}) must be between event start date "
                f"({event.start_date.strftime('%b %d, %Y')}) and end date ({event.end_date.strftime('%b %d, %Y')})."
            )
            return redirect(f"{request.path}?date={selected_date}")

        # Timeline Rule 2: Cannot mark attendance for future shift dates
        if selected_date_obj > today:
            messages.error(
                request,
                f"Cannot mark or submit attendance for a future shift date ({selected_date_obj.strftime('%b %d, %Y')})."
            )
            return redirect(f"{request.path}?date={selected_date}")

        action = request.POST.get('action', 'save')
        num_hours_post = int(request.POST.get('num_hours', 3))

        # Get or create the attendance sheet
        sheet, created = AttendanceSheet.objects.get_or_create(
            committee=committee,
            date=selected_date_obj,
            defaults={'num_hours': num_hours_post}
        )

        sheet.num_hours = num_hours_post

        # Update attendance records for each volunteer
        assigned_apps = VolunteerApplication.objects.filter(
            assigned_committee=committee, status='assigned'
        ).select_related('student')

        for app in assigned_apps:
            hours_list = []
            key_array = f'hours_{app.student.id}[]'
            val_array = request.POST.getlist(key_array)

            for h in range(1, num_hours_post + 1):
                key_single = f'hour_{app.student.id}_{h}'
                is_present = (request.POST.get(key_single) == 'on') or (str(h - 1) in val_array) or (str(h) in val_array)
                hours_list.append(is_present)

            tot = sum(1 for x in hours_list if x)
            AttendanceRecord.objects.update_or_create(
                sheet=sheet,
                student=app.student,
                defaults={'hours': hours_list, 'total_hours': tot}
            )

        if action == 'submit':
            sheet.status = 'pending'
            sheet.submitted_by = request.user.profile
            sheet.submitted_at = timezone.now()
            sheet.save()
            messages.success(request, f'Attendance sheet for {selected_date} submitted/updated for Dean approval.')
        else:
            if sheet.status != 'pending':
                sheet.status = 'not_submitted'
            sheet.save()
            messages.success(request, f'Attendance draft saved successfully.')

        return redirect(f"{request.path}?date={selected_date}&mode=view")

    # GET: load existing sheet data
    today = timezone.now().date()
    is_future_date = (selected_date_obj > today)
    is_out_of_bounds = (selected_date_obj < event.start_date or selected_date_obj > event.end_date)

    mode = request.GET.get('mode', 'view')

    # If date is in future or out of bounds, prevent entering edit mode
    if (is_future_date or is_out_of_bounds) and mode == 'edit':
        if is_future_date:
            messages.warning(
                request,
                f"Attendance cannot be taken for a future date ({selected_date_obj.strftime('%b %d, %Y')}). Shift hours can only be marked on or after the shift day."
            )
        else:
            messages.warning(
                request,
                f"Shift date ({selected_date_obj.strftime('%b %d, %Y')}) is outside event active duration ({event.start_date.strftime('%b %d, %Y')} – {event.end_date.strftime('%b %d, %Y')})."
            )
        return redirect(f"{request.path}?date={selected_date}&mode=view")

    try:
        sheet = AttendanceSheet.objects.get(
            committee=committee, date=selected_date_obj
        )
        sheet_status = sheet.get_status_display()
        raw_status = sheet.status
        feedback = sheet.feedback
        num_hours = sheet.num_hours
        sheet_exists = True
    except AttendanceSheet.DoesNotExist:
        sheet = None
        sheet_status = 'Not Submitted'
        raw_status = 'not_submitted'
        feedback = ''
        num_hours = 3
        sheet_exists = False

    # Only approved sheets are permanently locked. Pending/draft/sent_back sheets can be edited by faculty.
    is_locked = (raw_status == 'approved')
    is_editing = (mode == 'edit') and not is_locked and not is_future_date and not is_out_of_bounds

    # Get volunteers with their attendance records
    assigned_apps = VolunteerApplication.objects.filter(
        assigned_committee=committee, status='assigned'
    ).select_related('student__user')

    volunteers_data = []
    for app in assigned_apps:
        s = app.student
        hours = [False] * num_hours  # Default all absent
        total = 0

        if sheet:
            try:
                record = AttendanceRecord.objects.get(sheet=sheet, student=s)
                # Pad or trim hours list to match num_hours
                hours = (record.hours + [False] * num_hours)[:num_hours]
                total = sum(1 for h in hours if h)
            except AttendanceRecord.DoesNotExist:
                pass

        volunteers_data.append({
            'id': s.id,
            'name': s.user.get_full_name(),
            'class': s.class_batch,
            'hours': hours,
            'total_hours': total,
        })

    context = {
        'committee': {
            'id': committee.id,
            'name': committee.name,
            'event': event.name,
        },
        'event_dates': event_dates_list,
        'selected_date': selected_date,
        'sheet_status': sheet_status,
        'raw_status': raw_status,
        'sheet_exists': sheet_exists,
        'is_future_date': is_future_date,
        'is_out_of_bounds': is_out_of_bounds,
        'is_locked': is_locked,
        'is_editing': is_editing,
        'mode': mode,
        'feedback': feedback,
        'num_hours': num_hours,
        'hours_range': range(1, num_hours + 1),
        'volunteers': volunteers_data,
    }
    return render(request, 'volunteers/attendance.html', context)


@faculty_required
def committee_coordinators_view(request, pk):
    """View fellow committee coordinators of the same event."""
    committee = get_object_or_404(
        Committee.objects.select_related('event', 'faculty_head__user'),
        pk=pk
    )
    profile = request.user.profile
    if profile.role != 'dean' and not request.user.is_staff and committee.faculty_head != profile:
        messages.error(request, f"Access Denied: You are not assigned as the Faculty Head of the '{committee.name}' committee.")
        return redirect('events_committee:committee_dashboard')

    event = committee.event

    # All committees in this event with their faculty heads
    all_committees = Committee.objects.filter(
        event=event
    ).select_related('faculty_head__user')

    coordinators = []
    for c in all_committees:
        if c.faculty_head:
            coordinators.append({
                'name': c.faculty_head.user.get_full_name(),
                'committee': c.name,
                'phone': c.faculty_head.phone,
                'email': c.faculty_head.user.email,
                'role': 'Faculty Head',
                'is_me': (c.faculty_head == profile),
            })

    context = {
        'active_committee_id': pk,
        'committee': {
            'name': committee.name,
            'event': event.name,
        },
        'coordinators': coordinators,
    }
    return render(request, 'events/committee_coordinators.html', context)


@dean_required
def dean_committee_detail_view(request, pk):
    """Dean view of all volunteers and coordinators assigned to a specific committee."""
    committee = get_object_or_404(
        Committee.objects.select_related(
            'event', 'faculty_head__user', 'student_coordinator__user'
        ),
        pk=pk
    )

    if request.method == 'POST':
        student_coord_id = request.POST.get('student_coordinator')
        if student_coord_id:
            student_profile = UserProfile.objects.filter(id=student_coord_id, role='student').first()
            if student_profile:
                committee.student_coordinator = student_profile
                committee.save()
                messages.success(request, f"Assigned {student_profile.user.get_full_name()} as Student Lead for {committee.name}.")
        else:
            committee.student_coordinator = None
            committee.save()
            messages.info(request, f"Removed Student Lead for {committee.name}.")
        return redirect('events_dean:committee_detail', pk=pk)

    assigned_apps = VolunteerApplication.objects.filter(
        assigned_committee=committee,
        status='assigned'
    ).select_related('student__user')

    volunteers = []
    for app in assigned_apps:
        s = app.student
        volunteers.append({
            'id': s.id,
            'name': s.user.get_full_name(),
            'class': s.class_batch,
            'dept': s.department,
            'phone': s.phone,
            'email': s.user.email,
            'status': 'Active',
        })

    context = {
        'committee': {
            'id': committee.id,
            'name': committee.name,
            'event': committee.event.name,
            'faculty_head': (
                committee.faculty_head.user.get_full_name()
                if committee.faculty_head else 'Unassigned'
            ),
            'student_head': (
                committee.student_coordinator.user.get_full_name()
                if committee.student_coordinator else None
            ),
            'required': committee.required_volunteers,
            'assigned': committee.assigned_count,
        },
        'volunteers': volunteers,
    }
    return render(request, 'events/committee_detail.html', context)


@dean_required
def dean_approvals_view(request):
    """Dean view to manage and approve/reject volunteering hour sheets."""
    selected_event_id = request.GET.get('event_id', '')

    if request.method == 'POST':
        action = request.POST.get('action')
        sheet_id = request.POST.get('sheet_id')
        selected_date = request.GET.get('date', '')

        if sheet_id:
            try:
                sheet = AttendanceSheet.objects.get(id=sheet_id)
                if action == 'approve':
                    sheet.status = 'approved'
                    sheet.reviewed_by = request.user.profile
                    sheet.reviewed_at = timezone.now()
                    sheet.feedback = ''
                    sheet.save()
                    messages.success(request, f'Attendance sheet for {sheet.committee.name} ({_format_date(sheet.date)}) approved successfully. Hours credited!')
                elif action == 'send_back':
                    sheet.status = 'sent_back'
                    sheet.reviewed_by = request.user.profile
                    sheet.reviewed_at = timezone.now()
                    sheet.feedback = request.POST.get('feedback', '')
                    sheet.save()
                    messages.warning(request, f'Attendance sheet for {sheet.committee.name} ({_format_date(sheet.date)}) sent back with feedback.')
            except AttendanceSheet.DoesNotExist:
                messages.error(request, 'Sheet not found.')

        redirect_url = f"{request.path}?event_id={selected_event_id}"
        if selected_date:
            redirect_url += f"&date={selected_date}"
        return redirect(redirect_url)

    # GET: build pending approvals
    pending_sheets = AttendanceSheet.objects.filter(
        status='pending'
    ).select_related(
        'committee__event', 'submitted_by__user'
    ).order_by('-submitted_at')

    # Group by event for sidebar
    events_map = {}
    for sheet in pending_sheets:
        ev = sheet.committee.event
        if ev.id not in events_map:
            events_map[ev.id] = {
                'id': ev.id,
                'name': ev.name,
                'count': 0,
                'total_hours': 0.0,
                'student_count': 0,
            }
        events_map[ev.id]['count'] += 1
        events_map[ev.id]['total_hours'] += sheet.total_hours_logged
        events_map[ev.id]['student_count'] += sheet.student_count

    # Filter by selected event & date
    filtered_submissions = []
    selected_event_name = ''
    event_dates = []
    selected_date = ''

    if selected_event_id:
        selected_event = Event.objects.filter(id=selected_event_id).first()
        if selected_event:
            selected_event_name = selected_event.name
            event_dates = selected_event.event_dates
            raw_date = request.GET.get('date', event_dates[0] if event_dates else '')
            selected_date_obj, selected_date = _safe_parse_date(raw_date, selected_event.start_date)

            event_sheets = pending_sheets.filter(
                committee__event_id=selected_event_id
            )
            if selected_date_obj:
                event_sheets = event_sheets.filter(date=selected_date_obj)

            for sheet in event_sheets:
                records = AttendanceRecord.objects.filter(
                    sheet=sheet
                ).select_related('student__user')

                students = []
                for r in records:
                    present_hours = sum(1 for h in r.hours if h)
                    students.append({
                        'name': r.student.user.get_full_name(),
                        'class': r.student.class_batch,
                        'status': 'Present' if present_hours > 0 else 'Absent',
                        'hours': present_hours,
                    })

                filtered_submissions.append({
                    'id': sheet.id,
                    'event_id': sheet.committee.event.id,
                    'event_name': sheet.committee.event.name,
                    'committee_name': sheet.committee.name,
                    'duty_date': _format_date(sheet.date),
                    'coordinator': (
                        sheet.submitted_by.user.get_full_name()
                        if sheet.submitted_by else 'Unknown'
                    ),
                    'submitted_date': _format_date_short(sheet.submitted_at),
                    'student_count': sheet.student_count,
                    'total_hours': sheet.total_hours_logged,
                    'students': students,
                })

    context = {
        'events': list(events_map.values()),
        'selected_event_id': selected_event_id,
        'selected_event_name': selected_event_name,
        'event_dates': event_dates,
        'selected_date': selected_date,
        'pending_approvals': filtered_submissions,
    }
    return render(request, 'events/dean_approvals.html', context)
