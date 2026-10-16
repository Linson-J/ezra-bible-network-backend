from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.home, name="home"),
    path("live/", views.live, name="live"),
    path("live/toggle/", views.toggle_live, name="toggle-live"),
    path("schedule/", views.schedule, name="schedule"),
    path("schedule/new/", views.program_form, name="program-new"),
    path("schedule/copy/", views.schedule_copy, name="schedule-copy"),
    path("schedule/<int:pk>/", views.program_form, name="program-edit"),
    path("schedule/<int:pk>/delete/", views.program_delete, name="program-delete"),
    path("schedule/<int:pk>/toggle/", views.program_toggle, name="program-toggle"),
    path("verses/", views.verses, name="verses"),
    path("verses/day/<int:day>/", views.daily_verse_edit, name="daily-verse-edit"),
    path("verses/special/new/", views.special_verse_form, name="special-new"),
    path("verses/special/<int:pk>/", views.special_verse_form, name="special-edit"),
    path("verses/special/<int:pk>/delete/", views.special_verse_delete, name="special-delete"),
    path("prayers/", views.prayers, name="prayers"),
    path("prayers/<int:pk>/update/", views.prayer_update, name="prayer-update"),
    path("prayers/<int:pk>/delete/", views.prayer_delete, name="prayer-delete"),
    path("content/", views.content, name="content"),
]
