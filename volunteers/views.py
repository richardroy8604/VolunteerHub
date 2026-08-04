from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from accounts.models import UserProfile
from accounts.decorators import dean_required, student_required
from accounts.services import trigger_allocation_confirmed
from events.models import Event, Committee
from volunteers.models import VolunteerApplication, AttendanceSheet, AttendanceRecord

def get_ordinal(n):
    if not isinstance(n, int):
        return str(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}" + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

# =============================================================================
# Student views — /student/ prefix
# =============================================================================

@student_required
def student_dashboard_view(request):
    """Student's main dashboard with active assignments and stats."""
    profile = request.user.profile
    
    # Stats
    active_statuses = ['open', 'upcoming', 'ongoing']
    active_events = VolunteerApplication.objects.filter(
        student=profile,
        status='assigned',
        event__status__in=active_statuses
    ).count()
    
    total_applications = VolunteerApplication.objects.filter(student=profile).count()
    
    total_hours_agg = AttendanceRecord.objects.filter(
        student=profile,
        sheet__status='approved'
    ).aggregate(total=Sum('total_hours'))
    total_hours = total_hours_agg['total'] or 0
    
    pending_applications = VolunteerApplication.objects.filter(
        student=profile,
        status='pending'
    ).count()

    upcoming_events = Event.objects.filter(status__in=['open', 'upcoming']).count()

    target_hours = 30
    target_percentage = min(int((total_hours / target_hours) * 100), 100)

    stats = {
        'active_events': active_events,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'total_hours': total_hours,
        'upcoming_events': upcoming_events,
        'target_hours': target_hours,
        'target_percentage': target_percentage,
    }
    
    # Active assignments
    active_assignments_qs = VolunteerApplication.objects.filter(
        student=profile,
        status='assigned',
        event__status__in=active_statuses
    ).select_related('event', 'assigned_committee', 'assigned_committee__faculty_head', 'assigned_committee__faculty_head__user')
    
    active_assignments = []
    for app in active_assignments_qs:
        comm = app.assigned_committee
        coordinator_name = 'Unassigned'
        coordinator_phone = ''
        if comm and comm.faculty_head:
            coordinator_name = comm.faculty_head.user.get_full_name()
            coordinator_phone = getattr(comm.faculty_head, 'phone', '') or ''
            
        start_str = app.event.start_date.strftime('%b %d, %Y') if app.event.start_date else ''
        end_str = app.event.end_date.strftime('%b %d, %Y') if app.event.end_date else ''
        date_display = f"{start_str} - {end_str}" if (start_str and end_str and start_str != end_str) else start_str

        active_assignments.append({
            'event_name': app.event.name,
            'committee_name': comm.name if comm else 'Unassigned',
            'event_date': date_display,
            'event_time': 'Full Day' if app.event.venue else 'Campus Event',
            'status': 'Assigned',
            'event_id': app.event.id,
            'committee_id': comm.id if comm else None,
            'coordinator_name': coordinator_name,
            'coordinator_phone': coordinator_phone
        })
        
    # Recent events
    recent_events_qs = Event.objects.filter(
        status__in=['open', 'upcoming']
    ).order_by('start_date')[:3]
    
    recent_events = []
    for ev in recent_events_qs:
        recent_events.append({
            'id': ev.id,
            'name': ev.name,
            'date': ev.start_date.strftime('%b %d, %Y') if ev.start_date else '',
            'status': ev.dynamic_status_display,
            'raw_status': ev.dynamic_status,
        })
        
    context = {
        'stats': stats,
        'active_assignments': active_assignments,
        'recent_events': recent_events,
    }
    return render(request, 'dashboards/student_dashboard.html', context)


CANCELLATION_DEADLINE_DAYS = 2


