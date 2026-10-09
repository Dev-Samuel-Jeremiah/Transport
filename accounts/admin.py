from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role', 'phone')}),
        ('Company access', {'fields': ('company', 'password_is_temporary')}),
    )
    list_display = ('username', 'email', 'role', 'company', 'is_staff', 'is_active')
    list_filter = UserAdmin.list_filter + ('role', 'company')
