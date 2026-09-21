# Hosting

A guide to hosting Update Signal on your own account. The repo names no live deployment. It
ships a `Dockerfile` and a `fly.toml` as starting points, and this page covers three ways
to run them.

## 1. What the tool needs

- **One instance.** SQLite is one file, and the tagging thread lives inside the web process.
  A second instance would share neither. Never scale past one.
- **A persistent disk** for the SQLite file. Point `SIGNAL_DB` at it. Lose the disk and you
  lose every run.
- **Outbound HTTPS** to the model endpoint.
- **About 256 MB of memory.** The process is Django, one Gunicorn worker with eight threads,
  and a thread pool for the model calls.
- **HTTPS in front of it.** The tool trusts the `X-Forwarded-Proto` header from its proxy
  (`SECURE_PROXY_SSL_HEADER` in `config/settings.py`). Without that header every form post
  fails the CSRF origin check.

The container listens on port 8080. Its start command runs `migrate` and then Gunicorn, so
a deploy needs no separate migration step. WhiteNoise serves the one CSS file, so nothing
needs a static route or a `collectstatic` step.

## 2. Settings

| Variable | Set it to |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string. Make one with the command below. |
| `DJANGO_DEBUG` | `0`. |
| `DJANGO_ALLOWED_HOSTS` | The host name people type. Comma-separated if several. |
| `SIGNAL_DB` | The SQLite path on the persistent disk, for example `/data/db.sqlite3`. |
| `APP_PASSWORD` | The one shared password. Empty turns the gate off. |
| `OPENROUTER_API_KEY` | The key for the model endpoint. Required. |
| `OPENROUTER_BASE_URL` | The endpoint. Default `https://openrouter.ai/api/v1`. See [model.md](model.md). |
| `SIGNAL_MODEL` | The model. Default `anthropic/claude-haiku-4.5`. |
| `SIGNAL_CONCURRENCY` | Model calls side by side. Default 8. Lower it if the provider rate-limits you. |

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Treat `DJANGO_SECRET_KEY`, `APP_PASSWORD` and `OPENROUTER_API_KEY` as secrets. Put them in
the host's secret store, never in `fly.toml`, a compose file or git.

## 3. The password gate

`web/middleware.py` asks the browser for one shared password with HTTP Basic auth when
`APP_PASSWORD` is set. The browser shows its own prompt and resends the password on every
request, so the poll script and the CSV download need no change. There are no accounts and
no sessions. It is a gate for a small team on a private tool, not a login system. Anyone
with the password sees every run. Change the password by changing the variable and
restarting.

## 4. Option A: a container on any host

Docker on a VPS, Render, Railway, Cloud Run with a mounted disk, or any host that runs an
image and can attach a volume.

```bash
docker build -t update-signal .
docker volume create update-signal-data
docker run -d --name update-signal -p 8080:8080 \
  -v update-signal-data:/data \
  -e SIGNAL_DB=/data/db.sqlite3 \
  -e DJANGO_DEBUG=0 \
  -e DJANGO_ALLOWED_HOSTS=your-host.example.org \
  -e DJANGO_SECRET_KEY=... -e APP_PASSWORD=... -e OPENROUTER_API_KEY=... \
  update-signal
```

Or with compose:

```yaml
services:
  web:
    build: .
    ports: ["8080:8080"]
    volumes: ["data:/data"]
    env_file: .env
    environment:
      SIGNAL_DB: /data/db.sqlite3
      DJANGO_DEBUG: "0"
volumes:
  data: {}
```

Put a TLS proxy in front, the host's own or Caddy. It must pass `X-Forwarded-Proto`. Run
exactly one replica.

## 5. Option B: Fly.io

`fly.toml` at the repo root is a template. Change three values before the first deploy:
`app`, `primary_region`, and `DJANGO_ALLOWED_HOSTS`, which is `<app>.fly.dev` unless you add
your own domain.

```bash
fly apps create <app>
fly volumes create data --region <region> --size 1 --app <app>
fly secrets set DJANGO_SECRET_KEY=... APP_PASSWORD=... OPENROUTER_API_KEY=... --app <app>
fly deploy --ha=false
```

- `--ha=false` keeps one machine. Fly's default creates two, and the second cannot mount the
  same volume or see the tagging thread.
- `migrate` runs in the container `CMD`, not as a Fly release command, because release
  machines do not mount the volume.
- `auto_stop_machines = "stop"` and `min_machines_running = 0` stop the machine when idle
  and start it on the next request. A run in progress dies if every tab closes during
  tagging; `config/wsgi.py` marks it failed at the next start. Set `min_machines_running = 1`
  to keep the machine up, and pay for it around the clock.
- Later deploys: `fly deploy --ha=false` again. Deploy only when no run is `processing`.

## 6. Option C: plain Python on a server

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/gunicorn config.wsgi --bind 127.0.0.1:8080 --workers 1 --threads 8
```

One worker, always. A `systemd` unit:

```ini
[Unit]
Description=Update Signal
After=network.target

[Service]
WorkingDirectory=/srv/update-signal
EnvironmentFile=/srv/update-signal/.env
ExecStartPre=/srv/update-signal/.venv/bin/python manage.py migrate
ExecStart=/srv/update-signal/.venv/bin/gunicorn config.wsgi --bind 127.0.0.1:8080 --workers 1 --threads 8
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Put Nginx or Caddy in front for TLS. Caddy sets `X-Forwarded-Proto` on its own. In Nginx
add `proxy_set_header X-Forwarded-Proto $scheme;` to the location block.

## 7. Operating it

- **Deploy only when no run is `processing`.** A restart kills the tagging thread. The next
  start marks the run failed with the message "The server restarted during tagging. Upload
  the file again."
- **Back up** by copying the SQLite file. In WAL mode `-wal` and `-shm` files may sit beside
  it; copy them too, or stop the process first.
- **Change the model, the endpoint or the password** by changing the variable and
  restarting. A new model changes future tags only. Stored responses stay as they were.
- **Refresh the World Bank income groups** with `python -m signal_tool.reference` in a
  checkout, then commit `reference/` and deploy.
- **Rebuild `web/static/app.css`** with `npm run css` before a deploy that follows a
  template change. The image copies the built file; it does not run npm.

## 8. Updating

Pull, rebuild the image or the venv, deploy. Migrations run at start. Check that no run is
`processing` first.
