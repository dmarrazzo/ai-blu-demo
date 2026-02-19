import os
import boto3
from pathlib import Path

# Environment variables usually provided by Elyra/Kubeflow Secrets
S3_BUCKET = os.getenv("AWS_S3_BUCKET")
S3_PREFIX = os.getenv("S3_PREFIX", "")
S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT") # For MinIO compatibility
PVC_INPUT_DIR = Path(os.getenv("PVC_MOUNT", "/mnt/data")) / "inputs"

def download_from_s3():
    # Ensure our local input directory exists on the PVC
    PVC_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        endpoint_url=S3_ENDPOINT,
    )

    print(f"☁️  Listing objects in s3://{S3_BUCKET}/{S3_PREFIX}...")
    response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)

    if "Contents" not in response:
        print("⚠️ No files found to download.")
        return

    for obj in response["Contents"]:
        key = obj["Key"]
        if not key.lower().endswith(".pdf"):
            continue
        
        file_name = Path(key).name
        target_path = PVC_INPUT_DIR / file_name
        
        print(f"📥 Downloading {key} to {target_path}...")
        s3_client.download_file(S3_BUCKET, key, str(target_path))

    print(f"✅ Download complete. Files ready in {PVC_INPUT_DIR}")

if __name__ == "__main__":
    download_from_s3()