@student_required
def my_applications_view(request):
    """List all volunteer applications submitted by the student and handle cancellations."""
    profile = request.user.profile

    if request.method == 'POST' and request.POST.get('action') == 'cancel_application':
        app_id = request.POST.get('application_id')
        reason = request.POST.get('reason', '').strip()

        app = get_object_or_404(VolunteerApplication, id=app_id, student=profile)

        # 2-day prior deadline rule check
        today = timezone.now().date()
        cutoff_date = app.event.registration_deadline - timedelta(days=CANCELLATION_DEADLINE_DAYS)

        if today > cutoff_date:
            messages.error(
                request,
                f"Cancellation closed. Registrations can only be cancelled at least "
                f"{CANCELLATION_DEADLINE_DAYS} days prior to the registration deadline "
                f"({app.event.registration_deadline.strftime('%b %d, %Y')})."
            )
            return redirect('volunteers_student:my_applications')

        if not reason:
            messages.error(request, "Please provide a reason for cancelling your registration.")
            return redirect('volunteers_student:my_applications')

        # Cancel application
        app.status = 'cancelled'
        app.cancellation_reason = reason
        app.cancelled_at = timezone.now()
        app.save()

        # Notify Faculty In-Charge
        faculty_profile = None
        if app.assigned_committee and app.assigned_committee.faculty_head:
            faculty_profile = app.assigned_committee.faculty_head
        elif app.preference_1 and app.preference_1.faculty_head:
            faculty_profile = app.preference_1.faculty_head
        elif app.event.created_by:
            faculty_profile = getattr(app.event.created_by, 'profile', None)

        if faculty_profile:
            from accounts.models import Notification
            Notification.objects.create(
                recipient=faculty_profile,
                title=f"Registration Cancelled: {profile.user.get_full_name()} — {app.event.name}",
                message=(
                    f"Student {profile.user.get_full_name()} ({profile.user.email}) has cancelled "
                    f"their registration for {app.event.name}.\n\n"
                    f"Reason: {reason}"
                )
            )

        messages.success(request, f'Registration for "{app.event.name}" cancelled successfully. The faculty in-charge has been notified.')
        return redirect('volunteers_student:my_applications')

    # GET: build application list with deadline status
    today = timezone.now().date()
    
    # Exclude cancelled applications for completed/past events and sort latest to oldest (-applied_at)
    apps_qs = VolunteerApplication.objects.filter(
        student=profile
    ).exclude(
        Q(status='cancelled') & (Q(event__end_date__lt=today) | Q(event__status='completed'))
    ).select_related(
        'event', 'preference_1', 'preference_2', 'preference_3', 
        'assigned_committee', 'assigned_committee__faculty_head__user'
    ).order_by('-applied_at')
    
    applications = []
    for app in apps_qs:
        comm = app.assigned_committee
        coordinator_name = ''
        coordinator_phone = ''
        if comm and comm.faculty_head:
            coordinator_name = comm.faculty_head.user.get_full_name()
            coordinator_phone = comm.faculty_head.phone
            
        cutoff_date = app.event.registration_deadline - timedelta(days=CANCELLATION_DEADLINE_DAYS)
        can_cancel = (today <= cutoff_date) and (app.status in ['pending', 'assigned'])
        
        applications.append({
            'id': app.id,
            'event': app.event.name,
            'pref1': app.preference_1.name if app.preference_1 else '-',
            'pref2': app.preference_2.name if app.preference_2 else '-',
            'pref3': app.preference_3.name if app.preference_3 else '-',
            'status': app.get_status_display(),
            'raw_status': app.status,
            'assigned_committee': comm.name if comm else None,
            'event_id': app.event.id,
            'committee_id': comm.id if comm else None,
            'coordinator': coordinator_name,
            'coordinator_phone': coordinator_phone,
            'date': app.applied_at.strftime('%b %d, %Y') if app.applied_at else '',
            'start_date': app.event.start_date.strftime('%b %d, %Y'),
            'end_date': app.event.end_date.strftime('%b %d, %Y'),
            'event_dates': f"{app.event.start_date.strftime('%b %d, %Y')} – {app.event.end_date.strftime('%b %d, %Y')}",
            'registration_deadline': app.event.registration_deadline.strftime('%b %d, %Y'),
            'can_cancel': can_cancel,
            'cutoff_date': cutoff_date.strftime('%b %d, %Y'),
            'cancellation_reason': app.cancellation_reason,
        })
        
    context = {
        'applications': applications,
        'cancellation_deadline_days': CANCELLATION_DEADLINE_DAYS,
    }
    return render(request, 'volunteers/my_applications.html', context)


