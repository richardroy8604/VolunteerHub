"""
Security middleware for VolunteerHub.

1. NoCacheMiddleware prevents browsers from caching authenticated responses in the
   browser's disk/bfcache. When a user logs out and hits the browser Back button,
   the browser is forced to send a request to Django, which sees no active session
   and immediately redirects to the Login page.

2. FirstLoginEnforcementMiddleware ensures every logged-in user must set up their
   mandatory phone number and password before accessing any system features.
"""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import add_never_cache_headers


class NoCacheMiddleware:
    """
    Middleware that attaches No-Cache headers to all responses for authenticated users
    and login/logout endpoints to prevent back-button cache leaks.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated or request.path.startswith('/accounts/'):
            add_never_cache_headers(response)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response


class GlobalLoginRequiredMiddleware:
    """
    Global authentication enforcement middleware.
    Ensures NO page, route, or link across the application can be accessed without
    an active logged-in session.

    Exempt paths:
    - Login page (/accounts/login/)
    - Logout page (/accounts/logout/)
    - Google OAuth callback (/accounts/google/...)
    - Static assets (/static/...) & Media files (/media/...)
    """
    EXEMPT_PREFIXES = (
        '/accounts/login/',
        '/accounts/logout/',
        '/accounts/google/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if not request.user.is_authenticated:
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
                from django.contrib import messages
                messages.error(request, 'Please log in to access this page.')
                return redirect('/accounts/login/')

        return self.get_response(request)


class FirstLoginEnforcementMiddleware:
    """
    Enforces mandatory profile setup (phone number and password) for all signed-in users.
    If a user has is_first_login=True or has an empty phone number, they are redirected to
    /accounts/first-login/ until setup is completed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            path = request.path
            exempt_paths = [
                '/accounts/first-login/',
                '/accounts/logout/',
            ]
            if not any(path.startswith(ep) for ep in exempt_paths) and not path.startswith('/static/') and not path.startswith('/media/'):
                try:
                    profile = request.user.profile
                    if profile.is_first_login or not profile.phone or not profile.phone.strip():
                        return redirect('accounts:first_login')
                except Exception:
                    pass

        response = self.get_response(request)
        return response


class SessionIdleTimeoutMiddleware:
    """
    Middleware that enforces automatic session expiration on inactivity.
    - Admin (Dean) & Faculty: 30 minutes idle timeout (1800 seconds).
    - Students: 24 hours idle timeout (86400 seconds).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            import time
            from django.contrib import auth, messages
            
            now = time.time()
            last_activity = request.session.get('last_activity')
            
            try:
                role = request.user.profile.role
            except Exception:
                role = 'student'
                
            # Idle timeout limits (in seconds)
            # Dean / Admin & Faculty: 30 minutes (1800s); Student: 24 hours (86400s)
            timeout_limit = 1800 if role in ['dean', 'faculty'] else 86400
            
            if last_activity and (now - last_activity > timeout_limit):
                auth.logout(request)
                messages.warning(request, 'Your session expired due to inactivity. Please log in again.')
                return redirect('/accounts/login/')
                
            request.session['last_activity'] = now

        response = self.get_response(request)
        return response
