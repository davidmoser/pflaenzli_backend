import requests
from rest_framework.response import Response

from pflaenzli_backend import settings


def address(action):
    return f"http://{settings.ARDUINO_ADDRESS}/{action}"


def retrieve_configuration():
    if not settings.ARDUINO_ENABLED:
        return Response(f"Arduino requests disabled", status=500)
    try:
        response = requests.get(address("configuration"))
        response.raise_for_status()  # This will raise an exception for HTTP errors
        return Response(response.json())
    except requests.RequestException as e:
        print(f"Failed to retrieve data to Arduino: {e}")
        return Response(f"Failed to retrieve data to Arduino: {e}", status=500)


def send_configuration(data):
    return put_to_arduino(address("configuration"), data)


def trigger_measurement():
    return put_to_arduino(address("triggerMeasurement"))


def start_pump():
    return put_to_arduino(address("pump/start"))


def stop_pump():
    return put_to_arduino(address("pump/stop"))


def reset_consecutive_pumps():
    return put_to_arduino(address("pump/reset"))


def put_to_arduino(url, data=None):
    if not settings.ARDUINO_ENABLED:
        return Response({'status': 'ok'})
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        response.json()  # Make sure response is properly formatted
        return Response({'status': 'ok'})
    except requests.RequestException as e:
        print(f"Failed to send data to Arduino: {e}")
        return Response(f"Failed to send data to Arduino: {e}", status=500)
