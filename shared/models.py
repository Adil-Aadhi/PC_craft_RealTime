from django.db import models


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    email = models.EmailField()
    role = models.CharField(max_length=20)
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = "Authentication_user"

    def __str__(self):
        return self.email
