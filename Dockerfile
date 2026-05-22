FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    fontconfig \
    fonts-nanum \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generator/   ./generator/
COPY analysis/    ./analysis/
COPY visualization/ ./visualization/

# 출력 디렉토리
RUN mkdir -p /app/output

CMD ["python", "generator/event_generator.py"]
