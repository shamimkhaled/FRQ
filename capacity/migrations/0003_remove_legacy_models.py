from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0003_consolidate_models'),
        ('capacity', '0002_servicepricing_quantity'),
    ]

    operations = [
        migrations.DeleteModel(name='ServicePricing'),
        migrations.DeleteModel(name='CapacityConfirmation'),
    ]
