import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_user_role'),
        ('companies', '0003_company_password_is_temporary'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='company',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'For company users: the transporter this login belongs to. '
                    'Everything they can view or change is limited to this company.'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='users',
                to='companies.company',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='password_is_temporary',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'True while this login still has the temporary password issued at '
                    'enrollment. The user is forced to replace it on first sign-in.'
                ),
            ),
        ),
    ]
