from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import math
import secrets


def google_maps_url(latitude, longitude):
    if latitude is None or longitude is None:
        return ''
    return f'https://www.google.com/maps?q={latitude},{longitude}'


def google_maps_directions_url(origin_lat, origin_lng, dest_lat, dest_lng):
    if origin_lat is None or origin_lng is None or dest_lat is None or dest_lng is None:
        return ''
    return (
        'https://www.google.com/maps/dir/?api=1'
        f'&origin={origin_lat},{origin_lng}'
        f'&destination={dest_lat},{dest_lng}'
    )


class POPLocation(models.Model):
    name = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    address = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'POP Location'


class Division(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class District(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='districts')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = [('division', 'name')]

    def __str__(self):
        return self.name


class Upazila(models.Model):
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='upazilas')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        unique_together = [('district', 'name')]

    def __str__(self):
        return self.name


NTTN_PROVIDERS = [
    ('SCL', 'SCL'),
    ('fiber_home', 'Fiber@Home'),
    ('bahon', 'Bahon'),
    ('level3', 'Level3'),
]

FEASIBILITY_STATUS = [
    ('pending', 'Pending'),
    ('submitted', 'Submitted'),
    ('under_review', 'Under Review'),
    ('feasible', 'Feasible'),
    ('feasible_additional_cost', 'Feasible with Additional Cost'),
    ('not_feasible', 'Not Feasible'),
    ('rejected', 'Rejected'),
]

CUSTOMER_TYPES = [
    ('new', 'New'),
    ('existing', 'Existing'),
]

SFTP_TYPES = [
    ('dedicated', 'Dedicated'),
    ('shared', 'Shared'),
    ('colocation', 'Colocation'),
    ('others', 'Others'),
]

CUSTOMER_CATEGORIES = [
    ('BW', 'Bandwidth'),
    ('MAC', 'MAC'),
    ('DC', 'Data Connectivity'),
]

SFP_WAVELENGTHS = [
    ('1310', '1310'),
    ('1550', '1550'),
    ('1270', '1270'),
    ('1330', '1330'),
]

