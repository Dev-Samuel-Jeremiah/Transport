from django.conf import settings
from django.db import models

from companies.models import Company
from drivers.models import Driver
from trucks.models import Truck



class Transit(models.Model):
    """A single trip/consignment undertaken by one of a company's trucks."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='transits')
    truck = models.ForeignKey(Truck, on_delete=models.PROTECT, related_name='transits')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='transits')

    reference_code = models.CharField(max_length=30, unique=True)
    origin = models.CharField(max_length=150)
    destination = models.CharField(max_length=150)
    cargo_description = models.CharField(max_length=200, blank=True)
    cargo_weight_tons = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    scheduled_departure = models.DateTimeField(null=True, blank=True)
    actual_departure = models.DateTimeField(null=True, blank=True)
    expected_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_archived = models.BooleanField(
        default=False,
        help_text="Delivered transits moved off the active register into the audit log.",
    )
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transits_archived',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference_code}: {self.origin} -> {self.destination}"

    @property
    def display_weight_mt(self):
        """Tonnage to show for this trip.

        Order of preference: the figure stored on the transit, then the
        weight on the waybill covering the truck's load, then the truck's
        rated capacity. Tonnage lives on the waybill in practice —
        `Truck.capacity_tons` is a vehicle spec and is usually blank — so
        without this fallback the MT column reads "—" even when the weight
        is on file.
        """
        if self.cargo_weight_tons is not None:
            return self.cargo_weight_tons
        if not self.truck_id:
            return None

        from .services import weight_for_truck
        return weight_for_truck(self.truck)


class TrackingUpdate(models.Model):
    """
    A tracking checkpoint for a transit. Entered manually today; the same
    model can be populated automatically once a GPS feed is wired up
    (source distinguishes how the point was captured).
    """

    class Source(models.TextChoices):
        MANUAL = 'MANUAL', 'Manual Update'
        GPS = 'GPS', 'GPS Device'

    transit = models.ForeignKey(Transit, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=12, choices=Transit.Status.choices)
    location_text = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    remarks = models.CharField(max_length=250, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.transit.reference_code} @ {self.recorded_at:%Y-%m-%d %H:%M}"
