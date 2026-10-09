from django.urls import path

from . import views

app_name = 'companies'

urlpatterns = [
    path('', views.CompanyListView.as_view(), name='list'),
    path('bulk-delete/', views.CompanyBulkDeleteView.as_view(), name='bulk_delete'),
    path('register/', views.CompanyCreateView.as_view(), name='create'),
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CompanyUpdateView.as_view(), name='edit'),
    path('<int:pk>/documents/upload/', views.CompanyDocumentUploadView.as_view(), name='document_upload'),

    # Company: self-service profile
    path('profile/', views.CompanyProfileView.as_view(), name='profile'),
]