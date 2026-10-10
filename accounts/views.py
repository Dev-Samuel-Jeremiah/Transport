from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, View

from companies.models import Company
from drivers.forms import DriverOnboardingForm
from drivers.models import Driver
from transit.models import Transit
from trucks.models import Truck
from waybills.models import Waybill

from .forms import AdminEditForm, AdminEnrollForm, UserEditForm, UserEnrollForm
from .permissions import AdminRequiredMixin
from .utils import TEMPORARY_PASSWORD

User = get_user_model()


def enrolled_users():
    """Company-role logins only — used by the company-scoped edit/enroll
    flows launched from a Company's own page."""
    return User.objects.filter(role=User.Role.COMPANY, is_superuser=False)


def platform_users():
    """Every login the Control Room manages, across all three roles.

    Superusers are excluded — they act as administrators however they're
    reached, and aren't meant to be reset/disabled from this UI.
    """
    return User.objects.filter(is_superuser=False).select_related('company', 'driver_profile')


def safe_next(request, default):
    """Where to send the admin after an action: the page they came from if it
    is on this site, otherwise `default`."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return default


class ControlRoomView(AdminRequiredMixin, View):
    """The one dashboard for running the platform's people and access: a
    live overview of the network, every login across all three roles in one
    searchable table, and registration for all three roles — without
    leaving the page. Quick-access cards point to the rest of the admin
    tools, and the built-in Django admin is one click away at the bottom
    for anything this page doesn't cover."""

    template_name = 'accounts/control_room.html'

    def get(self, request):
        return render(request, self.template_name, self.build_context(request))

    def post(self, request):
        role = request.POST.get('register_role')
        forms = {}

        if role == 'admin':
            forms['admin_form'] = form = AdminEnrollForm(request.POST)
            if form.is_valid():
                user = form.save()
                messages.success(
                    request,
                    f"{user.display_name} registered as an administrator. Username '{user.username}', "
                    f"temporary password '{TEMPORARY_PASSWORD}' — they'll be asked to set a new one at first login."
                )
                return redirect(f"{reverse('accounts:control_room')}?tab=admin#register")

        elif role == 'company':
            forms['company_form'] = form = UserEnrollForm(request.POST)
            if form.is_valid():
                user = form.save()
                messages.success(
                    request,
                    f"{user.display_name} enrolled under {user.company.name}. Username '{user.username}', "
                    f"temporary password '{TEMPORARY_PASSWORD}' — they'll be asked to set a new one at first login."
                )
                return redirect(f"{reverse('accounts:control_room')}?tab=company#register")

        elif role == 'driver':
            forms['driver_form'] = form = DriverOnboardingForm(request.POST, request.FILES)
            if form.is_valid():
                driver = form.save(registered_by=request.user)
                messages.success(
                    request,
                    f"{driver.full_name} registered under {driver.company.name}. Login '{form.created_username}' "
                    f"created with the temporary password '{TEMPORARY_PASSWORD}' — {driver.company.name} can "
                    f"change it from their Drivers page."
                )
                return redirect(f"{reverse('accounts:control_room')}?tab=driver#register")

        ctx = self.build_context(request, active_tab=role or 'admin', **forms)
        return render(request, self.template_name, ctx)

    def build_context(self, request, active_tab=None, admin_form=None, company_form=None, driver_form=None):
        qs = platform_users().order_by('-date_joined')

        role_filter = request.GET.get('role', '')
        if role_filter in (User.Role.ADMIN, User.Role.COMPANY, User.Role.DRIVER):
            qs = qs.filter(role=role_filter)

        company_id = request.GET.get('company')
        if company_id:
            qs = qs.filter(company_id=company_id)

        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(company__name__icontains=q)
            )

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(request.GET.get('page'))

        params = request.GET.copy()
        params.pop('page', None)

        return {
            'admin_form': admin_form or AdminEnrollForm(),
            'company_form': company_form or UserEnrollForm(),
            'driver_form': driver_form or DriverOnboardingForm(),
            'active_tab': active_tab or request.GET.get('tab') or 'admin',
            'temporary_password': TEMPORARY_PASSWORD,
            'page_obj': page_obj,
            'users': page_obj.object_list,
            'is_paginated': page_obj.has_other_pages(),
            'companies': Company.objects.order_by('name'),
            'role_filter': role_filter,
            'selected_company': request.GET.get('company', ''),
            'search_query': request.GET.get('q', ''),
            'filter_query': params.urlencode(),
            'pending_password_count': platform_users().filter(password_is_temporary=True).count(),
            'stats': {
                'companies': Company.objects.count(),
                'admins': User.objects.filter(role=User.Role.ADMIN, is_superuser=False).count(),
                'company_users': User.objects.filter(role=User.Role.COMPANY).count(),
                'drivers': Driver.objects.count(),
                'driver_logins': Driver.objects.filter(user__isnull=False).count(),
                'trucks': Truck.objects.count(),
                'trucks_on_trip': Truck.objects.filter(status=Truck.Status.ON_TRIP).count(),
                'active_transits': Transit.objects.filter(status=Transit.Status.IN_TRANSIT, is_archived=False).count(),
                'waybills': Waybill.objects.count(),
            },
        }


