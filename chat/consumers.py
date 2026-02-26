import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from chat.models import ChatMessage, ChatRoom
from shared.models import User
from chat.redis import add_message_to_redis, get_messages_from_redis


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")

        if isinstance(user, AnonymousUser):
            await self.close()
            return

        self.user_id = user.id
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        # ✅ CHECK USER IS PARTICIPANT
        allowed = await self.is_participant(self.user_id)

        if not allowed:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        db_messages = await self.get_chat_history()
        redis_messages = get_messages_from_redis(self.room_name)

        db_ids = {m["id"] for m in db_messages}
        merged = db_messages + [m for m in redis_messages if m["id"] not in db_ids]

        for m in merged:
            m.setdefault("message_type", "text")
            m.setdefault("build_ids", None)

        messages = merged

        if not messages:
            messages = await self.get_chat_history()

        await self.send(text_data=json.dumps({
            "type": "chat_history",
            "payload": messages
        }))
        # 🔥 mark all messages from other user as seen
        await self.mark_room_messages_seen()

        # 🔥 notify other participant
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": {
                    "type": "message_seen",
                    "payload": {
                        "room_name": self.room_name,
                        "seen_by": self.user_id
                    }
                }
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get("type")

        if event_type == "chat_message":
            await self.handle_chat_message(data)

        elif event_type == "typing":
            await self.handle_typing(data)

        elif event_type == "message_delivered":
            await self.handle_message_delivered(data)

        elif event_type == "message_seen":
            await self.handle_message_seen(data)

        elif event_type == "build_bundle":
            await self.handle_build_bundle(data)

    # ------------------------
    # HANDLERS
    # ------------------------

    async def handle_chat_message(self, data):
        payload = data.get("payload", {})

        message_id = payload.get("id")
        message = payload.get("message")

        if not all([message_id, message]):
            print("❌ Invalid chat payload:", payload)
            return

        sender = await self.get_user(self.user_id)

        message_data = {
            "id": str(message_id),
            "room_name": self.room_name,
            "sender_id": sender.id,
            "sender_name": sender.email,
            "message": message,
            "message_type": "text",   # ✅ add
            "build_ids": None,
            "is_delivered": True,
            "is_seen": False,
        }

        # ✅ Save to DB
        await self.save_message(message_id, sender, message)

        # ✅ Save to Redis
        add_message_to_redis(self.room_name, message_data)

        # ✅ Broadcast
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": {
                    "type": "chat_message",
                    "payload": message_data
                }
            }
        )
    async def handle_build_bundle(self, data):
        payload = data.get("payload", {})
        message_id = payload.get("id")
        text = payload.get("message", "")
        build_ids = payload.get("build_ids", [])

        if not message_id or not build_ids:
            print("❌ Invalid build_bundle payload:", payload)
            return

        sender = await self.get_user(self.user_id)

        message_data = {
            "id": str(message_id),
            "room_name": self.room_name,
            "sender_id": sender.id,
            "sender_name": sender.email,
            "message": text,
            "message_type": "build_bundle",
            "build_ids": build_ids,
            "is_delivered": True,
            "is_seen": False,
        }
        print("📦 BUILD HANDLER HIT:", message_data)
        # ✅ Save to DB
        await self.save_build_bundle(message_id, sender, text, build_ids)

        # ✅ Save to Redis
        add_message_to_redis(self.room_name, message_data)

        # ✅ Broadcast
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": {
                    "type": "build_bundle",
                    "payload": message_data
                }
            }
        )

    async def handle_typing(self, data):
        payload = data.get("payload", {})

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": {
                    "type": "typing",
                    "payload": {
                        "sender_id": self.user_id,
                        "is_typing": payload.get("is_typing"),
                    }
                }
            }
        )

    async def handle_message_delivered(self, data):
        payload = data.get("payload", {})

        await self.mark_delivered(payload.get("message_id"))

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": data
            }
        )

    async def handle_message_seen(self, data):
        payload = data.get("payload", {})

        await self.mark_seen(payload.get("message_id"))

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "broadcast_message",
                "event": data
            }
        )

    # ------------------------
    # BROADCAST
    # ------------------------

    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps(event["event"]))

    # ------------------------
    # DB HELPERS
    # ------------------------

    @database_sync_to_async
    def get_user(self, user_id):
        return User.objects.get(id=user_id)

    @database_sync_to_async
    def save_message(self, message_id, sender, message):
        ChatMessage.objects.create(
            id=message_id,
            room_name=self.room_name,
            sender=sender,
            message=message,
            is_delivered=True,
        )
    @database_sync_to_async
    def save_build_bundle(self, message_id, sender, text, build_ids):
        ChatMessage.objects.create(
            id=message_id,
            room_name=self.room_name,
            sender=sender,
            message=text,
            message_type="build_bundle",
            build_ids=build_ids,
            is_delivered=True,
        )

    @database_sync_to_async
    def mark_delivered(self, message_id):
        if message_id:
            ChatMessage.objects.filter(id=message_id).update(is_delivered=True)

    @database_sync_to_async
    def mark_seen(self, message_id):
        if message_id:
            ChatMessage.objects.filter(id=message_id).update(is_seen=True)

    @database_sync_to_async
    def get_chat_history(self):
        qs = (
            ChatMessage.objects
            .filter(room_name=self.room_name)
            .order_by("-timestamp")[:50]
        )

        qs = list(reversed(qs))

        return [
            {
                "id": str(m.id),
                "sender_id": m.sender_id,
                "sender_name": m.sender.email, 
                "message": m.message,
                "message_type": m.message_type,        # ✅ add
                "build_ids": m.build_ids,
                "is_delivered": m.is_delivered,
                "is_seen": m.is_seen,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in qs
        ]

    # ------------------------
    # PARTICIPANT CHECK 🔒
    # ------------------------

    @database_sync_to_async
    def is_participant(self, user_id):
        return ChatRoom.objects.filter(
            room_name=self.room_name,
            participants__id=user_id
        ).exists()
    
    @database_sync_to_async
    def mark_room_messages_seen(self):
        ChatMessage.objects.filter(
            room_name=self.room_name
        ).exclude(sender_id=self.user_id).update(is_seen=True)
