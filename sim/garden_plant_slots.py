"""Admission limit from explicit native metadata; historical worlds remain eight."""
from garden_resources import require

RULE = "post-noon-sixteen-plant-slots-v1"
AFTER = 69120


def plant_capacity(row):
    if "plant_admission" not in row:
        return 8
    tick = row.get("tick")
    require(type(tick) is int and tick >= 0, "invalid plant admission tick")
    limit = 16 if tick > AFTER else 8
    value = row["plant_admission"]
    require(isinstance(value, dict) and type(value.get("after")) is int and type(value.get("limit")) is int and
            value == {"rule": RULE, "after": AFTER, "limit": limit},
            "invalid plant admission metadata")
    return limit
