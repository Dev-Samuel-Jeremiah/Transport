from django.contrib import admin

from .models import Company, CompanyDocument


class CompanyDocumentInline(admin.TabularInline):
    model = CompanyDocument
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'status', 'phone', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'registration_number', 'email')
    inlines = [CompanyDocumentInline]


@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ('company', 'doc_type', 'expiry_date', 'uploaded_at')
    list_filter = ('doc_type',)
