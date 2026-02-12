import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter



os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realtime.settings")

# 🔥 Initialize Django FIRST
django_asgi_app = get_asgi_application()

# 🔥 Import routing AFTER Django setup
from chat.middleware import JWTAuthMiddleware
import chat.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})
