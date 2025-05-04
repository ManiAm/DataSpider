FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv

RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv

RUN python3 -m venv $VIRTUAL_ENV

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install celery redis requests beautifulsoup4 elasticsearch==8.13.0

WORKDIR /app

COPY tasks.py .

CMD ["celery", "-A", "tasks", "worker", "--loglevel=WARNING"]
