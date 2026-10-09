from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('django-admin/', admin.site.urls),  # built-in Django admin, kept for data ops/superuser use

    path('', RedirectView.as_view(pattern_name='dashboard:redirect', permanent=False)),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('companies/', include('companies.urls')),
    path('drivers/', include('drivers.urls')),
    path('trucks/', include('trucks.urls')),
    path('transit/', include('transit.urls')),
    path('waybills/', include('waybills.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
