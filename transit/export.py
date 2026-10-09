"""Spreadsheet exports for the transit register and the delivered record.

The .csv/.xlsx response writers already used by the waybill downloads are
reused here so every export in the app produces the same shape of file.
"""

from django.utils import timezone

# Shared response writers (same ones behind the waybill downloads).
from waybills.import_export import rows_to_csv_response, rows_to_xlsx_response

TRANSIT_COLUMNS = [
    'Reference', 'Origin', 'Destination', 'Truck', 'Driver', 'MT', 'Status',
    'Truck Position', 'Scheduled Departure', 'Actual Departure',
    'Expected Arrival', 'Actual Arrival', 'Created',
]

DELIVERED_COLUMNS = [
    'Reference', 'Origin', 'Destination', 'Truck', 'Driver', 'MT',
    'Delivered On', 'Record', 'Created',
]

COMPANY_COLUMN = 'Company'


def _dt(value):
    """Format a datetime for a spreadsheet cell, blank when unset."""
    if not value:
        return ''
    return timezone.localtime(value).strftime('%Y-%m-%d %H:%M')


def _weight(transit):
    weight = transit.display_weight_mt
    return weight if weight is not None else ''


def _transit_row(t, include_company=False):
    row = [
        t.reference_code,
        t.origin,
        t.destination,
        t.truck.registration_number if t.truck_id else '',
        t.driver.full_name if t.driver_id else '',
        _weight(t),
        t.get_status_display(),
        t.truck.last_known_location if t.truck_id else '',
        _dt(t.scheduled_departure),
        _dt(t.actual_departure),
        _dt(t.expected_arrival),
        _dt(t.actual_arrival),
        _dt(t.created_at),
    ]
    if include_company:
        row.insert(1, t.company.name)
    return row


def _delivered_row(t, include_company=False):
    row = [
        t.reference_code,
        t.origin,
        t.destination,
        t.truck.registration_number if t.truck_id else '',
        t.driver.full_name if t.driver_id else '',
        _weight(t),
        _dt(t.actual_arrival) or _dt(t.updated_at),
        'Confirmed' if t.is_archived else 'Awaiting confirmation',
        _dt(t.created_at),
    ]
    if include_company:
        row.insert(1, t.company.name)
    return row


def transit_export_rows(queryset, include_company=False):
    headers = list(TRANSIT_COLUMNS)
    if include_company:
        headers.insert(1, COMPANY_COLUMN)
    return headers, [_transit_row(t, include_company) for t in queryset]


def delivered_export_rows(queryset, include_company=False):
    headers = list(DELIVERED_COLUMNS)
    if include_company:
        headers.insert(1, COMPANY_COLUMN)
    return headers, [_delivered_row(t, include_company) for t in queryset]


def spreadsheet_response(request, filename, sheet_title, headers, rows):
    """Return .csv when ?format=csv is asked for, .xlsx otherwise."""
    if request.GET.get('format') == 'csv':
        return rows_to_csv_response(filename, headers, rows)
    return rows_to_xlsx_response(filename, sheet_title, headers, rows)
