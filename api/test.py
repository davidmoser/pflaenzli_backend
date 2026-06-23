import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_et0():
    """Fetch today's reference evapotranspiration (mm) from Open-Meteo.

    The pots are on a covered balcony, so precipitation is deliberately ignored.
    """
    params = {
        "latitude": 47.3769,
        "longitude": 8.5417,
        "daily": "et0_fao_evapotranspiration",
        "timezone": "Europe/Zurich",
        "forecast_days": 1,
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    return response #.json()["daily"]["et0_fao_evapotranspiration"][0]

# teh user testing the et0 api
