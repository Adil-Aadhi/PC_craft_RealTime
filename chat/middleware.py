from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async

from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user(user_id):
    # 🔥 Import INSIDE function
    from shared.models import User
    from django.contrib.auth.models import AnonymousUser

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def __call__(self, scope, receive, send):
        print("JWT MIDDLEWARE HIT")

        # 🔥 Import INSIDE function
        from django.contrib.auth.models import AnonymousUser

        scope["user"] = AnonymousUser()

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token")

        if token:
            try:
                raw_token = token[0]
                validated_token = UntypedToken(raw_token)
                user_id = validated_token.payload.get("user_id")

                if user_id is not None:
                    scope["user"] = await get_user(int(user_id))

            except (InvalidToken, TokenError) as e:
                print("JWT ERROR:", e)
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
