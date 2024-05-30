# Pflaenzli Backend

This is the backend code for the plant watering project.

It receives moisture and pump data from the Arduino, and stores and provides the configuration to the Arduino. Further it provides those data to the frontend with a json rest api.

## Deployment

- Pull the `pflaenzli_backend` code from github to the server
- Install python, pip and venv: `sudo apt install python3 python3-pip python3-venv -y`
- Create the python environment: `python3 -m venv venv`
- Activate the python environment: `source venv/bin/activate`
- Create the db tables: `python manage.py migrate`
- Create the configuration: `python manage.py loaddata configuration`
- Set `DEBUG = False` in `settings.py`
- Set `CORS_ALLOWED_ORIGINS = ['<YOUR SERVER IP>']` in `settings.py`
- Install gunicorn: `pip install gunicorn`
- Run gunicorn to test: `gunicorn pflaenzli_backend.wsgi --bind 0.0.0.0:8000`
- If it works, install as a service:
- Copy `pflaenzli_backend.service` to `/etc/systemd/system/`
- Adjust `<ENTER PROJECT PATH>` to the location where the git project was cloned to
- Reload Systemd to load the service configuration: `sudo systemctl daemon-reload`
- Enable at boot: `sudo systemctl enable pflaenzli_backend.service`
- Start the service: `sudo systemctl start pflaenzli_backend.service`
- Check the status: `sudo systemctl status pflaenzli_backend.service`
- Check the logs: `sudo journalctl -u pflaenzli_backend.service`

## Redeployment
- Stop the service: `sudo systemctl stop pflaenzli_backend.service`
- Stash the settings if not committed
- Pull the code
- Pop the settings, check them
- (if model changed) Activate the python environment: `source venv/bin/activate`
- (if model changed) Update the model: `python manage.py migrate`
- Start the service: `sudo systemctl start pflaenzli_backend.service` 