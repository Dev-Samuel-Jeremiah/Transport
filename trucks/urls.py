from django.urls import path

from . import views

app_name = 'trucks'

urlpatterns = [
    # Admin: tracking board (read-only oversight)
    path('', views.AdminTruckListView.as_view(), name='admin_list'),
    path('bulk-delete/', views.AdminTruckBulkDeleteView.as_view(), name='admin_bulk_delete'),
    path('<int:pk>/', views.AdminTruckDetailView.as_view(), name='admin_detail'),

    # Company: manage own fleet
    path('mine/', views.CompanyTruckListView.as_view(), name='company_list'),
    path('mine/add/', views.CompanyTruckCreateView.as_view(), name='company_create'),
    path('mine/<int:pk>/', views.CompanyTruckDetailView.as_view(), name='company_detail'),
    path('mine/<int:pk>/edit/', views.CompanyTruckUpdateView.as_view(), name='company_edit'),
    path('mine/<int:pk>/documents/upload/', views.CompanyTruckDocumentUploadView.as_view(),
         name='company_document_upload'),
    path('mine/<int:pk>/location/update/', views.CompanyTruckLocationUpdateView.as_view(),
         name='company_location_update'),
    path('mine/<int:pk>/load/update/', views.CompanyTruckConsignmentUpdateView.as_view(),
         name='company_consignment_update'),
]