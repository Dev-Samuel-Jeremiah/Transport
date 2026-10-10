from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to platform admins only.

    Also gates every view behind the temporary-password check, same as
    CompanyRequiredMixin: an admin account still on the shared temporary
    password is bounced to their profile until they set a real one. This
    only affects admins registered through the app (role=ADMIN with the
    flag set) — superuser accounts made via createsuperuser never carry it.
    Set allow_temporary_password = True on the one view that must stay
    reachable regardless (the profile page itself)."""

    allow_temporary_password = False

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("This area is restricted to administrators.")

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.is_admin_role
            and user.password_is_temporary
            and not self.allow_temporary_password
        ):
            messages.warning(request, "Please set a new password before continuing.")
            return redirect('accounts:admin_profile')
        return super().dispatch(request, *args, **kwargs)


class CompanyRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to company users, and scope queries to their company.

    A company user belongs to exactly one company (`user.company`, set when an
    admin enrolls them). Every company-side view gets that company from
    `get_company()` and filters by it, so a user can only ever view or change
    their own company's data — never another transporter's.

    Also gates every view behind the temporary-password check: a user still on
    the shared temporary password is bounced to their profile until they set
    a real one. Set allow_temporary_password = True on the one view that must
    stay reachable regardless (the profile page itself)."""

    allow_temporary_password = False

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_company_role and user.company_id is not None

    def handle_no_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return super().handle_no_permission()
        if user.is_company_role and user.company_id is None:
            raise PermissionDenied(
                "Your account isn't linked to a company yet. Ask an administrator to associate it with one."
            )
        raise PermissionDenied("This area is restricted to company accounts.")

    def get_company(self):
        return self.request.user.company

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.is_company_role
            and user.company_id is not None
            and user.password_is_temporary
            and not self.allow_temporary_password
        ):
            messages.warning(request, "Please set a new password before continuing.")
            return redirect('companies:profile')
        return super().dispatch(request, *args, **kwargs)


class DriverRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to driver users, and scope queries to their own profile."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_driver_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("This area is restricted to driver accounts.")

    def get_driver(self):
        return self.request.user.driver_profile
