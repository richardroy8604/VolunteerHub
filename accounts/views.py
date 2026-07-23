from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
from accounts.models import UserProfile
from volunteers.models import VolunteerApplication, AttendanceRecord

def login_view(request):
    """Render the login page and handle authentication."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'accounts/login.html')

def logout_view(request):
    """Log the user out and redirect to the login page."""
    auth_logout(request)
    return redirect('accounts:login')

@login_required
def first_login_view(request):
    """Render the first-login setup page (phone verification, etc.)."""
    if request.method == 'POST':
        phone = request.POST.get('phone')
        profile = request.user.profile
        if phone:
            profile.phone = phone
        profile.is_first_login = False
        profile.save()
        return redirect('dashboard')
        
    return render(request, 'accounts/first_login.html')

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
        
        semester = profile.semester
        student_class = profile.class_batch
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
            'phone': profile.phone,
            'phone_verified': True,
            'total_hours': total_hours,
            'events_participated': events_participated,
            'profile_pic': profile.profile_pic,
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
            profile.phone = phone
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
