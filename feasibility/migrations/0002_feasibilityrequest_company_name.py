from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feasibility', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='feasibilityrequest',
            name='company_name',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
