from django.urls import path
from .views import company_dashboard, company_login, company_logout, company_settings
from . import views

urlpatterns = [
    path("login/", company_login, name="company_login"),
    path("dashboard/", company_dashboard, name="company_dashboard"),
    path('new-entry/', views.new_entry, name='new_entry'),
    path('reports/', views.reports_page, name='reports'),
    path("stock/add/", views.add_stock, name="add_stock"),
    path("dispatch/", views.dispatcher, name="dispatch"),
    path("staff/add/", views.add_staff, name="add_staff"),
    path("export/", views.export_data, name="export_data"),
    path("transactions/", views.transactions_list, name="transactions_list"),
    path("settings/", company_settings, name="company_settings"),
    path("logout/", company_logout, name="company_logout"),
    path('inventory/stock-movement/export-stock/', views.export_stock_movement_pdf, name='export_stock_movement_pdf'),
    path('inventory/stock-movement/export-stock/<int:pk>/', views.export_stock_movement_pdf, name='export_products_stock_movement_pdf'),
    path("staff/", views.staff_list, name="staff_list"),
    path("export/download/", views.export_data_download, name="export_data_download"),
    path("delete-entry/<int:entry_id>/", views.delete_entry, name="delete_entry"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/verify-otp/", views.verify_otp, name="verify_otp"),
    path("forgot-password/resend-otp/",views.resend_otp,name="resend_otp"),
    path("forgot-password/reset_password/",views.reset_password,name="reset_password"),
]