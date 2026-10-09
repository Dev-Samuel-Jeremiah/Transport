from django import forms

from .models import LTI, Waybill


class LTIForm(forms.ModelForm):
    class Meta:
        model = LTI
        fields = ['lti_number', 'sto', 'status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class WaybillForm(forms.ModelForm):
    class Meta:
        model = Waybill
        fields = [
            'lti', 'waybill_number', 'date', 'transporter_name',
            'truck', 'vehicle_id', 'driver', 'driver_name',
            'origin', 'destination', 'commodity', 'weight_mt', 'status',
        ]
        widgets = {
            'date': forms.TextInput(attrs={'placeholder': "e.g. '9 Jul' or '2026-07-09'"}),
        }

    def __init__(self, *args, company=None, lti=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['lti'].queryset = company.ltis.all()
            self.fields['truck'].queryset = company.trucks.all()
            self.fields['driver'].queryset = company.drivers.all()
        if lti is not None:
            self.fields['lti'].initial = lti
            self.fields['lti'].widget = forms.HiddenInput()
        self.fields['truck'].required = False
        self.fields['driver'].required = False