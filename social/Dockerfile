# Using Python 3
FROM python:3.7.9-stretch

# Set working directory for setup
WORKDIR /social

# Copy app directory to container
ADD . /social

# Install dependencies
RUN pip install -r requirements.txt

# Set working directory for runtime
WORKDIR /social/app

# Command to start uwsgi
CMD ["uwsgi", "social.ini"]
