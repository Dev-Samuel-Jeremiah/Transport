from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0003_company_password_is_temporary'),
        # The login -> company links must be copied onto User before the old
        # Company.user column is dropped.
        ('accounts', '0005_link_company_users'),
    ]

    operations = [
        migrations.RemoveField(model_name='company', name='password_is_temporary'),
        migrations.RemoveField(model_name='company', name='user'),
    ]
