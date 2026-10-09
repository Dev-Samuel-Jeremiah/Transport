from django.conf import settings
from django.db import models
from django.utils import timezone


class Company(models.Model):
    """A transport company registered by the platform admin."""

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    name = models.CharField(max_length=150)
    registration_number = models.CharField(max_length=60, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='companies_registered',
        help_text="Admin who registered this company.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class CompanyDocument(models.Model):
    """Compliance documents held on file for a company (e.g. trade license)."""

    class DocType(models.TextChoices):
        TRADE_LICENSE = 'TRADE_LICENSE', 'Trade License'
        TAX_CERTIFICATE = 'TAX_CERTIFICATE', 'Tax Certificate'
        INSURANCE_POLICY = 'INSURANCE_POLICY', 'Company Insurance Policy'
        INCORPORATION_CERT = 'INCORPORATION_CERT', 'Certificate of Incorporation'
        OTHER = 'OTHER', 'Other'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=25, choices=DocType.choices)
    title = models.CharField(max_length=120, blank=True)
    file = models.FileField(upload_to='companies/documents/%Y/%m/')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.company.name} - {self.get_doc_type_display()}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        days = (self.expiry_date - timezone.localdate()).days
        return 0 <= days <= 30
