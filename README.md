# Data Ingestion Sample

## Local mongodb

```sh
podman run -d \
  --name mongodb-atlas-local \
  -p 27017:27017 \
  mongodb/mongodb-atlas-local:latest
```

## Local minio

```sh
podman run -d \
  --name minio-local \
  -p 9000:9000 \
  -p 9001:9001 \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  -v ./data:/data:Z \
  quay.io/minio/minio server /data --console-address ":9001"
```

```sh
podman exec -it minio-local bin/sh -c "\
  mc alias set local_minio http://localhost:9000 minioadmin minioadmin && \
  mc mb local_minio/knowledge-base && \
  mc cp /data/*.pdf local_minio/knowledge-base/"
```
## Ingestion

```sh
export AWS_S3_BUCKET=knowledge-base
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export AWS_S3_ENDPOINT=http://localhost:9000
export AWS_REGION=us-east-1

uv run ingestion/ingest.py
```

## Build pipeline image

Local build:

```sh
podman build -t odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu:v1.0 -f k8s/Containerfile .
```

OpenShift build:

```sh
mkdir tmp 2>/dev/null
cp pyproject.toml uv.lock tmp
cp k8s/Containerfile tmp/Dockerfile
oc new-build --name=odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu --to=odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu:v1.0
oc start-build odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu --from-dir=tmp --follow
rm -rf tmp
```
