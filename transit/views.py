from django.contrib import messages
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import DetailView, ListView, View

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin
from trucks.forms import TruckLocationUpdateForm
from trucks.models import Truck

from .export import delivered_export_rows, spreadsheet_response, transit_export_rows
from .filters import apply_delivered_filters, apply_transit_filters
from .forms import TransitInlineStatusForm, TransitStatusUpdateForm, generate_reference_code
from .models import Transit
from .services import backfill_transit_weights, build_truck_weight_map


# ---------- Company: full trip lifecycle management ----------

class CompanyTransitListView(CompanyRequiredMixin, ListView):
    model = Transit
    template_name = 'transit/company_transit_list.html'
    context_object_name = 'transits'
    paginate_by = 20

    def _sync_transits_from_truck_records(self, company):
        """Auto-create a Transit straight from each truck's saved record —
        driver, origin, destination, capacity — for any truck that's
        carrying a route on file but doesn't have an active transit yet.
        This is what makes the register self-populating: a company sets a
        truck's current load once (on the Trucks page) and the trip shows
        up here on its own, no separate "New Transit" step required.

        A truck only gets skipped once it already has a PENDING or
        IN_TRANSIT transit open — so finishing (Delivered/Cancelled) a
        trip and loading the truck again on a new route will pick up and
        create the next one automatically too.
        """
        trucks_with_open_transit = Transit.objects.filter(
            company=company,
            status__in=[Transit.Status.PENDING, Transit.Status.IN_TRANSIT],
        ).values_list('truck_id', flat=True)

        candidate_trucks = list(
            company.trucks
            .exclude(pk__in=trucks_with_open_transit)
            .exclude(origin='')
            .exclude(destination='')
            .select_related('assigned_driver')
        )

        # MT comes off the waybill covering each truck's load — capacity_tons
        # is a vehicle spec and is blank on most fleets.
        weight_map = build_truck_weight_map(candidate_trucks)

        for truck in candidate_trucks:
            transit = Transit.objects.create(
                company=company,
                truck=truck,
                driver=truck.assigned_driver,
                reference_code=generate_reference_code(),
                origin=truck.origin,
                destination=truck.destination,
                cargo_weight_tons=weight_map.get(truck.pk) or truck.capacity_tons,
                status=Transit.Status.IN_TRANSIT if truck.status == Truck.Status.ON_TRIP else Transit.Status.PENDING,
                created_by=self.request.user,
            )
            transit.tracking_updates.create(
                status=transit.status,
                location_text=truck.last_known_location or transit.origin,
                source='MANUAL',
                remarks='Auto-created from the truck\'s saved record.',
                recorded_by=self.request.user,
            )

    def get_queryset(self):
        company = self.get_company()
        self._sync_transits_from_truck_records(company)
        backfill_transit_weights(Transit.objects.filter(company=company))

        qs = Transit.objects.filter(
            company=company, is_archived=False
        ).select_related('truck', 'driver')
        return apply_transit_filters(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Transit.Status.choices
        ctx['inline_status_form'] = TransitInlineStatusForm()
        # Powers the "Edit" button on the Truck Position column — the same
        # quick position update used on the trucks page, without leaving
        # the transit register.
        ctx['location_update_form'] = TruckLocationUpdateForm()
        return ctx



# NOTE: creating a transit by hand is an admin action. The company-facing
# CompanyTransitCreateView was removed with its URL, so a company account
# cannot reach it by typing the address. Transits still appear for them
# automatically from each truck's saved route (see the sync above).

class CompanyTransitDetailView(CompanyRequiredMixin, DetailView):
    model = Transit
    template_name = 'transit/company_transit_detail.html'
    context_object_name = 'transit'

    def get_queryset(self):
        return Transit.objects.filter(company=self.get_company()).select_related('truck', 'driver')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tracking_updates'] = self.object.tracking_updates.all()
        ctx['status_form'] = TransitStatusUpdateForm()
        return ctx


class CompanyDeliveredListView(CompanyRequiredMixin, ListView):
    """Permanent record of every completed delivery for this company.

    Unlike the active register, this keeps DELIVERED trips regardless of
    whether an admin has since confirmed them into the audit log — so a
    delivery never disappears from the company's own history.
    """

    model = Transit
    template_name = 'transit/company_delivered_list.html'
    context_object_name = 'transits'
    paginate_by = 25

    def _base_queryset(self):
        return Transit.objects.filter(
            company=self.get_company(),
            status=Transit.Status.DELIVERED,
        )

    def get_queryset(self):
        backfill_transit_weights(self._base_queryset())
        qs = self._base_queryset().select_related('truck', 'driver')
        qs = apply_delivered_filters(qs, self.request.GET)
        return qs.order_by(F('actual_arrival').desc(nulls_last=True), '-updated_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = self._base_queryset()
        today = timezone.localdate()

        ctx.update({
            'total_delivered': base.count(),
            'delivered_this_month': base.filter(
                actual_arrival__year=today.year,
                actual_arrival__month=today.month,
            ).count(),
            'total_tonnage': base.aggregate(total=Sum('cargo_weight_tons'))['total'],
            # order_by() clears Meta.ordering, which would otherwise leak
            # created_at into the SELECT and break DISTINCT.
            'destinations_served': base.order_by().values('destination').distinct().count(),
            'destination_choices': (
                base.order_by('destination')
                .values_list('destination', flat=True)
                .distinct()
            ),
            'filtered_count': self.object_list.count(),
            'has_filters': any(
                self.request.GET.get(key) for key in ('q', 'destination', 'from', 'to')
            ),
            'current_filters': {
                'q': self.request.GET.get('q', ''),
                'destination': self.request.GET.get('destination', ''),
                'from': self.request.GET.get('from', ''),
                'to': self.request.GET.get('to', ''),
            },
        })
        return ctx


class CompanyTransitExportView(CompanyRequiredMixin, View):
    """Download this company's transit register as .xlsx (default) or .csv.

    Scoped to `get_company()`, so a company account can only ever pull its
    own rows — there is no parameter that widens it.
    """

    def get(self, request):
        company = self.get_company()
        backfill_transit_weights(Transit.objects.filter(company=company))

        qs = Transit.objects.filter(
            company=company, is_archived=False
        ).select_related('truck', 'driver')
        qs = apply_transit_filters(qs, request.GET)

        headers, rows = transit_export_rows(qs, include_company=False)
        return spreadsheet_response(request, 'transits', 'Transits', headers, rows)


class CompanyDeliveredExportView(CompanyRequiredMixin, View):
    """Download this company's delivered record as .xlsx (default) or .csv."""

    def get(self, request):
        company = self.get_company()
        base = Transit.objects.filter(company=company, status=Transit.Status.DELIVERED)
        backfill_transit_weights(base)

        qs = apply_delivered_filters(
            base.select_related('truck', 'driver'), request.GET
        ).order_by(F('actual_arrival').desc(nulls_last=True), '-updated_at')

        headers, rows = delivered_export_rows(qs, include_company=False)
        return spreadsheet_response(request, 'delivered-transits', 'Delivered', headers, rows)


class CompanyTransitStatusUpdateView(CompanyRequiredMixin, View):
    """Posts a tracking checkpoint and keeps the transit + truck status in sync."""

    def post(self, request, pk):
        transit = get_object_or_404(Transit, pk=pk, company=self.get_company())
        form = TransitStatusUpdateForm(request.POST)
        if form.is_valid():
            update = form.save(commit=False)
            update.transit = transit
            update.source = 'MANUAL'
            update.recorded_by = request.user
            update.save()

            transit.status = update.status
            now = timezone.now()
            if update.status == Transit.Status.IN_TRANSIT and not transit.actual_departure:
                transit.actual_departure = now
            if update.status in (Transit.Status.DELIVERED, Transit.Status.CANCELLED):
                transit.actual_arrival = now
            transit.save()

            truck = transit.truck
            if update.status == Transit.Status.IN_TRANSIT:
                truck.status = Truck.Status.ON_TRIP
            elif update.status in (Transit.Status.DELIVERED, Transit.Status.CANCELLED):
                truck.status = Truck.Status.AVAILABLE
            if update.location_text:
                truck.last_known_location = update.location_text
                truck.last_location_updated_at = now
            truck.save()

            messages.success(request, f"Status updated to {transit.get_status_display()}.")
        else:
            messages.error(request, "Could not record update. Please check the form.")

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('transit:company_detail', pk=transit.pk)


# ---------- Admin: oversight of all transits ----------

def _safe_next(request, fallback):
    """Return the posted `next` URL if it's local to this site, else the fallback."""
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return reverse(fallback)


class AdminTransitListView(AdminRequiredMixin, ListView):
    model = Transit
    template_name = 'transit/admin_transit_list.html'
    context_object_name = 'transits'
    paginate_by = 25

    def get_queryset(self):
        backfill_transit_weights(Transit.objects.all())
        qs = Transit.objects.filter(is_archived=False).select_related('company', 'truck', 'driver')
        return apply_transit_filters(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Transit.Status.choices
        return ctx

    def paginate_queryset(self, queryset, page_size):
        # Confirming moves rows off this list, so the page the admin was on
        # can disappear. get_page() falls back to the last valid page
        # instead of raising a 404.
        paginator = self.get_paginator(
            queryset, page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page = paginator.get_page(self.request.GET.get(self.page_kwarg))
        return paginator, page, page.object_list, page.has_other_pages()


class AdminTransitExportView(AdminRequiredMixin, View):
    """Download the transit register across every company, or one company
    when ?company=<id> is supplied."""

    def get(self, request):
        backfill_transit_weights(Transit.objects.all())

        qs = Transit.objects.filter(is_archived=False).select_related('company', 'truck', 'driver')
        qs = apply_transit_filters(qs, request.GET)

        headers, rows = transit_export_rows(qs, include_company=True)
        return spreadsheet_response(request, 'transits-all', 'Transits', headers, rows)


class AdminDeliveredExportView(AdminRequiredMixin, View):
    """Download every delivered transit across all companies — both those
    already confirmed into the audit log and those still awaiting it."""

    def get(self, request):
        base = Transit.objects.filter(status=Transit.Status.DELIVERED)
        backfill_transit_weights(base)

        qs = apply_delivered_filters(
            base.select_related('company', 'truck', 'driver'), request.GET
        ).order_by(F('actual_arrival').desc(nulls_last=True), '-updated_at')

        headers, rows = delivered_export_rows(qs, include_company=True)
        return spreadsheet_response(request, 'delivered-transits-all', 'Delivered', headers, rows)


class AdminTransitBulkDeleteView(AdminRequiredMixin, View):
    """Delete multiple transits, across any company, in one request.
    TrackingUpdate rows cascade automatically, so this is always safe."""

    def post(self, request):
        ids = request.POST.getlist('transit_ids')
        qs = Transit.objects.filter(pk__in=ids)
        count = qs.count()
        if count:
            qs.delete()
            messages.success(request, f"Deleted {count} transit(s).")
        else:
            messages.warning(request, "No transits were selected for deletion.")
        return redirect('transit:admin_list')


class AdminTransitConfirmView(AdminRequiredMixin, View):
    """Confirm a single transit from the admin register. Confirming moves it
    straight into the Audit log. Only DELIVERED transits can be confirmed —
    only completed trips belong in the audit trail."""

    def post(self, request, pk):
        transit = get_object_or_404(Transit, pk=pk, is_archived=False)

        if transit.status != Transit.Status.DELIVERED:
            messages.warning(
                request,
                f"{transit.reference_code} is {transit.get_status_display()} — "
                f"only Delivered transits can be confirmed.",
            )
        else:
            transit.is_archived = True
            transit.archived_at = timezone.now()
            transit.archived_by = request.user
            transit.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])
            messages.success(request, f"{transit.reference_code} confirmed and moved to Audit.")

        return redirect(_safe_next(request, 'transit:admin_list'))


class AdminTransitRestoreView(AdminRequiredMixin, View):
    """Undo a confirmation: send a transit from the Audit log back to the
    active register (safety net for a mis-clicked Confirm box)."""

    def post(self, request, pk):
        transit = get_object_or_404(Transit, pk=pk, is_archived=True)
        transit.is_archived = False
        transit.archived_at = None
        transit.archived_by = None
        transit.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])
        messages.success(request, f"{transit.reference_code} restored to the active register.")
        return redirect(_safe_next(request, 'transit:admin_audit_list'))


class AdminTransitAuditListView(AdminRequiredMixin, ListView):
    """Read-only record of transits archived out of the active register."""
    model = Transit
    template_name = 'transit/admin_transit_audit_list.html'
    context_object_name = 'transits'
    paginate_by = 25

    def get_queryset(self):
        return Transit.objects.filter(is_archived=True).select_related(
            'company', 'truck', 'driver', 'archived_by'
        ).order_by('-archived_at')


class AdminTransitDetailView(AdminRequiredMixin, DetailView):
    model = Transit
    template_name = 'transit/admin_transit_detail.html'
    context_object_name = 'transit'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tracking_updates'] = self.object.tracking_updates.all()
        return ctx