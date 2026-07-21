"""
events app — Committee Head URL configuration.

Routes under /committee/ prefix for committee head views:
dashboard, volunteer list, attendance marking.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.committee_dashboard_view, name='committee_dashboard'),
    path('<int:pk>/volunteers/', views.committee_volunteers_view, name='committee_volunteers'),
    path('<int:pk>/attendance/', views.committee_attendance_view, name='committee_attendance'),
]
