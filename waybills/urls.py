from django.urls import path

from . import views

app_name = 'waybills'

urlpatterns = [
    # Company: own LTIs & waybills. Creating and editing an individual
    # waybill is admin-only, so those routes are deliberately absent —
    # hiding the buttons alone would not stop a typed URL.
    path('mine/', views.CompanyLTIListView.as_view(), name='company_lti_list'),
    path('mine/new/', views.CompanyLTICreateView.as_view(), name='company_lti_create'),
    path('mine/export/', views.CompanyLTIExportView.as_view(), name='company_lti_export'),
    path('mine/import/', views.CompanyLTIImportView.as_view(), name='company_lti_import'),
    path('mine/<int:pk>/', views.CompanyLTIDetailView.as_view(), name='company_lti_detail'),
    path('mine/<int:lti_pk>/waybills/import/', views.CompanyWaybillImportView.as_view(),
         name='company_waybill_import'),
    path('mine/waybills/', views.CompanyWaybillListView.as_view(), name='company_waybill_list'),
    path('mine/waybills/export/', views.CompanyWaybillExportView.as_view(), name='company_waybill_export'),

    # Admin: platform-wide oversight
    path('', views.AdminLTIListView.as_view(), name='admin_lti_list'),
    path('export/', views.AdminLTIExportView.as_view(), name='admin_lti_export'),
    path('<int:pk>/', views.AdminLTIDetailView.as_view(), name='admin_lti_detail'),
    path('waybills/', views.AdminWaybillListView.as_view(), name='admin_waybill_list'),
    path('waybills/bulk-delete/', views.AdminWaybillBulkDeleteView.as_view(), name='admin_waybill_bulk_delete'),
    path('waybills/export/', views.AdminWaybillExportView.as_view(), name='admin_waybill_export'),
    path('waybills/import-sheet/', views.AdminTransitImportView.as_view(), name='admin_transit_import'),
]