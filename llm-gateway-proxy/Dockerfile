FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY .env .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# curl.exe -X POST http://localhost:8080/chat/completions -H "Content-Type: application/json" -H "x-api-key: XXXXXX" -d "{\"model\":\"gpt-4o\",\"messages\":[{\"role\":\"user\",\"content\":\"Say 'Hello from LLM Gateway Proxy!' in a pirate voice\"}],\"max_tokens\":100}"