from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0003_consolidate_models'),
        ('workorders', '0002_workorder_onboarding_fields'),
    ]

    operations = [
        migrations.DeleteModel(name='WorkOrderDocument'),
        migrations.DeleteModel(name='WorkOrder'),
    ]