@student_required
def my_volunteering_view(request):
    """View the student's complete volunteering history and hours."""
    profile = request.user.profile
    
    total_hours_agg = AttendanceRecord.objects.filter(
        student=profile,
        sheet__status='approved'
    ).aggregate(total=Sum('total_hours'))
    total_hours = total_hours_agg['total'] or 0
    
    # Query all events where student is assigned to a committee
    history_qs = VolunteerApplication.objects.filter(
        student=profile,
        status='assigned'
    ).select_related('event', 'assigned_committee')
    
    completed_events = sum(1 for app in history_qs if app.event.dynamic_status == 'completed')

    history = []
    for app in history_qs:
        committee = app.assigned_committee
        event = app.event

        # Calculate approved hours for this specific committee
        app_hours_agg = AttendanceRecord.objects.filter(
            student=profile,
            sheet__committee=committee,
            sheet__status='approved'
        ).aggregate(total=Sum('total_hours'))
        app_hours = app_hours_agg['total'] or 0
        
        # Calculate attendance percentage based on approved shift sheets
        total_sheets = AttendanceSheet.objects.filter(
            committee=committee,
            status='approved'
        ).count()
        
        if total_sheets > 0 and app_hours > 0:
            sheets_qs = AttendanceSheet.objects.filter(committee=committee, status='approved')
            max_possible = sum(s.num_hours for s in sheets_qs)
            attendance_percent = min(int((app_hours / max_possible) * 100), 100) if max_possible > 0 else 100
        elif app_hours > 0:
            attendance_percent = 100
        else:
            attendance_percent = 0

        # Build daily attendance breakdown
        daily_details = []
        max_hours = 0
        today = timezone.now().date()

        if committee:
            sheets = AttendanceSheet.objects.filter(committee=committee)
            sheets_by_date = {s.date: s for s in sheets}
            records = AttendanceRecord.objects.filter(sheet__committee=committee, student=profile).select_related('sheet')
            records_by_sheet_id = {r.sheet_id: r for r in records}

            current_date = event.start_date
            while current_date <= event.end_date:
                sheet = sheets_by_date.get(current_date)
                date_str = current_date.strftime('%b %d, %Y')
                is_future = (current_date > today)

                if is_future:
                    num_hours = sheet.num_hours if sheet else 0
                    if num_hours > max_hours:
                        max_hours = num_hours
                    hours_status = []
                    total_day_hours = 0
                    sheet_status = 'Future Shift'
                    raw_status = 'future_date'
                elif sheet:
                    num_hours = sheet.num_hours
                    if num_hours > max_hours:
                        max_hours = num_hours
                    
                    rec = records_by_sheet_id.get(sheet.id)
                    if rec:
                        hours_status = rec.hours  # List of booleans
                        total_day_hours = rec.total_hours
                    else:
                        hours_status = [False] * num_hours
                        total_day_hours = 0
                    
                    sheet_status = sheet.get_status_display()
                    raw_status = sheet.status
                else:
                    num_hours = 0
                    hours_status = []
                    total_day_hours = 0
                    sheet_status = 'No Shift Logged'
                    raw_status = 'no_sheet'

                daily_details.append({
                    'date_str': date_str,
                    'is_future': is_future,
                    'num_hours': num_hours,
                    'hours_status': hours_status,
                    'total_day_hours': total_day_hours,
                    'sheet_status': sheet_status,
                    'raw_status': raw_status,
                })
                current_date += timedelta(days=1)

            # Build cell matrix up to max_hours across all days
            for day in daily_details:
                hour_cells = []
                for h in range(1, max_hours + 1):
                    if day['is_future']:
                        if day['num_hours'] > 0 and h <= day['num_hours']:
                            hour_cells.append({'hour_num': h, 'type': 'future'})
                        elif day['num_hours'] == 0:
                            hour_cells.append({'hour_num': h, 'type': 'future'})
                        else:
                            hour_cells.append({'hour_num': h, 'type': 'no_work'})
                    elif h <= day['num_hours']:
                        is_pres = day['hours_status'][h - 1] if (h - 1) < len(day['hours_status']) else False
                        hour_cells.append({'hour_num': h, 'type': 'present' if is_pres else 'absent'})
                    else:
                        hour_cells.append({'hour_num': h, 'type': 'no_work'})
                day['hour_cells'] = hour_cells

        history.append({
            'id': app.id,
            'event': event.name,
            'committee': committee.name if committee else 'N/A',
            'dates': f"{event.start_date.strftime('%b %d, %Y')} – {event.end_date.strftime('%b %d, %Y')}",
            'hours': app_hours,
            'attendance': attendance_percent,
            'status': event.dynamic_status_display,
            'event_status': event.dynamic_status,
            'daily_details': daily_details,
            'max_hours': max_hours,
            'max_hours_range': list(range(1, max_hours + 1)),
        })
        
    context = {
        'total_hours': total_hours,
        'total_events': completed_events,
        'history': history,
    }
    return render(request, 'volunteers/my_volunteering.html', context)


@student_required
def student_committee_detail_view(request, pk):
    """Student's view of their assigned committee details, coordinator, and fellow committee mates."""
    committee = get_object_or_404(Committee.objects.select_related('event', 'faculty_head__user', 'student_coordinator__user'), pk=pk)
    profile = request.user.profile
    
    # Check if logged in user is in a leadership role for this committee or event
    is_lead = (
        (committee.student_coordinator == profile) or
        (committee.event.main_student_coordinator == profile) or
        profile.role in ['dean', 'faculty']
    )

    faculty_head_name = committee.faculty_head.user.get_full_name() if committee.faculty_head else ''
    faculty_phone = getattr(committee.faculty_head, 'phone', '') if committee.faculty_head else ''
    faculty_email = committee.faculty_head.user.email if committee.faculty_head else ''
    
    student_head_name = committee.student_coordinator.user.get_full_name() if committee.student_coordinator else ''
    student_head_phone = getattr(committee.student_coordinator, 'phone', '') if committee.student_coordinator else ''
    student_head_email = committee.student_coordinator.user.email if committee.student_coordinator else ''

    committee_dict = {
        'id': committee.id,
        'name': committee.name,
        'event': committee.event.name,
        'faculty_head': faculty_head_name,
        'faculty_phone': faculty_phone,
        'faculty_email': faculty_email,
        'student_head': student_head_name,
        'student_head_phone': student_head_phone,
        'student_head_email': student_head_email,
    }
    
    volunteers_qs = VolunteerApplication.objects.filter(
        assigned_committee=committee,
        status='assigned'
    ).select_related('student', 'student__user')
    
    volunteers = []
    for app in volunteers_qs:
        student = app.student
        phone_num = getattr(student, 'phone', '') or ''
        volunteers.append({
            'name': student.user.get_full_name(),
            'class': student.class_batch,
            'dept': student.department,
            'email': student.user.email,
            'phone': phone_num if (is_lead or student == profile) else '',
            'is_me': (student == profile)
        })
        
    context = {
        'committee': committee_dict,
        'volunteers': volunteers,
        'is_lead': is_lead,
    }
    return render(request, 'volunteers/student_committee_detail.html', context)


