from django import forms
from .models import (
    FeasibilityRequest, NTTN_PROVIDERS, BANDWIDTH_STATUS, ServiceLine,
)


class FeasibilityRequestForm(forms.ModelForm):
    supported_nttn = forms.MultipleChoiceField(
        choices=NTTN_PROVIDERS,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Supported NTTN Providers',
    )

    class Meta:
        model = FeasibilityRequest
        fields = [
            'customer_name', 'proprietor_name', 'company_name', 'phone_number', 'address',
            'latitude', 'longitude', 'requested_capacity', 'preferred_nttn', 'supported_nttn',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 23.8103'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'placeholder': 'e.g. 90.4125'}),
            'company_name': forms.TextInput(attrs={'placeholder': 'Optional'}),
        }

    def clean_latitude(self):
        lat = self.cleaned_data.get('latitude')
        if lat is not None and not (-90 <= float(lat) <= 90):
            raise forms.ValidationError('Latitude must be between -90 and +90.')
        return lat

    def clean_longitude(self):
        lon = self.cleaned_data.get('longitude')
        if lon is not None and not (-180 <= float(lon) <= 180):
            raise forms.ValidationError('Longitude must be between -180 and +180.')
        return lon

    def clean_requested_capacity(self):
        cap = self.cleaned_data.get('requested_capacity')
        if cap is not None and cap <= 0:
            raise forms.ValidationError('Capacity must be greater than zero.')
        return cap

    def clean_preferred_nttn(self):
        preferred = self.cleaned_data.get('preferred_nttn')
        if not preferred:
            raise forms.ValidationError('Preferred NTTN provider is required.')
        return preferred

    def clean(self):
        cleaned = super().clean()
        preferred = cleaned.get('preferred_nttn')
        supported = cleaned.get('supported_nttn') or []
        if preferred and preferred not in supported:
            raise forms.ValidationError('Preferred NTTN must be included in supported providers.')
        return cleaned

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        qs = FeasibilityRequest.objects.filter(phone_number=phone)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A request with this phone number already exists.')
        return phone


class FeasibilityReviewForm(forms.ModelForm):
    class Meta:
        model = FeasibilityRequest
        fields = [
            'status', 'estimated_delivery_days', 'remarks', 'engineering_notes',
            'fiber_route_distance_km', 'estimated_fiber_cost',
        ]
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 3}),
            'engineering_notes': forms.Textarea(attrs={'rows': 3}),
        }


class OnboardingForm(forms.ModelForm):
    class Meta:
        model = FeasibilityRequest
        fields = [
            'nid_number', 'cheque_image', 'installation_notes',
            'onboarding_remarks', 'preferred_nttn', 'requested_capacity',
        ]
        widgets = {
            'installation_notes': forms.Textarea(attrs={'rows': 3}),
            'onboarding_remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_requested_capacity(self):
        cap = self.cleaned_data.get('requested_capacity')
        if cap is not None and cap <= 0:
            raise forms.ValidationError('Capacity must be greater than zero.')
        return cap


class BandwidthConfirmationForm(forms.Form):
    provider = forms.ChoiceField(choices=NTTN_PROVIDERS)
    requested_capacity = forms.IntegerField(min_value=1)
    available_capacity = forms.IntegerField(required=False, min_value=0)
    status = forms.ChoiceField(choices=BANDWIDTH_STATUS, initial='pending')
    confirmation_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    provider_reference = forms.CharField(required=False, max_length=100)
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))


class ServiceLineForm(forms.ModelForm):
    class Meta:
        model = ServiceLine
        fields = [
            'service_type', 'capacity_mbps', 'unit_price', 'quantity',
            'installation_charge', 'fiber_deployment_charge',
            'one_time_charge', 'vat_percent', 'discount',
        ]
