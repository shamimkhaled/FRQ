from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.views.static import serve


@login_required
def protected_media(request, path):
    """Serve MEDIA_ROOT files to authenticated users only (no anonymous /media/)."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    full = (media_root / path).resolve()
    try:
        full.relative_to(media_root)
    except ValueError as exc:
        raise Http404() from exc
    if not full.is_file():
        raise Http404()
    return serve(request, path, document_root=settings.MEDIA_ROOT)
