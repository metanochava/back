
from django.urls import path, include
from rest_framework import routers

router = routers.DefaultRouter()


router.register("pacientes", FicheiroAPIView, basename="ficheiros")

urlpatterns = [
    path("", include(router.urls)),
    path("clinica/", include(router.urls)),
]
