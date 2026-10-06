"""Suggest only the signed-in user's own local login, never the cloud owner's email."""
from .reporting import valid_email


def suggested_email(user):
    if user is None:
        return ""
    candidates = {
        credential.data.get("username", "").strip()
        for credential in user.credentials
        if credential.auth_provider_type == "homeassistant"
        and isinstance(credential.data.get("username"), str)
        and valid_email(credential.data["username"].strip())
    }
    return next(iter(candidates)) if len(candidates) == 1 else ""
