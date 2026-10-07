FROM ghcr.io/berriai/litellm:main-stable
COPY config.yaml /app/config.yaml
EXPOSE 4000
ENTRYPOINT ["litellm"]
CMD ["--config", "/app/config.yaml", "--port", "4000"]
