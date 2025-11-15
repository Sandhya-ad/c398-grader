from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse  

def health(request):
    return HttpResponse("ok")

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("grading.urls")),
]