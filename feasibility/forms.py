from django import forms
from .models import (
    FeasibilityRequest, NTTN_PROVIDERS, BANDWIDTH_STATUS, ServiceLine,
    NTTNProvider, NTTNProviderResponse, NTTNProviderAttachment,
    PROVIDER_RESPONSE_STATUS, ROUTE_CONDITIONS, FIBER_AVAILABILITY, ATTACHMENT_TYPES,
    Division, District, Upazila, CUSTOMER_TYPES, FRQNTTNReviewEntry,
)


class FeasibilityRequestForm(forms.ModelForm):
    class Meta:
        model = FeasibilityRequest
        fields = [
            'contact_person', 'email', 'customer_type', 'proprietor_name', 'company_name',
            'phone_number', 'address', 'division', 'district', 'upazila',
            'latitude', 'longitude', 'requested_capacity', 'remarks',
        ]
        widgets = {
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name of contact person'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'proprietor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Street / area details'}),
            'division': forms.Select(attrs={'class': 'form-select', 'id': 'id_division'}),
            'district': forms.Select(attrs={'class': 'form-select', 'id': 'id_district'}),
            'upazila': forms.Select(attrs={'class': 'form-select', 'id': 'id_upazila'}),
            'latitude': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control', 'placeholder': 'e.g. 23.8103'}),
            'longitude': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control', 'placeholder': 'e.g. 90.4125'}),
            'requested_capacity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 100'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any additional notes for the request'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['division'].queryset = Division.objects.filter(is_active=True)
        self.fields['district'].queryset = District.objects.none()
        self.fields['upazila'].queryset = Upazila.objects.none()
        self.fields['division'].empty_label = '-- Select Division --'
        self.fields['district'].empty_label = '-- Select District --'
        self.fields['upazila'].empty_label = '-- Select Upazila / Thana --'

        self.fields['contact_person'].required = True
        self.fields['email'].required = True
        self.fields['division'].required = True
        self.fields['district'].required = True
        self.fields['upazila'].required = True

        if self.data.get('division'):
            self.fields['district'].queryset = District.objects.filter(
                division_id=self.data.get('division'), is_active=True,
            )
        elif self.instance.pk and self.instance.division_id:
            self.fields['district'].queryset = District.objects.filter(
                division=self.instance.division, is_active=True,
            )

        if self.data.get('district'):
            self.fields['upazila'].queryset = Upazila.objects.filter(
                district_id=self.data.get('district'), is_active=True,
            )
        elif self.instance.pk and self.instance.district_id:
            self.fields['upazila'].queryset = Upazila.objects.filter(
                district=self.instance.district, is_active=True,
            )

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

    def clean(self):
        cleaned = super().clean()
        division = cleaned.get('division')
        district = cleaned.get('district')
        upazila = cleaned.get('upazila')
        if district and division and district.division_id != division.pk:
            self.add_error('district', 'District does not belong to the selected division.')
        if upazila and district and upazila.district_id != district.pk:
            self.add_error('upazila', 'Upazila does not belong to the selected district.')
        return cleaned

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        qs = FeasibilityRequest.objects.filter(phone_number=phone)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A request with this phone number already exists.')
        return phone


class FRQReviewClientForm(forms.ModelForm):
    """Section 1 — Client FRQ summary (editable on review page)."""

    class Meta:
        model = FeasibilityRequest
        fields = [
            'contact_person', 'email', 'customer_type', 'phone_number', 'company_name',
            'address', 'requested_capacity',
            'preferred_nttn_provider', 'preferred_nttn_other',
        ]
        widgets = {
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'requested_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'preferred_nttn_provider': forms.Select(attrs={'class': 'form-select', 'id': 'id_preferred_nttn_provider'}),
            'preferred_nttn_other': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_preferred_nttn_other', 'placeholder': 'Enter provider name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_nttn_provider'].queryset = NTTNProvider.objects.filter(is_active=True)
        self.fields['preferred_nttn_provider'].empty_label = '-- Select Preferred NTTN --'
        self.fields['preferred_nttn_other'].required = False

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get('preferred_nttn_provider')
        other = cleaned.get('preferred_nttn_other', '').strip()
        if provider and provider.code == 'others' and not other:
            self.add_error('preferred_nttn_other', 'Please enter the NTTN provider name.')
        return cleaned


class FeasibilityReviewForm(forms.ModelForm):
    """Section 3 — Engineering review."""

    class Meta:
        model = FeasibilityRequest
        fields = [
            'status', 'estimated_delivery_days', 'engineering_notes',
            'fiber_route_distance_km', 'estimated_fiber_cost', 'remarks',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'estimated_delivery_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'engineering_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'fiber_route_distance_km': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'estimated_fiber_cost': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
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


class NTTNProviderResponseForm(forms.ModelForm):
    class Meta:
        model = NTTNProviderResponse
        fields = [
            'provider_reference', 'response_date', 'status',
            'pop_name', 'pop_address', 'pop_latitude', 'pop_longitude',
            'fiber_route_distance_km', 'straight_line_distance_km',
            'estimated_deployment_time', 'available_capacity', 'max_supported_capacity',
            'fiber_deployment_cost', 'installation_cost', 'monthly_bandwidth_cost',
            'additional_charges', 'total_estimated_cost',
            'engineering_remarks', 'route_condition', 'existing_fiber',
            'civil_work_required', 'pole_required', 'underground_fiber_required',
            'additional_equipment', 'risk_assessment', 'recommended_solution',
        ]
        widgets = {
            'pop_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'engineering_remarks': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'additional_equipment': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'risk_assessment': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'recommended_solution': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'response_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'pop_latitude': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'pop_longitude': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'fiber_route_distance_km': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'straight_line_distance_km': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'route_condition': forms.Select(attrs={'class': 'form-select'}),
            'existing_fiber': forms.Select(attrs={'class': 'form-select'}),
            'provider_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'pop_name': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_deployment_time': forms.TextInput(attrs={'class': 'form-control'}),
            'available_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_supported_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'fiber_deployment_cost': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'installation_cost': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'monthly_bandwidth_cost': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'additional_charges': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'total_estimated_cost': forms.NumberInput(attrs={'step': 'any', 'class': 'form-control'}),
            'civil_work_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pole_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'underground_fiber_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('total_estimated_cost'):
            parts = [
                cleaned.get('fiber_deployment_cost'),
                cleaned.get('installation_cost'),
                cleaned.get('additional_charges'),
            ]
            total = sum(p for p in parts if p is not None)
            if total:
                cleaned['total_estimated_cost'] = total
        return cleaned


class NTTNProviderAttachmentForm(forms.ModelForm):
    class Meta:
        model = NTTNProviderAttachment
        fields = ['attachment_type', 'file', 'description']

    def clean_file(self):
        upload = self.cleaned_data.get('file')
        if upload:
            from feasibility.utils import validate_upload
            validate_upload(upload)
        return upload


NTTNProviderAttachmentFormSet = forms.inlineformset_factory(
    NTTNProviderResponse,
    NTTNProviderAttachment,
    form=NTTNProviderAttachmentForm,
    extra=2,
    can_delete=True,
)
