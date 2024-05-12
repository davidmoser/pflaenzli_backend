import requests
from rest_framework.response import Response

arduino_address = "http://192.168.68.112/"


def retrieve_configuration():
    try:
        response = requests.get(arduino_address + "configuration")
        response.raise_for_status()  # This will raise an exception for HTTP errors
        return Response(response.json())
    except requests.RequestException as e:
        print(f"Failed to retrieve data to Arduino: {e}")
        return Response(f"Failed to retrieve data to Arduino: {e}", status=500)


def send_configuration(data):
    return put_to_arduino(arduino_address + "configuration", data)


def trigger_measurement():
    return put_to_arduino(arduino_address + "triggerMeasurement")


def start_pump():
    return put_to_arduino(arduino_address + "pump/start")


def stop_pump():
    return put_to_arduino(arduino_address + "pump/stop")


def reset_consecutive_pumps():
    return put_to_arduino(arduino_address + "pump/reset")


def put_to_arduino(url, data=None):
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        response.json()  # Make sure response is properly formatted
        return Response({'status': 'ok'})
    except requests.RequestException as e:
        print(f"Failed to send data to Arduino: {e}")
        return Response(f"Failed to send data to Arduino: {e}", status=500)
