"""Query filters shared by the transit list pages and their exports.

Keeping these in one place means a download always contains exactly the rows
the user is looking at on screen — change a filter here and both follow.
"""

from django.db.models import Q


def apply_transit_filters(qs, params):
    """Filters used by the transit register (company and admin)."""
    status = params.get('status')
    if status:
        qs = qs.filter(status=status)

    location = params.get('location')
    if location:
        qs = qs.filter(truck__last_known_location__icontains=location)

    company = params.get('company')
    if company:
        qs = qs.filter(company_id=company)

    return qs


def apply_delivered_filters(qs, params):
    """Filters used by the Delivered pages."""
    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(reference_code__icontains=q)
            | Q(origin__icontains=q)
            | Q(destination__icontains=q)
            | Q(truck__registration_number__icontains=q)
            | Q(driver__full_name__icontains=q)
            | Q(cargo_description__icontains=q)
        )

    destination = (params.get('destination') or '').strip()
    if destination:
        qs = qs.filter(destination=destination)

    company = params.get('company')
    if company:
        qs = qs.filter(company_id=company)

    # Completed-on range, falling back to the record date for older rows
    # that never had an arrival time stamped.
    date_from = (params.get('from') or '').strip()
    date_to = (params.get('to') or '').strip()
    if date_from:
        qs = qs.filter(
            Q(actual_arrival__date__gte=date_from)
            | Q(actual_arrival__isnull=True, updated_at__date__gte=date_from)
        )
    if date_to:
        qs = qs.filter(
            Q(actual_arrival__date__lte=date_to)
            | Q(actual_arrival__isnull=True, updated_at__date__lte=date_to)
        )

    return qs
