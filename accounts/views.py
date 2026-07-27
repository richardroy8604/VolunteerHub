from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate, login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
import re
from accounts.models import UserProfile, Notification
from accounts.services import broadcast_announcement
from volunteers.models import VolunteerApplication, AttendanceRecord

def login_view(request):
    """Render the login page and handle authentication."""
    if request.user.is_authenticated:
        try:
            if request.user.profile.is_first_login:
                return redirect('accounts:first_login')
        except Exception:
            pass
        return redirect('dashboard')

    if request.method == 'POST':
        user_input = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # Try direct authentication first
        user = authenticate(request, username=user_input, password=password)

        # If user_input is an email, resolve to username via User model
        if user is None and '@' in user_input:
            from django.contrib.auth.models import User
            matching_user = User.objects.filter(email__iexact=user_input).first()
            if matching_user:
                user = authenticate(request, username=matching_user.username, password=password)

        # Fallback: check prefix if user typed full email
        if user is None and '@' in user_input:
            prefix = user_input.split('@')[0]
            user = authenticate(request, username=prefix, password=password)

        if user is not None:
            login(request, user)
            try:
                if user.profile.is_first_login:
                    return redirect('accounts:first_login')
            except Exception:
                pass
            return redirect('dashboard')
        else:
            from django.contrib.auth.models import User
            user_exists = User.objects.filter(username__iexact=user_input).exists() or \
                          User.objects.filter(email__iexact=user_input).exists() or \
                          ('@' in user_input and User.objects.filter(username__iexact=user_input.split('@')[0]).exists())

            if not user_exists:
                target_name = f" for '{user_input}'" if user_input else ""
                messages.warning(
                    request,
                    f"No account found{target_name}. If it's your first time, use 'Sign in with Google' below."
                )
            else:
                messages.error(request, "Invalid password. Please check your credentials and try again.")

    return render(request, 'accounts/login.html')

def logout_view(request):
    """Log the user out and redirect to the login page."""
    auth_logout(request)
    return redirect('accounts:login')

@login_required
def first_login_view(request):
    """Render the first-login setup page with 3-step animated wizard."""
    profile = request.user.profile
    user_name = request.user.get_full_name() or request.user.username
    
    if request.method == 'POST':
        raw_phone = request.POST.get('phone', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # Clean digits from phone
        phone_digits = re.sub(r'\D', '', raw_phone)
        if phone_digits.startswith('91') and len(phone_digits) == 12:
            phone_digits = phone_digits[2:]

        # Validate mandatory phone number
        if not phone_digits or len(phone_digits) != 10 or not phone_digits[0] in '6789':
            messages.error(request, "Please enter a valid 10-digit Indian mobile number (e.g. 9876543210).")
            return render(request, 'accounts/first_login.html', {
                'profile': profile,
                'user_name': user_name,
                'form_data': request.POST,
                'role_title': profile.display_role,
            })

        # Validate password setup
        if new_password:
            if len(new_password) < 6:
                messages.error(request, "Password must be at least 6 characters long.")
                return render(request, 'accounts/first_login.html', {
                    'profile': profile,
                    'user_name': user_name,
                    'form_data': request.POST,
                    'role_title': profile.display_role,
                })

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match. Please enter matching passwords.")
                return render(request, 'accounts/first_login.html', {
                    'profile': profile,
                    'user_name': user_name,
                    'form_data': request.POST,
                    'role_title': profile.display_role,
                })

            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)

        # Save verified phone with +91 formatting
        profile.phone = f"+91 {phone_digits}"
        profile.phone_verified = True
            
        if 'profile_picture' in request.FILES:
            profile.profile_pic = request.FILES['profile_picture']

        profile.is_first_login = False
        profile.save()

        messages.success(request, f"Welcome to VolunteerHub, {user_name}! Your account setup is complete.")
        return redirect('dashboard')
        
    context = {
        'profile': profile,
        'user_name': user_name,
        'user_obj': request.user,
        'role_title': profile.display_role,
    }
    return render(request, 'accounts/first_login.html', context)

