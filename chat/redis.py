import redis
import json
import os

REDIS_HOST = os.environ.get("REDIS_HOST", "host.docker.internal")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True,
)

REDIS_CHAT_LIMIT = 20


def get_room_key(room_name):
    return f"chat:room:{room_name}"


def add_message_to_redis(room_name, message_data):
    print("🔥 REDIS ADD:", room_name)
    key = get_room_key(room_name)
    redis_client.lpush(key, json.dumps(message_data))
    redis_client.ltrim(key, 0, REDIS_CHAT_LIMIT - 1)


def get_messages_from_redis(room_name):
    key = get_room_key(room_name)
    messages = redis_client.lrange(key, 0, -1)
    return [json.loads(msg) for msg in reversed(messages)]
