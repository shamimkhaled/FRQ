from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0012_restore_sftp_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='feasibilityrequest',
            name='customer_category',
            field=models.CharField(
                blank=True,
                choices=[('BW', 'Bandwidth'), ('MAC', 'MAC'), ('DC', 'Data Connectivity')],
                default='BW',
                max_length=10,
                verbose_name='Customer Category',
            ),
        ),
        migrations.AddField(
            model_name='feasibilityrequest',
            name='sfp_wavelength',
            field=models.CharField(
                blank=True,
                choices=[('1310', '1310'), ('1550', '1550'), ('1270', '1270'), ('1330', '1330')],
                max_length=10,
                verbose_name='SFP Wavelength',
            ),
        ),
        migrations.AlterField(
            model_name='serviceline',
            name='service_type',
            field=models.CharField(
                choices=[
                    ('IPT', 'IPT - Internet Protocol Transit'),
                    ('GGC', 'GGC - Google Global Cache'),
                    ('FNA', 'FNA - Facebook Network Appliance'),
                    ('BDIX', 'BDIX - Bangladesh Internet Exchange'),
                    ('CDN', 'CDN - Content Delivery Network'),
                ],
                max_length=10,
            ),
        ),
    ]
