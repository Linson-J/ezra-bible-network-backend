from network.models import AppConfig, PrayerRequest


def dashboard(request):
    """Shell data for every dashboard page: on-air pill and the prayer badge."""
    if request.path.startswith(("/api/", "/admin/")):
        return {}
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_staff):
        return {}
    return {
        "shell_is_live": AppConfig.load().is_live,
        "shell_new_prayers": PrayerRequest.objects.filter(status=PrayerRequest.Status.NEW).count(),
    }
