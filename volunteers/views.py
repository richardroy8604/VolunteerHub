from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from accounts.models import UserProfile
from accounts.decorators import dean_required, student_required
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
        coordinator_name = ''
        coordinator_phone = ''
        if comm and comm.faculty_head:
            coordinator_name = comm.faculty_head.user.get_full_name()
            coordinator_phone = comm.faculty_head.phone
            
        active_assignments.append({
            'event': app.event.name,
            'committee': comm.name if comm else 'Pending Assignment',
            'date': app.event.event_dates,
            'status': app.get_status_display(),
            'event_id': app.event.id,
            'committee_id': comm.id if comm else None,
            'coordinator': coordinator_name,
            'coordinator_phone': coordinator_phone
        })
        
    # Recent events
    recent_events_qs = Event.objects.filter(
        status__in=['open', 'upcoming']
    ).order_by('start_date')[:3]
    
    recent_events = []
    for ev in recent_events_qs:
        recent_events.append({
            'name': ev.name,
            'date': ev.start_date.strftime('%b %d, %Y') if ev.start_date else '',
            'status': ev.get_status_display()
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
        # Calculate approved hours for this specific committee
        app_hours_agg = AttendanceRecord.objects.filter(
            student=profile,
            sheet__committee=app.assigned_committee,
            sheet__status='approved'
        ).aggregate(total=Sum('total_hours'))
        app_hours = app_hours_agg['total'] or 0
        
        # Calculate attendance percentage based on approved shift sheets
        total_sheets = AttendanceSheet.objects.filter(
            committee=app.assigned_committee,
            status='approved'
        ).count()
        
        if total_sheets > 0 and app_hours > 0:
            sheets_qs = AttendanceSheet.objects.filter(committee=app.assigned_committee, status='approved')
            max_possible = sum(s.num_hours for s in sheets_qs)
            attendance_percent = min(int((app_hours / max_possible) * 100), 100) if max_possible > 0 else 100
        elif app_hours > 0:
            attendance_percent = 100
        else:
            attendance_percent = 0
            
        history.append({
            'event': app.event.name,
            'committee': app.assigned_committee.name if app.assigned_committee else 'N/A',
            'dates': app.event.event_dates,
            'hours': app_hours,
            'attendance': attendance_percent,
            'status': app.event.dynamic_status_display,
            'event_status': app.event.dynamic_status,
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
    
    faculty_head_name = committee.faculty_head.user.get_full_name() if committee.faculty_head else ''
    faculty_phone = committee.faculty_head.phone if committee.faculty_head else ''
    faculty_email = committee.faculty_head.user.email if committee.faculty_head else ''
    
    student_head_name = committee.student_coordinator.user.get_full_name() if committee.student_coordinator else ''
    
    committee_dict = {
        'id': committee.id,
        'name': committee.name,
        'event': committee.event.name,
        'faculty_head': faculty_head_name,
        'faculty_phone': faculty_phone,
        'faculty_email': faculty_email,
        'student_head': student_head_name
    }
    
    volunteers_qs = VolunteerApplication.objects.filter(
        assigned_committee=committee,
        status='assigned'
    ).select_related('student', 'student__user')
    
    volunteers = []
    for app in volunteers_qs:
        student = app.student
        volunteers.append({
            'name': student.user.get_full_name(),
            'class': student.class_batch,
            'dept': student.department,
            'email': student.user.email,
            'is_me': (student == request.user.profile)
        })
        
    context = {
        'committee': committee_dict,
        'volunteers': volunteers,
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
        return redirect('volunteers_student:available_events')

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

@dean_required
def volunteer_pool_view(request, event_id):
    """Dean's view of all applications for an event with allocation controls."""
    event_obj = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_allocations':
            updated_count = 0
            for key, val in request.POST.items():
                if key.startswith('assign_'):
                    app_id = key.replace('assign_', '')
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
                                updated_count += 1
                    except VolunteerApplication.DoesNotExist:
                        pass
            
            messages.success(request, f"Successfully saved volunteer allocations ({updated_count} changes updated).")
            return redirect('volunteers_dean:volunteer_pool', event_id=event_id)

        elif action == 'assign_single' or (request.POST.get('application_id') and not action):
            app_id = request.POST.get('application_id')
            comm_id = request.POST.get('committee_id')
            app = get_object_or_404(VolunteerApplication, id=app_id, event=event_obj)
            
            if comm_id == 'rejected':
                app.assigned_committee = None
                app.status = 'rejected'
                app.save()
                messages.success(request, f"Marked {app.student.user.get_full_name()} as Rejected / Waitlisted.")
            elif not comm_id:
                app.assigned_committee = None
                app.status = 'pending'
                app.save()
                messages.success(request, f"Unassigned {app.student.user.get_full_name()}.")
            else:
                comm = get_object_or_404(Committee, id=comm_id, event=event_obj)
                app.assigned_committee = comm
                app.status = 'assigned'
                app.save()
                messages.success(request, f"Assigned {app.student.user.get_full_name()} to {comm.name}.")

        elif action == 'bulk_assign':
            app_ids = request.POST.getlist('application_ids[]') or request.POST.getlist('application_ids')
            comm_id = request.POST.get('committee_id')
            if app_ids and comm_id:
                comm = get_object_or_404(Committee, id=comm_id, event=event_obj)
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
                updated = VolunteerApplication.objects.filter(id__in=app_ids, event=event_obj).update(
                    assigned_committee=None,
                    status='rejected'
                )
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
    
    applications = []
    for app in apps_qs:
        applications.append({
            'id': app.id,
            'student': app.student.user.get_full_name(),
            'class': app.student.class_batch,
            'dept': app.student.department,
            'pref1': app.preference_1.name if app.preference_1 else '-',
            'pref2': app.preference_2.name if app.preference_2 else '-',
            'pref3': app.preference_3.name if app.preference_3 else '-',
            'status': app.get_status_display(),
            'raw_status': app.status,
            'assigned': app.assigned_committee.name if app.assigned_committee else None,
            'assigned_id': app.assigned_committee.id if app.assigned_committee else None,
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
    }
    return render(request, 'volunteers/volunteer_pool.html', context)


@dean_required
def auto_allocate_view(request, event_id):
    """Auto-allocate volunteers to committees based on preferences and open slots."""
    event = get_object_or_404(Event, id=event_id)
    
    pending_apps = VolunteerApplication.objects.filter(
        event=event,
        status='pending'
    ).order_by('applied_at')
    
    allocated_count = 0
    for app in pending_apps:
        assigned = False
        for pref in [app.preference_1, app.preference_2, app.preference_3]:
            if pref and pref.open_slots > 0:
                app.assigned_committee = pref
                app.status = 'assigned'
                app.save()
                assigned = True
                allocated_count += 1
                break
                
    if allocated_count > 0:
        messages.success(request, f"Successfully auto-allocated {allocated_count} volunteers.")
    else:
        messages.info(request, "No pending applications could be auto-allocated (either no open slots or no preferences).")
        
    return redirect('volunteers_dean:volunteer_pool', event_id=event_id)
