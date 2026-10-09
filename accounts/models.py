from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user. Three roles use this system:
      - ADMIN: platform/operations admin. Registers companies & drivers,
               enrolls company users, views documents, tracks all trucks.
      - COMPANY: a user enrolled by an admin under ONE transport company
               (see `company`). Sees and manages only that company's
               trucks, drivers and transits. A company can have many users.
      - DRIVER: a driver with a login to their own profile.
    Superusers created via createsuperuser are treated as ADMIN.
    """

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        COMPANY = 'COMPANY', 'Company'
        DRIVER = 'DRIVER', 'Driver'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.COMPANY)
    phone = models.CharField(max_length=20, blank=True)

    company = models.ForeignKey(
        'companies.Company',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='users',
        help_text=(
            "For company users: the transporter this login belongs to. "
            "Everything they can view or change is limited to this company."
        ),
    )
    password_is_temporary = models.BooleanField(
        default=False,
        help_text=(
            "True while this login still has the temporary password issued at "
            "enrollment. The user is forced to replace it on first sign-in."
        ),
    )

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_company_role(self):
        return self.role == self.Role.COMPANY and not self.is_superuser

    @property
    def is_driver_role(self):
        return self.role == self.Role.DRIVER and not self.is_superuser

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
