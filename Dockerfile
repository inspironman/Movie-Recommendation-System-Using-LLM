FROM python:3.9

# Set the working directory inside the container
WORKDIR /api

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Expose port 8080
EXPOSE 8080

# Set environment variable to force Flask to run in production mode
ENV FLASK_ENV=development
ENV FLASK_APP=/api/api/index.py

# Command to run the application
CMD ["python", "/api/api/index.py"]

