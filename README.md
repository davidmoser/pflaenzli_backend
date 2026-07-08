# Pflaenzli Backend

This is the backend code for the plant watering project.

It receives moisture and pump data from the Arduino, and stores and provides the configuration to the Arduino. Further it provides those data to the frontend with a json rest api.

## Deployment

- Pull the `pflaenzli_backend` code from github to the server
- Install [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Create the environment and install dependencies (incl. gunicorn): `uv sync`
- Create the db tables: `uv run python manage.py migrate`
- Create the configuration: `uv run python manage.py loaddata configuration`
- Create `.env` file from `.env.example`
- Set `DEBUG = False` in `.env`
- Set `CORS_ALLOWED_ORIGINS = ['<YOUR SERVER IP>']` in `.env`
- Run gunicorn to test: `uv run gunicorn pflaenzli_backend.wsgi --bind 0.0.0.0:8000`
- If it works, install as a service:
- Copy `pflaenzli_backend.service` to `/etc/systemd/system/`
- Adjust `<ENTER PROJECT PATH>` to the location where the git project was cloned to
- Reload Systemd to load the service configuration: `sudo systemctl daemon-reload`
- Enable at boot: `sudo systemctl enable pflaenzli_backend.service`
- Start the service: `sudo systemctl start pflaenzli_backend.service`
- Check the status: `sudo systemctl status pflaenzli_backend.service`
- Check the logs: `sudo journalctl -u pflaenzli_backend.service`
- Add cron line: `sudo crontab -e`

  `* * * * * curl -fsS -m 10 -X POST http://127.0.0.1:8000/internal/tick >> /home/<user>/irr.log 2>&1`

## Redeployment
- Stop the service: `sudo systemctl stop pflaenzli_backend.service`
- Pull the code
- (if there are new dependencies) Sync the environment: `uv sync`
- (if model changed) Update the model: `uv run python manage.py migrate`
- Start the service: `sudo systemctl start pflaenzli_backend.service`