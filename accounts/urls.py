from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import StyledAuthenticationForm

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(
        template_name='registration/login.html',
        authentication_form=StyledAuthenticationForm,
    ), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # Admin: enroll and manage company users
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/enroll/', views.UserEnrollView.as_view(), name='user_enroll'),
    path('users/<int:pk>/reset-password/', views.UserResetPasswordView.as_view(), name='user_reset_password'),
    path('users/<int:pk>/edit/', views.UserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/toggle-active/', views.UserToggleActiveView.as_view(), name='user_toggle_active'),
]
