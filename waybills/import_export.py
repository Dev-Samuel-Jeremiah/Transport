import csv
import datetime
import io
import uuid

import openpyxl
from openpyxl.utils import get_column_letter

from companies.models import Company
from drivers.models import Driver
from trucks.models import Truck

from .models import LTI, Waybill

# ---------- Column layouts ----------

WAYBILL_COLUMNS = [
    ('Waybill No', 'waybill_number'),
    ('Date', 'date'),
    ('Transporter Name', 'transporter_name'),
    ('Vehicle Id', 'vehicle_id'),
    ('Driver Name', 'driver_name'),
    ('Origin', 'origin'),
    ('Destination', 'destination'),
    ('Commodity', 'commodity'),
    ('MT', 'weight_mt'),
    ('Transit Status', 'status'),
]

# Extra columns shown only on exports that span multiple companies/LTIs.
WAYBILL_LTI_COLUMN = ('LTI No', 'lti_number')
WAYBILL_COMPANY_COLUMN = ('Company', 'company_name')

LTI_COLUMNS = [
    ('LTI No', 'lti_number'),
    ('STO', 'sto'),
    ('Status', 'status'),
    ('Notes', 'notes'),
]
LTI_COMPANY_COLUMN = ('Company', 'company_name')

# Accepts common header spellings/synonyms found in real-world sheets
# (e.g. the WFP transit template) and maps them onto our field names.
WAYBILL_HEADER_ALIASES = {
    'waybill no': 'waybill_number', 'waybill number': 'waybill_number', 'waybill': 'waybill_number',
    'date': 'date', 'date/time': 'date',
    'transporter name': 'transporter_name', 'transporter': 'transporter_name',
    'vehicle id': 'vehicle_id', 'vehicle': 'vehicle_id',
    'driver name': 'driver_name', 'driver': 'driver_name',
    'origin': 'origin',
    'destination': 'destination',
    'commodity': 'commodity', 'commodities': 'commodity',
    'mt': 'weight_mt', 'weight': 'weight_mt', 'weight (mt)': 'weight_mt',
    'transit status': 'status', 'status': 'status',
    'lti no': 'lti_number', 'lti number': 'lti_number', 'lti': 'lti_number',
    'sto': 'sto',
    'notes': 'notes',
}

STATUS_ALIASES = {
    'offloaded': Waybill.TransitStatus.OFFLOADED,
    'in transit': Waybill.TransitStatus.IN_TRANSIT,
    'in_transit': Waybill.TransitStatus.IN_TRANSIT,
    'pending': Waybill.TransitStatus.PENDING,
    'cancelled': Waybill.TransitStatus.CANCELLED,
    'canceled': Waybill.TransitStatus.CANCELLED,
}


# ---------- Export ----------

def _waybill_row(w, include_lti=False, include_company=False):
    row = [
        w.waybill_number, w.date, w.transporter_name,
        w.truck.registration_number if w.truck else w.vehicle_id,
        w.driver.full_name if w.driver else w.driver_name,
        w.origin, w.destination, w.commodity,
        w.weight_mt if w.weight_mt is not None else '',
        w.get_status_display(),
    ]
    if include_lti:
        row.append(w.lti.lti_number)
    if include_company:
        row.append(w.lti.company.name)
    return row


def waybill_export_rows(queryset, include_lti=False, include_company=False):
    headers = [h for h, _ in WAYBILL_COLUMNS]
    if include_lti:
        headers.append(WAYBILL_LTI_COLUMN[0])
    if include_company:
        headers.append(WAYBILL_COMPANY_COLUMN[0])
    rows = [_waybill_row(w, include_lti, include_company) for w in queryset]
    return headers, rows


def _lti_row(lti, include_company=False):
    row = [lti.lti_number, lti.sto, lti.get_status_display(), lti.notes]
    if include_company:
        row.append(lti.company.name)
    return row


def lti_export_rows(queryset, include_company=False):
    headers = [h for h, _ in LTI_COLUMNS]
    if include_company:
        headers.append(LTI_COMPANY_COLUMN[0])
    rows = [_lti_row(l, include_company) for l in queryset]
    return headers, rows


