from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from companies.models import Company
from drivers.models import Driver
from trucks.models import Truck
from transit.models import Transit, TrackingUpdate

User = get_user_model()


class Command(BaseCommand):
    help = "Seed demo data: one admin, two companies, drivers, trucks and a sample transit."

    def handle(self, *args, **options):
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@freightline.test', 'admin12345', role=User.Role.ADMIN)
            self.stdout.write(self.style.SUCCESS("Created admin login: admin / admin12345"))

        admin_user = User.objects.get(username='admin')

        if not Company.objects.filter(registration_number='RC-001').exists():
            company = Company.objects.create(
                name='Swift Logistics Ltd', registration_number='RC-001',
                contact_person='Ada Obi', email='ops@swiftlogistics.test', phone='+2348012345678',
                address='12 Marina Road, Lagos', registered_by=admin_user,
            )
            company_user = User.objects.create_user(
                username='swiftlogistics', password='swiftlogistics12345',
                role=User.Role.COMPANY, company=company,
            )
            self.stdout.write(self.style.SUCCESS("Created company login: swiftlogistics / swiftlogistics12345"))

            driver = Driver.objects.create(
                company=company, full_name='Emeka Johnson', phone='+2348023456789',
                license_number='LIC-90210', status=Driver.Status.ACTIVE, registered_by=admin_user,
            )
            truck = Truck.objects.create(
                company=company, registration_number='LND-234-XY', make='MAN', model='TGS',
                year=2021, capacity_tons=15, status=Truck.Status.AVAILABLE,
                assigned_driver=driver, last_known_location='Swift Logistics Yard, Apapa',
            )
            transit = Transit.objects.create(
                company=company, truck=truck, driver=driver, reference_code='TRX-DEMO0001',
                origin='Apapa Port, Lagos', destination='Kano Central Market',
                cargo_description='Packaged consumer goods', cargo_weight_tons=12,
                status=Transit.Status.IN_TRANSIT, created_by=admin_user,
            )
            TrackingUpdate.objects.create(
                transit=transit, status=Transit.Status.PENDING, location_text='Apapa Port, Lagos',
                remarks='Trip created.', recorded_by=admin_user,
            )
            TrackingUpdate.objects.create(
                transit=transit, status=Transit.Status.IN_TRANSIT, location_text='Lagos-Ibadan Expressway, KM 25',
                remarks='Departed yard.', recorded_by=company_user,
            )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
