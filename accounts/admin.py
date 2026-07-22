"""Admin registrations for accounts app models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, CourseConfig


class UserProfileInline(admin.StackedInline):
    """Inline UserProfile editor shown within the User admin page."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = (
        'role', 'designation', 'is_hod', 'department',
        'phone', 'phone_verified', 'profile_pic',
        'class_batch', 'admission_year', 'roll_number',
        'is_first_login',
    )


class UserAdmin(BaseUserAdmin):
    """Extended User admin with inline UserProfile."""
    inlines = (UserProfileInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'is_staff', 'is_active', 'get_role',
    )
    list_filter = BaseUserAdmin.list_filter + ('profile__role',)

    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return '-'
    get_role.short_description = 'Role'


@admin.register(CourseConfig)
class CourseConfigAdmin(admin.ModelAdmin):
    """Admin for CourseConfig (email parsing lookup table)."""
    list_display = ('code', 'full_name', 'short_name', 'duration_years', 'department')
    list_filter = ('department', 'duration_years')
    search_fields = ('code', 'full_name', 'short_name')
    ordering = ('department', 'full_name')


# Re-register User with the extended admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
