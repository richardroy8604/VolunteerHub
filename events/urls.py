"""
events app — Public / Student-facing URL configuration.

Routes under /events/ prefix for browsing events and applying.
"""

from django.urls import path
from events import views as event_views
from volunteers import views as volunteer_views

urlpatterns = [
    path('', event_views.browse_events_view, name='browse_events'),
    path('<int:pk>/', event_views.event_public_detail_view, name='event_public_detail'),
    path('<int:event_id>/apply/', volunteer_views.apply_view, name='apply'),
]
