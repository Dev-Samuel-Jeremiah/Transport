from django.conf import settings
from django.db import models

from companies.models import Company
from drivers.models import Driver
from trucks.models import Truck


class LTI(models.Model):
    """A Local Transit Instrument. One company can raise many LTIs, and each
    LTI can cover many individual waybills (one LTI -> many waybills)."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        CLOSED = 'CLOSED', 'Closed'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='ltis')
    lti_number = models.CharField(max_length=60)
    sto = models.CharField(max_length=60, blank=True, help_text="STO / batch reference, if any.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ltis_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['company', 'lti_number'], name='unique_lti_number_per_company'),
        ]
        verbose_name = 'LTI'
        verbose_name_plural = 'LTIs'

    def __str__(self):
        return f"{self.lti_number} ({self.company.name})"

    @property
    def waybill_count(self):
        return self.waybills.count()


class Waybill(models.Model):
    """A single waybill/consignment raised under an LTI. Each waybill belongs
    to exactly one LTI (one company -> many LTIs -> many waybills)."""

    class TransitStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        OFFLOADED = 'OFFLOADED', 'Offloaded'
        CANCELLED = 'CANCELLED', 'Cancelled'

    lti = models.ForeignKey(LTI, on_delete=models.CASCADE, related_name='waybills')
    waybill_number = models.CharField(max_length=60)
    date = models.CharField(max_length=40, blank=True, help_text="e.g. '9 Jul' or '2026-07-09'.")

    transporter_name = models.CharField(max_length=150, blank=True)
    truck = models.ForeignKey(
        Truck, on_delete=models.SET_NULL, null=True, blank=True, related_name='waybills'
    )
    vehicle_id = models.CharField(max_length=40, blank=True, help_text="Vehicle plate number as text.")
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='waybills'
    )
    driver_name = models.CharField(max_length=120, blank=True, help_text="Driver name as text.")

    origin = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    commodity = models.CharField(max_length=150, blank=True)
    weight_mt = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=12, choices=TransitStatus.choices, default=TransitStatus.PENDING)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='waybills_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['lti', 'waybill_number'], name='unique_waybill_number_per_lti'),
        ]

    def __str__(self):
        return self.waybill_number

    @property
    def company(self):
        return self.lti.company