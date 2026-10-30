FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install --default-timeout=120 --retries 10 fastapi==0.115.6 "uvicorn[standard]==0.34.0"
COPY app.py .
RUN useradd --uid 10002 receiver
USER receiver
EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
