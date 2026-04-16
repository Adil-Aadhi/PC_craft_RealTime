import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realtime.settings")
django.setup()

django_asgi_app = get_asgi_application()

from chat.middleware import JWTAuthMiddleware
import chat.routing

class OriginBypassMiddleware:
    """Bypass Daphne origin check completely"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            # Replace origin with allowed host
            headers = dict(scope.get("headers", []))
            headers[b"origin"] = b"https://pccraft3d.duckdns.org"
            scope["headers"] = list(headers.items())
        return await self.app(scope, receive, send)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": OriginBypassMiddleware(
        JWTAuthMiddleware(
            URLRouter(
                chat.routing.websocket_urlpatterns
            )
        )
    ),
})