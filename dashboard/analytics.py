"""Analytics aggregation for the admin analysis page.

Everything the page renders is computed here so the view stays thin and the
numbers can be unit-tested on their own. Each helper returns plain dicts and
lists — no querysets leak into the template, so nothing triggers a surprise
query while rendering.
"""

from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from companies.models import Company, CompanyDocument
from drivers.models import Driver, DriverDocument
from transit.models import Transit
from trucks.models import Truck, TruckDocument
from waybills.models import LTI, Waybill

# Fixed colour per entity — validated with the dataviz palette validator
# (adjacent CVD ΔE 9.9, normal-vision ΔE 24.0 on a white surface). Colour
# follows the entity everywhere on the page, never its rank, so filtering
# never repaints a survivor.
TRANSIT_STATUS_COLORS = {
    'PENDING': '#eda100',
    'IN_TRANSIT': '#2a78d6',
    'DELIVERED': '#1baf7a',
    'CANCELLED': '#d03b3b',
}

TRUCK_STATUS_COLORS = {
    'AVAILABLE': '#1baf7a',
    'ON_TRIP': '#2a78d6',
    'MAINTENANCE': '#eda100',
    'INACTIVE': '#94a3b8',
}

WAYBILL_STATUS_COLORS = {
    'PENDING': '#eda100',
    'IN_TRANSIT': '#2a78d6',
    'OFFLOADED': '#1baf7a',
    'CANCELLED': '#d03b3b',
}

SERIES_BLUE = '#2a78d6'

PERIOD_CHOICES = [
    ('30', 'Last 30 days'),
    ('90', 'Last 90 days'),
    ('365', 'Last 12 months'),
    ('all', 'All time'),
]


# ---------- small helpers ----------

def _pct(part, whole):
    """Percentage as a plain float.

    Coerces both sides: tonnage arrives as Decimal and counts as int, and
    mixing Decimal with float raises TypeError — which would take the whole
    page down the first time a commodity ranking was drawn.
    """
    if not whole:
        return 0.0
    return round(float(part) * 100.0 / float(whole), 1)


def _share_rows(counts, labels, colors, total):
    """Rows for a composition bar: label, count, %, colour — in a fixed order."""
    rows = []
    for value, label in labels:
        count = counts.get(value, 0)
        rows.append({
            'key': value,
            'label': label,
            'count': count,
            'pct': _pct(count, total),
            'color': colors.get(value, SERIES_BLUE),
        })
    return rows


def _ranked(rows, value_key):
    """Add a `bar_pct` sized against the biggest row, for ranked bar charts."""
    top = max((float(r[value_key] or 0) for r in rows), default=0.0)
    for row in rows:
        row['bar_pct'] = _pct(row[value_key] or 0, top) if top else 0
    return rows


def _num(value):
    if value is None:
        return Decimal('0')
    return value


# ---------- the report ----------

