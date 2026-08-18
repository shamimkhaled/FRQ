from django.core.files.base import ContentFile
from django.db import migrations, models


def copy_legacy_files(apps, schema_editor):
    FeasibilityRequest = apps.get_model('feasibility', 'FeasibilityRequest')
    OnboardingDocument = apps.get_model('feasibility', 'OnboardingDocument')
    mapping = (
        ('nid_front', 'nid_front'),
        ('nid_back', 'nid_back'),
        ('cheque_image', 'cheque'),
        ('extra_document', 'other'),
    )
    for fr in FeasibilityRequest.objects.all():
        for field_name, doc_type in mapping:
            field = getattr(fr, field_name, None)
            if not field:
                continue
            if OnboardingDocument.objects.filter(request=fr, doc_type=doc_type).exists():
                continue
            try:
                field.open()
                OnboardingDocument.objects.create(
                    request=fr,
                    doc_type=doc_type,
                    file=ContentFile(field.read(), name=field.name.split('/')[-1]),
                )
            except Exception:
                continue
            finally:
                try:
                    field.close()
                except Exception:
                    pass
        OnboardingDocument.objects.filter(request=fr, doc_type='nid').update(doc_type='nid_front')


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0014_wo_client_share_percent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='onboardingdocument',
            name='doc_type',
            field=models.CharField(
                choices=[
                    ('nid_front', 'NID Front'),
                    ('nid_back', 'NID Back'),
                    ('cheque', 'Cheque / Payment'),
                    ('agreement', 'Agreement'),
                    ('other', 'Other'),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(copy_legacy_files, migrations.RunPython.noop),
    ]
