from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = "Ezra Bible Network"
admin.site.site_title = "Ezra Bible Network"
admin.site.index_title = "Database admin"

urlpatterns = [
    path("api/", include("network.urls")),
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
]

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
