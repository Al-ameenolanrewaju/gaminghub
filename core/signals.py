# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from .models import Room
from .utils.email_service import EmailNotificationService
from django.dispatch import Signal

@receiver(post_save, sender=User)
def send_welcome_email_on_registration(sender, instance, created, **kwargs):
    """Send welcome email when new user registers"""
    if created and instance.email:
        EmailNotificationService.send_welcome_email(instance)

@receiver(post_save, sender=Room)
def send_room_update_notifications(sender, instance, created, **kwargs):
    """Send notifications for room events"""
    if created:
        # Notify host
        EmailNotificationService.send_room_notification(instance.host, instance, 'created')
    elif instance.status == 'started':
        # Notify all players when game starts
        for player in instance.players.all():
            EmailNotificationService.send_room_notification(player, instance, 'started')

@receiver(user_logged_in)
def send_login_notification(sender, request, user, **kwargs):
    """Send security notification for login from new device/location"""
    # You can add IP/location checking here
    if user.email:
        EmailNotificationService.send_admin_notification(
            "User Logged In",
            f"User {user.username} logged in from IP: {request.META.get('REMOTE_ADDR')}"
        )



# Create a new signal for bulk emails
weekly_email_signal = Signal()


@receiver(weekly_email_signal)
def handle_weekly_email(sender, **kwargs):
    """Handle weekly email trigger"""
    from .utils.email_service import EmailNotificationService

    print("📧 Triggering weekly emails via signal...")
    result = EmailNotificationService.send_bulk_weekly_update()
    print(f"✅ {result}")


@receiver(post_save, sender=Room)
def send_room_update_notifications(sender, instance, created, **kwargs):
    """Send notifications for room events - PUBLIC BROADCAST"""

    if created:
        # 1. Notify the host (private) - uses your existing template
        EmailNotificationService.send_room_notification(instance.host, instance, 'created')

        # 2. Broadcast to ALL other users (PUBLIC)
        # Delay by 2 minutes to let host prepare
        import threading
        def delayed_broadcast():
            import time
            time.sleep(120)  # Wait 2 minutes
            EmailNotificationService.broadcast_new_room(instance, exclude_user=instance.host)

        thread = threading.Thread(target=delayed_broadcast, daemon=True)
        thread.start()

        print(f"📢 Scheduled public broadcast for room: {instance.title}")

    elif instance.status == 'started':
        # Notify all players in the room - uses your existing template
        for player in instance.players.all():
            EmailNotificationService.send_room_notification(player, instance, 'started')