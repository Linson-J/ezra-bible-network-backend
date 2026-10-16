from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("config", views.config, name="config"),
    path("schedule", views.schedule, name="schedule"),
    path("content", views.content, name="content"),
    path("verses", views.verses, name="verses"),
    path("prayer-requests", views.prayer_requests, name="prayer-requests"),
    path("devices", views.devices, name="devices"),
    path("health", views.health, name="health"),
]
