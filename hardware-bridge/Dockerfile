FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY tijara_bridge /app/tijara_bridge

EXPOSE 9109
CMD ["python", "-m", "tijara_bridge.server"]
