from django.urls import path

from . import views

app_name = 'drivers'

urlpatterns = [
    # Admin
    path('', views.DriverListView.as_view(), name='list'),
    path('bulk-delete/', views.DriverBulkDeleteView.as_view(), name='bulk_delete'),
    path('register/', views.DriverCreateView.as_view(), name='create'),
    path('onboard/', views.DriverOnboardView.as_view(), name='onboard'),
    path('<int:pk>/', views.DriverDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DriverUpdateView.as_view(), name='edit'),
    path('<int:pk>/documents/upload/', views.DriverDocumentUploadView.as_view(), name='document_upload'),
    path('<int:pk>/account/', views.DriverAccountView.as_view(), name='account'),

    # Company (read + document upload only)
    path('mine/', views.CompanyDriverListView.as_view(), name='company_list'),
    path('mine/<int:pk>/', views.CompanyDriverDetailView.as_view(), name='company_detail'),
    path('mine/<int:pk>/edit/', views.CompanyDriverUpdateView.as_view(), name='company_edit'),
    # Password-only: the single driver-account action a company gets.
    path('mine/<int:pk>/password/', views.CompanyDriverPasswordView.as_view(), name='company_password'),
    path('mine/<int:pk>/documents/upload/', views.CompanyDriverDocumentUploadView.as_view(),
         name='company_document_upload'),

    # Driver: self-service profile
    path('profile/', views.DriverProfileView.as_view(), name='profile'),
]