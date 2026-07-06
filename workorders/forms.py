from django import forms
from feasibility.models import FeasibilityRequest, ONBOARDING_STATUS, BANDWIDTH_STATUS, NTTN_PROVIDERS


class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = FeasibilityRequest
        fields = [
            'nid_number', 'email', 'cheque_image', 'installation_notes',
            'expected_installation_date', 'onboarding_status', 'onboarding_remarks',
            'preferred_nttn', 'requested_capacity', 'wo_vat_percent', 'wo_discount',
        ]
        widgets = {
            'installation_notes': forms.Textarea(attrs={'rows': 3}),
            'onboarding_remarks': forms.Textarea(attrs={'rows': 2}),
            'expected_installation_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['onboarding_status'].choices = [('', '-- Select --')] + list(ONBOARDING_STATUS)

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


class BandwidthForm(forms.Form):
    provider = forms.ChoiceField(choices=NTTN_PROVIDERS, widget=forms.Select(attrs={'class': 'form-select'}))
    requested_capacity = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    approved_capacity = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    available_capacity = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    status = forms.ChoiceField(choices=BANDWIDTH_STATUS, initial='pending', widget=forms.Select(attrs={'class': 'form-select'}))
    confirmation_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    provider_reference = forms.CharField(required=False, max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
