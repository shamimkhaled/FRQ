from django.db import migrations, models


def add_sftp_type_if_missing(apps, schema_editor):
    """Re-add sftp_type if a later (now-deleted) migration dropped/renamed it."""
    table = 'feasibility_feasibilityrequest'
    existing = {
        col.name
        for col in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(), table
        )
    }
    if 'sftp_type' in existing:
        return
    FeasibilityRequest = apps.get_model('feasibility', 'FeasibilityRequest')
    field = models.CharField(
        blank=True,
        choices=[
            ('dedicated', 'Dedicated'),
            ('shared', 'Shared'),
            ('colocation', 'Colocation'),
            ('others', 'Others'),
        ],
        max_length=30,
        verbose_name='SFTP Type',
    )
    field.set_attributes_from_name('sftp_type')
    schema_editor.add_field(FeasibilityRequest, field)


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0010_phase5_approvals'),
    ]

    operations = [
        migrations.RunPython(add_sftp_type_if_missing, migrations.RunPython.noop),
    ]
