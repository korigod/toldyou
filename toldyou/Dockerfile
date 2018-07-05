FROM python:3.7.0-slim-stretch

WORKDIR /app

COPY requirements.txt /app

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r requirements.txt \
    && apt-get purge -y --auto-remove gcc libc-dev

COPY . /app

CMD python toldyou.py
