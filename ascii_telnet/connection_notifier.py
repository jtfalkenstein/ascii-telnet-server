from os import getenv
import yagmail

NOTIFICATION_USERNAME = getenv('NOTIFICATION_USERNAME')
NOTIFICATION_PASSWORD = getenv('NOTIFICATION_PASSWORD')
DESTINATION_EMAIL_ADDRESS = getenv('DESTINATION_EMAIL_ADDRESS')
APP_NAME = getenv('APP_NAME')


class MisconfiguredNotificationError(Exception):
    pass


def send_notification(
    notification_contents: str,
    username=NOTIFICATION_USERNAME,
    password=NOTIFICATION_PASSWORD,
    destination=DESTINATION_EMAIL_ADDRESS,
    app_name=APP_NAME
):
    if None in [username, password, destination, app_name]:
        raise MisconfiguredNotificationError(
            "You need NOTIFICATION_USERNAME, NOTIFICATION_PASSWORD, AND DESTINATION_EMAIL_ADDRESS set as environment "
            "variables."
        )

    gmail_client = yagmail.SMTP(
        username,
        password
    )
    gmail_client.send(
        to=destination,
        subject=f"Notification from {app_name}",
        contents=notification_contents
    )