def rows_to_csv_response(filename, headers, rows):
    from django.http import HttpResponse
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    resp = HttpResponse(buf.getvalue(), content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    return resp


def rows_to_xlsx_response(filename, sheet_title, headers, rows):
    from django.http import HttpResponse
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
    for i, header in enumerate(headers, start=1):
        width = max(12, len(str(header)) + 2)
        ws.column_dimensions[get_column_letter(i)].width = width
    buf = io.BytesIO()
    wb.save(buf)
    resp = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return resp


# ---------- Import ----------

class ImportError_(Exception):
    pass


def _normalize_header(value):
    return str(value or '').strip().lower()


def _clean_text(value):
    """Stringify a cell value, formatting Excel date/datetime cells as a plain date."""
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        return value.date().isoformat() if value.time() == datetime.time() else value.isoformat(sep=' ')
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value).strip()


def read_uploaded_rows(uploaded_file):
    """Read an uploaded .csv/.xlsx file into a list of dicts keyed by our
    internal field names, using WAYBILL_HEADER_ALIASES / LTI column names."""
    name = uploaded_file.name.lower()
    if name.endswith('.xlsx'):
        wb = openpyxl.load_workbook(uploaded_file, data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
    elif name.endswith('.csv'):
        text = uploaded_file.read().decode('utf-8-sig')
        raw_rows = list(csv.reader(io.StringIO(text)))
    else:
        raise ImportError_("Unsupported file type. Please upload a .csv or .xlsx file.")

    # Find the header row: the first row containing at least one recognised column name.
    header_index = None
    for i, row in enumerate(raw_rows):
        normalized = [_normalize_header(c) for c in row]
        if any(c in WAYBILL_HEADER_ALIASES for c in normalized):
            header_index = i
            break
    if header_index is None:
        raise ImportError_("Could not find a recognisable header row in the file.")

    headers = [_normalize_header(c) for c in raw_rows[header_index]]
    field_names = [WAYBILL_HEADER_ALIASES.get(h) for h in headers]

    records = []
    for row in raw_rows[header_index + 1:]:
        if row is None or all(c in (None, '') for c in row):
            continue
        record = {}
        for field, value in zip(field_names, row):
            if field:
                record[field] = value
        if record:
            records.append(record)
    return records


def parse_status(value, default):
    if not value:
        return default
    key = str(value).strip().lower()
    return STATUS_ALIASES.get(key, default)


def _parse_weight(value):
    try:
        return float(value) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _get_or_create_truck(company, vehicle_id):
    """Look up a Truck by registration number (matching is case-insensitive
    since plate numbers get typed inconsistently across sheets). Registration
    numbers are unique platform-wide, so an existing truck is reused as-is
    even if it was originally registered under a different company. If none
    exists yet, a new Truck row is created for the importing company so it
    shows up in that company's Trucks table."""
    reg = _clean_text(vehicle_id)
    if not reg:
        return None
    truck = Truck.objects.filter(registration_number__iexact=reg).first()
    if truck:
        return truck
    return Truck.objects.create(
        company=company,
        registration_number=reg,
        status=Truck.Status.AVAILABLE,
    )


def _get_or_create_driver(company, driver_name, user):
    """Look up a Driver by name within the company (case-insensitive). If the
    driver doesn't exist yet, create one so it shows up in the Drivers table.
    Import sheets like the WFP transit template only give a name — no phone
    or license number — so a unique placeholder license number is generated;
    staff can fill in the real license/phone later from the Drivers page."""
    name = _clean_text(driver_name)
    if not name:
        return None
    driver = Driver.objects.filter(company=company, full_name__iexact=name).first()
    if driver:
        return driver
    return Driver.objects.create(
        company=company,
        full_name=name,
        phone='',
        license_number=f"PENDING-{uuid.uuid4().hex[:10].upper()}",
        status=Driver.Status.ACTIVE,
        registered_by=user,
    )


def match_company_by_transporter_name(transporter_name):
    """Resolve a sheet's 'Transporter Name' cell to a registered Company.

    Tries an exact (case-insensitive) name match first, since that's what
    real company names in the system look like. Falls back to a partial
    match only when it's unambiguous — i.e. exactly one company's name
    contains the transporter name or vice versa. Returns None (no match, or
    more than one plausible match) rather than guessing, so a misspelled or
    unregistered transporter never gets silently filed under the wrong
    company.
    """
    name = _clean_text(transporter_name)
    if not name:
        return None

    exact = Company.objects.filter(name__iexact=name).first()
    if exact:
        return exact

    candidates = list(Company.objects.filter(name__icontains=name))
    if len(candidates) == 1:
        return candidates[0]

    return None


def _create_waybill_from_record(rec, lti, user):
    """Build and save a Waybill from a parsed record dict, resolving (or
    auto-creating) the matching Truck and Driver rows so the upload also
    populates the Trucks and Drivers tables — not just free-text fields on
    the Waybill. Returns the created Waybill, or None (with a reason) if the
    row is missing required fields or is a duplicate within the LTI."""
    waybill_number = _clean_text(rec.get('waybill_number'))
    origin = _clean_text(rec.get('origin'))
    destination = _clean_text(rec.get('destination'))
    if not waybill_number or not origin or not destination:
        return None, "missing waybill number, origin or destination — skipped."
    if Waybill.objects.filter(lti=lti, waybill_number=waybill_number).exists():
        return None, f"waybill '{waybill_number}' already exists under LTI '{lti.lti_number}' — skipped."

    vehicle_id = _clean_text(rec.get('vehicle_id'))
    driver_name = _clean_text(rec.get('driver_name'))
    commodity = _clean_text(rec.get('commodity'))
    status = parse_status(rec.get('status'), Waybill.TransitStatus.PENDING)

    truck = _get_or_create_truck(lti.company, vehicle_id)
    driver = _get_or_create_driver(lti.company, driver_name, user)

    waybill = Waybill.objects.create(
        lti=lti,
        waybill_number=waybill_number,
        date=_clean_text(rec.get('date')),
        transporter_name=_clean_text(rec.get('transporter_name')),
        truck=truck,
        vehicle_id=vehicle_id,
        driver=driver,
        driver_name=driver_name,
        origin=origin,
        destination=destination,
        commodity=commodity,
        weight_mt=_parse_weight(rec.get('weight_mt')),
        status=status,
        created_by=user,
    )

    if truck is not None:
        # Keep the truck's "current consignment" fields in sync with the
        # latest waybill imported for it, so the Trucks table reflects what
        # was on the sheet (not just a bare link back to the waybill).
        truck.waybill_number = waybill_number
        truck.lti_number = lti.lti_number
        truck.origin = origin
        truck.destination = destination
        truck.commodities = commodity
        if driver is not None:
            truck.assigned_driver = driver
        truck.status = (
            Truck.Status.AVAILABLE if status == Waybill.TransitStatus.OFFLOADED
            else Truck.Status.ON_TRIP
        )
        truck.save(update_fields=[
            'waybill_number', 'lti_number', 'origin', 'destination',
            'commodities', 'assigned_driver', 'status',
        ])

    return waybill, None


def import_waybills(uploaded_file, lti, user):
    """Bulk-create Waybill rows under a single LTI. Returns (created, skipped, errors)."""
    records = read_uploaded_rows(uploaded_file)
    created, skipped, errors = 0, 0, []
    for i, rec in enumerate(records, start=1):
        waybill, reason = _create_waybill_from_record(rec, lti, user)
        if waybill is None:
            skipped += 1
            errors.append(f"Row {i}: {reason}")
            continue
        created += 1
    return created, skipped, errors


def import_ltis(uploaded_file, company, user):
    """Bulk-create LTI rows for a single company. Returns (created, skipped, errors)."""
    records = read_uploaded_rows(uploaded_file)
    created, skipped, errors = 0, 0, []
    for i, rec in enumerate(records, start=1):
        lti_number = _clean_text(rec.get('lti_number'))
        if not lti_number:
            skipped += 1
            errors.append(f"Row {i}: missing LTI number — skipped.")
            continue
        if LTI.objects.filter(company=company, lti_number=lti_number).exists():
            skipped += 1
            errors.append(f"Row {i}: LTI '{lti_number}' already exists — skipped.")
            continue

        status_value = _clean_text(rec.get('status')).upper()
        status = status_value if status_value in LTI.Status.values else LTI.Status.OPEN

        LTI.objects.create(
            company=company,
            lti_number=lti_number,
            sto=_clean_text(rec.get('sto')),
            status=status,
            notes=_clean_text(rec.get('notes')),
            created_by=user,
        )
        created += 1
    return created, skipped, errors


UNSPECIFIED_BATCH_LABEL = 'UNSPECIFIED'


def import_transit_sheet(uploaded_file, user):
    """
    Bulk-import a single-sheet transit tracking file — the same shape as the
    real-world WFP transit template (one sheet, one row per truck, an 'STO' /
    batch reference column instead of a pre-existing LTI number).

    The company for each row is resolved automatically from its 'Transporter
    Name' cell (see match_company_by_transporter_name) — the sheet can carry
    rows for several different companies at once, and each row lands under
    its own company's LTIs/waybills. A row whose transporter name doesn't
    match exactly one registered company is skipped and reported rather than
    guessed at.

    Within each company, rows are grouped by their LTI No. (if the sheet has
    one) or otherwise by STO, and one LTI per distinct batch is looked up or
    created automatically — so nobody needs to pre-create an LTI or split
    the sheet by batch or company before uploading. Waybills are then
    created under the matching LTI for each row.

    Returns (created, skipped, errors, lti_summary, unmatched_transporters).
    lti_summary is a list of (LTI, created_count, was_created) for every
    batch touched by this upload, across every company found in the sheet.
    unmatched_transporters is the sorted set of distinct Transporter Name
    values that didn't match a registered company — the list to register
    before re-uploading, without digging through per-row error text.
    """
    records = read_uploaded_rows(uploaded_file)
    if not records:
        raise ImportError_("No data rows were found in the file.")

    # Preserve first-seen order of (company, batch) so the summary reads
    # top-to-bottom the way the sheet does.
    batches = {}
    skipped, errors = 0, []
    unmatched_transporters = set()
    for i, rec in enumerate(records, start=1):
        transporter_name = _clean_text(rec.get('transporter_name'))
        if not transporter_name:
            skipped += 1
            errors.append(f"Row {i}: missing Transporter Name — skipped.")
            continue

        company = match_company_by_transporter_name(transporter_name)
        if company is None:
            skipped += 1
            unmatched_transporters.add(transporter_name)
            continue

        batch_key = _clean_text(rec.get('lti_number')) or _clean_text(rec.get('sto')) or UNSPECIFIED_BATCH_LABEL
        batches.setdefault((company.pk, batch_key), {'company': company, 'rows': []})
        batches[(company.pk, batch_key)]['rows'].append((i, rec))

    created = 0
    lti_summary = []

    for (company_pk, batch_key), batch in batches.items():
        company = batch['company']
        rows = batch['rows']
        lti, was_created = LTI.objects.get_or_create(
            company=company,
            lti_number=batch_key,
            defaults={
                'sto': _clean_text(rows[0][1].get('sto')),
                'created_by': user,
            },
        )
        batch_created = 0
        for i, rec in rows:
            waybill, reason = _create_waybill_from_record(rec, lti, user)
            if waybill is None:
                skipped += 1
                errors.append(f"Row {i}: {reason}")
                continue
            created += 1
            batch_created += 1

        if was_created and batch_created == 0:
            # Every row in this batch failed validation (e.g. no usable STO
            # and no waybill data) — don't leave an empty LTI behind.
            lti.delete()
            continue

        lti_summary.append((lti, batch_created, was_created))

    return created, skipped, errors, lti_summary, sorted(unmatched_transporters)