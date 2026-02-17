# Data Ingestion Sample

## Local mongodb

podman run -d \
  --name mongodb-atlas-local \
  -p 27017:27017 \
  mongodb/mongodb-atlas-local:latest

## Local minio

podman run -d \
  --name minio-local \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  -v ./data:/data:Z \
  quay.io/minio/minio server /data --console-address ":9001"

podman exec -it minio-local bin/sh -c "\
  mc alias set local_minio http://localhost:9000 minioadmin minioadmin && \
  mc mb local_minio/knowledge-base && \
  mc cp /data/*.pdf local_minio/knowledge-base/"

export S3_BUCKET=knowledge-base
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export S3_ENDPOINT_URL=http://localhost:9000
export AWS_REGION=us-east-1

uv run ingestion/ingest.py