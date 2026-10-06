"""Known SMTP providers and safe credential preservation."""
from .reporting import valid_email

SIGNUP_URLS = {"brevo": "https://www.brevo.com/", "mailjet": "https://www.mailjet.com/"}

PRESETS = {
    "gmail": ("smtp.gmail.com", 587, "starttls"),
    "yahoo": ("smtp.mail.yahoo.com", 465, "ssl"),
    "icloud": ("smtp.mail.me.com", 587, "starttls"),
    "brevo": ("smtp-relay.brevo.com", 587, "starttls"),
    "mailjet": ("in-v3.mailjet.com", 587, "starttls"),
}


def mail_settings(provider, values, previous):
    if provider == "microsoft":
        raise ValueError("microsoft_oauth")
    username = values.get("smtp_username", "").strip()
    password = values.get("smtp_password", "")
    same_account = previous.get("smtp_provider", "custom") == provider and previous.get("smtp_username", "") == username
    if not password and same_account:
        password = previous.get("smtp_password", "")
    result = {"smtp_provider": provider, "smtp_enabled": True, "smtp_username": username, "smtp_password": password}
    if provider in PRESETS:
        host, port, security = PRESETS[provider]
        if not valid_email(username):
            raise ValueError("invalid_email")
        if not password:
            raise ValueError("password_required")
        result.update(smtp_host=host, smtp_port=port, smtp_security=security, smtp_sender=username)
    elif provider == "custom":
        if not values.get("smtp_host", "").strip() or not valid_email(values.get("smtp_sender", "")):
            raise ValueError("smtp_config")
        if username and not password:
            raise ValueError("password_required")
        result.update({key: values[key] for key in ("smtp_host", "smtp_port", "smtp_security", "smtp_sender")})
    else:
        raise ValueError("smtp_config")
    return result
