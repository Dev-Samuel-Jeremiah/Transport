from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.redirect_by_role, name='redirect'),
    path('admin-panel/', views.AdminHomeView.as_view(), name='admin_home'),
    path('admin-panel/analysis/', views.AdminAnalyticsView.as_view(), name='admin_analytics'),
    path('company/', views.CompanyHomeView.as_view(), name='company_home'),
]
