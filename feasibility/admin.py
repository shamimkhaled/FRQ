from django.contrib import admin
from .models import (
    POPLocation, FeasibilityRequest, ServiceLine, OnboardingDocument,
    NTTNProvider, NTTNProviderResponse, NTTNProviderAttachment,
    ProviderRecommendationConfig, Division, District, Upazila,
    FRQNTTNReviewEntry, UpstreamProvider, WorkOrderApproval,
)


@admin.register(POPLocation)
class POPLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'latitude', 'longitude', 'is_active']
    list_filter = ['is_active']


class ServiceLineInline(admin.TabularInline):
    model = ServiceLine
    extra = 0
    readonly_fields = ['monthly_price', 'total_monthly_charge', 'total_payable']


class NTTNProviderResponseInline(admin.TabularInline):
    model = NTTNProviderResponse
    extra = 0
    readonly_fields = ['request_sent_at', 'response_token', 'is_recommended']
    fields = [
        'provider', 'status', 'provider_reference', 'response_date',
        'fiber_route_distance_km', 'available_capacity', 'is_recommended',
    ]


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ['name', 'division', 'is_active']
    list_filter = ['division', 'is_active']
    search_fields = ['name']


@admin.register(Upazila)
class UpazilaAdmin(admin.ModelAdmin):
    list_display = ['name', 'district', 'is_active']
    list_filter = ['district__division', 'is_active']
    search_fields = ['name']


@admin.register(FRQNTTNReviewEntry)
class FRQNTTNReviewEntryAdmin(admin.ModelAdmin):
    list_display = ['feasibility_request', 'provider', 'straight_distance_km', 'sort_order']
    list_filter = ['provider']


class OnboardingDocumentInline(admin.TabularInline):
    model = OnboardingDocument
    extra = 0


@admin.register(FeasibilityRequest)
class FeasibilityRequestAdmin(admin.ModelAdmin):
    list_display = [
        'frq_number', 'wo_number', 'contact_person', 'company_name', 'status', 'onboarding_status',
        'requested_capacity', 'nearest_pop', 'created_at',
    ]
    list_filter = ['status', 'onboarding_status', 'customer_type', 'customer_category', 'preferred_nttn']
    search_fields = ['frq_number', 'contact_person', 'customer_name', 'phone_number', 'address', 'company_name', 'email']
    readonly_fields = [
        'frq_number', 'wo_number', 'created_at', 'updated_at', 'nearest_pop', 'distance_to_pop_km',
        'air_distance_km', 'fiber_route_distance_km', 'estimated_fiber_cost',
    ]
    inlines = [ServiceLineInline, OnboardingDocumentInline, NTTNProviderResponseInline]
    fieldsets = (
        ('FRQ', {'fields': ('frq_number', 'wo_number', 'status', 'customer_type')}),
        ('Customer', {'fields': (
            'contact_person', 'customer_name', 'proprietor_name', 'company_name',
            'phone_number', 'email', 'address', 'division', 'district', 'upazila',
        )}),
        ('Location', {'fields': ('latitude', 'longitude', 'nearest_pop', 'distance_to_pop_km', 'air_distance_km', 'fiber_route_distance_km', 'estimated_fiber_cost')}),
        ('Feasibility', {'fields': (
            'requested_capacity', 'preferred_nttn_provider', 'preferred_nttn_other',
            'preferred_nttn', 'supported_nttn', 'estimated_delivery_days',
            'remarks', 'engineering_notes', 'emails_sent', 'review_submitted_at', 'review_email_sent',
        )}),
        ('Onboarding', {'fields': (
            'onboarding_status', 'customer_category', 'sfp_wavelength', 'billing_date',
            'upstream_provider', 'upstream_provider_other',
            'nid_number',
            'installation_notes', 'expected_installation_date', 'onboarding_remarks',
            'wo_vat_percent', 'wo_discount', 'wo_client_share_percent', 'bandwidth_confirmations',
            'bw_emails_sent', 'wo_submitted_at', 'wo_email_sent',
            'vlan_id', 'scr', 'link_id', 'technical_notes', 'activation_date',
            'correction_from_stage',
        )}),
        ('Audit', {'fields': (
            'submitted_by', 'reviewed_by', 'onboarded_by', 'approved_by',
            'accounts_reviewed_by', 'management_reviewed_by',
            'tech_configured_by', 'tech_reviewed_by',
            'created_at', 'updated_at',
        )}),
    )


@admin.register(ServiceLine)
class ServiceLineAdmin(admin.ModelAdmin):
    list_display = ['request', 'service_type', 'capacity_mbps', 'quantity', 'client_share_percent', 'total_monthly_charge', 'total_payable']
    list_filter = ['service_type']


@admin.register(OnboardingDocument)
class OnboardingDocumentAdmin(admin.ModelAdmin):
    list_display = ['request', 'doc_type', 'uploaded_at']


@admin.register(WorkOrderApproval)
class WorkOrderApprovalAdmin(admin.ModelAdmin):
    list_display = ['request', 'stage', 'action', 'user', 'created_at']
    list_filter = ['stage', 'action', 'created_at']
    search_fields = ['request__wo_number', 'remarks']


@admin.register(UpstreamProvider)
class UpstreamProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'sort_order']
    list_filter = ['is_active']
    list_editable = ['is_active', 'sort_order']
    search_fields = ['name', 'code']


@admin.register(NTTNProvider)
class NTTNProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'contact_email', 'color', 'is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


class NTTNProviderAttachmentInline(admin.TabularInline):
    model = NTTNProviderAttachment
    extra = 0


@admin.register(NTTNProviderResponse)
class NTTNProviderResponseAdmin(admin.ModelAdmin):
    list_display = [
        'feasibility_request', 'provider', 'status', 'fiber_route_distance_km',
        'available_capacity', 'is_recommended', 'response_date',
    ]
    list_filter = ['status', 'provider', 'is_recommended']
    search_fields = ['feasibility_request__customer_name', 'provider_reference']
    readonly_fields = ['response_token', 'request_sent_at', 'recommendation_reasons']
    inlines = [NTTNProviderAttachmentInline]


@admin.register(ProviderRecommendationConfig)
class ProviderRecommendationConfigAdmin(admin.ModelAdmin):
    list_display = ['criteria', 'enabled', 'priority']
    list_editable = ['enabled', 'priority']
