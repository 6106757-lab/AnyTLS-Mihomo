FROM python:3.10-alpine
RUN apk add --no-cache openssl curl wget unzip ca-certificates
RUN pip install --no-cache-dir flask
WORKDIR /app
COPY panel.py /app/panel.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
