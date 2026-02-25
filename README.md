# Data Ingestion Sample

## Local test environment

Mongodb

```sh
podman run -d \
  --name mongodb-atlas-local \
  -p 27017:27017 \
  mongodb/mongodb-atlas-local:latest
```

Minio

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

Create the bucket and upload files:

```sh
podman exec -it minio-local bin/sh -c "\
  mc alias set local_minio http://localhost:9000 minioadmin minioadmin && \
  mc mb local_minio/knowledge-base && \
  mc cp /data/*.pdf local_minio/knowledge-base/"
```

Run Ingestion:

```sh
export AWS_S3_BUCKET=knowledge-base
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin
export AWS_S3_ENDPOINT=http://localhost:9000
export AWS_REGION=us-east-1

uv run ingestion/s3_download.py
uv run ingestion/chunking.py
uv run ingestion/embeddings.py
uv run ingestion/ingestion.py
```

## Configure OpenShift Environment

### Build pipeline image

Local build:

```sh
podman build -t odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu:v1.0 -f k8s/Containerfile .
```

OpenShift build:

```sh
mkdir tmp 2>/dev/null
cp pyproject.toml uv.lock tmp
cp k8s/Containerfile tmp/Dockerfile
oc delete buildconfigs odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu
oc new-build --name=odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu --to=odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu:v1.1 --binary --strategy=docker
oc start-build odh-pipeline-runtime-datascience-cpu-py312-rhel9-blu --from-dir=tmp --follow
rm -rf tmp
```

Make sure that following environment variable are defined in `ingestion/.env`:

```sh
MONGO_URI
DB_NAME
AWS_S3_BUCKET
AWS_ACCESS_KEY
AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION
AWS_S3_ENDPOINT
```

Create configmap and secret:

```sh
oc apply -f 
oc create secret generic ingest-secret --from-env-file=ingestion/.env
```

[Add Elyra configuration for deployment](/docs/elyra_config.md)