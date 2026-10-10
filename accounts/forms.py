from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.validators import UnicodeUsernameValidator

from companies.models import Company

from .utils import TEMPORARY_PASSWORD

User = get_user_model()


class StyledAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'field-input'})


class _UserProfileForm(forms.Form):
    """Fields shared by enrolling and editing a company user (admin only)."""

    company = forms.ModelChoiceField(
        queryset=Company.objects.none(),
        empty_label="Select a company…",
        help_text="The transporter this user belongs to. They'll only ever see this company's data.",
    )
    full_name = forms.CharField(max_length=150)
    username = forms.CharField(
        max_length=150,
        help_text="What they type to sign in. Letters, digits and . @ + - _ only — no spaces.",
    )
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None:
            # FormView always passes initial={}, so setdefault() would never
            # apply — merge instead, letting anything the view set win.
            kwargs['initial'] = {
                'company': instance.company_id,
                'full_name': instance.get_full_name(),
                'username': instance.username,
                'email': instance.email,
                'phone': instance.phone,
                **(kwargs.get('initial') or {}),
            }
        super().__init__(*args, **kwargs)
        self.fields['company'].queryset = Company.objects.order_by('name')

    def clean_full_name(self):
        return ' '.join(self.cleaned_data['full_name'].split())

    def clean_username(self):
        username = self.cleaned_data['username'].strip()

        # An unchanged username is always accepted, so legacy logins whose
        # username has spaces (e.g. a company name) can still have their other
        # details edited without being forced to rename them first.
        if self.instance is not None and username == self.instance.username:
            return username

        UnicodeUsernameValidator()(username)

        taken = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def _apply(self, user):
        data = self.cleaned_data
        first_name, _, last_name = data['full_name'].partition(' ')
        user.first_name = first_name
        user.last_name = last_name
        user.username = data['username']
        user.email = data['email']
        user.phone = data['phone']
        user.company = data['company']


class UserEnrollForm(_UserProfileForm):
    """Enroll a user under one transport company.

    The user is created with the shared temporary password and flagged, so
    they are forced to choose their own the first time they sign in. Once
    signed in they can only see and change the company chosen here.
    """

    def save(self):
        user = User(role=User.Role.COMPANY, password_is_temporary=True)
        self._apply(user)
        # set_password (not create_user(password=...)) so the temporary
        # password bypasses AUTH_PASSWORD_VALIDATORS, which would reject it.
        user.set_password(TEMPORARY_PASSWORD)
        user.save()
        return user


class UserEditForm(_UserProfileForm):
    """Edit an enrolled user's profile, including their username and company.

    Never touches the password — resetting it is a separate action."""

    def save(self):
        self._apply(self.instance)
        self.instance.save()
        return self.instance


class _AdminProfileForm(forms.Form):
    """Fields shared by registering and editing an administrator."""

    full_name = forms.CharField(max_length=150)
    username = forms.CharField(
        max_length=150,
        help_text="What they type to sign in. Letters, digits and . @ + - _ only — no spaces.",
    )
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None:
            kwargs['initial'] = {
                'full_name': instance.get_full_name(),
                'username': instance.username,
                'email': instance.email,
                'phone': instance.phone,
                **(kwargs.get('initial') or {}),
            }
        super().__init__(*args, **kwargs)

    def clean_full_name(self):
        return ' '.join(self.cleaned_data['full_name'].split())

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if self.instance is not None and username == self.instance.username:
            return username
        UnicodeUsernameValidator()(username)
        taken = User.objects.filter(username__iexact=username)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def _apply(self, user):
        data = self.cleaned_data
        first_name, _, last_name = data['full_name'].partition(' ')
        user.first_name = first_name
        user.last_name = last_name
        user.username = data['username']
        user.email = data['email']
        user.phone = data['phone']


class AdminEnrollForm(_AdminProfileForm):
    """Register a new platform administrator — full access, no company
    scoping. Created with the shared temporary password and flagged, same
    as every other role: they must set their own on first sign-in."""

    def save(self):
        user = User(role=User.Role.ADMIN, password_is_temporary=True)
        self._apply(user)
        # set_password (not create_user(password=...)) so the temporary
        # password bypasses AUTH_PASSWORD_VALIDATORS, which would reject it.
        user.set_password(TEMPORARY_PASSWORD)
        user.save()
        return user


class AdminEditForm(_AdminProfileForm):
    """Edit an administrator's profile, including their username. Never
    touches the password — resetting it is a separate action."""

    def save(self):
        self._apply(self.instance)
        self.instance.save()
        return self.instance
