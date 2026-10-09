from django.contrib import admin

from .models import Truck, TruckDocument


class TruckDocumentInline(admin.TabularInline):
    model = TruckDocument
    extra = 0


@admin.register(Truck)
class TruckAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'company', 'status', 'assigned_driver', 'last_known_location')
    list_filter = ('status', 'company')
    search_fields = ('registration_number',)
    inlines = [TruckDocumentInline]


@admin.register(TruckDocument)
class TruckDocumentAdmin(admin.ModelAdmin):
    list_display = ('truck', 'doc_type', 'expiry_date', 'uploaded_at')
    list_filter = ('doc_type',)
