from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin

from .forms import TruckConsignmentUpdateForm, TruckDocumentForm, TruckForm, TruckLocationUpdateForm
from .models import Truck


# ---------- Admin: track all trucks, view documents (read-only oversight) ----------

class AdminTruckListView(AdminRequiredMixin, ListView):
    """The admin's truck-tracking board across every company."""
    model = Truck
    template_name = 'trucks/admin_truck_list.html'
    context_object_name = 'trucks'
    paginate_by = 25

    def get_queryset(self):
        qs = Truck.objects.select_related('company', 'assigned_driver')
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        location = self.request.GET.get('location')
        if q:
            qs = qs.filter(registration_number__icontains=q)
        if status:
            qs = qs.filter(status=status)
        if location:
            qs = qs.filter(last_known_location__icontains=location)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Truck.Status.choices
        return ctx


class AdminTruckDetailView(AdminRequiredMixin, DetailView):
    model = Truck
    template_name = 'trucks/admin_truck_detail.html'
    context_object_name = 'truck'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['transits'] = self.object.transits.all()[:10]
        return ctx


class AdminTruckBulkDeleteView(AdminRequiredMixin, View):
    """Delete multiple trucks, across any company, in one request. Trucks
    that are referenced by a transit (Transit.truck is on_delete=PROTECT)
    can't be removed, so those are skipped and reported back instead of
    failing the whole batch."""

    def post(self, request):
        ids = request.POST.getlist('truck_ids')
        trucks = Truck.objects.filter(pk__in=ids)

        deleted = 0
        blocked = []
        for truck in trucks:
            try:
                truck.delete()
                deleted += 1
            except ProtectedError:
                blocked.append(truck.registration_number)

        if deleted:
            messages.success(request, f"Deleted {deleted} truck(s).")
        if blocked:
            messages.warning(
                request,
                "Could not delete " + ", ".join(blocked) +
                " — they have transit records linked to them."
            )
        if not deleted and not blocked:
            messages.warning(request, "No trucks were selected for deletion.")
        return redirect('trucks:admin_list')


# ---------- Company: manage their own trucks & transit-readiness ----------

class CompanyTruckListView(CompanyRequiredMixin, ListView):
    model = Truck
    template_name = 'trucks/company_truck_list.html'
    context_object_name = 'trucks'
    paginate_by = 20

    def get_queryset(self):
        qs = Truck.objects.filter(company=self.get_company()).select_related('assigned_driver')
        location = self.request.GET.get('location')
        if location:
            qs = qs.filter(last_known_location__icontains=location)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['location_update_form'] = TruckLocationUpdateForm()
        return ctx


class CompanyTruckCreateView(CompanyRequiredMixin, CreateView):
    model = Truck
    form_class = TruckForm
    template_name = 'trucks/company_truck_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.get_company()
        return kwargs

    def form_valid(self, form):
        truck = form.save(commit=False)
        truck.company = self.get_company()
        truck.save()
        messages.success(self.request, f"Truck '{truck.registration_number}' added to your fleet.")
        return redirect('trucks:company_detail', pk=truck.pk)



class CompanyTruckDetailView(CompanyRequiredMixin, DetailView):
    model = Truck
    template_name = 'trucks/company_truck_detail.html'
    context_object_name = 'truck'

    def get_queryset(self):
        return Truck.objects.filter(company=self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['document_form'] = TruckDocumentForm()
        ctx['location_form'] = TruckLocationUpdateForm(instance=self.object)
        ctx['consignment_form'] = TruckConsignmentUpdateForm(instance=self.object)
        ctx['transits'] = self.object.transits.all()[:10]
        return ctx


class CompanyTruckUpdateView(CompanyRequiredMixin, UpdateView):
    model = Truck
    form_class = TruckForm
    template_name = 'trucks/company_truck_form.html'

    def get_queryset(self):
        return Truck.objects.filter(company=self.get_company())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.get_company()
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Truck details updated.")
        return reverse_lazy('trucks:company_detail', kwargs={'pk': self.object.pk})


class CompanyTruckDocumentUploadView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        truck = get_object_or_404(Truck, pk=pk, company=self.get_company())
        form = TruckDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.truck = truck
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
        else:
            messages.error(request, "Could not upload document. Please check the form.")
        return redirect('trucks:company_detail', pk=truck.pk)


class CompanyTruckLocationUpdateView(CompanyRequiredMixin, View):
    """Manual 'where is this truck now' update. Kept separate from the GPS
    fields so a future GPS integration can write to the same Truck record
    without conflicting with manual entries."""

    def post(self, request, pk):
        truck = get_object_or_404(Truck, pk=pk, company=self.get_company())
        form = TruckLocationUpdateForm(request.POST, instance=truck)
        if form.is_valid():
            truck = form.save(commit=False)
            truck.last_location_updated_at = timezone.now()
            truck.save()
            messages.success(request, "Truck location & status updated.")
        else:
            messages.error(request, "Could not update location.")
        return redirect('trucks:company_detail', pk=truck.pk)


class CompanyTruckConsignmentUpdateView(CompanyRequiredMixin, View):
    """Quick update for the current load's waybill/LTI number, origin,
    destination and commodities — these change with every trip."""

    def post(self, request, pk):
        truck = get_object_or_404(Truck, pk=pk, company=self.get_company())
        form = TruckConsignmentUpdateForm(request.POST, instance=truck)
        if form.is_valid():
            form.save()
            messages.success(request, "Current load details updated.")
        else:
            messages.error(request, "Could not update load details.")
        return redirect('trucks:company_detail', pk=truck.pk)