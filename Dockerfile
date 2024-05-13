# Use the official Python image as a base image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port that the Quart app runs on
EXPOSE 8000

# Run the application
# CMD ["hypercorn", "app:zentica_demo", "--bind", "0.0.0.0:8000"]
