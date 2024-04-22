# We use as base the latest nginx image
FROM --platform=linux/amd64 python:3.12.3-slim-bullseye as build

WORKDIR /flask-app

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY config.py config.py

COPY config.json config.json

COPY run.py run.py

COPY app app

COPY lib lib

RUN mkdir log 

CMD ["python3", "run.py"]
