from django.db import migrations


def backfill_wo_numbers(apps, schema_editor):
    FeasibilityRequest = apps.get_model('feasibility', 'FeasibilityRequest')
    for fr in FeasibilityRequest.objects.exclude(onboarding_status='').filter(wo_number__isnull=True):
        fr.wo_number = f'WO-{fr.pk:04d}'
        fr.save(update_fields=['wo_number'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0008_phase4_work_order'),
    ]

    operations = [
        migrations.RunPython(backfill_wo_numbers, noop),
    ]
