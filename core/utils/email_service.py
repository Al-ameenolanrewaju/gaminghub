# utils/email_service.py
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone



class EmailNotificationService:

    @staticmethod
    def send_welcome_email(user):
        """Send welcome email to new user"""
        subject = f"🎮 Welcome to {settings.SITE_NAME}!"
        html_message = render_to_string('emails/welcome.html', {
            'user': user,
            'site_name': settings.SITE_NAME,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

    @staticmethod
    def send_game_invitation(user, game, inviter):
        """Send game invitation email"""
        subject = f"🎮 {inviter.username} invited you to play {game.title}!"
        html_message = render_to_string('emails/game_invitation.html', {
            'user': user,
            'game': game,
            'inviter': inviter,
            'site_name': settings.SITE_NAME,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

    @staticmethod
    def send_room_notification(user, room, action):
        """Send room-related notifications"""
        actions = {
            'created': f"🎮 New Room Created: {room.title}",
            'joined': f"🎮 You've Joined: {room.title}",
            'started': f"🎮 Game Started: {room.title}",
            'ended': f"🎮 Game Ended: {room.title}",
        }

        subject = actions.get(action, f"Room Update: {room.title}")
        html_message = render_to_string('emails/room_notification.html', {
            'user': user,
            'room': room,
            'action': action,
            'site_name': settings.SITE_NAME,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

    @staticmethod
    def send_password_changed(user):
        """Send password change confirmation"""
        subject = f"🔒 Password Changed - {settings.SITE_NAME}"
        html_message = render_to_string('emails/password_changed.html', {
            'user': user,
            'site_name': settings.SITE_NAME,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

    @staticmethod
    def send_admin_notification(subject, message):
        """Send notification to admins"""
        admin_emails = [admin[1] for admin in settings.ADMINS]
        if admin_emails:
            send_mail(
                subject=f"👑 ADMIN: {subject}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False,
            )

    @staticmethod
    def send_bulk_weekly_update():
        """Send weekly update to all active users"""
        # Get all active users with emails
        users = User.objects.filter(is_active=True).exclude(email='')

        for user in users:
            try:
                # Get context for this user
                context = {
                    'user': user,
                    'username': user.username,
                    'dashboard_link': f"https://gaminghubcompany.pythonanywhere.com/dashboard",
                    'current_date': timezone.now().strftime("%B %d, %Y"),
                    'unsubscribe_link': f"https://gaminghubcompany.pythonanywhere.com/unsubscribe/{user.id}/",
                }

                # Render email template
                html_content = render_to_string('emails/weekly_update.html', context)

                # Create and send email
                email = EmailMultiAlternatives(
                    subject="🎮 Your Weekly Gaming Hub Update",
                    body="Check out new rooms and tournaments on Gaming Hub!",  # Plain text fallback
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[user.email]
                )
                email.attach_alternative(html_content, "text/html")
                email.send()

                print(f"✅ Sent weekly update to {user.email}")

            except Exception as e:
                print(f"❌ Failed for {user.email}: {str(e)}")

        return f"Sent to {users.count()} users"

    @staticmethod
    def send_bulk_announcement(subject, message):
        """Send announcement to all users"""
        users = User.objects.filter(is_active=True).exclude(email='')

        for user in users:
            try:
                send_mail(
                    subject=subject,
                    message=f"Hey {user.username},\n\n{message}\n\n- Gaming Hub Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except:
                pass  # Skip failed emails

        return f"Announcement sent to {users.count()} users"


@staticmethod
def broadcast_new_room(room, exclude_user=None):
    """
    Broadcast new room notification to ALL active users
    """
    from django.contrib.auth.models import User
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    # Get all active users with emails
    users = User.objects.filter(
        is_active=True
    ).exclude(email='').exclude(email__isnull=True)

    # Exclude the host (they already got a creation email)
    if exclude_user:
        users = users.exclude(id=exclude_user.id)

    print(f"📢 Broadcasting '{room.name}' to {users.count()} users")

    sent_count = 0
    failed_count = 0

    for i, user in enumerate(users):
        try:
            # Skip if no valid email
            if not user.email or '@' not in user.email:
                continue

            # Prepare context
            context = {
                'user': user,
                'room': room,
                'action': 'broadcast',
                'site_name': settings.SITE_NAME,
                'unsubscribe_link': f"https://gaminghubcompany.pythonanywhere.com/unsubscribe/{user.id}/",
            }

            # Render template
            html_content = render_to_string('emails/room_notification.html', context)

            # Create plain text version
            plain_text = f"""
🎮 NEW GAMING ROOM: {room.name}

A new room has been created on Gaming Hub!

Room: {room.name}
Game: {getattr(room, 'game', 'Multiplayer')}
Host: {room.host.username if room.host else 'A player'}
Players: {getattr(room, 'players', '1')}/{getattr(room, 'max_players', '10')}

Join now: https://gaminghubcompany.pythonanywhere.com/room/{room.id}/

- Gaming Hub Team
"""

            # Send email
            send_mail(
                subject=f"🎮 NEW ROOM: {room.name}",
                message=plain_text.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=False,
            )

            sent_count += 1
            print(f"  ✅ [{i + 1}/{users.count()}] Sent to {user.email}")

            # Rate limiting (every 10 emails)
            if sent_count % 10 == 0:
                import time
                print(f"  ⏳ Pausing 10 seconds...")
                time.sleep(10)

        except Exception as e:
            failed_count += 1
            print(f"  ❌ Failed for {user.email}: {str(e)[:50]}")

    # Log results
    print(f"\n{'=' * 50}")
    print(f"📊 BROADCAST COMPLETE")
    print(f"   Room: {room.name}")
    print(f"   Total users: {users.count()}")
    print(f"   Successfully sent: {sent_count}")
    print(f"   Failed: {failed_count}")
    print(f"{'=' * 50}")

    # Save to log file
    import time
    from django.utils import timezone
    log_entry = (
        f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"BROADCAST: Room='{room.name}' (ID:{room.id}), "
        f"Sent={sent_count}, Failed={failed_count}\n"
    )

    try:
        with open('/home/Gaminghubcompany/email_logs.txt', 'a') as f:
            f.write(log_entry)
    except:
        pass

    return sent_count