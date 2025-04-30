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
    pip install grpcio grpcio-tools celery redis

WORKDIR /app

COPY server.py .
COPY proto/* .

RUN python -m grpc_tools.protoc -I . \
    --python_out=. \
    --grpc_python_out=. \
    scraper.proto

EXPOSE 50051

CMD ["python", "server.py"]