@student_required
def student_coordinators_collaboration_view(request):
    """Collaboration page for Student Leads (Main Event & Committee Student Leads)."""
    profile = request.user.profile
    
    # Find an active event where this student is coordinator
    event = Event.objects.filter(
        Q(status__in=['open', 'upcoming', 'ongoing']) & 
        (Q(main_student_coordinator=profile) | Q(committees__student_coordinator=profile))
    ).distinct().first()
    
    if not event:
        messages.error(request, "You are not a coordinator for any active events.")
        return redirect('volunteers_student:student_dashboard')
        
    is_main = (event.main_student_coordinator == profile)
    my_role = 'Main Student Coordinator' if is_main else 'Committee Student Lead'
    
    coordinators = []
    if event.main_student_coordinator:
        sc = event.main_student_coordinator
        coordinators.append({
            'name': sc.user.get_full_name(),
            'role': 'Main Student Coordinator',
            'committee': 'Overall Event Coordinator',
            'phone': sc.phone,
            'email': sc.user.email,
            'is_me': (sc == profile)
        })
        
    committees = event.committees.select_related('student_coordinator__user').exclude(student_coordinator__isnull=True)
    for comm in committees:
        sc = comm.student_coordinator
        coordinators.append({
            'name': sc.user.get_full_name(),
            'role': 'Committee Student Lead',
            'committee': comm.name,
            'phone': sc.phone,
            'email': sc.user.email,
            'is_me': (sc == profile)
        })
        
    context = {
        'event': {
            'name': event.name,
        },
        'my_role': my_role,
        'coordinators': coordinators,
    }
    return render(request, 'volunteers/student_coordinators_collaboration.html', context)


# =============================================================================
# Student apply view — used in /events/<id>/apply/
# =============================================================================

@student_required
def apply_view(request, event_id):
    """Volunteer application form with committee preference selection and timeline validation."""
    event = get_object_or_404(Event, id=event_id)
    profile = request.user.profile
    today = timezone.now().date()

    # Timeline validation check: Registration window boundary
    if today > event.registration_deadline or today >= event.start_date or event.dynamic_status != 'open':
        formatted_deadline = event.registration_deadline.strftime('%b %d, %Y')
        messages.error(
            request,
            f"Registration for '{event.name}' closed on {formatted_deadline}. Applications are no longer accepted."
        )
        return redirect('events:browse_events')

    # Check if already applied (excluding cancelled or rejected applications)
    existing_app = VolunteerApplication.objects.filter(student=profile, event=event).exclude(status__in=['cancelled', 'rejected']).first()
    if existing_app:
        messages.info(request, f"You have an active application for {event.name}.")
        return redirect('volunteers_student:my_applications')

    if request.method == 'POST':
        # Accept pref1 or preference_1
        pref1_id = request.POST.get('pref1') or request.POST.get('preference_1')
        pref2_id = request.POST.get('pref2') or request.POST.get('preference_2')
        pref3_id = request.POST.get('pref3') or request.POST.get('preference_3')

        pref1 = Committee.objects.filter(id=pref1_id, event=event).first() if pref1_id else None
        pref2 = Committee.objects.filter(id=pref2_id, event=event).first() if pref2_id else None
        pref3 = Committee.objects.filter(id=pref3_id, event=event).first() if pref3_id else None

        # Fallback: if only 1 committee exists in event, default to that committee
        event_committees = list(event.committees.all())
        if not pref1 and len(event_committees) > 0:
            pref1 = event_committees[0]

        # Re-activate cancelled or rejected application or create new one
        reopenable_app = VolunteerApplication.objects.filter(student=profile, event=event, status__in=['cancelled', 'rejected']).first()
        if reopenable_app:
            reopenable_app.preference_1 = pref1
            reopenable_app.preference_2 = pref2
            reopenable_app.preference_3 = pref3
            reopenable_app.experience = request.POST.get('experience', '')
            reopenable_app.skills = request.POST.get('skills', '')
            reopenable_app.status = 'pending'
            reopenable_app.cancellation_reason = None
            reopenable_app.cancelled_at = None
            reopenable_app.assigned_committee = None
            reopenable_app.save()
        else:
            VolunteerApplication.objects.create(
                student=profile,
                event=event,
                preference_1=pref1,
                preference_2=pref2,
                preference_3=pref3,
                experience=request.POST.get('experience', ''),
                skills=request.POST.get('skills', '')
            )

        messages.success(request, f"Successfully applied for {event.name}!")
        return redirect('volunteers_student:my_applications')
        
    event_dict = {
        'id': event.id,
        'name': event.name,
        'committees': [{'id': c.id, 'name': c.name} for c in event.committees.all()],
    }
    
    student_dict = {
        'name': profile.user.get_full_name(),
        'department': profile.department,
        'semester': f"{get_ordinal(profile.semester)} Semester" if profile.semester else '',
        'student_class': profile.class_batch,
        'email': profile.user.email,
        'phone': profile.phone,
    }
    
    context = {
        'event': event_dict,
        'student': student_dict,
    }
    return render(request, 'volunteers/apply.html', context)


