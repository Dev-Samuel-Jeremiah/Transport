from django.contrib import admin

from .models import Driver, DriverDocument


class DriverDocumentInline(admin.TabularInline):
    model = DriverDocument
    extra = 0


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'company', 'phone', 'license_number', 'status')
    list_filter = ('status', 'company')
    search_fields = ('full_name', 'license_number', 'phone')
    inlines = [DriverDocumentInline]


@admin.register(DriverDocument)
class DriverDocumentAdmin(admin.ModelAdmin):
    list_display = ('driver', 'doc_type', 'expiry_date', 'uploaded_at')
    list_filter = ('doc_type',)
