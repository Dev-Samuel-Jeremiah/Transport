from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, ListView, View

from companies.models import Company

from .forms import UserEditForm, UserEnrollForm
from .permissions import AdminRequiredMixin
from .utils import TEMPORARY_PASSWORD

User = get_user_model()


def enrolled_users():
    """The users this page manages: logins enrolled under a company.

    Superusers are excluded — they act as administrators whatever role they
    happen to carry.
    """
    return User.objects.filter(role=User.Role.COMPANY, is_superuser=False)


def safe_next(request, default):
    """Where to send the admin after an action: the page they came from if it
    is on this site, otherwise `default`."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return default


class UserListView(AdminRequiredMixin, ListView):
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        qs = enrolled_users().select_related('company').order_by('company__name', 'username')

        company_id = self.request.GET.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)

        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(company__name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['companies'] = Company.objects.order_by('name')
        ctx['selected_company'] = self.request.GET.get('company', '')
        ctx['temporary_password'] = TEMPORARY_PASSWORD
        ctx['pending_password_count'] = enrolled_users().filter(password_is_temporary=True).count()
        # Keep filters when paging.
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_query'] = params.urlencode()
        return ctx


class UserEnrollView(AdminRequiredMixin, FormView):
    template_name = 'accounts/user_enroll.html'
    form_class = UserEnrollForm

    def get_initial(self):
        initial = super().get_initial()
        company_id = self.request.GET.get('company')
        if company_id:
            initial['company'] = company_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['temporary_password'] = TEMPORARY_PASSWORD
        ctx['cancel_url'] = reverse('accounts:user_list')
        return ctx

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"{user.display_name} enrolled under {user.company.name}. Username '{user.username}', "
            f"temporary password '{TEMPORARY_PASSWORD}' — they'll be asked to set a new one at first login."
        )
        return redirect(f"{reverse('accounts:user_list')}?company={user.company_id}")


class UserEditView(AdminRequiredMixin, FormView):
    """Edit an enrolled user's profile: name, username, email, phone and the
    company they belong to. The password is left alone (use Reset password)."""

    template_name = 'accounts/user_enroll.html'
    form_class = UserEditForm

    def get_target(self):
        if not hasattr(self, '_target'):
            self._target = get_object_or_404(enrolled_users().select_related('company'), pk=self.kwargs['pk'])
        return self._target

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_target()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['editing'] = True
        ctx['target'] = self.get_target()
        ctx['cancel_url'] = safe_next(self.request, reverse('accounts:user_list'))
        return ctx

    def form_valid(self, form):
        old_username = self.get_target().username
        user = form.save()
        if user.username != old_username:
            messages.success(
                self.request,
                f"{user.display_name} updated. Their username is now '{user.username}' "
                f"(was '{old_username}') — they must sign in with the new one."
            )
        else:
            messages.success(self.request, f"{user.display_name} updated.")
        return redirect(safe_next(self.request, reverse('accounts:user_list')))


class _UserActionView(AdminRequiredMixin, View):
    """Base for the one-click, POST-only actions on a single enrolled user."""

    def get_user(self, pk):
        return get_object_or_404(enrolled_users().select_related('company'), pk=pk)

    def done(self, request):
        return redirect(safe_next(request, reverse('accounts:user_list')))


class UserResetPasswordView(_UserActionView):
    """For when someone is locked out: puts their login back on the shared
    temporary password and flags it, so they must pick a new one next sign-in."""

    def post(self, request, pk):
        user = self.get_user(pk)
        user.set_password(TEMPORARY_PASSWORD)
        user.password_is_temporary = True
        user.save(update_fields=['password', 'password_is_temporary'])
        messages.success(
            request,
            f"Password reset for {user.display_name}. They'll sign in as '{user.username}' with the "
            f"temporary password '{TEMPORARY_PASSWORD}' and be asked to set a new one."
        )
        return self.done(request)


class UserToggleActiveView(_UserActionView):
    """Disable a login (they can no longer sign in, and any open session ends)
    or switch it back on."""

    def post(self, request, pk):
        user = self.get_user(pk)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        state = 'enabled — they can sign in again' if user.is_active else 'disabled — they can no longer sign in'
        messages.success(request, f"{user.display_name} ({user.username}) {state}.")
        return self.done(request)
