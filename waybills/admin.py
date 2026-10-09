from django.contrib import admin

from .models import LTI, Waybill


class WaybillInline(admin.TabularInline):
    model = Waybill
    extra = 0
    fields = ('waybill_number', 'origin', 'destination', 'status', 'weight_mt')


@admin.register(LTI)
class LTIAdmin(admin.ModelAdmin):
    list_display = ('lti_number', 'company', 'sto', 'status', 'waybill_count', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('lti_number', 'sto', 'company__name')
    inlines = [WaybillInline]


@admin.register(Waybill)
class WaybillAdmin(admin.ModelAdmin):
    list_display = (
        'waybill_number', 'lti', 'get_company', 'origin', 'destination',
        'status', 'weight_mt', 'created_at',
    )
    list_filter = ('status', 'lti__company', 'origin', 'destination')
    search_fields = ('waybill_number', 'lti__lti_number', 'vehicle_id', 'driver_name', 'transporter_name')

    @admin.display(description='Company', ordering='lti__company')
    def get_company(self, obj):
        return obj.lti.company