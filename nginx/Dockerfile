# Use nginx image
FROM nginx

# remove default config file
RUN rm /etc/nginx/conf.d/default.conf

# replace that file with this one
COPY nginx.conf /etc/nginx/conf.d/