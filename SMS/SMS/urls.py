from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="accounts/index.html"), name="index"),
    path('django-admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('company/', include('company.urls')),
    path("inventory/", include("inventory.urls")),
]