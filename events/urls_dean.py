"""
events app — Dean URL configuration.

Routes under /dean/ prefix for Dean-only views:
event management, committee oversight, user management, reports.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dean_dashboard_view, name='dean_dashboard'),
    path('events/', views.event_list_view, name='event_list'),
    path('events/create/', views.event_create_view, name='event_create'),
    path('events/<int:pk>/', views.event_detail_view, name='event_detail'),
    path('events/<int:pk>/edit/', views.event_edit_view, name='event_edit'),
    path('committees/', views.committee_list_view, name='committee_list'),
    path('committees/<int:pk>/', views.dean_committee_detail_view, name='committee_detail'),
    path('approvals/', views.dean_approvals_view, name='approvals'),
    path('users/', views.user_management_view, name='user_management'),
    path('reports/', views.reports_view, name='reports'),
]
