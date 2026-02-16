# Data Ingestion Sample

## Local mongodb

podman run -d \
  --name mongodb-atlas-local \
  -p 27017:27017 \
  mongodb/mongodb-atlas-local:latest