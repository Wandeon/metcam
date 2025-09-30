"""
Notification service for FootballVision Pro
Handles email, SMS, and webhook notifications
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import requests
import logging
from ..config import get_settings
from ..database.db_manager import get_db_manager

logger = logging.getLogger(__name__)


class NotificationService:
    """Handles sending notifications via various channels"""

    def __init__(self):
        self.settings = get_settings()
        self.db = get_db_manager()

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send email notification

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (HTML supported)

        Returns:
            True if sent successfully
        """
        if not self.settings.smtp_host:
            logger.warning("SMTP not configured, skipping email notification")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.settings.smtp_from
            msg['To'] = to
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.smtp_username and self.settings.smtp_password:
                    server.starttls()
                    server.login(self.settings.smtp_username, self.settings.smtp_password)

                server.send_message(msg)

            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_sms(self, to: str, message: str) -> bool:
        """
        Send SMS notification via Twilio

        Args:
            to: Recipient phone number
            message: SMS message

        Returns:
            True if sent successfully
        """
        if not self.settings.twilio_account_sid:
            logger.warning("Twilio not configured, skipping SMS notification")
            return False

        try:
            from twilio.rest import Client

            client = Client(
                self.settings.twilio_account_sid,
                self.settings.twilio_auth_token
            )

            message = client.messages.create(
                body=message,
                from_=self.settings.twilio_from_number,
                to=to
            )

            logger.info(f"SMS sent to {to}: {message.sid}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return False

    def send_webhook(self, url: str, data: dict) -> bool:
        """
        Send webhook notification

        Args:
            url: Webhook URL
            data: Data to send

        Returns:
            True if sent successfully
        """
        try:
            response = requests.post(
                url,
                json=data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            response.raise_for_status()
            logger.info(f"Webhook sent to {url}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False

    def send_discord(self, message: str, embed: Optional[dict] = None) -> bool:
        """
        Send Discord notification

        Args:
            message: Message content
            embed: Optional Discord embed

        Returns:
            True if sent successfully
        """
        if not self.settings.discord_webhook_url:
            logger.warning("Discord webhook not configured")
            return False

        payload = {"content": message}
        if embed:
            payload["embeds"] = [embed]

        return self.send_webhook(self.settings.discord_webhook_url, payload)

    def send_slack(self, message: str, blocks: Optional[list] = None) -> bool:
        """
        Send Slack notification

        Args:
            message: Message text
            blocks: Optional Slack blocks

        Returns:
            True if sent successfully
        """
        if not self.settings.slack_webhook_url:
            logger.warning("Slack webhook not configured")
            return False

        payload = {"text": message}
        if blocks:
            payload["blocks"] = blocks

        return self.send_webhook(self.settings.slack_webhook_url, payload)

    def notify_recording_started(self, match_id: str, home_team: str, away_team: str):
        """Send notification when recording starts"""
        subject = f"Recording Started: {home_team} vs {away_team}"
        body = f"""
        <h2>Recording Started</h2>
        <p>Match: <strong>{home_team} vs {away_team}</strong></p>
        <p>Match ID: {match_id}</p>
        <p>Status: Recording in progress</p>
        """

        # Get notification email from config
        config = self.db.execute_query(
            "SELECT value FROM device_config WHERE key = 'notification_email'"
        )

        if config and config[0]['value']:
            self.send_email(config[0]['value'], subject, body)

        # Send Discord notification
        self.send_discord(
            f"🔴 **Recording Started**\n{home_team} vs {away_team}",
            embed={
                "title": "Match Recording",
                "description": f"{home_team} vs {away_team}",
                "color": 0x00ff00,
                "fields": [
                    {"name": "Status", "value": "Recording", "inline": True},
                    {"name": "Match ID", "value": match_id, "inline": True}
                ]
            }
        )

    def notify_recording_stopped(self, match_id: str, duration_seconds: int, file_size_gb: float):
        """Send notification when recording stops"""
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60

        subject = "Recording Completed"
        body = f"""
        <h2>Recording Completed</h2>
        <p>Match ID: {match_id}</p>
        <p>Duration: {hours}h {minutes}m</p>
        <p>File Size: {file_size_gb:.2f} GB</p>
        <p>Processing will start automatically.</p>
        """

        config = self.db.execute_query(
            "SELECT value FROM device_config WHERE key = 'notification_email'"
        )

        if config and config[0]['value']:
            self.send_email(config[0]['value'], subject, body)

        self.send_discord(
            f"⏹️ **Recording Completed**\nDuration: {hours}h {minutes}m | Size: {file_size_gb:.2f} GB"
        )

    def notify_processing_completed(self, match_id: str, panorama_path: str):
        """Send notification when processing completes"""
        subject = "Match Processing Completed"
        body = f"""
        <h2>Match Processing Completed</h2>
        <p>Match ID: {match_id}</p>
        <p>Panoramic video is ready for download.</p>
        <p>File: {panorama_path}</p>
        """

        config = self.db.execute_query(
            "SELECT value FROM device_config WHERE key = 'notification_email'"
        )

        if config and config[0]['value']:
            self.send_email(config[0]['value'], subject, body)

        self.send_discord(
            f"✅ **Processing Completed**\nMatch {match_id} is ready for download!"
        )

    def notify_error(self, error_type: str, message: str):
        """Send error notification"""
        subject = f"System Error: {error_type}"
        body = f"""
        <h2>System Error</h2>
        <p>Type: {error_type}</p>
        <p>Message: {message}</p>
        <p>Please check the system logs for details.</p>
        """

        config = self.db.execute_query(
            "SELECT value FROM device_config WHERE key = 'notification_email'"
        )

        if config and config[0]['value']:
            self.send_email(config[0]['value'], subject, body)

        self.send_discord(
            f"⚠️ **System Error**\n{error_type}: {message}"
        )


# Singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service