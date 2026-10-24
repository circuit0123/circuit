"""Response shapes shared by several apps. One way to show a person to someone who is allowed to see them."""

from ninja import Schema

SRC_PATTERN = r"^[a-z0-9_-]*$"  # a signup source label such as "landing-students": lower-case letters, digits, - and _ only
SRC_MAX = 40


class PersonOut(Schema):
    id: int
    display_name: str
    role: str
    verification_level: int


def person(m) -> dict:
    return {"id": m.pk, "display_name": m.display_name, "role": m.role, "verification_level": m.verification_level}
