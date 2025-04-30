FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv

RUN apt-get update && \
    apt-get install -y \
        build-essential \
        python3 \
        python3-pip \
        python3-venv

RUN python3 -m venv $VIRTUAL_ENV

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install redis flask grpcio grpcio-tools elasticsearch==8.13.0 beautifulsoup4

WORKDIR /app

COPY app.py .
COPY templates/ templates/
COPY static/ static/
COPY proto/* .

RUN python -m grpc_tools.protoc -I . \
    --python_out=. \
    --grpc_python_out=. \
    scraper.proto

EXPOSE 5000

CMD ["python", "app.py"]
