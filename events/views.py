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
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, Value
from django.db.models.functions import Concat
from django.utils import timezone
from django.core.paginator import Paginator

from accounts.models import UserProfile, CourseConfig
from accounts.decorators import dean_required, faculty_required, student_required
from events.models import Event, Committee
from volunteers.models import VolunteerApplication, AttendanceSheet, AttendanceRecord


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


def _event_to_dict(event):
    """
    Convert an Event model instance to a template-compatible dict.
    Matches the exact key structure templates expect from the old DUMMY_EVENTS.
    """
    committees = []
    for c in event.committees.select_related('faculty_head__user', 'student_coordinator__user').all():
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
        })

    return {
        'id': event.id,
        'name': event.name,
        'description': event.description,
        'venue': event.venue,
        'start_date': _format_date(event.start_date),
        'end_date': _format_date(event.end_date),
        'registration_deadline': _format_date(event.registration_deadline),
        'max_volunteers': event.max_volunteers,
        'total_applications': event.total_applications,
        'assigned_volunteers': event.assigned_volunteers,
        'status': event.get_status_display(),
        'banner': event.banner if event.banner else None,
        'main_student_coordinator': (
            event.main_student_coordinator.user.get_full_name()
            if event.main_student_coordinator else None
        ),
        'committees': committees,
    }


# =============================================================================
# Dean views — /dean/ prefix
# =============================================================================

