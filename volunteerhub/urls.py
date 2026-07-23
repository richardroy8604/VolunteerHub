"""
volunteerhub URL Configuration

Root URL routing for the VolunteerHub project.
Routes are organized by user role:
  /admin/       — Django admin
  /accounts/    — Authentication (login, logout, profile)
  /dashboard/   — Smart redirect to role-appropriate dashboard
  /dean/        — Dean-only views (dashboard, event management, reports)
  /committee/   — Committee Head views (volunteer management, attendance)
  /student/     — Student views (dashboard, applications, history)
  /events/      — Public/student-facing event browsing
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect


def dashboard_redirect(request):
    """Redirect to role-appropriate dashboard based on UserProfile.role."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    try:
        role = request.user.profile.role
    except Exception:
        return redirect('accounts:login')
    if role == 'dean':
        return redirect('events_dean:dean_dashboard')
    elif role == 'faculty':
        return redirect('events_committee:committee_dashboard')
    else:
        return redirect('volunteers_student:student_dashboard')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('accounts:login')),
    path('dashboard/', dashboard_redirect, name='dashboard'),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('dean/', include(('events.urls_dean', 'events_dean'), namespace='events_dean')),
    path('events/', include(('events.urls', 'events'), namespace='events')),
    path('committee/', include(('events.urls_committee', 'events_committee'), namespace='events_committee')),
    path('student/', include(('volunteers.urls_student', 'volunteers_student'), namespace='volunteers_student')),
    path('dean/events/', include(('volunteers.urls_dean', 'volunteers_dean'), namespace='volunteers_dean')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
