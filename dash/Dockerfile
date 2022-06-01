FROM continuumio/miniconda3:4.10.3
MAINTAINER Mingxun Wang "mwang87@gmail.com"

RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

