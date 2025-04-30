
FROM golang:1.20 AS builder

WORKDIR /app

RUN git clone https://github.com/seamia/protodot.git .

RUN go build -o protodot

FROM ubuntu:22.04

# Install Graphviz for SVG/PNG output support
RUN apt-get update && \
    apt-get install -y graphviz

WORKDIR /app

# Copy the protodot binary from the builder stage
COPY --from=builder /app/protodot /usr/local/bin/protodot

CMD ["bash"]
