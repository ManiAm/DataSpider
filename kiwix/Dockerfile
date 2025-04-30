FROM debian:bullseye-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y wget curl ca-certificates unzip && \
    apt-get install -y zlib1g-dev libzim-dev libmicrohttpd-dev && \
    apt-get install -y kiwix-tools

RUN mkdir -p /data
WORKDIR /data

EXPOSE 8080

CMD ["/usr/bin/kiwix-serve", "--port=8080", "/data/wikipedia_en_simple_all_maxi_2024-06.zim"]
