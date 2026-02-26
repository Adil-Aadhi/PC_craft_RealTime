import uuid
from django.db import models
from shared.models import User

class ChatMessage(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    room_name = models.CharField(max_length=255, db_index=True)

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    message = models.TextField()
    
    message_type = models.CharField(max_length=20, default="text")
    build_ids = models.JSONField(blank=True, null=True)

    is_delivered = models.BooleanField(default=False)
    is_seen = models.BooleanField(default=False)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

class ChatRoom(models.Model):
    id = models.UUIDField(primary_key=True)
    room_name = models.CharField(max_length=255)
    participants = models.ManyToManyField(User)

    class Meta:
        managed = False
        db_table = "Worker_chatroom"




