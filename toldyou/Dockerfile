FROM python:3.7.0-slim-stretch

WORKDIR /app

COPY requirements.txt /app

RUN pip install -r requirements.txt

COPY . /app

CMD python toldyou.py
