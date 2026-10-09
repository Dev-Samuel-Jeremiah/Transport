import re
import unicodedata

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Driver, DriverDocument

User = get_user_model()

# The password every driver account is issued with at onboarding. It is set
# programmatically (never run through the password validators, which would
# reject it), and the account is flagged so the company is prompted to
# replace it.
TEMPORARY_PASSWORD = 'password'


def suggest_username(full_name, license_number=''):
    """Build a unique, readable username from the driver's name.

    Falls back to the licence number, then to a numeric suffix, so an
    onboarding never fails just because two drivers share a name.
    """
    base = unicodedata.normalize('NFKD', full_name or '').encode('ascii', 'ignore').decode()
    base = re.sub(r'[^a-zA-Z0-9]+', '.', base).strip('.').lower()

    if not base:
        base = re.sub(r'[^a-zA-Z0-9]+', '', license_number or '').lower() or 'driver'

    candidate = base[:140]
    if not User.objects.filter(username=candidate).exists():
        return candidate

    suffix = 2
    while User.objects.filter(username=f'{candidate}{suffix}').exists():
        suffix += 1
    return f'{candidate}{suffix}'


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            'company', 'full_name', 'phone', 'email', 'address',
            'license_number', 'license_expiry', 'photo', 'status',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'license_expiry': forms.DateInput(attrs={'type': 'date'}),
        }


class DriverOnboardingForm(forms.ModelForm):
    """Admin-only: register a driver AND issue their login in one step.

    The account is always created with the shared temporary password, and
    flagged, so the company that owns the driver is prompted to replace it.
    """

    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Leave blank to generate one from the driver's name.",
    )

    class Meta:
        model = Driver
        fields = [
            'company', 'full_name', 'phone', 'email', 'address',
            'license_number', 'license_expiry', 'photo', 'status',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'license_expiry': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            return ''
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def save(self, commit=True, registered_by=None):
        driver = super().save(commit=False)
        driver.registered_by = registered_by

        username = self.cleaned_data.get('username') or suggest_username(
            driver.full_name, driver.license_number
        )

        # set_password, not create_user(password=...), so the temporary
        # password bypasses AUTH_PASSWORD_VALIDATORS — which would reject
        # it as too common.
        user = User(username=username, role=User.Role.DRIVER)
        if driver.email:
            user.email = driver.email
        user.set_password(TEMPORARY_PASSWORD)
        user.save()

        driver.user = user
        driver.password_is_temporary = True
        driver.save()

        self.created_username = username
        return driver


class DriverPasswordForm(forms.Form):
    """Company-facing: replace one of their own drivers' temporary password.

    Deliberately narrow — a company can set the password and nothing else.
    Creating, renaming, disabling or deleting a driver login stays with the
    administrator.
    """

    password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def __init__(self, *args, driver=None, **kwargs):
        self.driver = driver
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')

        if not password1:
            return cleaned
        if password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        if password1 == TEMPORARY_PASSWORD:
            raise forms.ValidationError(
                "That is the temporary password. Please choose a different one."
            )
        validate_password(password1, user=self.driver.user if self.driver else None)
        return cleaned

    def save(self):
        user = self.driver.user
        user.set_password(self.cleaned_data['password1'])
        user.is_active = True
        user.save()

        self.driver.password_is_temporary = False
        self.driver.save(update_fields=['password_is_temporary'])
        return user


class DriverAccountForm(forms.Form):
    """Admin-facing form to create or reset a driver's login credentials."""

    username = forms.CharField(max_length=150)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def __init__(self, *args, driver=None, **kwargs):
        self.driver = driver
        super().__init__(*args, **kwargs)
        if driver and driver.user:
            self.fields['username'].initial = driver.user.username
            self.fields['password1'].required = False
            self.fields['password2'].required = False
            self.fields['password1'].help_text = "Leave blank to keep the current password."

    def clean_username(self):
        username = self.cleaned_data['username']
        existing_user_id = self.driver.user_id if self.driver else None
        if User.objects.exclude(pk=existing_user_id).filter(username=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("The two password fields didn't match.")
            validate_password(password1)
        return cleaned

    def save(self):
        username = self.cleaned_data['username']
        password = self.cleaned_data.get('password1')

        if self.driver.user:
            user = self.driver.user
            user.username = username
            if password:
                user.set_password(password)
            user.is_active = True
            user.role = User.Role.DRIVER
            user.save()
        else:
            user = User.objects.create_user(username=username, password=password, role=User.Role.DRIVER)
            self.driver.user = user
            self.driver.save(update_fields=['user'])

        # Keep the temporary-password flag honest: an admin who sets a real
        # password here clears the company's "change this" prompt.
        if password:
            self.driver.password_is_temporary = (password == TEMPORARY_PASSWORD)
            self.driver.save(update_fields=['password_is_temporary'])

        return user


class DriverProfileForm(forms.ModelForm):
    """Self-service form a driver uses to edit their own contact details."""

    class Meta:
        model = Driver
        fields = ['full_name', 'phone', 'email', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class DriverDocumentForm(forms.ModelForm):
    class Meta:
        model = DriverDocument
        fields = ['doc_type', 'title', 'file', 'issue_date', 'expiry_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
