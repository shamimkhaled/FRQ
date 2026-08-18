import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('feasibility', '0004_workorder_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='NTTNProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('color', models.CharField(default='#607d8b', help_text='Hex color for map routes', max_length=7)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'NTTN Provider',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='ProviderRecommendationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criteria', models.CharField(choices=[('shortest_route', 'Shortest Fiber Route'), ('lowest_deployment_cost', 'Lowest Deployment Cost'), ('highest_capacity', 'Highest Available Capacity'), ('fastest_deployment', 'Fastest Deployment Time'), ('lowest_monthly_cost', 'Lowest Monthly Cost')], max_length=30, unique=True)),
                ('enabled', models.BooleanField(default=True)),
                ('priority', models.PositiveIntegerField(default=1, help_text='Lower number = higher priority')),
            ],
            options={
                'verbose_name': 'Recommendation Criteria',
                'verbose_name_plural': 'Recommendation Criteria',
                'ordering': ['priority'],
            },
        ),
        migrations.CreateModel(
            name='NTTNProviderResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_reference', models.CharField(blank=True, max_length=100, verbose_name='Provider Reference / Ticket ID')),
                ('response_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('under_review', 'Under Review'), ('feasible', 'Feasible'), ('feasible_additional_cost', 'Feasible with Additional Cost'), ('not_feasible', 'Not Feasible'), ('rejected', 'Rejected')], default='pending', max_length=30)),
                ('request_sent_at', models.DateTimeField(blank=True, null=True)),
                ('response_token', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('pop_name', models.CharField(blank=True, max_length=200, verbose_name='Provider POP Name')),
                ('pop_address', models.TextField(blank=True, verbose_name='Provider POP Address')),
                ('pop_latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('pop_longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('customer_latitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('customer_longitude', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('fiber_route_distance_km', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Estimated Fiber Route Distance (km)')),
                ('straight_line_distance_km', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Straight-Line Distance (km)')),
                ('estimated_deployment_time', models.CharField(blank=True, max_length=100)),
                ('available_capacity', models.PositiveIntegerField(blank=True, help_text='Mbps', null=True)),
                ('max_supported_capacity', models.PositiveIntegerField(blank=True, help_text='Mbps', null=True)),
                ('route_polyline', models.JSONField(blank=True, default=list, help_text='List of [lat, lng] coordinate pairs')),
                ('fiber_deployment_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('installation_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='One-Time Installation Cost')),
                ('monthly_bandwidth_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('additional_charges', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('total_estimated_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('engineering_remarks', models.TextField(blank=True)),
                ('route_condition', models.CharField(blank=True, choices=[('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor'), ('unknown', 'Unknown')], max_length=20)),
                ('existing_fiber', models.CharField(blank=True, choices=[('available', 'Available'), ('partial', 'Partially Available'), ('not_available', 'Not Available'), ('unknown', 'Unknown')], max_length=20, verbose_name='Existing Fiber Availability')),
                ('civil_work_required', models.BooleanField(blank=True, null=True)),
                ('pole_required', models.BooleanField(blank=True, null=True)),
                ('underground_fiber_required', models.BooleanField(blank=True, null=True)),
                ('additional_equipment', models.TextField(blank=True)),
                ('risk_assessment', models.TextField(blank=True)),
                ('recommended_solution', models.TextField(blank=True)),
                ('is_recommended', models.BooleanField(default=False)),
                ('recommendation_reasons', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('feasibility_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nttn_responses', to='feasibility.feasibilityrequest')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='responses', to='feasibility.nttnprovider')),
                ('submitted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='nttn_responses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'NTTN Provider Response',
                'ordering': ['provider__sort_order', 'provider__name'],
                'unique_together': {('feasibility_request', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='NTTNProviderAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attachment_type', models.CharField(choices=[('route_survey', 'Route Survey Report'), ('fiber_layout', 'Fiber Layout Diagram'), ('coverage_map', 'Coverage Map'), ('quotation', 'Quotation'), ('image', 'Image'), ('pdf', 'PDF Document'), ('other', 'Other')], default='other', max_length=20)),
                ('file', models.FileField(upload_to='nttn_attachments/')),
                ('description', models.CharField(blank=True, max_length=200)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('response', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='feasibility.nttnproviderresponse')),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
