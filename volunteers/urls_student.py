"""
volunteers app — Student URL configuration.

Routes under /student/ prefix for student-specific views:
dashboard, application history, volunteering history.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('applications/', views.my_applications_view, name='my_applications'),
    path('volunteering/', views.my_volunteering_view, name='my_volunteering'),
    path('committees/<int:pk>/', views.student_committee_detail_view, name='student_committee_detail'),
]
