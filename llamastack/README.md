# LLamaStack deployment

Postgres:

```sh
oc create -f llamastack/postgres.yaml
```

Create a config map to store the configuration:

```sh
oc create configmap llama-stack-local --from-file=config.yaml=llamastack/config.yaml
```

CR Deployment:

```sh
set -x NAMESPACE <namespace>
cat llamastack/llama-stack-dist.yaml | envsubst | oc create -f -
```