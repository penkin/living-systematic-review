import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

from django.db import DatabaseError  # noqa: E402
from web.models import Run  # noqa: E402

# A fresh process has no tagging thread, so a run still processing died with the old one.
try:
    Run.objects.filter(status=Run.PROCESSING).update(
        status=Run.FAILED, error="The server restarted during tagging. Upload the file again."
    )
except DatabaseError:  # no tables yet: migrate has not run
    pass