@login_required
def profile_view(request):
    """Render the user profile page with volunteer statistics."""
    profile = request.user.profile
    
    if profile.role == 'student':
        # Compute total hours from approved AttendanceRecords
        hours_agg = AttendanceRecord.objects.filter(
            student=profile, 
            sheet__status='approved'
        ).aggregate(total=Sum('total_hours'))
        total_hours = hours_agg['total'] or 0.0
        
        # Compute events participated from assigned VolunteerApplications for completed events
        events_participated = VolunteerApplication.objects.filter(
            student=profile,
            status='assigned',
            event__status='completed'
        ).count()
        
        semester = f"{profile.semester}th Sem" if profile.semester else 'N/A'
        student_class = profile.class_batch or 'N/A'
    else:
        total_hours = 'N/A'
        events_participated = 'N/A'
        semester = 'N/A'
        student_class = 'N/A'

    context = {
        'profile_user': {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'role': profile.display_role,
            'department': str(profile.department) if profile.department else 'N/A',
            'semester': semester,
            'student_class': student_class,
            'phone': profile.phone if (profile.phone and profile.phone.strip()) else 'Not provided',
            'phone_verified': bool(profile.phone and profile.phone.strip()),
            'total_hours': total_hours,
            'events_participated': events_participated,
            'profile_pic': profile.profile_pic.url if profile.profile_pic else None,
        }
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def profile_edit_view(request):
    """Render the profile edit form."""
    profile = request.user.profile
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        if phone:
            profile.phone = phone.strip()
        if 'profile_picture' in request.FILES:
            profile.profile_pic = request.FILES['profile_picture']
        profile.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('accounts:profile')
            
    if profile.role == 'student':
        semester = profile.semester
        student_class = profile.class_batch
    else:
        semester = 'N/A'
        student_class = 'N/A'
        
    context = {
        'profile_user': {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
            'role': profile.display_role,
            'department': str(profile.department) if profile.department else 'N/A',
            'semester': semester,
            'student_class': student_class,
            'phone': profile.phone,
            'phone_verified': True,
        }
    }
    return render(request, 'accounts/profile_edit.html', context)


@require_POST
def mark_notification_read_view(request, pk):
    """Mark an individual notification as read."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    Notification.objects.filter(pk=pk, recipient=request.user.profile).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@require_POST
def delete_notification_view(request, pk):
    """Delete an individual notification item."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    Notification.objects.filter(pk=pk, recipient=request.user.profile).delete()
    return JsonResponse({'status': 'ok'})


@require_POST
def mark_all_notifications_read_view(request):
    """Mark all notifications as read for current user."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    Notification.objects.filter(recipient=request.user.profile, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@require_POST
def clear_all_notifications_view(request):
    """Delete all notifications for current user."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=401)
    Notification.objects.filter(recipient=request.user.profile).delete()
    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def dean_broadcast_notification_view(request):
    """Handle Dean broadcast announcement form submission with multi-committee support."""
    profile = request.user.profile
    if profile.role != 'dean' and not request.user.is_staff:
        messages.error(request, 'Only System Admins (Dean) can send broadcast announcements.')
        return redirect('/dean/dashboard/')

    scope = request.POST.get('scope', 'system')
    title = request.POST.get('title', '').strip()
    message = request.POST.get('message', '').strip()
    event_id = request.POST.get('event_id')
    target_committee_ids = request.POST.getlist('target_committee_ids[]')

    if not title or not message:
        messages.error(request, 'Title and Message are required for broadcast.')
        return redirect(request.META.get('HTTP_REFERER') or '/dean/dashboard/')

    sent_count = broadcast_announcement(
        dean_profile=profile,
        scope=scope,
        title=title,
        message=message,
        event_id=event_id,
        target_committee_ids=target_committee_ids
    )

    messages.success(request, f'Broadcast announcement "{title}" sent successfully to {sent_count} user(s)!')
    return redirect(request.META.get('HTTP_REFERER') or '/dean/dashboard/')