@dean_required
def dean_dashboard_view(request):
    """Dean's main dashboard with overview stats and recent activity."""
    all_events = Event.objects.all()

    # Stats
    total_events = all_events.count()
    active_events = all_events.filter(
        status__in=['open', 'upcoming', 'ongoing']
    ).count()
    total_volunteers = VolunteerApplication.objects.filter(
        status='assigned'
    ).count()
    pending_applications = VolunteerApplication.objects.filter(
        status='pending'
    ).count()
    total_committees = Committee.objects.count()
    total_hours = AttendanceRecord.objects.filter(
        sheet__status='approved'
    ).aggregate(total=Sum('total_hours'))['total'] or 0

    # Recent events (last 3 by start_date)
    recent_qs = all_events.prefetch_related(
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
            'total_volunteers': total_volunteers,
            'pending_applications': pending_applications,
            'total_committees': total_committees,
            'total_hours': total_hours,
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
    """Event creation form with committee setup."""
    if request.method == 'POST':
        max_v = request.POST.get('max_volunteers')
        max_volunteers = int(max_v) if max_v and max_v.strip() else 100

        # Create the event
        event = Event.objects.create(
            name=request.POST.get('name', ''),
            description=request.POST.get('description', ''),
            venue=request.POST.get('venue', ''),
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            registration_deadline=request.POST.get('registration_deadline'),
            max_volunteers=max_volunteers,
            status='open',
            allocation_mode=request.POST.get('allocation_mode', 'manual'),
            created_by=request.user,
        )

        # Handle banner upload
        if 'banner' in request.FILES:
            event.banner = request.FILES['banner']
            event.save()

        # Handle main student coordinator
        msc_id = request.POST.get('main_student_coordinator')
        if msc_id:
            try:
                event.main_student_coordinator = UserProfile.objects.get(id=msc_id)
                event.save()
            except UserProfile.DoesNotExist:
                pass

        # Create committees from the dynamic form
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
            # Assign faculty head
            if i < len(committee_heads) and committee_heads[i]:
                try:
                    committee.faculty_head = UserProfile.objects.get(id=committee_heads[i])
                    committee.save()
                except UserProfile.DoesNotExist:
                    pass
            # Assign student coordinator
            if i < len(committee_student_coords) and committee_student_coords[i]:
                try:
                    committee.student_coordinator = UserProfile.objects.get(id=committee_student_coords[i])
                    committee.save()
                except UserProfile.DoesNotExist:
                    pass

        messages.success(request, f'Event "{event.name}" created successfully!')
        return redirect('events_dean:event_detail', pk=event.id)

    # GET: show the form
    # Faculty members who can be committee heads
    faculty_profiles = UserProfile.objects.filter(
        role__in=['faculty', 'dean']
    ).select_related('user').order_by('user__first_name')
    committee_heads = [{'id': p.id, 'name': p.user.get_full_name()} for p in faculty_profiles]

    # Student profiles for coordinator selection
    student_profiles = UserProfile.objects.filter(
        role='student'
    ).select_related('user').order_by('user__first_name')
    students_pool = [{'id': p.id, 'name': p.user.get_full_name()} for p in student_profiles]

    context = {
        'is_edit': False,
        'committee_heads': committee_heads,
        'students_pool': students_pool,
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
    """Event edit form pre-filled with existing data."""
    event = get_object_or_404(Event, pk=pk)

    if request.method == 'POST':
        event.name = request.POST.get('name', event.name)
        event.description = request.POST.get('description', event.description)
        event.venue = request.POST.get('venue', event.venue)
        event.start_date = request.POST.get('start_date', event.start_date)
        event.end_date = request.POST.get('end_date', event.end_date)
        event.registration_deadline = request.POST.get('registration_deadline', event.registration_deadline)
        max_v = request.POST.get('max_volunteers')
        if max_v and max_v.strip():
            event.max_volunteers = int(max_v)
        event.allocation_mode = request.POST.get('allocation_mode', event.allocation_mode)

        if 'banner' in request.FILES:
            event.banner = request.FILES['banner']

        msc_id = request.POST.get('main_student_coordinator')
        if msc_id:
            try:
                event.main_student_coordinator = UserProfile.objects.get(id=msc_id)
            except UserProfile.DoesNotExist:
                pass
        else:
            event.main_student_coordinator = None

        event.save()
        messages.success(request, f'Event "{event.name}" updated successfully!')
        return redirect('events_dean:event_detail', pk=event.id)

    # GET: prefill the form
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
    }
    return render(request, 'events/event_form.html', context)


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
    total_events = Event.objects.count()
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
            'total_events': total_events,
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
    events_qs = Event.objects.filter(
        status__in=['open', 'upcoming']
    ).prefetch_related(
        'committees__faculty_head__user',
        'committees__student_coordinator__user',
    )
    events = [_event_to_dict(e) for e in events_qs]

    context = {
        'events': events,
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
        Committee.objects.select_related('event'),
        pk=pk
    )

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
        Committee.objects.select_related('event'),
        pk=pk
    )
    event = committee.event

    # Build event dates list
    event_dates_list = event.event_dates  # List of formatted date strings

    selected_date = request.GET.get('date', event_dates_list[0] if event_dates_list else '')

    # Parse selected_date back to a date object for DB lookup
    from datetime import datetime
    try:
        selected_date_obj = datetime.strptime(selected_date, '%B %d, %Y').date()
    except (ValueError, TypeError):
        selected_date_obj = event.start_date

    # Handle POST: save attendance data
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        num_hours_post = int(request.POST.get('num_hours', 3))

        # Get or create the attendance sheet
        sheet, created = AttendanceSheet.objects.get_or_create(
            committee=committee,
            date=selected_date_obj,
            defaults={'num_hours': num_hours_post}
        )

        if not created:
            sheet.num_hours = num_hours_post
            sheet.save()

        # Update attendance records for each volunteer
        assigned_apps = VolunteerApplication.objects.filter(
            assigned_committee=committee, status='assigned'
        ).select_related('student')

        for app in assigned_apps:
            hours_list = []
            for h in range(1, num_hours_post + 1):
                key = f'hour_{app.student.id}_{h}'
                hours_list.append(request.POST.get(key) == 'on')

            record, _ = AttendanceRecord.objects.update_or_create(
                sheet=sheet,
                student=app.student,
                defaults={'hours': hours_list}
            )

        if action == 'submit':
            sheet.status = 'pending'
            sheet.submitted_by = request.user.profile
            sheet.submitted_at = timezone.now()
            sheet.save()
            messages.success(request, 'Attendance sheet submitted for review.')
        else:
            messages.success(request, 'Attendance saved as draft.')

        return redirect(f"{request.path}?date={selected_date}")

    # GET: load existing sheet data
    try:
        sheet = AttendanceSheet.objects.get(
            committee=committee, date=selected_date_obj
        )
        sheet_status = sheet.get_status_display()
        feedback = sheet.feedback
        num_hours = sheet.num_hours
    except AttendanceSheet.DoesNotExist:
        sheet = None
        sheet_status = 'Not Submitted'
        feedback = ''
        num_hours = 3

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
            'name': committee.name,
            'event': event.name,
        },
        'event_dates': event_dates_list,
        'selected_date': selected_date,
        'sheet_status': sheet_status,
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
    event = committee.event
    profile = request.user.profile

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

        if sheet_id:
            try:
                sheet = AttendanceSheet.objects.get(id=sheet_id)
                if action == 'approve':
                    sheet.status = 'approved'
                    sheet.reviewed_by = request.user.profile
                    sheet.reviewed_at = timezone.now()
                    sheet.feedback = ''
                    sheet.save()
                    messages.success(request, f'Attendance sheet for {sheet.committee.name} approved.')
                elif action == 'send_back':
                    sheet.status = 'sent_back'
                    sheet.reviewed_by = request.user.profile
                    sheet.reviewed_at = timezone.now()
                    sheet.feedback = request.POST.get('feedback', '')
                    sheet.save()
                    messages.warning(request, f'Attendance sheet for {sheet.committee.name} sent back.')
            except AttendanceSheet.DoesNotExist:
                messages.error(request, 'Sheet not found.')

        return redirect(f"{request.path}?event_id={selected_event_id}")

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

    # Filter by selected event
    filtered_submissions = []
    selected_event_name = ''
    if selected_event_id:
        for sheet in pending_sheets.filter(committee__event_id=selected_event_id):
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
                'coordinator': (
                    sheet.submitted_by.user.get_full_name()
                    if sheet.submitted_by else 'Unknown'
                ),
                'submitted_date': _format_date_short(sheet.submitted_at),
                'student_count': sheet.student_count,
                'total_hours': sheet.total_hours_logged,
                'students': students,
            })
            selected_event_name = sheet.committee.event.name

    context = {
        'events': list(events_map.values()),
        'selected_event_id': selected_event_id,
        'selected_event_name': selected_event_name,
        'pending_approvals': filtered_submissions,
    }
    return render(request, 'events/dean_approvals.html', context)
