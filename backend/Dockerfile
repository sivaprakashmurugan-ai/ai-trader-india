FROM python:3.11-slim

RUN apt-get update && apt-get install -y libgomp1 curl && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /usr/src/app/app

# This is a general purpose image. The command will be specified in docker-compose.
CMD ["python"]
