"""Helpers for resolving a trip's tonnage (MT).

Tonnage is captured on the **waybill**, not on the truck: `Truck.capacity_tons`
is a vehicle specification and is left blank on most fleets, which is why the
MT column rendered as "—" for every row. The functions here read the real
figure off the waybill covering a truck's load and keep `Transit.cargo_weight_tons`
in step with it.
"""

from waybills.models import Waybill

from .models import Transit


def build_truck_weight_map(trucks):
    """Return {truck_id: weight_mt} for the given trucks.

    A truck's *current* waybill number (``Truck.waybill_number``) wins, since
    that is the load it is carrying right now. Where that doesn't resolve —
    the field is blank, or the number doesn't match a waybill on record — the
    most recently created waybill for the truck is used instead.
    """
    truck_by_id = {t.pk: t for t in trucks if t is not None}
    if not truck_by_id:
        return {}

    exact, fallback = {}, {}

    rows = (
        Waybill.objects
        .filter(truck_id__in=truck_by_id.keys(), weight_mt__isnull=False)
        .values('truck_id', 'waybill_number', 'weight_mt')
        .order_by('-created_at')
    )

    for row in rows:
        truck_id = row['truck_id']
        current_number = (truck_by_id[truck_id].waybill_number or '').strip()

        if current_number and row['waybill_number'] == current_number:
            exact.setdefault(truck_id, row['weight_mt'])
        else:
            fallback.setdefault(truck_id, row['weight_mt'])

    return {**fallback, **exact}


def weight_for_truck(truck):
    """Tonnage for a single truck, falling back to its rated capacity."""
    if truck is None:
        return None
    return build_truck_weight_map([truck]).get(truck.pk) or truck.capacity_tons


def backfill_transit_weights(queryset):
    """Fill in `cargo_weight_tons` from waybill data wherever it is missing.

    Called from the list views so the register heals itself — transits created
    before the waybills were imported (or from a truck with no capacity on
    file) pick up their real MT on the next page load. Returns the number of
    rows updated.
    """
    pending = list(
        queryset.filter(cargo_weight_tons__isnull=True)
        .select_related('truck')
        .only('id', 'cargo_weight_tons', 'truck__id', 'truck__waybill_number', 'truck__capacity_tons')
    )
    if not pending:
        return 0

    weights = build_truck_weight_map({t.truck for t in pending if t.truck_id})

    updates = []
    for transit in pending:
        weight = weights.get(transit.truck_id)
        if weight is None and transit.truck_id:
            weight = transit.truck.capacity_tons
        if weight is not None:
            transit.cargo_weight_tons = weight
            updates.append(transit)

    if updates:
        # bulk_update deliberately: it leaves `updated_at` alone, so healing
        # old rows doesn't reshuffle lists ordered by last-modified.
        Transit.objects.bulk_update(updates, ['cargo_weight_tons'])

    return len(updates)
