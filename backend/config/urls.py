from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.views import health

api_v1 = [
    path("health/", health, name="health"),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.domains.urls")),
    path("", include("apps.organizations.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
]

# Django admin is exposed only when explicitly enabled, on an obscure path.
if settings.DEBUG or getattr(settings, "ENABLE_ADMIN", False):
    urlpatterns.append(path("dv-admin/", admin.site.urls))
