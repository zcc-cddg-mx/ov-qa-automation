FROM qa-agent-base:latest

WORKDIR /app
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
