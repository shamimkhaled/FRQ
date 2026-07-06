from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='bw_emails_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='workorder',
            name='installation_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='workorder',
            name='requested_capacity',
            field=models.PositiveIntegerField(default=0, help_text='Mbps'),
        ),
        migrations.AddField(
            model_name='workorder',
            name='selected_nttn',
            field=models.CharField(blank=True, choices=[('SCL', 'SCL'), ('fiber_home', 'Fiber@Home'), ('bahon', 'Bahon'), ('level3', 'Level3')], max_length=20),
        ),
        migrations.AlterField(
            model_name='workorder',
            name='company_name',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
