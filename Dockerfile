FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git

# copy assets
COPY . .

ENV PYTHONPATH=/app/src

RUN pip install "git+https://github.com/Kotak-Neo/kotak-neo-api.git#egg=neo_api_client"

RUN pip install --no-deps -r requirements.txt
EXPOSE 8001

CMD ["python", "app/main.py"]