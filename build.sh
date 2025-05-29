#!/bin/bash

# Install only the minimal requirements needed for the API
pip install -r requirements-vercel.txt

# Create the output directory structure
mkdir -p /vercel/output/static
mkdir -p /vercel/output/functions/api

# Copy the api directory to the functions output
cp -r api/* /vercel/output/functions/api/

# Create the config.json for each function
echo '{"runtime":"python3.9","handler":"index.handler","memory":1024}' > /vercel/output/functions/api/config.json

# Create the static routes
echo '{}' > /vercel/output/config.json
