from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import math


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


NTTN_PROVIDERS = [
    ('SCL', 'SCL'),
    ('fiber_home', 'Fiber@Home'),
    ('bahon', 'Bahon'),
    ('level3', 'Level3'),
]

FEASIBILITY_STATUS = [
    ('pending', 'Pending'),
    ('under_review', 'Under Review'),
    ('feasible', 'Feasible'),
    ('feasible_additional_cost', 'Feasible with Additional Cost'),
    ('not_feasible', 'Not Feasible'),
    ('rejected', 'Rejected'),
]

ONBOARDING_STATUS = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('pending_approval', 'Pending Approval'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('provisioning', 'Provisioning'),
    ('activated', 'Activated'),
    ('closed', 'Closed'),
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

APPROVED_FEASIBILITY_STATUSES = ('feasible', 'feasible_additional_cost')


class FeasibilityRequest(models.Model):
    """Single hub model for feasibility → onboarding → provisioning lifecycle."""

    # Customer & location
    customer_name = models.CharField(max_length=200)
    proprietor_name = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    # Service request
    requested_capacity = models.PositiveIntegerField(help_text='Capacity in Mbps')
    preferred_nttn = models.CharField(max_length=20, choices=NTTN_PROVIDERS, blank=True)
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

    # Onboarding (merged work order — no duplicate customer table)
    nid_number = models.CharField(max_length=50, blank=True)
    cheque_image = models.ImageField(upload_to='cheques/', null=True, blank=True)
    installation_notes = models.TextField(blank=True)
    expected_installation_date = models.DateField(null=True, blank=True)
    wo_vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15)
    wo_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    onboarding_status = models.CharField(max_length=20, choices=ONBOARDING_STATUS, blank=True)
    onboarding_remarks = models.TextField(blank=True)
    bandwidth_confirmations = models.JSONField(default=list, blank=True)
    bw_emails_sent = models.BooleanField(default=False)

    # Audit
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feasibility_requests')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    onboarded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarded_requests')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_name} - {self.get_status_display()}"

    @property
    def work_order_label(self):
        return f'WO-{self.pk:04d}'

    @property
    def is_onboarded(self):
        return bool(self.onboarding_status)

    @property
    def can_onboard(self):
        return self.status in APPROVED_FEASIBILITY_STATUSES

    @property
    def can_create_work_order(self):
        return self.can_onboard and not self.is_onboarded

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
        return {
            'subtotal_monthly': subtotal,
            'vat_total': vat_total,
            'discount_total': discount_total,
            'total_monthly': total_monthly,
            'total_one_time': total_one_time,
            'grand_total': total_monthly + total_one_time,
            'service_count': lines.count(),
            'total_mbps': total_mbps,
        }

    class Meta:
        ordering = ['-created_at']


class ServiceLine(models.Model):
    """Unified service + pricing line (replaces separate ServicePricing model)."""

    request = models.ForeignKey(FeasibilityRequest, on_delete=models.CASCADE, related_name='service_lines')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)
    capacity_mbps = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
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
        vat_amount = self.monthly_price * self.vat_percent / 100
        self.total_monthly_charge = self.monthly_price + vat_amount - self.discount
        self.total_payable = (
            self.total_monthly_charge + self.installation_charge
            + self.fiber_deployment_charge + self.one_time_charge
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.request.customer_name} | {self.service_type} | {self.capacity_mbps} Mbps'

    class Meta:
        ordering = ['-created_at']


class OnboardingDocument(models.Model):
    DOC_TYPES = [
        ('nid', 'NID Copy'),
        ('cheque', 'Cheque Image'),
        ('agreement', 'Agreement'),
        ('other', 'Other'),
    ]
    request = models.ForeignKey(FeasibilityRequest, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPES)
    file = models.FileField(upload_to='onboarding_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.request.work_order_label} - {self.get_doc_type_display()}'
