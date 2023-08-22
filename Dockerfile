FROM python:3.11-slim
WORKDIR /usr/src/smarthouse

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Europe/Moscow
RUN apt-get install -y tzdata
RUN cp /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip3 install --upgrade pip
COPY requirements/requirements.txt .
RUN pip install -r requirements.txt

COPY smarthouse smarthouse
COPY example example
COPY server.py server.py
COPY .env .env
