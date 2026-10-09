from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin, DriverRequiredMixin

from .forms import (
    TEMPORARY_PASSWORD,
    DriverAccountForm,
    DriverDocumentForm,
    DriverForm,
    DriverOnboardingForm,
    DriverPasswordForm,
    DriverProfileForm,
)
from .models import Driver


# ---------- Admin: full CRUD, registers drivers under any company ----------

class DriverListView(AdminRequiredMixin, ListView):
    model = Driver
    template_name = 'drivers/driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 20

    def get_queryset(self):
        qs = Driver.objects.select_related('company')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(full_name__icontains=q)
        return qs


class DriverBulkDeleteView(AdminRequiredMixin, View):
    """Delete multiple drivers, across any company, in one request. No
    model protects against deleting a Driver (Truck.assigned_driver,
    Transit.driver and Waybill.driver all fall back to null), so this is
    always safe and never partially blocked."""

    def post(self, request):
        ids = request.POST.getlist('driver_ids')
        qs = Driver.objects.filter(pk__in=ids)
        count = qs.count()
        if count:
            qs.delete()
            messages.success(request, f"Deleted {count} driver(s).")
        else:
            messages.warning(request, "No drivers were selected for deletion.")
        return redirect('drivers:list')


class DriverCreateView(AdminRequiredMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = 'drivers/driver_form.html'

    def get_initial(self):
        initial = super().get_initial()
        company_id = self.request.GET.get('company')
        if company_id:
            initial['company'] = company_id
        return initial

    def form_valid(self, form):
        driver = form.save(commit=False)
        driver.registered_by = self.request.user
        driver.save()
        messages.success(self.request, f"Driver '{driver.full_name}' registered under {driver.company.name}.")
        return redirect('drivers:detail', pk=driver.pk)


class DriverOnboardView(AdminRequiredMixin, CreateView):
    """Admin-only driver onboarding: registers the driver and issues their
    login in one pass, always with the shared temporary password.

    The company that owns the driver can then replace that password — and
    that is the only thing they can do to a driver login."""

    model = Driver
    form_class = DriverOnboardingForm
    template_name = 'drivers/driver_onboard.html'

    def get_initial(self):
        initial = super().get_initial()
        company_id = self.request.GET.get('company')
        if company_id:
            initial['company'] = company_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['temporary_password'] = TEMPORARY_PASSWORD
        ctx['pending_password_count'] = Driver.objects.filter(
            password_is_temporary=True, user__isnull=False
        ).count()
        ctx['recent_onboarded'] = (
            Driver.objects.filter(user__isnull=False)
            .select_related('company', 'user')
            .order_by('-created_at')[:6]
        )
        return ctx

    def form_valid(self, form):
        driver = form.save(registered_by=self.request.user)
        messages.success(
            self.request,
            f"{driver.full_name} registered under {driver.company.name}. "
            f"Login '{form.created_username}' created with the temporary password "
            f"'{TEMPORARY_PASSWORD}' — {driver.company.name} can change it from their Drivers page."
        )
        return redirect('drivers:detail', pk=driver.pk)


class DriverDetailView(AdminRequiredMixin, DetailView):
    model = Driver
    template_name = 'drivers/driver_detail.html'
    context_object_name = 'driver'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['document_form'] = DriverDocumentForm()
        ctx['account_form'] = DriverAccountForm(driver=self.object)
        return ctx


class DriverUpdateView(AdminRequiredMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = 'drivers/driver_form.html'

    def get_success_url(self):
        messages.success(self.request, "Driver details updated.")
        return reverse_lazy('drivers:detail', kwargs={'pk': self.object.pk})


class DriverDocumentUploadView(AdminRequiredMixin, View):
    def post(self, request, pk):
        driver = get_object_or_404(Driver, pk=pk)
        form = DriverDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.driver = driver
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
        else:
            messages.error(request, "Could not upload document. Please check the form.")
        return redirect('drivers:detail', pk=driver.pk)


class DriverAccountView(AdminRequiredMixin, View):
    """Admin action to create login access for a driver, or reset an
    existing login's username/password."""

    def post(self, request, pk):
        driver = get_object_or_404(Driver, pk=pk)
        had_account = bool(driver.user)
        form = DriverAccountForm(request.POST, driver=driver)
        if form.is_valid():
            form.save()
            verb = "reset" if had_account else "created"
            messages.success(request, f"Login credentials {verb} for {driver.full_name}.")
        else:
            for error in form.errors.get('__all__', []):
                messages.error(request, error)
            for field, errors in form.errors.items():
                if field == '__all__':
                    continue
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect('drivers:detail', pk=driver.pk)


# ---------- Company: view own drivers, upload documents for them ----------

class CompanyDriverListView(CompanyRequiredMixin, ListView):
    model = Driver
    template_name = 'drivers/company_driver_list.html'
    context_object_name = 'drivers'
    paginate_by = 20

    def get_queryset(self):
        return Driver.objects.filter(company=self.get_company())


class CompanyDriverDetailView(CompanyRequiredMixin, DetailView):
    model = Driver
    template_name = 'drivers/company_driver_detail.html'
    context_object_name = 'driver'

    def get_queryset(self):
        return Driver.objects.filter(company=self.get_company())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['document_form'] = DriverDocumentForm()
        ctx['password_form'] = DriverPasswordForm(driver=self.object)
        ctx['temporary_password'] = TEMPORARY_PASSWORD
        return ctx


class CompanyDriverUpdateView(CompanyRequiredMixin, UpdateView):
    """Lets a company edit their own driver's contact details (name,
    phone, email, address) — the same fields a driver can edit for
    themselves. License/status/photo stay admin-only, since those are
    verified onboarding/compliance data."""
    model = Driver
    form_class = DriverProfileForm
    template_name = 'drivers/company_driver_form.html'

    def get_queryset(self):
        return Driver.objects.filter(company=self.get_company())

    def get_success_url(self):
        messages.success(self.request, "Driver details updated.")
        return reverse_lazy('drivers:company_detail', kwargs={'pk': self.object.pk})


class CompanyDriverPasswordView(CompanyRequiredMixin, View):
    """A company replacing the temporary password on one of their own
    drivers' logins. Scoped to their company, and password-only: no
    username change, no account creation, no deactivation."""

    def post(self, request, pk):
        driver = get_object_or_404(Driver, pk=pk, company=self.get_company())

        if not driver.user:
            messages.warning(
                request,
                f"{driver.full_name} has no login yet. An administrator creates driver logins.",
            )
            return redirect('drivers:company_detail', pk=driver.pk)

        form = DriverPasswordForm(request.POST, driver=driver)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password updated for {driver.full_name}.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error if field == '__all__' else f"{field}: {error}")

        return redirect('drivers:company_detail', pk=driver.pk)


class CompanyDriverDocumentUploadView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        driver = get_object_or_404(Driver, pk=pk, company=self.get_company())
        form = DriverDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.driver = driver
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
        else:
            messages.error(request, "Could not upload document. Please check the form.")
        return redirect('drivers:company_detail', pk=driver.pk)


# ---------- Driver: self-service profile ----------

class DriverProfileView(DriverRequiredMixin, View):
    template_name = 'drivers/driver_profile.html'

    def get(self, request):
        driver = self.get_driver()
        return render(request, self.template_name, {
            'driver': driver,
            'profile_form': DriverProfileForm(instance=driver),
            'password_form': PasswordChangeForm(user=request.user),
        })

    def post(self, request):
        driver = self.get_driver()

        if 'update_profile' in request.POST:
            profile_form = DriverProfileForm(request.POST, instance=driver)
            password_form = PasswordChangeForm(user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile updated.")
                return redirect('drivers:profile')
        else:
            profile_form = DriverProfileForm(instance=driver)
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                if driver.password_is_temporary:
                    driver.password_is_temporary = False
                    driver.save(update_fields=['password_is_temporary'])
                messages.success(request, "Password changed.")
                return redirect('drivers:profile')

        return render(request, self.template_name, {
            'driver': driver,
            'profile_form': profile_form,
            'password_form': password_form,
        })