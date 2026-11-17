FROM alpine:3.20
RUN apk add --no-cache wireguard-tools iproute2 iputils python3 py3-flask
WORKDIR /app
COPY app.py entrypoint.sh ./
RUN chmod +x entrypoint.sh
EXPOSE 5000 51820/udp
VOLUME /data
ENTRYPOINT ["/app/entrypoint.sh"]
