from django import forms

from .models import Truck, TruckDocument


class TruckForm(forms.ModelForm):
    class Meta:
        model = Truck
        fields = [
            'registration_number', 'photo', 'make', 'model', 'year',
            'capacity_tons', 'status', 'assigned_driver', 'gps_device_id',
            'waybill_number', 'lti_number', 'origin', 'destination', 'commodities',
        ]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['assigned_driver'].queryset = company.drivers.all()
        self.fields['gps_device_id'].help_text = (
            "Optional. Fill this in once a GPS tracking device is installed on the truck."
        )
        self.fields['photo'].help_text = "Optional. JPG or PNG works best."


class TruckConsignmentUpdateForm(forms.ModelForm):
    """Quick update for the load currently on the truck — these change with
    every trip, so they're editable separately from the truck's core details."""

    class Meta:
        model = Truck
        fields = ['waybill_number', 'lti_number', 'origin', 'destination', 'commodities']


class TruckDocumentForm(forms.ModelForm):
    class Meta:
        model = TruckDocument
        fields = ['doc_type', 'title', 'file', 'issue_date', 'expiry_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


class TruckLocationUpdateForm(forms.ModelForm):
    """Quick manual location/status update. When a GPS feed is later wired up,
    latitude/longitude/gps_last_ping_at can be populated by that integration
    instead of this form."""

    class Meta:
        model = Truck
        fields = ['status', 'last_known_location']
        widgets = {
            'last_known_location': forms.TextInput(attrs={
                'placeholder': "e.g. 'Lagos-Ibadan Expressway, KM 25'"
            }),
        }