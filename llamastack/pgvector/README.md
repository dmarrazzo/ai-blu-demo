# Image build

based on https://catalog.redhat.com/en/software/containers/rhel10/postgresql-16/677d13af607921b4d74fca88#overview

1. Create the Build Configuration
This YAML creates a **BuildConfig** and an **ImageStream**. The ImageStream acts as the internal address for your new, custom image.

```yaml
apiVersion: v1
kind: List
items:
- apiVersion: image.openshift.io/v1
  kind: ImageStream
  metadata:
    name: postgresql-pgvector
- apiVersion: build.openshift.io/v1
  kind: BuildConfig
  metadata:
    name: postgresql-pgvector-build
  spec:
    source:
      dockerfile: |
        FROM registry.redhat.io/rhel10/postgresql-16:10.1
        USER 0
        RUN dnf install -y --nodocs postgresql16-pgvector && \
            dnf clean all
        USER 26
      type: Dockerfile
    strategy:
      dockerStrategy:
        from:
          kind: DockerImage
          name: registry.redhat.io/rhel10/postgresql-16:10.1
      type: Docker
    output:
      to:
        kind: ImageStreamTag
        name: postgresql-pgvector:latest
```

2. Apply and Run the Build
Save the YAML above as `build-pgvector.yaml` and run:

   1.  **Apply the config:**
       ```bash
       oc apply -f build-pgvector.yaml
       ```
   2.  **Start the build:**
       ```bash
       oc start-build postgresql-pgvector-build --follow
       ```
       *The `--follow` flag lets you see the logs as it installs the RPM.*

3. Deploy the Resulting Image
Now that the image is built and stored in your ImageStream, you can deploy it just like any other image. If you are using the `oc new-app` command, it looks like this:

```bash
oc new-app postgresql-pgvector:latest \
    -e POSTGRESQL_USER=myuser \
    -e POSTGRESQL_PASSWORD=mypassword \
    -e POSTGRESQL_DATABASE=myvectors
```

---

### Why this works well in OpenShift:
* **Internal Registry:** OpenShift automatically manages the storage of the image.
* **Security:** The build runs in a specialized "build pod" with the necessary permissions, so your main database pod doesn't need to run as root.
* **Triggers:** You can set it up so that if the base Red Hat image is updated (e.g., a security patch for Postgres 16), OpenShift will **automatically rebuild** your `pgvector` image to include those patches.

### A Quick Reminder on the Database Side
Once the pod is running with this image, don't forget that `pgvector` is "installed" but not yet "active" in your DB. You must run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Does this "Build-in-OpenShift" approach fit your current workflow, or are you using a specific GitOps tool like ArgoCD?