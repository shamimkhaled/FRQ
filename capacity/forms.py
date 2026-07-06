from django import forms
from .models import CapacityConfirmation, ServicePricing, SERVICE_TYPES, SERVICE_UNIT_PRICE


class CapacityConfirmationForm(forms.ModelForm):
    class Meta:
        model = CapacityConfirmation
        fields = ['provider', 'requested_capacity', 'available_capacity', 'status', 'confirmation_date', 'provider_reference', 'remarks']
        widgets = {
            'confirmation_date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }


class ServicePricingForm(forms.ModelForm):
    class Meta:
        model = ServicePricing
        fields = [
            'service_type', 'capacity_mbps', 'unit_price', 'quantity',
            'installation_charge', 'fiber_deployment_charge',
            'one_time_charge', 'vat_percent', 'discount',
        ]

    def clean(self):
        cleaned = super().clean()
        stype = cleaned.get('service_type')
        if stype and not cleaned.get('unit_price'):
            cleaned['unit_price'] = SERVICE_UNIT_PRICE.get(stype, 0)
        qty = cleaned.get('quantity') or 1
        if qty < 1:
            cleaned['quantity'] = 1
        return cleaned
