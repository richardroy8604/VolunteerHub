"""
Notification Services & Dispatcher Module for VolunteerHub.

100% Decoupled & Fail-Safe:
All notification helper methods are wrapped in safe exception handling
so notification dispatching NEVER breaks or interrupts core operations.
"""

import logging
from django.db import transaction
from django.utils import timezone
from accounts.models import UserProfile, Notification
from events.models import Event, Committee
from volunteers.models import VolunteerApplication, AttendanceSheet

logger = logging.getLogger(__name__)


def notify_user(recipient, title, message, notification_type='system', link_url='', event=None, committee=None):
    """
    Safely dispatch or aggregate an in-system notification for a single user.
    Anti-Spam Grouping: If an unread notification of the same type & context exists,
    it increments its count and updates the message instead of creating duplicates.
    """
    if not recipient or not isinstance(recipient, UserProfile):
        return None

    try:
        # Determine role-appropriate link URL (Broadcasts have no link)
        target_link = link_url
        if notification_type == 'broadcast':
            target_link = ""
        elif event and (not link_url or '/dean/events/' in link_url):
            if recipient.role == 'dean':
                target_link = f"/dean/events/{event.id}/"
            elif recipient.role == 'faculty':
                target_link = f"/committee/dashboard/"
            elif recipient.role == 'student':
                target_link = f"/student/dashboard/"
            else:
                target_link = f"/events/{event.id}/"

        # Check for existing unread notification to aggregate (Do NOT aggregate broadcasts)
        existing = None
        if notification_type != 'broadcast':
            existing = Notification.objects.filter(
                recipient=recipient,
                notification_type=notification_type,
                event=event,
                committee=committee,
                is_read=False
            ).first()

        if existing:
            existing.count += 1
            existing.title = title
            existing.message = message
            if target_link:
                existing.link_url = target_link
            existing.save()
            return existing
        else:
            return Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                link_url=target_link,
                event=event,
                committee=committee,
                count=1,
                is_read=False
            )
    except Exception as e:
        logger.warning(f"Notification dispatch error for {recipient}: {e}")
        return None


def notify_group(recipients_qs, title, message, notification_type='system', link_url='', event=None, committee=None):
    """
    Dispatch notifications to a queryset or list of UserProfiles.
    """
    if not recipients_qs:
        return 0
    count = 0
    for profile in recipients_qs:
        if profile and isinstance(profile, UserProfile):
            res = notify_user(
                recipient=profile,
                title=title,
                message=message,
                notification_type=notification_type,
                link_url=link_url,
                event=event,
                committee=committee
            )
            if res:
                count += 1
    return count


def broadcast_announcement(dean_profile, scope, title, message, event_id=None, target_committee_ids=None):
    """
    Dean-only broadcast announcement dispatcher with 3 targeting scopes:
    1. 'system': Broadcast to all active users (Faculty & Students).
    2. 'event': Broadcast to all participants (Faculty Heads & Students) in an event.
    3. 'committee': Broadcast to members of selected committee IDs (multi-committee selection).
    """
    try:
        recipients = set()
        event_obj = None

        if event_id:
            event_obj = Event.objects.filter(id=event_id).first()

        if scope == 'system':
            # All active users except Dean sending it
            profiles = UserProfile.objects.filter(user__is_active=True).exclude(id=dean_profile.id)
            recipients.update(profiles)

        elif scope == 'event' and event_obj:
            # Faculty heads of committees in this event
            fac_heads = UserProfile.objects.filter(headed_committees__event=event_obj).distinct()
            recipients.update(fac_heads)
            # Assigned students in this event
            student_apps = VolunteerApplication.objects.filter(
                event=event_obj, status='assigned'
            ).select_related('student')
            for app in student_apps:
                recipients.add(app.student)

        elif scope == 'committee' and target_committee_ids:
            # Multi-committee scope
            target_comms = Committee.objects.filter(id__in=target_committee_ids)
            for comm in target_comms:
                if comm.faculty_head:
                    recipients.add(comm.faculty_head)
                if comm.student_coordinator:
                    recipients.add(comm.student_coordinator)
            # Assigned students in these committees
            student_apps = VolunteerApplication.objects.filter(
                assigned_committee_id__in=target_committee_ids, status='assigned'
            ).select_related('student')
            for app in student_apps:
                recipients.add(app.student)

        # Exclude sender from receiving broadcast
        recipients.discard(dean_profile)

        return notify_group(
            recipients_qs=list(recipients),
            title=f"📢 Announcement: {title}",
            message=message,
            notification_type='broadcast',
            link_url="",
            event=event_obj
        )
    except Exception as e:
        logger.warning(f"Broadcast announcement error: {e}")
        return 0


