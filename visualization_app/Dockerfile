FROM python:2.7

RUN pip install psycopg2
RUN pip install Flask

RUN mkdir /app
WORKDIR /app

COPY . /app

CMD python app.py