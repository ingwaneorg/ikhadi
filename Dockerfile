FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Use gunicorn for production (better than python app.py)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
