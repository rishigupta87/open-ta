# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install streamlit streamlit-autorefresh requests redis pandas plotly matplotlib
# RUN pip install --upgrade pip && pip install --upgrade streamlit

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.headless=true"]

