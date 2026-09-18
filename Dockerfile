FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# migrate runs here, not as a Fly release command: release machines do not mount the volume.
# One worker: the tagging thread lives in this process, and SQLite is one file.
CMD python manage.py migrate && gunicorn config.wsgi --bind 0.0.0.0:8080 --workers 1 --threads 8 --access-logfile -
