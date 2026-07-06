from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_data(apps, schema_editor):
    FeasibilityRequest = apps.get_model('feasibility', 'FeasibilityRequest')
    ServiceLine = apps.get_model('feasibility', 'ServiceLine')

    try:
        WorkOrder = apps.get_model('workorders', 'WorkOrder')
    except LookupError:
        WorkOrder = None
    try:
        OldPricing = apps.get_model('capacity', 'ServicePricing')
    except LookupError:
        OldPricing = None
    try:
        OldCapacity = apps.get_model('capacity', 'CapacityConfirmation')
    except LookupError:
        OldCapacity = None

    if WorkOrder:
        for wo in WorkOrder.objects.select_related('feasibility').all():
            fr = wo.feasibility
            fr.nid_number = wo.nid_number or ''
            fr.cheque_image = wo.cheque_image
            fr.installation_notes = wo.installation_notes or ''
            fr.onboarding_status = wo.status or ''
            fr.onboarding_remarks = wo.remarks or ''
            fr.bw_emails_sent = wo.bw_emails_sent
            fr.onboarded_by_id = wo.created_by_id
            fr.approved_by_id = wo.approved_by_id
            if wo.selected_nttn:
                fr.preferred_nttn = wo.selected_nttn
            if wo.requested_capacity:
                fr.requested_capacity = wo.requested_capacity
            fr.save()

    if OldPricing:
        for p in OldPricing.objects.all():
            ServiceLine.objects.create(
                request_id=p.feasibility_id,
                service_type=p.service_type,
                capacity_mbps=p.capacity_mbps,
                unit_price=p.unit_price,
                quantity=getattr(p, 'quantity', 1) or 1,
                monthly_price=p.monthly_price,
                installation_charge=p.installation_charge,
                fiber_deployment_charge=p.fiber_deployment_charge,
                one_time_charge=p.one_time_charge,
                vat_percent=p.vat_percent,
                discount=p.discount,
                total_monthly_charge=p.total_monthly_charge,
                total_payable=p.total_payable,
            )

    if OldCapacity:
        by_request = {}
        for cc in OldCapacity.objects.all():
            by_request.setdefault(cc.feasibility_id, []).append({
                'provider': cc.provider,
                'requested_capacity': cc.requested_capacity,
                'available_capacity': cc.available_capacity,
                'status': cc.status,
                'confirmation_date': str(cc.confirmation_date) if cc.confirmation_date else None,
                'provider_reference': cc.provider_reference or '',
                'remarks': cc.remarks or '',
            })
        for fr_id, confs in by_request.items():
            FeasibilityRequest.objects.filter(pk=fr_id).update(bandwidth_confirmations=confs)


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0002_feasibilityrequest_company_name'),
        ('workorders', '0002_workorder_onboarding_fields'),
        ('capacity', '0002_servicepricing_quantity'),
    ]

    operations = [
        migrations.AddField(model_name='feasibilityrequest', name='bandwidth_confirmations', field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name='feasibilityrequest', name='bw_emails_sent', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='feasibilityrequest', name='cheque_image', field=models.ImageField(blank=True, null=True, upload_to='cheques/')),
        migrations.AddField(model_name='feasibilityrequest', name='installation_notes', field=models.TextField(blank=True)),
        migrations.AddField(model_name='feasibilityrequest', name='nid_number', field=models.CharField(blank=True, max_length=50)),
        migrations.AddField(model_name='feasibilityrequest', name='onboarding_remarks', field=models.TextField(blank=True)),
        migrations.AddField(model_name='feasibilityrequest', name='onboarding_status', field=models.CharField(blank=True, choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('pending_approval', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('provisioning', 'Provisioning'), ('activated', 'Activated'), ('closed', 'Closed')], max_length=20)),
        migrations.AddField(model_name='feasibilityrequest', name='approved_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_requests', to='auth.user')),
        migrations.AddField(model_name='feasibilityrequest', name='onboarded_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='onboarded_requests', to='auth.user')),
        migrations.CreateModel(
            name='ServiceLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_type', models.CharField(choices=[('IPT', 'IPT - Internet Protocol Transit'), ('GGC', 'GGC - Google Global Cache'), ('FNA', 'FNA - Facebook Network Appliance'), ('BDIX', 'BDIX - Bangladesh Internet Exchange'), ('CDN', 'CDN - Content Delivery Network')], max_length=10)),
                ('capacity_mbps', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('monthly_price', models.DecimalField(decimal_places=2, editable=False, max_digits=12)),
                ('installation_charge', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('fiber_deployment_charge', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('one_time_charge', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('vat_percent', models.DecimalField(decimal_places=2, default=15, max_digits=5)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('total_monthly_charge', models.DecimalField(decimal_places=2, editable=False, max_digits=12)),
                ('total_payable', models.DecimalField(decimal_places=2, editable=False, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_lines', to='feasibility.feasibilityrequest')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='OnboardingDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_type', models.CharField(choices=[('nid', 'NID Copy'), ('cheque', 'Cheque Image'), ('agreement', 'Agreement'), ('other', 'Other')], max_length=20)),
                ('file', models.FileField(upload_to='onboarding_docs/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='feasibility.feasibilityrequest')),
            ],
        ),
        migrations.RunPython(migrate_legacy_data, migrations.RunPython.noop),
    ]