class UserEnrollView(AdminRequiredMixin, FormView):
    """Standalone enroll page, reached from a specific Company's own page
    (pre-fills that company). The Control Room covers the general case."""

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
        ctx['cancel_url'] = reverse('accounts:control_room')
        return ctx

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"{user.display_name} enrolled under {user.company.name}. Username '{user.username}', "
            f"temporary password '{TEMPORARY_PASSWORD}' — they'll be asked to set a new one at first login."
        )
        return redirect(f"{reverse('accounts:control_room')}?company={user.company_id}")


class UserEditView(AdminRequiredMixin, FormView):
    """Edit an enrolled company user's profile: name, username, email,
    phone and the company they belong to. The password is left alone (use
    Reset password)."""

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
        ctx['cancel_url'] = safe_next(self.request, reverse('accounts:control_room'))
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
        return redirect(safe_next(self.request, reverse('accounts:control_room')))


class AdminEditView(AdminRequiredMixin, FormView):
    """Edit an administrator's profile: name, username, email, phone. The
    password is left alone (use Reset password)."""

    template_name = 'accounts/admin_edit.html'
    form_class = AdminEditForm

    def get_target(self):
        if not hasattr(self, '_target'):
            self._target = get_object_or_404(
                User.objects.filter(role=User.Role.ADMIN, is_superuser=False), pk=self.kwargs['pk']
            )
        return self._target

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.get_target()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['target'] = self.get_target()
        ctx['cancel_url'] = safe_next(self.request, reverse('accounts:control_room'))
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
        return redirect(safe_next(self.request, reverse('accounts:control_room')))


class AdminProfileView(AdminRequiredMixin, View):
    """An admin's own account settings — currently just their password.
    This is the one page an admin can still reach while on the temporary
    password; see AdminRequiredMixin."""

    allow_temporary_password = True
    template_name = 'accounts/admin_profile.html'

    def get(self, request):
        return render(request, self.template_name, {'password_form': PasswordChangeForm(user=request.user)})

    def post(self, request):
        password_form = PasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            if user.password_is_temporary:
                user.password_is_temporary = False
                user.save(update_fields=['password_is_temporary'])
            messages.success(request, "Password changed.")
            return redirect('dashboard:admin_home')
        return render(request, self.template_name, {'password_form': password_form})


class _UserActionView(AdminRequiredMixin, View):
    """Base for the one-click, POST-only actions on a single platform user."""

    def get_user(self, pk):
        return get_object_or_404(platform_users(), pk=pk)

    def done(self, request):
        return redirect(safe_next(request, reverse('accounts:control_room')))


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
        if user.pk == request.user.pk:
            messages.error(request, "You can't disable your own account.")
            return self.done(request)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        state = 'enabled — they can sign in again' if user.is_active else 'disabled — they can no longer sign in'
        messages.success(request, f"{user.display_name} ({user.username}) {state}.")
        return self.done(request)
