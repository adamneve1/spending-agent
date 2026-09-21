FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY server.py .
COPY expense.py .
COPY config.py .
COPY report.py .
COPY scheduler.py .

CMD ["python", "agent.py"]