# =============================================================================
# Dean views — /dean/events/ prefix (volunteer pool management)
# =============================================================================

def _generate_auto_allocation_draft(event_obj, reallocate_all=False, target_committee_ids=None):
    """
    Greedy Balanced Auto-Allocation Draft Generator.
    
    Principles:
    1. Buddy/Cohort System: Clusters students from the same class_batch (>=2) per committee.
    2. Preference Rank: Tries Pref 1, then Pref 2, then Pref 3.
    3. Balanced Class Diversity: Spreads distinct classes proportionally across committees.
    4. Exception Flagging: Flags single-classmate occurrences or class dominance.
    5. Advisory Preview: Zero database mutations until explicitly finalized.
    """
    committees_qs = event_obj.committees.all()
    if target_committee_ids:
        committees_qs = committees_qs.filter(id__in=target_committee_ids)
    committees = list(committees_qs)
    
    if reallocate_all:
        active_apps = list(VolunteerApplication.objects.filter(
            event=event_obj
        ).exclude(status__in=['rejected', 'cancelled']).select_related(
            'student', 'student__user', 'preference_1', 'preference_2', 'preference_3'
        ))
        committee_capacities = {c.id: c.required_volunteers for c in committees}
    else:
        active_apps = list(VolunteerApplication.objects.filter(
            event=event_obj, status='pending'
        ).select_related(
            'student', 'student__user', 'preference_1', 'preference_2', 'preference_3'
        ))
        committee_capacities = {c.id: max(0, c.required_volunteers - c.assigned_count) for c in committees}

    draft_assignments = {c.id: [] for c in committees}
    unassigned_apps = list(active_apps)

    class_groups = {}
    for app in unassigned_apps:
        cb = app.student.class_batch or "General"
        if cb not in class_groups:
            class_groups[cb] = []
        class_groups[cb].append(app)

    def remaining_slots(c_id):
        return committee_capacities[c_id] - len(draft_assignments[c_id])

    # Phase 1: Allocate Buddy Pairs (>= 2 from same class) matching Preference 1
    for cb, apps in class_groups.items():
        pref1_map = {}
        for app in apps:
            if app.preference_1:
                p1_id = app.preference_1.id
                if p1_id not in pref1_map:
                    pref1_map[p1_id] = []
                pref1_map[p1_id].append(app)

        for comm_id, candidate_apps in pref1_map.items():
            if comm_id in draft_assignments:
                while len(candidate_apps) >= 2 and remaining_slots(comm_id) >= 2:
                    pair = [candidate_apps.pop(0), candidate_apps.pop(0)]
                    for item in pair:
                        draft_assignments[comm_id].append({
                            'app': item,
                            'match_type': '1st Choice',
                            'match_badge_class': 'bg-success',
                            'is_buddy': True,
                        })
                        if item in unassigned_apps:
                            unassigned_apps.remove(item)

    # Phase 2: Allocate remaining Pref 1 candidates
    for c in committees:
        comm_id = c.id
        pref1_candidates = [a for a in unassigned_apps if a.preference_1_id == comm_id]
        for app in pref1_candidates:
            if remaining_slots(comm_id) > 0 and app in unassigned_apps:
                draft_assignments[comm_id].append({
                    'app': app,
                    'match_type': '1st Choice',
                    'match_badge_class': 'bg-success',
                    'is_buddy': False,
                })
                unassigned_apps.remove(app)

    # Phase 3: Allocate Pref 2 candidates
    for c in committees:
        comm_id = c.id
        pref2_candidates = [a for a in unassigned_apps if a.preference_2_id == comm_id]
        for app in pref2_candidates:
            if remaining_slots(comm_id) > 0 and app in unassigned_apps:
                draft_assignments[comm_id].append({
                    'app': app,
                    'match_type': '2nd Choice',
                    'match_badge_class': 'bg-info text-dark',
                    'is_buddy': False,
                })
                unassigned_apps.remove(app)

    # Phase 4: Allocate Pref 3 candidates
    for c in committees:
        comm_id = c.id
        pref3_candidates = [a for a in unassigned_apps if a.preference_3_id == comm_id]
        for app in pref3_candidates:
            if remaining_slots(comm_id) > 0 and app in unassigned_apps:
                draft_assignments[comm_id].append({
                    'app': app,
                    'match_type': '3rd Choice',
                    'match_badge_class': 'bg-warning text-dark',
                    'is_buddy': False,
                })
                unassigned_apps.remove(app)

    # Phase 5: General Pool Fill for remaining open slots
    for c in committees:
        comm_id = c.id
        while remaining_slots(comm_id) > 0 and unassigned_apps:
            app = unassigned_apps.pop(0)
            draft_assignments[comm_id].append({
                'app': app,
                'match_type': 'General Pool',
                'match_badge_class': 'bg-secondary',
                'is_buddy': False,
            })

    # Phase 6: Analyze Exceptions & Cohort Badging per Committee
    committee_draft_summaries = []
    total_draft_allocated = 0
    total_pref1_matches = 0
    total_buddy_paired = 0
    total_exceptions = 0

    for c in committees:
        comm_id = c.id
        assigned_items = draft_assignments[comm_id]
        total_draft_allocated += len(assigned_items)

        class_counts = {}
        for item in assigned_items:
            cb = item['app'].student.class_batch or "General"
            class_counts[cb] = class_counts.get(cb, 0) + 1
            if item['match_type'] == '1st Choice':
                total_pref1_matches += 1

        for item in assigned_items:
            cb = item['app'].student.class_batch or "General"
            if class_counts[cb] >= 2:
                item['is_buddy'] = True
                total_buddy_paired += 1
            else:
                item['is_buddy'] = False

        exceptions = []
        for cb, count in class_counts.items():
            if count == 1 and len(assigned_items) > 1:
                exceptions.append(f"Single classmate exception: Only 1 student from {cb} assigned.")
                total_exceptions += 1
            elif len(assigned_items) >= 4 and (count / len(assigned_items)) > 0.6:
                pct = int((count / len(assigned_items)) * 100)
                exceptions.append(f"High class concentration: {pct}% of members belong to {cb}.")

        classes_represented = len(class_counts)

        committee_draft_summaries.append({
            'committee_id': c.id,
            'committee_name': c.name,
            'required': c.required_volunteers,
            'draft_count': len(assigned_items),
            'classes_represented': classes_represented,
            'class_breakdown': [f"{count}x {cb}" for cb, count in class_counts.items()],
            'exceptions': exceptions,
            'members': assigned_items,
        })

    unassigned_names = [app.student.user.get_full_name() for app in unassigned_apps]
    unassigned_names_str = ", ".join(unassigned_names[:3]) + ("..." if len(unassigned_apps) > 3 else "")
    all_committees_full = (len(unassigned_apps) > 0 and sum(committee_capacities.values()) == 0)

    total_pending = len(active_apps)
    pref1_match_pct = int((total_pref1_matches / total_draft_allocated * 100)) if total_draft_allocated > 0 else 0
    buddy_pair_pct = int((total_buddy_paired / total_draft_allocated * 100)) if total_draft_allocated > 0 else 0

    return {
        'total_pending': total_pending,
        'total_draft_allocated': total_draft_allocated,
        'unassigned_remaining': len(unassigned_apps),
        'unassigned_names_str': unassigned_names_str,
        'all_committees_full': all_committees_full,
        'pref1_match_pct': pref1_match_pct,
        'buddy_pair_pct': buddy_pair_pct,
        'total_exceptions': total_exceptions,
        'committees': committee_draft_summaries,
        'unassigned_list': unassigned_apps,
    }


