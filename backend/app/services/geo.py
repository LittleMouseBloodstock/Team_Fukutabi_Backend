import math

WALK_KMPH = 4.8
DRIVE_KMPH = 25.0  # 都市MVP用の控えめ設定（必要なら調整）
EARTH_R = 6371.0088

def minutes_to_radius_km(minutes: int, mode: str) -> float:
    speed = WALK_KMPH if mode == "walk" else DRIVE_KMPH
    return (speed * minutes) / 60.0

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    to_rad = math.radians
    dlat = to_rad(lat2 - lat1)
    dlng = to_rad(lng2 - lng1)
    a = (math.sin(dlat/2)**2
        + math.cos(to_rad(lat1))*math.cos(to_rad(lat2))*math.sin(dlng/2)**2)
    return 2 * EARTH_R * math.asin(math.sqrt(a))
