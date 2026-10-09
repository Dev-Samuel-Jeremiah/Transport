from django.urls import path

from . import views

app_name = 'transit'

urlpatterns = [
    # Company. Creating a transit by hand is an admin action, so no
    # create route is exposed here — hiding the button alone would not
    # stop a typed URL.
    # Company
    path('mine/', views.CompanyTransitListView.as_view(), name='company_list'),
    path('mine/delivered/', views.CompanyDeliveredListView.as_view(), name='company_delivered'),
    # Downloads are scoped to the signed-in company by the view itself.
    path('mine/export/', views.CompanyTransitExportView.as_view(), name='company_export'),
    path('mine/delivered/export/', views.CompanyDeliveredExportView.as_view(), name='company_delivered_export'),
    path('mine/<int:pk>/', views.CompanyTransitDetailView.as_view(), name='company_detail'),
    path('mine/<int:pk>/update/', views.CompanyTransitStatusUpdateView.as_view(), name='company_status_update'),

    # Admin
    path('', views.AdminTransitListView.as_view(), name='admin_list'),
    path('export/', views.AdminTransitExportView.as_view(), name='admin_export'),
    path('delivered/export/', views.AdminDeliveredExportView.as_view(), name='admin_delivered_export'),
    path('bulk-delete/', views.AdminTransitBulkDeleteView.as_view(), name='admin_bulk_delete'),
    path('<int:pk>/confirm/', views.AdminTransitConfirmView.as_view(), name='admin_confirm'),
    path('<int:pk>/restore/', views.AdminTransitRestoreView.as_view(), name='admin_restore'),
    path('audit/', views.AdminTransitAuditListView.as_view(), name='admin_audit_list'),
    path('<int:pk>/', views.AdminTransitDetailView.as_view(), name='admin_detail'),
]