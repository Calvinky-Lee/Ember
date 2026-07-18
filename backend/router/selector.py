"""P2 owns — spec 04, task P2-M3.
pick_zone() -> {"simulated": intensity-record, "baseline": intensity-record,
                "label": "simulated placement"}"""
from backend import config
from backend.measurement import carbon


def pick_zone() -> dict:
    return {
        "simulated": carbon.greenest_zone(),
        "baseline": carbon.get_intensity(config.BASELINE_ZONE),
        "label": "simulated placement",
    }
