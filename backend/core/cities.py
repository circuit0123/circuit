"""The cities a member can pick in sign-up ("Choose a city", and naming the city when they allow their location).

A fixed list with a centre point each (the app rounds a chosen location to about 1 km anyway). The pilot city from SEED_CITY comes
first. No database table: adding a city is a one-line change here.
"""

from django.conf import settings
from ninja import Router, Schema

router = Router()

CITIES = (
    ("Chennai", 13.0827, 80.2707), ("Bengaluru", 12.9716, 77.5946), ("Mumbai", 19.0760, 72.8777),
    ("Delhi", 28.6139, 77.2090), ("Hyderabad", 17.3850, 78.4867), ("Pune", 18.5204, 73.8567),
    ("Kolkata", 22.5726, 88.3639), ("Ahmedabad", 23.0225, 72.5714), ("Jaipur", 26.9124, 75.7873),
    ("Coimbatore", 11.0168, 76.9558), ("Kochi", 9.9312, 76.2673), ("Thiruvananthapuram", 8.5241, 76.9366),
    ("Madurai", 9.9252, 78.1198), ("Tiruchirappalli", 10.7905, 78.7047), ("Mysuru", 12.2958, 76.6394),
    ("Mangaluru", 12.9141, 74.8560), ("Hubballi", 15.3647, 75.1240), ("Visakhapatnam", 17.6868, 83.2185),
    ("Vijayawada", 16.5062, 80.6480), ("Indore", 22.7196, 75.8577), ("Bhopal", 23.2599, 77.4126),
    ("Lucknow", 26.8467, 80.9462), ("Chandigarh", 30.7333, 76.7794), ("Nagpur", 21.1458, 79.0882),
    ("Surat", 21.1702, 72.8311), ("Vadodara", 22.3072, 73.1812), ("Bhubaneswar", 20.2961, 85.8245),
    ("Guwahati", 26.1445, 91.7362),
)  # fmt: skip


class CityOut(Schema):
    name: str
    lat: float
    lng: float
    pilot: bool  # the city this launch is running in: listed first


def city_list() -> list[dict]:
    pilot = settings.SEED_CITY
    rest = [{"name": n, "lat": lat, "lng": lng, "pilot": False} for n, lat, lng in CITIES if n.lower() != pilot["name"].lower()]
    return [{"name": pilot["name"], "lat": pilot["lat"], "lng": pilot["lng"], "pilot": True}, *rest]


@router.get(
    "",
    response=list[CityOut],
    summary="Cities",
    description="The cities a member can choose in sign-up, each with its centre point. The pilot city is first.",
)
def cities(request):
    return city_list()
