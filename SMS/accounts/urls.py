from django.urls import path
from .views import admin_login, admin_dashboard, admin_logout
from .import views

urlpatterns = [
    path('login/', admin_login, name='admin_login'),
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('logout/', admin_logout, name='admin_logout'),

    path('admin/company/delete/<int:id>/', views.delete_company, name='delete_company'),
    path('admin/company/edit/<int:id>/', views.edit_company, name='edit_company'),
    path("admin/companies/", views.company_list, name="company_list"),


    path('notifications/', views.notifications, name='notifications')
]