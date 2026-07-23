from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
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
    
    upcoming_events = Event.objects.filter(status__in=['open', 'upcoming']).count()
    
    stats = {
        'active_events': active_events,
        'total_applications': total_applications,
        'total_hours': total_hours,
        'upcoming_events': upcoming_events,
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


@student_required
def my_applications_view(request):
    """List all volunteer applications submitted by the student."""
    profile = request.user.profile
    apps_qs = VolunteerApplication.objects.filter(student=profile).select_related(
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
            
        applications.append({
            'id': app.id,
            'event': app.event.name,
            'pref1': app.preference_1.name if app.preference_1 else '-',
            'pref2': app.preference_2.name if app.preference_2 else '-',
            'pref3': app.preference_3.name if app.preference_3 else '-',
            'status': app.get_status_display(),
            'assigned_committee': comm.name if comm else None,
            'event_id': app.event.id,
            'committee_id': comm.id if comm else None,
            'coordinator': coordinator_name,
            'coordinator_phone': coordinator_phone,
            'date': app.applied_at.strftime('%b %d, %Y') if app.applied_at else ''
        })
        
    context = {
        'applications': applications,
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
    
    history_qs = VolunteerApplication.objects.filter(
        student=profile,
        status='assigned',
        event__status='completed'
    ).select_related('event', 'assigned_committee')
    
    total_events = history_qs.count()
    
    history = []
    for app in history_qs:
        # Calculate hours for this specific committee
        app_hours = AttendanceRecord.objects.filter(
            student=profile,
            sheet__committee=app.assigned_committee,
            sheet__status='approved'
        ).aggregate(total=Sum('total_hours'))['total'] or 0
        
        attendance_percent = 100 if app_hours > 0 else 0
        
        history.append({
            'event': app.event.name,
            'committee': app.assigned_committee.name if app.assigned_committee else '',
            'dates': app.event.event_dates,
            'hours': app_hours,
            'attendance': attendance_percent,
            'status': app.event.get_status_display()
        })
        
    context = {
        'total_hours': total_hours,
        'total_events': total_events,
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
        (Q(main_student_coordinator=profile) | Q(committee__student_coordinator=profile))
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
    """Volunteer application form with committee preference selection."""
    event = get_object_or_404(Event, id=event_id)
    profile = request.user.profile
    
    if request.method == 'POST':
        # Create application
        pref1_id = request.POST.get('preference_1')
        pref2_id = request.POST.get('preference_2')
        pref3_id = request.POST.get('preference_3')
        
        pref1 = Committee.objects.filter(id=pref1_id).first() if pref1_id else None
        pref2 = Committee.objects.filter(id=pref2_id).first() if pref2_id else None
        pref3 = Committee.objects.filter(id=pref3_id).first() if pref3_id else None
        
        VolunteerApplication.objects.create(
            student=profile,
            event=event,
            preference_1=pref1,
            preference_2=pref2,
            preference_3=pref3,
            experience=request.POST.get('experience', ''),
            skills=request.POST.get('skills', '')
        )
        
        messages.success(request, f"Successfully applied for {event.name}.")
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
        app_id = request.POST.get('application_id')
        committee_id = request.POST.get('committee_id')
        if app_id and committee_id:
            app = get_object_or_404(VolunteerApplication, id=app_id, event=event_obj)
            comm = get_object_or_404(Committee, id=committee_id, event=event_obj)
            app.assigned_committee = comm
            app.status = 'assigned'
            app.save()
            messages.success(request, f"Assigned {app.student.user.get_full_name()} to {comm.name}.")
        return redirect('volunteers_dean:volunteer_pool', event_id=event_id)
        
    committees_data = []
    for c in event_obj.committees.all():
        committees_data.append({
            'id': c.id,
            'name': c.name,
            'required': c.required_volunteers,
            'assigned': c.assigned_count,
        })
        
    event_dict = {
        'id': event_obj.id,
        'name': event_obj.name,
        'committees': committees_data,
    }
    
    apps_qs = VolunteerApplication.objects.filter(event=event_obj).select_related(
        'student', 'student__user', 'preference_1', 'preference_2', 'preference_3', 'assigned_committee'
    )
    
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
            'assigned': app.assigned_committee.name if app.assigned_committee else None
        })
        
    context = {
        'event': event_dict,
        'applications': applications,
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
