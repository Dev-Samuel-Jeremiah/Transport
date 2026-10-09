from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.permissions import AdminRequiredMixin, CompanyRequiredMixin

from .forms import CompanyDocumentForm, CompanyEditForm, CompanyRegistrationForm
from .models import Company


class CompanyListView(AdminRequiredMixin, ListView):
    model = Company
    template_name = 'companies/company_list.html'
    context_object_name = 'companies'
    paginate_by = 20

    def get_queryset(self):
        qs = Company.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class CompanyBulkDeleteView(AdminRequiredMixin, View):
    """Delete multiple companies (and everything under them — enrolled users,
    drivers, trucks, LTIs, waybills, transits) in one request.

    A company is skipped (not deleted) if one of its trucks is linked to
    a transit record — Transit.truck is a protected foreign key, so the
    database refuses that deletion until the transit is removed or
    reassigned. Skipped companies are reported back instead of failing
    the whole batch.
    """

    def post(self, request):
        ids = request.POST.getlist('company_ids')
        companies = Company.objects.filter(pk__in=ids)

        deleted = 0
        blocked = []
        for company in companies:
            name = company.name
            try:
                company.delete()
                deleted += 1
            except ProtectedError:
                blocked.append(name)

        if deleted:
            messages.success(request, f"Deleted {deleted} compan{'y' if deleted == 1 else 'ies'}.")
        if blocked:
            messages.warning(
                request,
                "Could not delete " + ", ".join(blocked) +
                " — they have trucks linked to transit records."
            )
        if not deleted and not blocked:
            messages.warning(request, "No companies were selected for deletion.")
        return redirect('companies:list')


class CompanyCreateView(AdminRequiredMixin, CreateView):
    model = Company
    form_class = CompanyRegistrationForm
    template_name = 'companies/company_form.html'

    def form_valid(self, form):
        self.object = form.save(registered_by=self.request.user)
        messages.success(
            self.request,
            f"Company '{self.object.name}' registered. Enroll a user below so someone can sign in for it."
        )
        return redirect('companies:detail', pk=self.object.pk)


class CompanyDetailView(AdminRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/company_detail.html'
    context_object_name = 'company'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['documents'] = self.object.documents.all()
        ctx['drivers'] = self.object.drivers.all()
        ctx['trucks'] = self.object.trucks.all()
        ctx['users'] = self.object.users.order_by('username')
        ctx['document_form'] = CompanyDocumentForm()
        return ctx


class CompanyUpdateView(AdminRequiredMixin, UpdateView):
    model = Company
    form_class = CompanyEditForm
    template_name = 'companies/company_form.html'

    def get_success_url(self):
        messages.success(self.request, "Company details updated.")
        return reverse_lazy('companies:detail', kwargs={'pk': self.object.pk})


class CompanyDocumentUploadView(AdminRequiredMixin, View):
    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        form = CompanyDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.company = company
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
        else:
            messages.error(request, "Could not upload document. Please check the form.")
        return redirect('companies:detail', pk=company.pk)


# ---------- Company: self-service profile ----------

class CompanyProfileView(CompanyRequiredMixin, View):
    """A company user's own account settings — currently just their password,
    shown next to the company they belong to. This is the one page a user can
    still reach while on the temporary password; see CompanyRequiredMixin."""

    allow_temporary_password = True
    template_name = 'companies/company_profile.html'

    def get(self, request):
        return render(request, self.template_name, {
            'company': self.get_company(),
            'password_form': PasswordChangeForm(user=request.user),
        })

    def post(self, request):
        company = self.get_company()
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            if user.password_is_temporary:
                user.password_is_temporary = False
                user.save(update_fields=['password_is_temporary'])
            messages.success(request, "Password changed.")
            return redirect('dashboard:company_home')

        return render(request, self.template_name, {
            'company': company,
            'password_form': password_form,
        })