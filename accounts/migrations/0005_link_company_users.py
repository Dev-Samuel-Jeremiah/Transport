from django.db import migrations


def link_company_users(apps, schema_editor):
    """Carry every existing company login over to the new model.

    Until now each Company had exactly one login (Company.user). Those logins
    become ordinary enrolled users of that company, keeping their username,
    password and temporary-password state, so nobody is locked out.
    """
    Company = apps.get_model('companies', 'Company')
    User = apps.get_model('accounts', 'User')

    for company in Company.objects.all().iterator():
        User.objects.filter(pk=company.user_id).update(
            company_id=company.pk,
            password_is_temporary=company.password_is_temporary,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_user_company_user_password_is_temporary'),
        ('companies', '0003_company_password_is_temporary'),
    ]

    operations = [
        migrations.RunPython(link_company_users, migrations.RunPython.noop),
    ]
