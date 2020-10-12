# Using Python 3
FROM python:3.7.9-stretch

# Set working directory
WORKDIR /social

# Copy app directory to container
ADD . /social

# Install dependencies
RUN pip install -r requirements.txt

# Command to start uwsgi
CMD ["uwsgi", "social.ini"]