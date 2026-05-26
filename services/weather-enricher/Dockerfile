FROM python:3.11-slim
RUN pip install --no-cache-dir influxdb requests
COPY weather_enricher.py /app/weather_enricher.py
CMD ["python", "-u", "/app/weather_enricher.py"]
