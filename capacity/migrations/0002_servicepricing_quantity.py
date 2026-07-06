from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('capacity', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicepricing',
            name='quantity',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
