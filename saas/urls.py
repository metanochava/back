"""
URL configuration for dev project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from django_saas.core.utils.autoload_urls import build_saas_urls
from django_saas.view import home
from django_saas.view import deploy

router, extra_patterns = build_saas_urls()


urlpatterns = [
    path('', home, name='home'),
    path('api/', include(router.urls)),
    path('api/', include('django_saas.urls')),
    path('admin/', admin.site.urls),

]

urlpatterns += extra_patterns
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
