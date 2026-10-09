from django import forms

from .models import Company, CompanyDocument


class CompanyRegistrationForm(forms.ModelForm):
    """Used by admin to register a new transporter.

    This only creates the company. Logins are enrolled separately, under the
    company, from the Users page — a company can have as many as it needs.
    """

    class Meta:
        model = Company
        fields = [
            'name', 'registration_number', 'contact_person',
            'email', 'phone', 'address', 'status',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

    def save(self, registered_by, commit=True):
        company = super().save(commit=False)
        company.registered_by = registered_by
        if commit:
            company.save()
        return company


class CompanyEditForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'registration_number', 'contact_person',
            'email', 'phone', 'address', 'status',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }


class CompanyDocumentForm(forms.ModelForm):
    class Meta:
        model = CompanyDocument
        fields = ['doc_type', 'title', 'file', 'issue_date', 'expiry_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
