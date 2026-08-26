# reductstore-k8s

Charmhub package name: **reductstore-k8s**  
More information: https://charmhub.io/reductstore-k8s

This charm deploys **ReductStore**, a time-indexed object store for high-frequency unstructured data, on Kubernetes with Pebble, persistent storage, and optional ingress/COS catalogue integration.

## Building

Install [Charmcraft](https://documentation.ubuntu.com/charmcraft/) and run the tests before packing the charm:

```shell
tox
charmcraft pack --platform amd64
```

The pack command creates `reductstore-k8s_amd64.charm` in the repository root. Run it on an arm64 host with `--platform arm64` to create an arm64 artifact.

To build all platforms declared in `charmcraft.yaml` using Launchpad builders, use:

```shell
charmcraft remote-build
```

Remote builds require a Launchpad account and download the resulting charm artifacts to the repository root.

## Deploying

Deploy the stable charm from Charmhub into the current Kubernetes model:

```shell
juju deploy reductstore-k8s --channel latest/stable
juju status reductstore-k8s --watch 2s
```

To test the most recent development release, replace `latest/stable` with `latest/edge`.

For local development, deploy the packed charm and provide its OCI image resource explicitly:

```shell
juju deploy ./reductstore-k8s_amd64.charm reductstore-k8s \
  --resource reductstore-image=reduct/store:v1.20.11
```

Configure a stable ReductStore instance name when needed:

```shell
juju config reductstore-k8s instance-name=production-reductstore
```

Integrate optional ingress and Catalogue applications after they have been deployed:

```shell
juju integrate reductstore-k8s:ingress traefik-k8s:ingress
juju integrate reductstore-k8s:catalogue catalogue-k8s:catalogue
```

If `reductstore-k8s` already exists in the model, update it instead of deploying another application:

```shell
juju refresh reductstore-k8s --channel latest/edge
```

Refreshing preserves the application's configuration, relations, and persistent storage.

## Publishing

Publish from a tested, clean `main` branch. The Charmhub package is already registered, so maintainers only need to authenticate:

```shell
charmcraft login
charmcraft whoami
```

The OCI image is a separate Charmhub resource. Pull the intended ReductStore version and upload its local Docker image ID:

```shell
docker pull reduct/store:v1.20.11
IMAGE_ID=$(docker image inspect --format='{{.Id}}' reduct/store:v1.20.11)
charmcraft upload-resource reductstore-k8s reductstore-image --image="${IMAGE_ID}"
```

Record the resource revision printed by `upload-resource`. Then pack and upload the charm to the edge channel, attaching that resource revision:

```shell
charmcraft pack --platform amd64
charmcraft upload reductstore-k8s_amd64.charm \
  --release=latest/edge \
  --resource=reductstore-image:<RESOURCE_REVISION>
```

The upload command prints a separate charm revision. Confirm the channel map and test the release:

```shell
charmcraft status reductstore-k8s
juju refresh reductstore-k8s --channel latest/edge
juju status reductstore-k8s --watch 2s
```

After validation, release the same charm and resource revisions to the stable channel:

```shell
charmcraft release reductstore-k8s \
  --revision=<CHARM_REVISION> \
  --channel=latest/stable \
  --resource=reductstore-image:<RESOURCE_REVISION>
```

Charm and resource revisions use independent numbering. For multi-architecture releases, build and upload each charm platform with an OCI resource revision for the matching architecture.

Use a Git tag for the source release version; a separate Charmhub track is only needed when maintaining multiple incompatible release lines:

```shell
git tag -a v1.0.0 -m "Release charm v1.0.0"
git push origin v1.0.0
```

## Other resources

- [Project website](https://www.reduct.store)
- [Documentation](https://www.reduct.store/docs)

See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
