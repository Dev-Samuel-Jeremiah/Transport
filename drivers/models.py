from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import Company


class Driver(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        ON_TRIP = 'ON_TRIP', 'On Trip'
        INACTIVE = 'INACTIVE', 'Inactive'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='drivers')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_profile',
        help_text="Login account this driver uses to access their profile, if one has been created.",
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    license_number = models.CharField(max_length=60, unique=True)
    license_expiry = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='drivers/photos/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='drivers_registered',
        help_text="Admin (or company user) who registered this driver.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    password_is_temporary = models.BooleanField(
        default=False,
        help_text=(
            "True while the driver's login still carries the temporary password "
            "issued at onboarding. Cleared once the company — or the driver — sets a real one."
        ),
    )

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.company.name})"

    @property
    def has_login(self):
        return self.user_id is not None

    @property
    def needs_password_change(self):
        """Account exists but is still on the temporary password."""
        return bool(self.user_id and self.password_is_temporary)

    @property
    def license_expired(self):
        return bool(self.license_expiry and self.license_expiry < timezone.localdate())


class DriverDocument(models.Model):
    class DocType(models.TextChoices):
        DRIVING_LICENSE = 'DRIVING_LICENSE', 'Driving License'
        NATIONAL_ID = 'NATIONAL_ID', 'National ID / Passport'
        MEDICAL_CERT = 'MEDICAL_CERT', 'Medical Fitness Certificate'
        BACKGROUND_CHECK = 'BACKGROUND_CHECK', 'Background Check'
        OTHER = 'OTHER', 'Other'

    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=25, choices=DocType.choices)
    title = models.CharField(max_length=120, blank=True)
    file = models.FileField(upload_to='drivers/documents/%Y/%m/')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.driver.full_name} - {self.get_doc_type_display()}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        days = (self.expiry_date - timezone.localdate()).days
        return 0 <= days <= 30