@dean_required
def auto_allocate_view(request, event_id):
    """Auto-allocate preview launcher — redirects to pool with auto_draft=1."""
    return redirect(f"/dean/events/{event_id}/volunteer-pool/?auto_draft=1")


@dean_required
def volunteer_pool_view(request, event_id):
    """Dean's view of all applications for an event with allocation controls and Draft Preview."""
    event_obj = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_auto_allocation_draft':
            # Auto-allocation draft plan resolves over-manning. Apply draft plan directly.
            updated_count = 0
            reallocated_app_ids = [k.replace('assign_', '') for k in request.POST.keys() if k.startswith('assign_')]
            if reallocated_app_ids:
                VolunteerApplication.objects.filter(event=event_obj, id__in=reallocated_app_ids).update(
                    assigned_committee=None,
                    status='pending'
                )
            for key, val in request.POST.items():
                if key.startswith('assign_'):
                    app_id = key.replace('assign_', '')
                    try:
                        app = VolunteerApplication.objects.get(id=app_id, event=event_obj)
                        if val and val not in ['rejected', '']:
                            comm = Committee.objects.filter(id=val, event=event_obj).first()
                            if comm:
                                app.assigned_committee = comm
                                app.status = 'assigned'
                                app.save()
                                trigger_allocation_confirmed(app)
                                updated_count += 1
                    except VolunteerApplication.DoesNotExist:
                        pass

            messages.success(request, f"Successfully saved and finalized Auto-Allocation Plan ({updated_count} assignments updated, over-manning resolved!).")
            return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

        elif action == 'save_allocations':
            updated_count = 0
            
            # Build proposed assignments map from POST parameters
            proposed_changes = {}
            for key, val in request.POST.items():
                if key.startswith('assign_'):
                    app_id = key.replace('assign_', '')
                    proposed_changes[app_id] = val

            # Calculate proposed resulting counts from zero to avoid double-counting unchanged assignments
            committee_counts = {c.id: 0 for c in event_obj.committees.all()}
            committee_objs = {c.id: c for c in event_obj.committees.all()}
            all_event_apps = VolunteerApplication.objects.filter(event=event_obj)

            for app in all_event_apps:
                str_id = str(app.id)
                target_val = proposed_changes.get(str_id, str(app.assigned_committee_id) if app.assigned_committee_id else '')
                if target_val and target_val not in ['rejected', '']:
                    try:
                        cid = int(target_val)
                        if cid in committee_counts:
                            committee_counts[cid] += 1
                    except (ValueError, KeyError):
                        pass

            full_violations = set()
            for cid, count in committee_counts.items():
                comm_obj = committee_objs[cid]
                if count > comm_obj.required_volunteers:
                    full_violations.add(f"{comm_obj.name} ({count}/{comm_obj.required_volunteers})")

            if full_violations:
                messages.error(
                    request, 
                    f"⛔ Save Blocked: The following committee(s) would exceed their volunteer capacity: {', '.join(full_violations)}. "
                    f"Please unassign some students or adjust committee capacity before saving."
                )
                return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

            # Proceed to save valid manual assignments
            for app_id, val in proposed_changes.items():
                try:
                    app = VolunteerApplication.objects.get(id=app_id, event=event_obj)
                    if val == 'rejected':
                        if app.status != 'rejected' or app.assigned_committee is not None:
                            app.assigned_committee = None
                            app.status = 'rejected'
                            app.save()
                            updated_count += 1
                    elif not val:  # unassigned
                        if app.status != 'pending' or app.assigned_committee is not None:
                            app.assigned_committee = None
                            app.status = 'pending'
                            app.save()
                            updated_count += 1
                    else:  # specific committee id
                        comm = Committee.objects.filter(id=val, event=event_obj).first()
                        if comm and (app.assigned_committee != comm or app.status != 'assigned'):
                            app.assigned_committee = comm
                            app.status = 'assigned'
                            app.save()
                            trigger_allocation_confirmed(app)
                            updated_count += 1
                except VolunteerApplication.DoesNotExist:
                    pass
            
            messages.success(request, f"Successfully finalized and saved volunteer allocations ({updated_count} assignments updated).")
            return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

        elif action == 'assign_single' or (request.POST.get('application_id') and not action):
            app_id = request.POST.get('application_id')
            comm_id = request.POST.get('committee_id')
            app = get_object_or_404(VolunteerApplication, id=app_id, event=event_obj)
            was_assigned = (app.status == 'assigned')
            prev_comm_name = app.assigned_committee.name if app.assigned_committee else ''
            
            if comm_id == 'rejected':
                app.assigned_committee = None
                app.status = 'rejected'
                app.save()
                msg = f"Marked {app.student.user.get_full_name()} as Rejected / Waitlisted."
                if was_assigned:
                    msg += f" (Removed from active committee '{prev_comm_name}')."
                messages.warning(request, msg) if was_assigned else messages.success(request, msg)
            elif not comm_id:
                app.assigned_committee = None
                app.status = 'pending'
                app.save()
                msg = f"Unassigned {app.student.user.get_full_name()}."
                if was_assigned:
                    msg += f" (Removed from active committee '{prev_comm_name}')."
                messages.warning(request, msg) if was_assigned else messages.success(request, msg)
            else:
                comm = get_object_or_404(Committee, id=comm_id, event=event_obj)
                if app.assigned_committee != comm:
                    if comm.assigned_count >= comm.required_volunteers:
                        messages.error(
                            request, 
                            f"⛔ Assignment Failed: '{comm.name}' is FULL ({comm.assigned_count}/{comm.required_volunteers} slots filled). Over-allocation is blocked."
                        )
                        return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

                app.assigned_committee = comm
                app.status = 'assigned'
                app.save()
                trigger_allocation_confirmed(app)
                messages.success(request, f"Assigned {app.student.user.get_full_name()} to {comm.name}.")

        elif action == 'bulk_assign':
            app_ids = request.POST.getlist('application_ids[]') or request.POST.getlist('application_ids')
            comm_id = request.POST.get('committee_id')
            if app_ids and comm_id:
                comm = get_object_or_404(Committee, id=comm_id, event=event_obj)
                apps_to_assign = VolunteerApplication.objects.filter(id__in=app_ids, event=event_obj).exclude(assigned_committee=comm)
                new_add_count = apps_to_assign.count()
                available_slots = max(0, comm.required_volunteers - comm.assigned_count)
                
                if new_add_count > available_slots:
                    messages.error(
                        request, 
                        f"⛔ Bulk Assignment Blocked: '{comm.name}' has only {available_slots} slot(s) available "
                        f"({comm.assigned_count}/{comm.required_volunteers} filled), but you selected {new_add_count} volunteer(s)."
                    )
                    return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

                updated = VolunteerApplication.objects.filter(id__in=app_ids, event=event_obj).update(
                    assigned_committee=comm,
                    status='assigned'
                )
                messages.success(request, f"Successfully assigned {updated} volunteers to {comm.name}.")
            elif not comm_id:
                messages.error(request, "Please select a committee for bulk assignment.")

        elif action == 'bulk_reject':
            app_ids = request.POST.getlist('application_ids[]') or request.POST.getlist('application_ids')
            if app_ids:
                assigned_count = VolunteerApplication.objects.filter(id__in=app_ids, event=event_obj, status='assigned').count()
                updated = VolunteerApplication.objects.filter(id__in=app_ids, event=event_obj).update(
                    assigned_committee=None,
                    status='rejected'
                )
                if assigned_count > 0:
                    messages.warning(request, f"Marked {updated} volunteers as Rejected / Waitlisted. (⚠️ {assigned_count} volunteer(s) were removed from active committees).")
                else:
                    messages.success(request, f"Marked {updated} volunteers as Rejected / Waitlisted.")

        return redirect('volunteers_dean:volunteer_pool', event_id=event_id)
        
    committees_data = []
    has_overmanned = False
    for c in event_obj.committees.all():
        is_overmanned = (c.assigned_count > c.required_volunteers)
        if is_overmanned:
            has_overmanned = True
        committees_data.append({
            'id': c.id,
            'name': c.name,
            'required': c.required_volunteers,
            'assigned': c.assigned_count,
            'is_overmanned': is_overmanned,
            'surplus': c.assigned_count - c.required_volunteers if is_overmanned else 0,
        })
        
    event_dict = {
        'id': event_obj.id,
        'name': event_obj.name,
        'committees': committees_data,
    }
    
    apps_qs = VolunteerApplication.objects.filter(event=event_obj).select_related(
        'student', 'student__user', 'preference_1', 'preference_2', 'preference_3', 'assigned_committee'
    ).order_by('-applied_at')
    
    total_apps = apps_qs.count()
    assigned_count = apps_qs.filter(status='assigned').count()
    pending_count = apps_qs.filter(status='pending').count()
    rejected_count = apps_qs.filter(status__in=['rejected', 'waitlisted']).count()

    pool_stats = {
        'total': total_apps,
        'assigned': assigned_count,
        'pending': pending_count,
        'rejected': rejected_count,
    }
    
    # Check if Draft Preview is requested
    is_auto_draft = (request.GET.get('auto_draft') == '1')
    draft_plan = None
    draft_map = {}
    draft_comm_names = {}
    if is_auto_draft:
        reallocate_all = (request.GET.get('reallocate_all') == '1')
        raw_target_ids = request.GET.getlist('target_committees[]') or request.GET.getlist('target_committees')
        target_comm_ids = [int(cid) for cid in raw_target_ids if cid.isdigit()]
        draft_plan = _generate_auto_allocation_draft(event_obj, reallocate_all=reallocate_all, target_committee_ids=target_comm_ids)
        for comm in draft_plan['committees']:
            for item in comm['members']:
                app_obj = item['app']
                draft_map[app_obj.id] = comm['committee_id']
                draft_comm_names[app_obj.id] = comm['committee_name']

    applications = []
    for app in apps_qs:
        d_id = draft_map.get(app.id, None)
        d_name = draft_comm_names.get(app.id, None)
        applications.append({
            'id': app.id,
            'student': app.student.user.get_full_name(),
            'class': app.student.class_batch,
            'dept': app.student.department,
            'pref1': app.preference_1.name if app.preference_1 else '-',
            'pref2': app.preference_2.name if app.preference_2 else '-',
            'pref3': app.preference_3.name if app.preference_3 else '-',
            'status': 'Draft Allocated' if (is_auto_draft and d_name) else app.get_status_display(),
            'raw_status': 'assigned' if (is_auto_draft and d_name) else app.status,
            'assigned': app.assigned_committee.name if app.assigned_committee else None,
            'assigned_id': app.assigned_committee.id if app.assigned_committee else None,
            'draft_assigned_id': d_id,
            'draft_assigned_name': d_name,
        })
        
    is_registration_open = (timezone.now().date() <= event_obj.registration_deadline)
    registration_deadline_str = event_obj.registration_deadline.strftime('%b %d, %Y')

    context = {
        'event': event_dict,
        'applications': applications,
        'pool_stats': pool_stats,
        'is_registration_open': is_registration_open,
        'registration_deadline': registration_deadline_str,
        'has_overmanned': has_overmanned,
        'is_auto_draft': is_auto_draft,
        'draft_plan': draft_plan,
    }
    return render(request, 'volunteers/volunteer_pool.html', context)
