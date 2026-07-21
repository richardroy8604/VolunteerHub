"""
volunteers app — Dean URL configuration for volunteer pool management.

Routes under /dean/events/ prefix for managing the volunteer pool
and auto-allocation per event.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('<int:event_id>/volunteer_pool/', views.volunteer_pool_view, name='volunteer_pool'),
    path('<int:event_id>/auto_allocate/', views.auto_allocate_view, name='auto_allocate'),
]
