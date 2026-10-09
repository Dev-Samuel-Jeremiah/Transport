from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('drivers', '0003_driver_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='driver',
            name='password_is_temporary',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "True while the driver's login still carries the temporary password "
                    "issued at onboarding. Cleared once the company — or the driver — sets a real one."
                ),
            ),
        ),
    ]
