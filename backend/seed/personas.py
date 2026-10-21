"""Stable identities for the demo stories and the DEMO_AUTH persona switcher."""

import uuid

# key -> (role, display name). Keys are what DEMO_AUTH and the story tests refer to.
PERSONAS = {
    "asha": ("founder", "Asha Raman"),
    "priya": ("founder", "Priya Nair"),
    "arjun": ("founder", "Arjun Mehta"),
    "kavya": ("founder", "Dr. Kavya Subramanian"),
    "rohan": ("founder", "Rohan Gupta"),
    "divya": ("founder", "Divya Menon"),
    "sneha": ("founder", "Sneha Pillai"),
    "lakshmi": ("mentor", "Dr. Lakshmi Narayanan"),
    "vikram": ("investor", "Vikram Anand"),
    "ravi": ("student", "Ravi Kumar"),
    "meenakshi": ("partner_admin", "Meenakshi Iyer"),
    "admin": ("super_admin", "Circuit Admin"),
}


def auth_uuid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"circuit-demo:{key}")
