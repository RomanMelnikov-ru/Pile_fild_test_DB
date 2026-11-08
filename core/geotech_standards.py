# core/geotech_standards.py

SOIL_TYPES_REGISTRY = [
    "Насыпной",
    "Торф",
    "Песок",
    "Супесь",
    "Суглинок",
    "Глина"
]

SAND_FRACTIONS = [
    "Пылеватый",
    "Мелкий",
    "Средней крупности",
    "Крупный",
    "Гравелистый"
]

SAND_DENSITIES = [
    "Рыхлый",
    "Средней плотности",
    "Плотный"
]

CLAY_CONSISTENCIES = [
    "Твердый",
    "Полутвердый",
    "Тугопластичный",
    "Мягкопластичный",
    "Текучепластичный",
    "Текучий",
    "Пластичная"  # Для супесей
]

def check_clay_type_by_ip(ip: float) -> str:
    if ip is None: return ""
    if ip < 1: return "Неглинистый (Ip < 1)"
    elif 1 <= ip <= 7: return "Супесь"
    elif 7 < ip <= 17: return "Суглинок"
    else: return "Глина"

def get_clay_consistency_by_il(soil_type: str, il: float) -> str:
    if il is None: return ""
    if soil_type == "Супесь":
        if il < 0: return "Твердая"
        elif 0 <= il <= 1.0: return "Пластичная"
        else: return "Текучая"
    elif soil_type in ["Суглинок", "Глина"]:
        if il < 0: return "Твердый"
        elif 0 <= il <= 0.25: return "Полутвердый"
        elif 0.25 < il <= 0.50: return "Тугопластичный"
        elif 0.50 < il <= 0.75: return "Мягкопластичный"
        elif 0.75 < il <= 1.00: return "Текучепластичный"
        else: return "Текучий"
    return ""

def get_sand_density_by_e(fraction: str, e: float) -> str:
    if e is None or not fraction: return ""
    if fraction in ["Гравелистый", "Крупный", "Средней крупности"]:
        if e < 0.55: return "Плотный"
        elif 0.55 <= e <= 0.70: return "Средней плотности"
        else: return "Рыхлый"
    elif fraction == "Мелкий":
        if e < 0.60: return "Плотный"
        elif 0.60 <= e <= 0.75: return "Средней плотности"
        else: return "Рыхлый"
    elif fraction == "Пылеватый":
        if e < 0.60: return "Плотный"
        elif 0.60 <= e <= 0.80: return "Средней плотности"
        else: return "Рыхлый"
    return ""