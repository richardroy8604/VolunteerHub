"""
accounts app URL configuration.

Handles authentication and user profile routes.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('first-login/', views.first_login_view, name='first_login'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('notifications/<int:pk>/read/', views.mark_notification_read_view, name='notification_read'),
    path('notifications/<int:pk>/delete/', views.delete_notification_view, name='notification_delete'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read_view, name='notification_mark_all_read'),
    path('notifications/clear-all/', views.clear_all_notifications_view, name='notification_clear_all'),
    path('notifications/broadcast/', views.dean_broadcast_notification_view, name='notification_broadcast'),
]