def build_analytics(company=None, period='all'):
    """Assemble every figure the analysis page shows.

    `company` limits the whole report to one company; `period` is one of the
    PERIOD_CHOICES keys and limits the time-bound sections (transits and
    waybills) without distorting the standing fleet counts.
    """
    now = timezone.now()
    today = timezone.localdate()

    cutoff = None
    if period and period != 'all':
        try:
            cutoff = now - timedelta(days=int(period))
        except (TypeError, ValueError):
            cutoff = None

    # --- base querysets, scoped ---
    companies = Company.objects.all()
    trucks = Truck.objects.all()
    drivers = Driver.objects.all()
    transits = Transit.objects.all()
    waybills = Waybill.objects.all()
    ltis = LTI.objects.all()

    if company is not None:
        companies = companies.filter(pk=company.pk)
        trucks = trucks.filter(company=company)
        drivers = drivers.filter(company=company)
        transits = transits.filter(company=company)
        waybills = waybills.filter(lti__company=company)
        ltis = ltis.filter(company=company)

    if cutoff is not None:
        transits = transits.filter(created_at__gte=cutoff)
        waybills = waybills.filter(created_at__gte=cutoff)

    # --- headline counts ---
    truck_total = trucks.count()
    transit_total = transits.count()
    waybill_total = waybills.count()

    status_counts = {
        row['status']: row['n']
        for row in transits.values('status').annotate(n=Count('id'))
    }
    truck_status_counts = {
        row['status']: row['n']
        for row in trucks.values('status').annotate(n=Count('id'))
    }
    waybill_status_counts = {
        row['status']: row['n']
        for row in waybills.values('status').annotate(n=Count('id'))
    }

    delivered_count = status_counts.get(Transit.Status.DELIVERED, 0)
    in_transit_count = status_counts.get(Transit.Status.IN_TRANSIT, 0)
    on_trip_count = truck_status_counts.get(Truck.Status.ON_TRIP, 0)

    delivered_tonnage = _num(
        transits.filter(status=Transit.Status.DELIVERED)
        .aggregate(total=Sum('cargo_weight_tons'))['total']
    )
    waybill_tonnage = _num(waybills.aggregate(total=Sum('weight_mt'))['total'])
    moving_tonnage = _num(
        transits.filter(status=Transit.Status.IN_TRANSIT)
        .aggregate(total=Sum('cargo_weight_tons'))['total']
    )

    # --- average time on the road (computed in Python: small N, and it
    #     keeps duration arithmetic off SQLite) ---
    durations = [
        (t.actual_arrival - t.actual_departure).total_seconds()
        for t in transits.filter(
            status=Transit.Status.DELIVERED,
            actual_departure__isnull=False,
            actual_arrival__isnull=False,
        ).only('actual_departure', 'actual_arrival')
        if t.actual_arrival >= t.actual_departure
    ]
    avg_days = round(sum(durations) / len(durations) / 86400, 1) if durations else None

    # --- monthly delivery trend (last 12 calendar months) ---
    months = []
    cursor = today.replace(day=1)
    for _ in range(12):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()

    monthly = OrderedDict((m, {'count': 0, 'tonnage': Decimal('0')}) for m in months)
    delivered_rows = transits.filter(
        status=Transit.Status.DELIVERED, actual_arrival__isnull=False
    ).values_list('actual_arrival', 'cargo_weight_tons')

    for arrival, weight in delivered_rows:
        key = timezone.localtime(arrival).date().replace(day=1)
        if key in monthly:
            monthly[key]['count'] += 1
            monthly[key]['tonnage'] += _num(weight)

    max_month_count = max((v['count'] for v in monthly.values()), default=0)
    max_month_tonnage = max((v['tonnage'] for v in monthly.values()), default=Decimal('0'))

    trend = [
        {
            'label': m.strftime('%b'),
            'full_label': m.strftime('%B %Y'),
            'count': v['count'],
            'tonnage': v['tonnage'],
            'count_pct': _pct(v['count'], max_month_count),
            'tonnage_pct': _pct(float(v['tonnage']), float(max_month_tonnage)) if max_month_tonnage else 0,
        }
        for m, v in monthly.items()
    ]

    # --- rankings ---
    routes = _ranked([
        {
            'label': f"{r['origin']} → {r['destination']}",
            'trips': r['n'],
            'tonnage': _num(r['mt']),
        }
        for r in transits.values('origin', 'destination')
        .annotate(n=Count('id'), mt=Sum('cargo_weight_tons'))
        .order_by('-n')[:8]
    ], 'trips')

    company_rows = _ranked([
        {
            'label': r['company__name'],
            'trips': r['n'],
            'delivered': r['delivered'],
            'tonnage': _num(r['mt']),
        }
        for r in transits.values('company__name')
        .annotate(
            n=Count('id'),
            delivered=Count('id', filter=Q(status=Transit.Status.DELIVERED)),
            mt=Sum('cargo_weight_tons', filter=Q(status=Transit.Status.DELIVERED)),
        )
        .order_by('-n')[:8]
    ], 'trips')

    driver_rows = _ranked([
        {
            'label': r['driver__full_name'],
            'trips': r['n'],
            'delivered': r['delivered'],
        }
        for r in transits.filter(driver__isnull=False)
        .values('driver__full_name')
        .annotate(
            n=Count('id'),
            delivered=Count('id', filter=Q(status=Transit.Status.DELIVERED)),
        )
        .order_by('-n')[:8]
    ], 'trips')

    truck_rows = _ranked([
        {
            'label': r['truck__registration_number'],
            'trips': r['n'],
            'tonnage': _num(r['mt']),
        }
        for r in transits.values('truck__registration_number')
        .annotate(n=Count('id'), mt=Sum('cargo_weight_tons'))
        .order_by('-n')[:8]
    ], 'trips')

    commodity_rows = _ranked([
        {
            'label': r['commodity'] or 'Unspecified',
            'loads': r['n'],
            'tonnage': _num(r['mt']),
        }
        for r in waybills.values('commodity')
        .annotate(n=Count('id'), mt=Sum('weight_mt'))
        .order_by('-mt')[:6]
    ], 'tonnage')

    # --- compliance: documents expiring or already expired ---
    doc_sets = (
        list(CompanyDocument.objects.select_related('company')),
        list(DriverDocument.objects.select_related('driver')),
        list(TruckDocument.objects.select_related('truck')),
    )
    expired = expiring = 0
    for docs in doc_sets:
        for doc in docs:
            if doc.is_expired:
                expired += 1
            elif doc.is_expiring_soon:
                expiring += 1

    expired_licences = drivers.filter(
        license_expiry__isnull=False, license_expiry__lt=today
    ).count()

    return {
        'generated_at': now,
        'period': period,
        'period_label': dict(PERIOD_CHOICES).get(period, 'All time'),
        'scoped_company': company,

        # headline
        'company_count': companies.count(),
        'active_company_count': companies.filter(status=Company.Status.ACTIVE).count(),
        'truck_count': truck_total,
        'driver_count': drivers.count(),
        'transit_count': transit_total,
        'waybill_count': waybill_total,
        'lti_count': ltis.count(),

        'delivered_count': delivered_count,
        'in_transit_count': in_transit_count,
        'delivered_tonnage': delivered_tonnage,
        'moving_tonnage': moving_tonnage,
        'waybill_tonnage': waybill_tonnage,
        'completion_rate': _pct(delivered_count, transit_total),
        'utilisation_rate': _pct(on_trip_count, truck_total),
        'avg_days': avg_days,
        'trucks_on_trip': on_trip_count,
        'trucks_idle': truck_status_counts.get(Truck.Status.AVAILABLE, 0),

        # compositions
        'transit_status_rows': _share_rows(
            status_counts, Transit.Status.choices, TRANSIT_STATUS_COLORS, transit_total
        ),
        'truck_status_rows': _share_rows(
            truck_status_counts, Truck.Status.choices, TRUCK_STATUS_COLORS, truck_total
        ),
        'waybill_status_rows': _share_rows(
            waybill_status_counts, Waybill.TransitStatus.choices, WAYBILL_STATUS_COLORS, waybill_total
        ),

        # series & rankings
        'trend': trend,
        'trend_total': sum(r['count'] for r in trend),
        'routes': routes,
        'company_rows': company_rows,
        'driver_rows': driver_rows,
        'truck_rows': truck_rows,
        'commodity_rows': commodity_rows,

        # compliance
        'docs_expired': expired,
        'docs_expiring': expiring,
        'expired_licences': expired_licences,

        'series_blue': SERIES_BLUE,
    }
