from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, ListView, View

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin
from companies.models import Company

from . import import_export as ie
from .forms import LTIForm
from .models import LTI, Waybill


# ---------- Company: manage own LTIs & waybills (isolated to their company) ----------

class CompanyLTIListView(CompanyRequiredMixin, ListView):
    model = LTI
    template_name = 'waybills/company_lti_list.html'
    context_object_name = 'ltis'
    paginate_by = 20

    def get_queryset(self):
        qs = LTI.objects.filter(company=self.get_company())
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = LTI.Status.choices
        return ctx


class CompanyLTICreateView(CompanyRequiredMixin, CreateView):
    model = LTI
    form_class = LTIForm
    template_name = 'waybills/company_lti_form.html'

    def form_valid(self, form):
        lti = form.save(commit=False)
        lti.company = self.get_company()
        lti.created_by = self.request.user
        lti.save()
        messages.success(self.request, f"LTI '{lti.lti_number}' created.")
        return redirect('waybills:company_lti_detail', pk=lti.pk)


class CompanyLTIDetailView(CompanyRequiredMixin, DetailView):
    model = LTI
    template_name = 'waybills/company_lti_detail.html'
    context_object_name = 'lti'

    def get_queryset(self):
        return LTI.objects.filter(company=self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['waybills'] = self.object.waybills.all()
        return ctx


class CompanyWaybillListView(CompanyRequiredMixin, ListView):
    """Every waybill belonging to the logged-in company, across all its
    LTIs, filterable by LTI, waybill number, origin and destination."""
    model = Waybill
    template_name = 'waybills/company_waybill_list.html'
    context_object_name = 'waybills'
    paginate_by = 25

    def get_queryset(self):
        qs = Waybill.objects.filter(lti__company=self.get_company()).select_related('lti', 'truck', 'driver')
        return _apply_waybill_filters(qs, self.request.GET, company_scoped=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = Waybill.objects.filter(lti__company=self.get_company())
        ctx.update(_waybill_filter_context(self.get_company().ltis.all(), base_qs))
        return ctx


# NOTE: adding and editing individual waybills is restricted to admins.
# CompanyWaybillCreateView / CompanyWaybillUpdateView were removed along
# with their URLs so company accounts cannot reach them by typing the
# address. Companies keep read, filter, download and bulk import.

class CompanyLTIImportView(CompanyRequiredMixin, View):
    """Bulk-create LTIs for the logged-in company from an uploaded .csv/.xlsx."""

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            messages.error(request, "Please choose a .csv or .xlsx file to upload.")
            return redirect('waybills:company_lti_list')
        try:
            created, skipped, errors = ie.import_ltis(upload, self.get_company(), request.user)
        except ie.ImportError_ as exc:
            messages.error(request, str(exc))
            return redirect('waybills:company_lti_list')

        if created:
            messages.success(request, f"Imported {created} LTI(s).")
        if skipped:
            messages.warning(request, f"Skipped {skipped} row(s). " + " ".join(errors[:5]))
        return redirect('waybills:company_lti_list')


class CompanyLTIExportView(CompanyRequiredMixin, View):
    """Download the company's own LTIs as .csv or .xlsx."""

    def get(self, request):
        qs = LTI.objects.filter(company=self.get_company())
        status = request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        headers, rows = ie.lti_export_rows(qs, include_company=False)
        fmt = request.GET.get('format', 'xlsx')
        if fmt == 'csv':
            return ie.rows_to_csv_response('ltis', headers, rows)
        return ie.rows_to_xlsx_response('ltis', 'LTIs', headers, rows)


class CompanyWaybillImportView(CompanyRequiredMixin, View):
    """Bulk-create waybills under one of the company's own LTIs."""

    def post(self, request, lti_pk):
        lti = get_object_or_404(LTI, pk=lti_pk, company=self.get_company())
        upload = request.FILES.get('file')
        if not upload:
            messages.error(request, "Please choose a .csv or .xlsx file to upload.")
            return redirect('waybills:company_lti_detail', pk=lti.pk)
        try:
            created, skipped, errors = ie.import_waybills(upload, lti, request.user)
        except ie.ImportError_ as exc:
            messages.error(request, str(exc))
            return redirect('waybills:company_lti_detail', pk=lti.pk)

        if created:
            messages.success(request, f"Imported {created} waybill(s) into {lti.lti_number}.")
        if skipped:
            messages.warning(request, f"Skipped {skipped} row(s). " + " ".join(errors[:5]))
        return redirect('waybills:company_lti_detail', pk=lti.pk)


class CompanyWaybillExportView(CompanyRequiredMixin, View):
    """Download the company's own waybills (respecting the current filters) as .csv or .xlsx."""

    def get(self, request):
        qs = Waybill.objects.filter(lti__company=self.get_company()).select_related('lti', 'truck', 'driver')
        qs = _apply_waybill_filters(qs, request.GET, company_scoped=True)
        headers, rows = ie.waybill_export_rows(qs, include_lti=True, include_company=False)
        fmt = request.GET.get('format', 'xlsx')
        if fmt == 'csv':
            return ie.rows_to_csv_response('waybills', headers, rows)
        return ie.rows_to_xlsx_response('waybills', 'Waybills', headers, rows)



# ---------- Admin: oversight across every company ----------

class AdminLTIListView(AdminRequiredMixin, ListView):
    model = LTI
    template_name = 'waybills/admin_lti_list.html'
    context_object_name = 'ltis'
    paginate_by = 25

    def get_queryset(self):
        qs = LTI.objects.select_related('company')
        company = self.request.GET.get('company')
        status = self.request.GET.get('status')
        if company:
            qs = qs.filter(company_id=company)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = LTI.Status.choices
        ctx['companies'] = Company.objects.all()
        return ctx


class AdminLTIDetailView(AdminRequiredMixin, DetailView):
    model = LTI
    template_name = 'waybills/admin_lti_detail.html'
    context_object_name = 'lti'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['waybills'] = self.object.waybills.all()
        return ctx


class AdminWaybillListView(AdminRequiredMixin, ListView):
    """Platform-wide waybill register, filterable by company, LTI, waybill
    number, origin and destination."""
    model = Waybill
    template_name = 'waybills/admin_waybill_list.html'
    context_object_name = 'waybills'
    paginate_by = 25

    def get_queryset(self):
        qs = Waybill.objects.select_related('lti', 'lti__company', 'truck', 'driver')
        return _apply_waybill_filters(qs, self.request.GET, company_scoped=False)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_waybill_filter_context(LTI.objects.all(), Waybill.objects.all()))
        ctx['companies'] = Company.objects.all()
        return ctx


class AdminLTIExportView(AdminRequiredMixin, View):
    """Download LTIs across every company as .csv or .xlsx."""

    def get(self, request):
        qs = LTI.objects.select_related('company')
        company = request.GET.get('company')
        status = request.GET.get('status')
        if company:
            qs = qs.filter(company_id=company)
        if status:
            qs = qs.filter(status=status)
        headers, rows = ie.lti_export_rows(qs, include_company=True)
        fmt = request.GET.get('format', 'xlsx')
        if fmt == 'csv':
            return ie.rows_to_csv_response('ltis', headers, rows)
        return ie.rows_to_xlsx_response('ltis', 'LTIs', headers, rows)


class AdminWaybillExportView(AdminRequiredMixin, View):
    """Download waybills across every company (respecting the current filters) as .csv or .xlsx."""

    def get(self, request):
        qs = Waybill.objects.select_related('lti', 'lti__company', 'truck', 'driver')
        qs = _apply_waybill_filters(qs, request.GET, company_scoped=False)
        headers, rows = ie.waybill_export_rows(qs, include_lti=True, include_company=True)
        fmt = request.GET.get('format', 'xlsx')
        if fmt == 'csv':
            return ie.rows_to_csv_response('waybills', headers, rows)
        return ie.rows_to_xlsx_response('waybills', 'Waybills', headers, rows)


class AdminWaybillBulkDeleteView(AdminRequiredMixin, View):
    """Delete multiple waybills, across every company, in one request. Two
    modes:

    - Specific rows: the form posts one 'waybill_ids' value per checked
      checkbox — only those rows are deleted.
    - Every matching record: the form posts select_all=1 (used by the
      "Delete all matching filters" action) along with the current filter
      values, so every waybill matching those filters is deleted —
      including rows on other pages, and across all companies unless a
      company filter is set.
    """

    def post(self, request):
        base_qs = Waybill.objects.all()

        if request.POST.get('select_all') == '1':
            qs = _apply_waybill_filters(base_qs, request.POST, company_scoped=False)
        else:
            ids = request.POST.getlist('waybill_ids')
            qs = base_qs.filter(pk__in=ids)

        count = qs.count()
        if count:
            qs.delete()
            messages.success(request, f"Deleted {count} waybill(s).")
        else:
            messages.warning(request, "No waybills were selected for deletion.")
        return redirect('waybills:admin_waybill_list')


class AdminTransitImportView(AdminRequiredMixin, View):
    """
    Bulk-import waybills straight from a raw transit tracking sheet
    (.csv/.xlsx) — e.g. the WFP transit template — without requiring an LTI
    to be created first, and without the admin needing to pick a company:
    each row's company is resolved automatically from its 'Transporter
    Name' cell, matched against registered company names. A single upload
    can carry rows for several different companies at once — each lands
    under its own company's LTIs/waybills. Rows grouped by LTI No./STO get
    matching LTIs looked up or created automatically per company.
    """

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            messages.error(request, "Please choose a .csv or .xlsx file to upload.")
            return redirect('waybills:admin_waybill_list')
        try:
            created, skipped, errors, lti_summary, unmatched_transporters = ie.import_transit_sheet(
                upload, request.user
            )
        except ie.ImportError_ as exc:
            messages.error(request, str(exc))
            return redirect('waybills:admin_waybill_list')

        if created:
            batch_count = len(lti_summary)
            new_ltis = sum(1 for _, _, was_created in lti_summary if was_created)
            company_count = len({lti.company_id for lti, _, _ in lti_summary})
            messages.success(
                request,
                f"Imported {created} waybill(s) across {company_count} "
                f"compan{'y' if company_count == 1 else 'ies'} and {batch_count} "
                f"batch(es) ({new_ltis} new LTI(s) created)."
            )
        if unmatched_transporters:
            unmatched_rows = skipped - len(errors)
            messages.warning(
                request,
                f"Skipped {unmatched_rows} row(s) — no registered company matches these "
                f"transporter name(s): {', '.join(unmatched_transporters)}. Register each "
                f"one under Companies (using this exact name, or a name that contains it), "
                f"then re-upload the sheet to bring in their rows."
            )
        if errors:
            messages.warning(request, f"Skipped {len(errors)} other row(s). " + " ".join(errors[:5]))
        return redirect('waybills:admin_waybill_list')


# ---------- Shared filter helpers ----------

def _apply_waybill_filters(qs, params, company_scoped):
    if not company_scoped:
        company = params.get('company')
        if company:
            qs = qs.filter(lti__company_id=company)
    lti = params.get('lti')
    if lti:
        qs = qs.filter(lti_id=lti)
    waybill = params.get('waybill')
    if waybill:
        qs = qs.filter(waybill_number__icontains=waybill)
    origin = params.get('origin')
    if origin:
        qs = qs.filter(origin__icontains=origin)
    destination = params.get('destination')
    if destination:
        qs = qs.filter(destination__icontains=destination)
    status = params.get('status')
    if status:
        qs = qs.filter(status=status)
    return qs


def _waybill_filter_context(lti_queryset, base_waybill_qs):
    return {
        'ltis': lti_queryset,
        'status_choices': Waybill.TransitStatus.choices,
        'origins': base_waybill_qs.order_by('origin').values_list('origin', flat=True).distinct(),
        'destinations': base_waybill_qs.order_by('destination').values_list('destination', flat=True).distinct(),
    }