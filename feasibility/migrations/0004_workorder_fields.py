from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0003_consolidate_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='feasibilityrequest',
            name='email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='feasibilityrequest',
            name='expected_installation_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='feasibilityrequest',
            name='wo_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='feasibilityrequest',
            name='wo_vat_percent',
            field=models.DecimalField(decimal_places=2, default=15, max_digits=5),
        ),
    ]