# --- Specific Event Triggers ---

def trigger_attendance_submitted(sheet):
    """Fired when a Faculty Coordinator submits an attendance sheet for Dean review."""
    try:
        dean_profiles = UserProfile.objects.filter(role='dean', user__is_active=True)
        date_str = sheet.date.strftime('%b %d, %Y') if sheet.date else ''
        title = f"Hours Sheet Submitted: {sheet.committee.name}"
        message = f"Faculty Coordinator {sheet.submitted_by.user.get_full_name() if sheet.submitted_by else 'Staff'} submitted hours sheet for {sheet.committee.name} ({date_str})."
        link_url = f"/dean/approvals/?event_id={sheet.committee.event.id}&date={sheet.date.strftime('%Y-%m-%d')}"
        notify_group(dean_profiles, title, message, 'attendance', link_url, event=sheet.committee.event, committee=sheet.committee)
    except Exception as e:
        logger.warning(f"trigger_attendance_submitted error: {e}")


def trigger_attendance_approved(sheet):
    """Fired when the Dean approves an attendance sheet."""
    try:
        date_str = sheet.date.strftime('%b %d, %Y') if sheet.date else ''
        # Notify Faculty Coordinator
        if sheet.submitted_by:
            notify_user(
                recipient=sheet.submitted_by,
                title=f"Hours Sheet Approved! ({sheet.committee.name})",
                message=f"Dean approved hours sheet for {sheet.committee.name} on {date_str}. Volunteering hours credited to students!",
                notification_type='approval',
                link_url=f"/committee/attendance/?date={date_str}",
                event=sheet.committee.event,
                committee=sheet.committee
            )
        # Notify Assigned Students credited
        from volunteers.models import AttendanceRecord
        records = AttendanceRecord.objects.filter(sheet=sheet).select_related('student')
        for r in records:
            hours_count = sum(1 for h in r.hours if h)
            if hours_count > 0:
                notify_user(
                    recipient=r.student,
                    title=f"Volunteering Hours Credited! ({hours_count} hrs)",
                    message=f"{hours_count} hours credited for your service in {sheet.committee.name} on {date_str}.",
                    notification_type='approval',
                    link_url="/student/dashboard/",
                    event=sheet.committee.event,
                    committee=sheet.committee
                )
    except Exception as e:
        logger.warning(f"trigger_attendance_approved error: {e}")


def trigger_attendance_returned(sheet, feedback=""):
    """Fired when the Dean sends back an attendance sheet with feedback."""
    try:
        date_str = sheet.date.strftime('%b %d, %Y') if sheet.date else ''
        if sheet.submitted_by:
            fb_text = f' Feedback: "{feedback}"' if feedback else ''
            notify_user(
                recipient=sheet.submitted_by,
                title=f"Hours Sheet Sent Back ({sheet.committee.name})",
                message=f"Dean sent back attendance sheet for {sheet.committee.name} ({date_str}).{fb_text}",
                notification_type='approval',
                link_url=f"/committee/attendance/?date={date_str}",
                event=sheet.committee.event,
                committee=sheet.committee
            )
    except Exception as e:
        logger.warning(f"trigger_attendance_returned error: {e}")


def trigger_allocation_confirmed(app):
    """Fired when a student application allocation is saved/confirmed."""
    try:
        if app.student and app.assigned_committee:
            notify_user(
                recipient=app.student,
                title=f"Committee Allocation Confirmed! ({app.event.name})",
                message=f"You have been assigned to {app.assigned_committee.name} for {app.event.name}.",
                notification_type='allocation',
                link_url="/student/dashboard/",
                event=app.event,
                committee=app.assigned_committee
            )
    except Exception as e:
        logger.warning(f"trigger_allocation_confirmed error: {e}")
