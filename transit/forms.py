import random
import string

from django import forms

from .models import TrackingUpdate, Transit


def generate_reference_code():
    return 'TRX-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


class TransitForm(forms.ModelForm):
    class Meta:
        model = Transit
        fields = [
            'truck', 'driver', 'origin', 'destination',
            'cargo_weight_tons',
            'scheduled_departure', 'expected_arrival', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
            'scheduled_departure': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'expected_arrival': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['truck'].queryset = company.trucks.all()
            self.fields['driver'].queryset = company.drivers.all()
        self.fields['driver'].required = False
        # "Cargo description" was dropped in favour of a single MT
        # (metric tonnage) field, auto-filled from the truck's capacity.
        self.fields['cargo_weight_tons'].label = 'MT'

        # Driver / Origin / Destination / MT are fetched automatically from
        # the selected truck's saved record (see the autofill script on the
        # form template) rather than typed in by the company. Marking the
        # text inputs readonly keeps their auto-filled values intact and
        # submittable, while stopping manual edits; the Driver <select> gets
        # the same "field-autofilled" look but stays enabled (not disabled)
        # so its selected value still posts with the form — a <select> has
        # no native readonly attribute, so the lock there is visual only
        # (CSS pointer-events, see the template) rather than at the HTML level.
        for field_name in ('origin', 'destination', 'cargo_weight_tons'):
            self.fields[field_name].widget.attrs['readonly'] = True
            self.fields[field_name].widget.attrs['class'] = (
                self.fields[field_name].widget.attrs.get('class', '') + ' field-autofilled'
            ).strip()
        self.fields['driver'].widget.attrs['class'] = (
            self.fields['driver'].widget.attrs.get('class', '') + ' field-autofilled field-autofilled-select'
        ).strip()
        self.fields['driver'].widget.attrs['tabindex'] = '-1'


class TransitInlineStatusForm(forms.ModelForm):
    """Bare status-only control used for the quick inline updater on the
    transit list page — just the dropdown, no location/remarks fields."""

    class Meta:
        model = TrackingUpdate
        fields = ['status']


class TransitStatusUpdateForm(forms.ModelForm):
    """Posts a new tracking checkpoint and moves the transit's overall status."""

    class Meta:
        model = TrackingUpdate
        fields = ['status', 'location_text', 'latitude', 'longitude', 'remarks']
        widgets = {
            'remarks': forms.TextInput(attrs={'placeholder': 'Optional note, e.g. delay reason'}),
            'location_text': forms.TextInput(attrs={'placeholder': "e.g. 'Cleared Ore checkpoint'"}),
        }
