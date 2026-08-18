from django import forms
from feasibility.models import (
    FeasibilityRequest, UpstreamProvider, SFP_WAVELENGTHS, CUSTOMER_CATEGORIES,
)


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = FeasibilityRequest
        fields = [
            'nid_number', 'email',
            'installation_notes', 'expected_installation_date',
            'onboarding_remarks', 'requested_capacity', 'wo_vat_percent', 'wo_discount',
            'wo_client_share_percent', 'sfp_wavelength', 'customer_category', 'billing_date',
            'upstream_provider', 'upstream_provider_other',
        ]
        widgets = {
            'installation_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'onboarding_remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'expected_installation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'billing_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sfp_wavelength': forms.Select(attrs={'class': 'form-select'}),
            'customer_category': forms.HiddenInput(),
            'upstream_provider': forms.Select(attrs={'class': 'form-select', 'id': 'id_upstream_provider'}),
            'upstream_provider_other': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Provider name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'nid_number': forms.TextInput(attrs={'class': 'form-control'}),
            'requested_capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'wo_vat_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'wo_discount': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'wo_client_share_percent': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'min': 0, 'max': 100, 'id': 'id_wo_client_share_percent',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sfp_wavelength'].choices = [('', '-- Select --')] + list(SFP_WAVELENGTHS)
        self.fields['customer_category'].choices = CUSTOMER_CATEGORIES
        self.fields['customer_category'].required = True
        if not self.initial.get('customer_category') and not (self.instance and self.instance.customer_category):
            self.initial['customer_category'] = 'BW'
        self.fields['upstream_provider'].queryset = UpstreamProvider.objects.filter(is_active=True)
        self.fields['upstream_provider'].empty_label = '-- Select Upstream Provider --'
        self.fields['upstream_provider'].required = True
        self.fields['billing_date'].required = True

    def clean_nid_number(self):
        nid = self.cleaned_data.get('nid_number', '').strip()
        if not nid:
            raise forms.ValidationError('NID number is required.')
        return nid

    def clean_requested_capacity(self):
        cap = self.cleaned_data.get('requested_capacity')
        if cap is not None and cap <= 0:
            raise forms.ValidationError('Capacity must be greater than zero.')
        return cap

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get('upstream_provider')
        other = (cleaned.get('upstream_provider_other') or '').strip()
        if provider and provider.code == 'others' and not other:
            self.add_error('upstream_provider_other', 'Enter the upstream provider name.')
        share = cleaned.get('wo_client_share_percent')
        if share is not None:
            if share < 0 or share > 100:
                self.add_error('wo_client_share_percent', 'Client share must be between 0 and 100.')
        return cleaned
