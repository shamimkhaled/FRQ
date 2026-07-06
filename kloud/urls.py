from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('feasibility/', include('feasibility.urls')),
    path('workorders/', include('workorders.urls')),
    path('capacity/', include('capacity.urls')),
    path('', lambda request: redirect('feasibility:dashboard'), name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
