FROM python:3.12-slim
WORKDIR /usr/src/smarthouse

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Europe/Moscow
RUN apt-get update -q -y && apt-get install -q -y gcc tzdata curl
RUN cp /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN pip3 install --upgrade pip
COPY requirements/requirements.txt .
RUN pip install -r requirements.txt

COPY smarthouse smarthouse
COPY example example
COPY server.py server.py
COPY .env .env

RUN chmod +x /usr/src/smarthouse/server.py
ENTRYPOINT ["python3", "/usr/src/smarthouse/server.py"]
