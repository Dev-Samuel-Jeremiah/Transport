from django.conf import settings
from django.db import models
from django.utils import timezone

from companies.models import Company
from drivers.models import Driver


class Truck(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        ON_TRIP = 'ON_TRIP', 'On Trip'
        MAINTENANCE = 'MAINTENANCE', 'Under Maintenance'
        INACTIVE = 'INACTIVE', 'Inactive'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='trucks')
    registration_number = models.CharField(max_length=40, unique=True)
    photo = models.ImageField(
        upload_to='trucks/photos/%Y/%m/', blank=True, null=True,
        help_text="A photo of the truck, shown on its detail page and in truck lists."
    )
    make = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=60, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    capacity_tons = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    assigned_driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='trucks'
    )

    # --- Current consignment reference fields ---
    waybill_number = models.CharField(
        max_length=60, blank=True,
        help_text="Waybill number for the load currently on this truck."
    )
    lti_number = models.CharField(
        max_length=60, blank=True,
        help_text="LTI (Local Transit Instrument) number for the current load."
    )
    origin = models.CharField(max_length=150, blank=True, help_text="Where the current load is coming from.")
    destination = models.CharField(max_length=150, blank=True, help_text="Where the current load is headed.")
    commodities = models.CharField(max_length=255, blank=True, help_text="What the truck is currently carrying.")

    # --- Manual tracking fields (used today) ---
    last_known_location = models.CharField(
        max_length=200, blank=True,
        help_text="Free-text location entered manually, e.g. 'Lagos-Ibadan Expressway, KM 25'."
    )
    last_location_updated_at = models.DateTimeField(null=True, blank=True)

    # --- GPS-ready fields (populated automatically once a GPS device/API is integrated) ---
    gps_device_id = models.CharField(max_length=80, blank=True, help_text="External GPS device/IMEI ID.")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    gps_last_ping_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} ({self.company.name})"

    @property
    def has_live_gps(self):
        return bool(self.gps_device_id and self.latitude and self.longitude)


class TruckDocument(models.Model):
    class DocType(models.TextChoices):
        REGISTRATION_CERT = 'REGISTRATION_CERT', 'Vehicle Registration (RC)'
        INSURANCE = 'INSURANCE', 'Insurance Certificate'
        ROADWORTHINESS = 'ROADWORTHINESS', 'Roadworthiness / Fitness Certificate'
        PERMIT = 'PERMIT', 'Road Use Permit'
        EMISSIONS = 'EMISSIONS', 'Emissions / PUC Certificate'
        OTHER = 'OTHER', 'Other'

    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=25, choices=DocType.choices)
    title = models.CharField(max_length=120, blank=True)
    file = models.FileField(upload_to='trucks/documents/%Y/%m/')
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.truck.registration_number} - {self.get_doc_type_display()}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        days = (self.expiry_date - timezone.localdate()).days
        return 0 <= days <= 30