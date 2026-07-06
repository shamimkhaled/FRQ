from django.contrib import admin
from .models import POPLocation, FeasibilityRequest, ServiceLine, OnboardingDocument


@admin.register(POPLocation)
class POPLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'latitude', 'longitude', 'is_active']
    list_filter = ['is_active']


class ServiceLineInline(admin.TabularInline):
    model = ServiceLine
    extra = 0
    readonly_fields = ['monthly_price', 'total_monthly_charge', 'total_payable']


@admin.register(FeasibilityRequest)
class FeasibilityRequestAdmin(admin.ModelAdmin):
    list_display = [
        'customer_name', 'company_name', 'status', 'onboarding_status',
        'requested_capacity', 'nearest_pop', 'created_at',
    ]
    list_filter = ['status', 'onboarding_status', 'preferred_nttn']
    search_fields = ['customer_name', 'phone_number', 'address', 'company_name']
    readonly_fields = [
        'created_at', 'updated_at', 'nearest_pop', 'distance_to_pop_km',
        'air_distance_km', 'fiber_route_distance_km', 'estimated_fiber_cost',
    ]
    inlines = [ServiceLineInline]
    fieldsets = (
        ('Customer', {'fields': ('customer_name', 'proprietor_name', 'company_name', 'phone_number', 'address')}),
        ('Location', {'fields': ('latitude', 'longitude', 'nearest_pop', 'distance_to_pop_km', 'air_distance_km', 'fiber_route_distance_km', 'estimated_fiber_cost')}),
        ('Feasibility', {'fields': ('status', 'requested_capacity', 'preferred_nttn', 'supported_nttn', 'estimated_delivery_days', 'remarks', 'engineering_notes', 'emails_sent')}),
        ('Onboarding', {'fields': ('onboarding_status', 'nid_number', 'cheque_image', 'installation_notes', 'onboarding_remarks', 'bandwidth_confirmations', 'bw_emails_sent')}),
        ('Audit', {'fields': ('submitted_by', 'reviewed_by', 'onboarded_by', 'approved_by', 'created_at', 'updated_at')}),
    )


@admin.register(ServiceLine)
class ServiceLineAdmin(admin.ModelAdmin):
    list_display = ['request', 'service_type', 'capacity_mbps', 'quantity', 'total_monthly_charge', 'total_payable']
    list_filter = ['service_type']


@admin.register(OnboardingDocument)
class OnboardingDocumentAdmin(admin.ModelAdmin):
    list_display = ['request', 'doc_type', 'uploaded_at']
