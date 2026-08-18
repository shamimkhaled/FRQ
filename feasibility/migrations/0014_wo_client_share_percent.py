from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0013_customer_category_sfp_wavelength'),
    ]

    operations = [
        migrations.AddField(
            model_name='feasibilityrequest',
            name='wo_client_share_percent',
            field=models.DecimalField(
                decimal_places=2, default=50, max_digits=5, verbose_name='Client Share %',
            ),
        ),
    ]