ONBOARDING_STATUS = [
    ('draft', 'Draft'),
    ('submitted', 'Accounts Review'),
    ('pending_approval', 'Pending Approval'),
    ('accounts_approved', 'Management Review'),
    ('management_approved', 'Technical Configuration'),
    ('tech_submitted', 'Technical Review'),
    ('correction_requested', 'Correction Requested'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('provisioning', 'Provisioning'),
    ('activated', 'Activated'),
    ('closed', 'Closed'),
]

WO_WORKFLOW_STEPS = [
    ('accounts', 'Accounts', ('submitted', 'pending_approval')),
    ('management', 'Management', ('accounts_approved',)),
    ('core', 'Tech Config', ('management_approved',)),
    ('technical', 'Tech Review', ('tech_submitted',)),
    ('activation', 'Activation', ('approved', 'provisioning', 'activated')),
]

BANDWIDTH_STATUS = [
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('partially_confirmed', 'Partially Confirmed'),
    ('rejected', 'Rejected'),
]

SERVICE_TYPES = [
    ('IPT', 'IPT - Internet Protocol Transit'),
    ('GGC', 'GGC - Google Global Cache'),
    ('FNA', 'FNA - Facebook Network Appliance'),
    ('BDIX', 'BDIX - Bangladesh Internet Exchange'),
    ('CDN', 'CDN - Content Delivery Network'),
]

SERVICE_UNIT_PRICE = {
    'IPT': 100, 'GGC': 100, 'FNA': 10, 'BDIX': 50, 'CDN': 50,
}

DEFAULT_UPSTREAM_PROVIDERS = [
    ('summit', 'Summit', 1),
    ('level3', 'Level 3', 2),
    ('others', 'Others', 3),
]

APPROVED_FEASIBILITY_STATUSES = ('feasible', 'feasible_additional_cost')


class UpstreamProvider(models.Model):
    """Admin-configurable upstream / preferred provider for work orders."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Upstream Provider'

    def __str__(self):
        return self.name


class FeasibilityRequest(models.Model):
    """Single hub model for feasibility → onboarding → provisioning lifecycle."""

    # Customer & location
    frq_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name='FRQ ID')
    contact_person = models.CharField(max_length=200, blank=True)
    customer_name = models.CharField(max_length=200)  # legacy — synced from contact_person
    proprietor_name = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default='new')
    address = models.TextField()
    division = models.ForeignKey(
        Division, null=True, blank=True, on_delete=models.SET_NULL, related_name='feasibility_requests',
    )
    district = models.ForeignKey(
        District, null=True, blank=True, on_delete=models.SET_NULL, related_name='feasibility_requests',
    )
    upazila = models.ForeignKey(
        Upazila, null=True, blank=True, on_delete=models.SET_NULL, related_name='feasibility_requests',
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    # Service request
    requested_capacity = models.PositiveIntegerField(help_text='Capacity in Mbps')
    preferred_nttn = models.CharField(max_length=30, choices=NTTN_PROVIDERS, blank=True)  # legacy code sync
    preferred_nttn_provider = models.ForeignKey(
        'NTTNProvider', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='preferred_requests', verbose_name='Preferred NTTN',
    )
    preferred_nttn_other = models.CharField(max_length=100, blank=True, verbose_name='Other NTTN Name')
    supported_nttn = models.JSONField(default=list)

    # Distance / POP
    nearest_pop = models.ForeignKey(POPLocation, null=True, blank=True, on_delete=models.SET_NULL)
    distance_to_pop_km = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    air_distance_km = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    fiber_route_distance_km = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    estimated_fiber_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Feasibility review
    status = models.CharField(max_length=30, choices=FEASIBILITY_STATUS, default='pending')
    estimated_delivery_days = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    engineering_notes = models.TextField(blank=True)
    emails_sent = models.BooleanField(default=False)
    review_submitted_at = models.DateTimeField(null=True, blank=True)
    review_email_sent = models.BooleanField(default=False)

    # Onboarding (merged work order — no duplicate customer table)
    nid_number = models.CharField(max_length=50, blank=True)
    cheque_image = models.ImageField(upload_to='cheques/', null=True, blank=True)
    installation_notes = models.TextField(blank=True)
    expected_installation_date = models.DateField(null=True, blank=True)
    wo_vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    wo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wo_client_share_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=50, verbose_name='Client Share %',
    )
    onboarding_status = models.CharField(max_length=32, choices=ONBOARDING_STATUS, blank=True)
    onboarding_remarks = models.TextField(blank=True)
    bandwidth_confirmations = models.JSONField(default=list, blank=True)
    bw_emails_sent = models.BooleanField(default=False)
    wo_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name='Work Order ID')
    sftp_type = models.CharField(max_length=30, choices=SFTP_TYPES, blank=True, verbose_name='SFTP Type')
    sfp_wavelength = models.CharField(
        max_length=10, choices=SFP_WAVELENGTHS, blank=True, verbose_name='SFP Wavelength',
    )
    customer_category = models.CharField(
        max_length=10, choices=CUSTOMER_CATEGORIES, blank=True, default='BW',
        verbose_name='Customer Category',
    )
    billing_date = models.DateField(null=True, blank=True)
    nid_front = models.FileField(upload_to='nid/front/', null=True, blank=True, verbose_name='NID Front')
    nid_back = models.FileField(upload_to='nid/back/', null=True, blank=True, verbose_name='NID Back')
    extra_document = models.FileField(upload_to='wo_docs/', null=True, blank=True, verbose_name='Additional Document')
    upstream_provider = models.ForeignKey(
        UpstreamProvider, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='work_orders', verbose_name='Upstream Provider',
    )
    upstream_provider_other = models.CharField(max_length=100, blank=True, verbose_name='Other Upstream Name')
    wo_submitted_at = models.DateTimeField(null=True, blank=True)
    wo_email_sent = models.BooleanField(default=False)
    vlan_id = models.CharField(max_length=50, blank=True, verbose_name='VLAN ID')
    scr = models.CharField(max_length=80, blank=True, verbose_name='SCR')
    link_id = models.CharField(max_length=80, blank=True, verbose_name='Link ID')
    technical_notes = models.TextField(blank=True)
    activation_date = models.DateField(null=True, blank=True)
    correction_from_stage = models.CharField(max_length=20, blank=True)
    accounts_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts_reviewed_orders',
    )
    management_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='management_reviewed_orders',
    )
    tech_configured_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tech_configured_orders',
    )
    tech_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tech_reviewed_orders',
    )

    # Audit
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feasibility_requests')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    onboarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarded_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        label = self.display_name
        frq = self.frq_number or f'#{self.pk}'
        return f"{frq} — {label} ({self.get_status_display()})"

    @property
    def display_name(self):
        return self.contact_person or self.customer_name

    @property
    def frq_label(self):
        return self.frq_number or (f'FRQ-{self.pk}' if self.pk else '—')

    def save(self, *args, **kwargs):
        if self.contact_person:
            self.customer_name = self.contact_person
        elif self.customer_name and not self.contact_person:
            self.contact_person = self.customer_name
        self.sync_preferred_nttn_code()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        updates = []
        if is_new and not self.frq_number:
            self.frq_number = f'FRQ-{self.pk}'
            updates.append('frq_number')
        if self.onboarding_status and not self.wo_number:
            self.wo_number = f'WO-{self.pk:04d}'
            updates.append('wo_number')
        if updates:
            super().save(update_fields=updates)

    @property
    def wo_kloud_share_percent(self):
        client = Decimal(str(self.wo_client_share_percent or 50))
        client = min(max(client, Decimal('0')), Decimal('100'))
        return Decimal('100') - client

    @property
    def can_create_work_order(self):
        return self.can_onboard and not self.is_onboarded

    @property
    def work_order_label(self):
        return self.wo_number or (f'WO-{self.pk:04d}' if self.pk else 'WO')

    @property
    def upstream_provider_label(self):
        if self.upstream_provider_id:
            if self.upstream_provider.code == 'others' and self.upstream_provider_other:
                return self.upstream_provider_other
            return self.upstream_provider.name
        return '—'

    @property
    def is_onboarded(self):
        return bool(self.onboarding_status)

    @property
    def can_onboard(self):
        return self.status in APPROVED_FEASIBILITY_STATUSES

    @property
    def preferred_nttn_label(self):
        if self.preferred_nttn_provider_id:
            if self.preferred_nttn_provider.code == 'others' and self.preferred_nttn_other:
                return self.preferred_nttn_other
            return self.preferred_nttn_provider.name
        if self.preferred_nttn:
            return NTTNProvider.get_display_name(self.preferred_nttn)
        return '—'

    @property
    def customer_maps_url(self):
        return google_maps_url(self.latitude, self.longitude)

    def sync_preferred_nttn_code(self):
        if self.preferred_nttn_provider_id:
            self.preferred_nttn = self.preferred_nttn_provider.code
        elif not self.preferred_nttn:
            self.preferred_nttn = ''

    def ensure_primary_nttn_review_entry(self):
        """Create initial NTTN review row from preferred provider if none exist."""
        if self.nttn_review_entries.exists() or not self.preferred_nttn_provider_id:
            return
        FRQNTTNReviewEntry.objects.create(
            feasibility_request=self,
            provider=self.preferred_nttn_provider,
            provider_other_name=self.preferred_nttn_other,
            pop_latitude=self.latitude,
            pop_longitude=self.longitude,
            sort_order=0,
        )

    @property
    def distance_meters(self):
        if self.distance_to_pop_km is None:
            return None
        return round(float(self.distance_to_pop_km) * 1000, 1)

    @property
    def coverage_assessment(self):
        if not self.nearest_pop:
            return 'no_coverage', 'No active POP within network coverage.'
        dist = float(self.air_distance_km or 0)
        if dist > 30:
            return 'extended', f'Extended coverage area ({dist} km from nearest POP). Additional fiber cost may apply.'
        return 'standard', f'Within standard coverage ({dist} km from nearest POP).'

    @property
    def all_bandwidth_confirmed(self):
        confs = self.bandwidth_confirmations or []
        if not confs:
            return False
        return all(c.get('status') not in ('pending', 'rejected') for c in confs)

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
        dphi = math.radians(float(lat2) - float(lat1))
        dlambda = math.radians(float(lon2) - float(lon1))
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def find_nearest_pop_and_calculate(self):
        pops = POPLocation.objects.filter(is_active=True)
        if not pops.exists():
            return
        nearest, min_dist = None, float('inf')
        for pop in pops:
            dist = self.haversine(self.latitude, self.longitude, pop.latitude, pop.longitude)
            if dist < min_dist:
                min_dist, nearest = dist, pop
        self.nearest_pop = nearest
        self.air_distance_km = round(min_dist, 3)
        self.distance_to_pop_km = round(min_dist, 3)
        self.fiber_route_distance_km = round(min_dist * 1.3, 3)
        self.estimated_fiber_cost = round(min_dist * 25000, 2)

    def seed_bandwidth_confirmation(self):
        if not self.preferred_nttn:
            return
        confs = list(self.bandwidth_confirmations or [])
        if any(c.get('provider') == self.preferred_nttn for c in confs):
            return
        confs.append({
            'provider': self.preferred_nttn,
            'requested_capacity': self.requested_capacity,
            'approved_capacity': None,
            'available_capacity': None,
            'status': 'pending',
            'confirmation_date': None,
            'provider_reference': '',
            'remarks': '',
        })
        self.bandwidth_confirmations = confs

    @property
    def bandwidth_status_label(self):
        confs = self.bandwidth_confirmations or []
        if not confs:
            return 'Not Started'
        if all(c.get('status') == 'confirmed' for c in confs):
            return 'Confirmed'
        if any(c.get('status') == 'rejected' for c in confs):
            return 'Rejected'
        if any(c.get('status') == 'partially_confirmed' for c in confs):
            return 'Partially Confirmed'
        if any(c.get('status') == 'pending' for c in confs):
            return 'Pending'
        return 'In Progress'

    def get_pricing_summary(self):
        lines = self.service_lines.all()
        if not lines:
            return None
        subtotal = sum(line.monthly_price for line in lines)
        vat_total = sum(line.monthly_price * line.vat_percent / 100 for line in lines)
        wo_discount = Decimal(str(self.wo_discount or 0))
        discount_total = sum(line.discount for line in lines) + wo_discount
        total_monthly = sum(line.total_monthly_charge for line in lines) - wo_discount
        total_one_time = sum(
            line.installation_charge + line.fiber_deployment_charge + line.one_time_charge
            for line in lines
        )
        total_mbps = sum(line.capacity_mbps * (line.quantity or 1) for line in lines)
        if self.customer_category == 'MAC':
            client_pct = Decimal(str(self.wo_client_share_percent or 50))
            client_pct = min(max(client_pct, Decimal('0')), Decimal('100'))
            mac_client = subtotal * client_pct / 100
            mac_kloud = subtotal - mac_client
        else:
            mac_client = mac_kloud = 0
        return {
            'subtotal_monthly': subtotal,
            'vat_total': vat_total,
            'discount_total': discount_total,
            'total_monthly': total_monthly,
            'total_one_time': total_one_time,
            'grand_total': total_monthly + total_one_time,
            'service_count': lines.count(),
            'total_mbps': total_mbps,
            'mac_client_share': mac_client,
            'mac_kloud_share': mac_kloud,
        }

    @property
    def workflow_current_key(self):
        status = self.onboarding_status
        if status in ('rejected', 'correction_requested'):
            return self.correction_from_stage or 'accounts'
        if status in ('activated', 'closed'):
            return 'activation'
        for key, _label, statuses in WO_WORKFLOW_STEPS:
            if status in statuses:
                return key
        return 'accounts'

    class Meta:
        ordering = ['-created_at']


class WorkOrderApproval(models.Model):
    """Stage review action on a work order (Accounts → Management → Core → Technical)."""

    STAGE_CHOICES = [
        ('accounts', 'Accounts'),
        ('management', 'Management'),
        ('core', 'Core / NTTN'),
        ('technical', 'Technical Team'),
        ('sales', 'Sales & Marketing'),
    ]
    ACTION_CHOICES = [
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('request_correction', 'Correction Requested'),
        ('submit_config', 'Configuration Submitted'),
        ('resubmit', 'Resubmitted'),
    ]

    request = models.ForeignKey(
        FeasibilityRequest, on_delete=models.CASCADE, related_name='wo_approvals',
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    remarks = models.TextField(blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Work Order Approval'

    def __str__(self):
        return f'{self.request.work_order_label} {self.stage} {self.action}'


class ServiceLine(models.Model):
    """Unified service + pricing line (replaces separate ServicePricing model)."""

    request = models.ForeignKey(FeasibilityRequest, on_delete=models.CASCADE, related_name='service_lines')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)
    capacity_mbps = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    client_share_percent = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    kloud_share_percent = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    installation_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fiber_deployment_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    one_time_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_monthly_charge = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        qty = self.quantity or 1
        self.monthly_price = self.capacity_mbps * self.unit_price * qty
        is_mac = bool(self.request_id and getattr(self.request, 'customer_category', '') == 'MAC')
        if is_mac:
            client = Decimal(str(
                getattr(self.request, 'wo_client_share_percent', None) or self.client_share_percent or 50
            ))
            client = min(max(client, Decimal('0')), Decimal('100'))
            self.client_share_percent = client
            self.kloud_share_percent = Decimal('100') - client
        vat_amount = self.monthly_price * self.vat_percent / 100
        self.total_monthly_charge = self.monthly_price + vat_amount - self.discount
        self.total_payable = (
            self.total_monthly_charge + self.installation_charge
            + self.fiber_deployment_charge + self.one_time_charge
        )
        super().save(*args, **kwargs)

    @property
    def client_share_amount(self):
        return (self.monthly_price or 0) * (self.client_share_percent or 0) / 100

    @property
    def kloud_share_amount(self):
        return (self.monthly_price or 0) * (self.kloud_share_percent or 0) / 100

    def __str__(self):
        return f'{self.request.display_name} | {self.get_service_type_display()} | {self.capacity_mbps} Mbps'

    class Meta:
        ordering = ['-created_at']


class OnboardingDocument(models.Model):
    DOC_TYPES = [
        ('nid_front', 'NID Front'),
        ('nid_back', 'NID Back'),
        ('cheque', 'Cheque / Payment'),
        ('agreement', 'Agreement'),
        ('other', 'Other'),
    ]
    request = models.ForeignKey(FeasibilityRequest, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    file = models.FileField(upload_to='onboarding_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.request.work_order_label} - {self.get_doc_type_display()}'


PROVIDER_RESPONSE_STATUS = FEASIBILITY_STATUS  # same status choices

ROUTE_CONDITIONS = [
    ('good', 'Good'),
    ('fair', 'Fair'),
    ('poor', 'Poor'),
    ('unknown', 'Unknown'),
]

FIBER_AVAILABILITY = [
    ('available', 'Available'),
    ('partial', 'Partially Available'),
    ('not_available', 'Not Available'),
    ('unknown', 'Unknown'),
]

ATTACHMENT_TYPES = [
    ('route_survey', 'Route Survey Report'),
    ('fiber_layout', 'Fiber Layout Diagram'),
    ('coverage_map', 'Coverage Map'),
    ('quotation', 'Quotation'),
    ('image', 'Image'),
    ('pdf', 'PDF Document'),
    ('other', 'Other'),
]

RECOMMENDATION_CRITERIA = [
    ('shortest_route', 'Shortest Fiber Route'),
    ('lowest_deployment_cost', 'Lowest Deployment Cost'),
    ('highest_capacity', 'Highest Available Capacity'),
    ('fastest_deployment', 'Fastest Deployment Time'),
    ('lowest_monthly_cost', 'Lowest Monthly Cost'),
]

DEFAULT_PROVIDER_COLORS = {
    'kloud': '#1565c0',
    'SCL': '#2e7d32',
    'fiber_home': '#f57f17',
    'bangla_phone': '#6a1b9a',
    'others': '#607d8b',
    'bahon': '#6a1b9a',
    'level3': '#c62828',
}

# Phase 2 default NTTN registry (database-driven via NTTNProvider)
DEFAULT_NTTN_PROVIDERS = [
    ('SCL', 'SCL', '#2e7d32'),
    ('fiber_home', 'Fiber@Home', '#f57f17'),
    ('bangla_phone', 'Bangla Phone', '#6a1b9a'),
    ('others', 'Others', '#607d8b'),
]


class NTTNProvider(models.Model):
    """Configurable NTTN provider registry."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    contact_email = models.EmailField(blank=True)
    color = models.CharField(max_length=7, default='#607d8b', help_text='Hex color for map routes')
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'NTTN Provider'

    def __str__(self):
        return self.name

    @classmethod
    def get_display_name(cls, code):
        try:
            return cls.objects.get(code=code).name
        except cls.DoesNotExist:
            for c, label in NTTN_PROVIDERS:
                if c == code:
                    return label
            return code


class FRQNTTNReviewEntry(models.Model):
    """Inline NTTN review row on the unified FRQ review page."""

    feasibility_request = models.ForeignKey(
        FeasibilityRequest, on_delete=models.CASCADE, related_name='nttn_review_entries',
    )
    provider = models.ForeignKey(NTTNProvider, on_delete=models.PROTECT, related_name='review_entries')
    provider_other_name = models.CharField(max_length=100, blank=True)
    pop_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    pop_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    straight_distance_km = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Distance from customer (km)',
    )
    notes = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'FRQ NTTN Review Entry'

    def __str__(self):
        return f'{self.provider_label} → {self.feasibility_request.frq_label}'

    @property
    def provider_label(self):
        if self.provider.code == 'others' and self.provider_other_name:
            return self.provider_other_name
        return self.provider.name

    @property
    def maps_url(self):
        fr = self.feasibility_request
        return google_maps_directions_url(
            fr.latitude, fr.longitude, self.pop_latitude, self.pop_longitude,
        )

    def recalculate_distance(self):
        fr = self.feasibility_request
        if self.pop_latitude and self.pop_longitude and fr.latitude and fr.longitude:
            dist = FeasibilityRequest.haversine(
                fr.latitude, fr.longitude, self.pop_latitude, self.pop_longitude,
            )
            self.straight_distance_km = round(dist, 3)
        return self.straight_distance_km

    def save(self, *args, **kwargs):
        self.recalculate_distance()
        super().save(*args, **kwargs)


