from django.contrib import admin

from .models import Transit, TrackingUpdate


class TrackingUpdateInline(admin.TabularInline):
    model = TrackingUpdate
    extra = 0
    readonly_fields = ('recorded_at',)


@admin.register(Transit)
class TransitAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'company', 'truck', 'status', 'origin', 'destination', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('reference_code', 'origin', 'destination')
    inlines = [TrackingUpdateInline]


@admin.register(TrackingUpdate)
class TrackingUpdateAdmin(admin.ModelAdmin):
    list_display = ('transit', 'status', 'location_text', 'source', 'recorded_at')
    list_filter = ('source', 'status')
