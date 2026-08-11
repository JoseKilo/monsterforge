from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paperminis', '0022_creature_cavalry_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='printsettings',
            name='crop_whitespace',
            field=models.BooleanField(default=False),
        ),
    ]