class ProviderRecommendationConfig(models.Model):
    """Configurable business rules for automatic provider recommendation."""

    criteria = models.CharField(max_length=30, choices=RECOMMENDATION_CRITERIA, unique=True)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1, help_text='Lower number = higher priority')

    class Meta:
        ordering = ['priority']
        verbose_name = 'Recommendation Criteria'
        verbose_name_plural = 'Recommendation Criteria'

    def __str__(self):
        return f'{self.get_criteria_display()} (priority {self.priority})'


class NTTNProviderResponse(models.Model):
    """Independent feasibility response from an NTTN provider."""

    feasibility_request = models.ForeignKey(
        FeasibilityRequest, on_delete=models.CASCADE, related_name='nttn_responses',
    )
    provider = models.ForeignKey(NTTNProvider, on_delete=models.PROTECT, related_name='responses')
    provider_reference = models.CharField(max_length=100, blank=True, verbose_name='Provider Reference / Ticket ID')
    response_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=PROVIDER_RESPONSE_STATUS, default='pending')
    request_sent_at = models.DateTimeField(null=True, blank=True)
    response_token = models.CharField(max_length=64, blank=True, unique=True, null=True)

    # Distance & network
    pop_name = models.CharField(max_length=200, blank=True, verbose_name='Provider POP Name')
    pop_address = models.TextField(blank=True, verbose_name='Provider POP Address')
    pop_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    pop_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    customer_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    customer_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    fiber_route_distance_km = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Estimated Fiber Route Distance (km)',
    )
    straight_line_distance_km = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Straight-Line Distance (km)',
    )
    estimated_deployment_time = models.CharField(max_length=100, blank=True)
    available_capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Mbps')
    max_supported_capacity = models.PositiveIntegerField(null=True, blank=True, help_text='Mbps')
    route_polyline = models.JSONField(default=list, blank=True, help_text='List of [lat, lng] coordinate pairs')

    # Commercial
    fiber_deployment_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    installation_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='One-Time Installation Cost')
    monthly_bandwidth_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    additional_charges = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Engineering feedback
    engineering_remarks = models.TextField(blank=True)
    route_condition = models.CharField(max_length=20, choices=ROUTE_CONDITIONS, blank=True)
    existing_fiber = models.CharField(max_length=20, choices=FIBER_AVAILABILITY, blank=True, verbose_name='Existing Fiber Availability')
    civil_work_required = models.BooleanField(null=True, blank=True)
    pole_required = models.BooleanField(null=True, blank=True)
    underground_fiber_required = models.BooleanField(null=True, blank=True)
    additional_equipment = models.TextField(blank=True)
    risk_assessment = models.TextField(blank=True)
    recommended_solution = models.TextField(blank=True)

    # Recommendation
    is_recommended = models.BooleanField(default=False)
    recommendation_reasons = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='nttn_responses')

    class Meta:
        ordering = ['provider__sort_order', 'provider__name']
        unique_together = [('feasibility_request', 'provider')]
        verbose_name = 'NTTN Provider Response'

    def __str__(self):
        return f'{self.provider.name} → {self.feasibility_request.customer_name}'

    def save(self, *args, **kwargs):
        if not self.response_token:
            self.response_token = secrets.token_urlsafe(32)
        if self.feasibility_request_id and not self.customer_latitude:
            fr = self.feasibility_request
            self.customer_latitude = fr.latitude
            self.customer_longitude = fr.longitude
        if self.pop_latitude and self.pop_longitude and self.customer_latitude and self.customer_longitude:
            if not self.straight_line_distance_km:
                dist = FeasibilityRequest.haversine(
                    self.customer_latitude, self.customer_longitude,
                    self.pop_latitude, self.pop_longitude,
                )
                self.straight_line_distance_km = round(dist, 3)
        super().save(*args, **kwargs)

    @property
    def distance_difference_km(self):
        if self.straight_line_distance_km and self.fiber_route_distance_km:
            return round(float(self.fiber_route_distance_km) - float(self.straight_line_distance_km), 3)
        return None

    @property
    def map_color(self):
        return self.provider.color or DEFAULT_PROVIDER_COLORS.get(self.provider.code, '#607d8b')

    @property
    def is_feasible(self):
        return self.status in ('feasible', 'feasible_additional_cost')

    def calculate_total_cost(self):
        parts = [self.fiber_deployment_cost, self.installation_cost, self.additional_charges]
        total = sum(p for p in parts if p is not None)
        if total:
            self.total_estimated_cost = total
        return self.total_estimated_cost


class NTTNProviderAttachment(models.Model):
    response = models.ForeignKey(NTTNProviderResponse, on_delete=models.CASCADE, related_name='attachments')
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPES, default='other')
    file = models.FileField(upload_to='nttn_attachments/')
    description = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.response.provider.name} - {self.get_attachment_type_display()}'
