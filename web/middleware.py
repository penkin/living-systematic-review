import base64
import hmac

from django.conf import settings
from django.http import HttpResponse


class PasswordGate:
    """Ask the browser for the one shared password when APP_PASSWORD is set.

    HTTP Basic auth: the browser shows its own prompt and resends the credentials on
    every request, so the poll script and the CSV download need no change.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.APP_PASSWORD and not self.allowed(request):
            response = HttpResponse("Password required.", status=401)
            response["WWW-Authenticate"] = 'Basic realm="Signal tool"'
            return response
        return self.get_response(request)

    @staticmethod
    def allowed(request):
        scheme, _, encoded = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            _, _, given = base64.b64decode(encoded, validate=True).decode().partition(":")
        except (ValueError, UnicodeDecodeError):
            return False
        return hmac.compare_digest(given, settings.APP_PASSWORD)
