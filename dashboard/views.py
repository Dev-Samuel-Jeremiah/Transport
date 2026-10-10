from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin
from companies.models import Company, CompanyDocument
from drivers.models import Driver, DriverDocument
from trucks.models import Truck, TruckDocument
from transit.models import Transit, TrackingUpdate
from transit.services import backfill_transit_weights
from waybills.models import Waybill

from .analytics import PERIOD_CHOICES, build_analytics


@login_required
def redirect_by_role(request):
    if request.user.is_admin_role:
        if request.user.password_is_temporary:
            return redirect('accounts:admin_profile')
        return redirect('dashboard:admin_home')
    if request.user.is_driver_role:
        return redirect('drivers:profile')
    if request.user.company_id and request.user.password_is_temporary:
        return redirect('companies:profile')
    return redirect('dashboard:company_home')


class AdminHomeView(AdminRequiredMixin, TemplateView):
    template_name = 'dashboard/admin_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        docs = list(CompanyDocument.objects.select_related('company')) + \
               list(DriverDocument.objects.select_related('driver')) + \
               list(TruckDocument.objects.select_related('truck'))
        expiring = [d for d in docs if d.is_expiring_soon or d.is_expired]

        ctx.update({
            'company_count': Company.objects.count(),
            'driver_count': Driver.objects.count(),
            'truck_count': Truck.objects.count(),
            'waybill_count': Waybill.objects.count(),
            'delivered_count': Transit.objects.filter(status=Transit.Status.DELIVERED).count(),
            'trucks_on_trip': Truck.objects.filter(status=Truck.Status.ON_TRIP).count(),
            'active_transits': Transit.objects.filter(status=Transit.Status.IN_TRANSIT).select_related(
                'company', 'truck', 'driver'
            )[:8],
            'recent_companies': Company.objects.order_by('-created_at')[:5],
            'expiring_documents': sorted(
                expiring, key=lambda d: (d.expiry_date is None, d.expiry_date)
            )[:8],
            'recent_tracking': TrackingUpdate.objects.select_related('transit', 'transit__truck')[:8],
            'recent_waybills': Waybill.objects.select_related('lti', 'lti__company', 'truck', 'driver')[:8],
        })
        return ctx


class CompanyHomeView(CompanyRequiredMixin, TemplateView):
    template_name = 'dashboard/company_home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        company = self.get_company()

        ctx.update({
            'company': company,
            'driver_count': company.drivers.count(),
            'truck_count': company.trucks.count(),
            'waybill_count': Waybill.objects.filter(lti__company=company).count(),
            'active_transits': company.transits.filter(status=Transit.Status.IN_TRANSIT).select_related(
                'truck', 'driver'
            ),
            'pending_transits': company.transits.filter(status=Transit.Status.PENDING).count(),
            # All-time completed deliveries — this is what the Delivered
            # stat card links through to on the Delivered Deliveries page.
            'delivered_count': company.transits.filter(
                status=Transit.Status.DELIVERED,
            ).count(),
            'delivered_this_month': company.transits.filter(
                status=Transit.Status.DELIVERED,
                actual_arrival__year=timezone.localdate().year,
                actual_arrival__month=timezone.localdate().month,
            ).count(),
            'recent_transits': company.transits.select_related('truck', 'driver')[:8],
            'trucks': company.trucks.select_related('assigned_driver')[:8],
            'recent_waybills': Waybill.objects.filter(lti__company=company).select_related('lti', 'truck', 'driver')[:8],
        })
        return ctx


class AdminAnalyticsView(AdminRequiredMixin, TemplateView):
    """Platform-wide analysis. Admin only — the whole point of the page is
    the cross-company view, so it is never exposed to a company account."""

    template_name = 'dashboard/admin_analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Tonnage drives most of this page, so make sure it is resolved from
        # the waybills before anything is summed.
        backfill_transit_weights(Transit.objects.all())

        company = None
        company_id = self.request.GET.get('company')
        if company_id:
            company = Company.objects.filter(pk=company_id).first()

        period = self.request.GET.get('period') or 'all'
        if period not in dict(PERIOD_CHOICES):
            period = 'all'

        ctx.update(build_analytics(company=company, period=period))
        ctx['companies'] = Company.objects.order_by('name')
        ctx['period_choices'] = PERIOD_CHOICES
        return ctx
