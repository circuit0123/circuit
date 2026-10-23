from core.schemas import PersonOut, person


class AuthorOut(PersonOut):
    headline: str
    city: str


def author(m) -> dict:
    return {**person(m), "headline": (m.bio or "").strip()[:140], "city": m.city}
