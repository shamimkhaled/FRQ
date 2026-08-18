from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.shortcuts import redirect

from kloud.media import protected_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('accounts_dept.urls')),
    path('feasibility/', include('feasibility.urls')),
    path('workorders/', include('workorders.urls')),
    path('', lambda request: redirect('feasibility:dashboard'), name='home'),
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        protected_media,
        name='protected_media',
    ),
]
