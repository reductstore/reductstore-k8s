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

Stable releases are published by GitHub Actions from strict final SemVer tags (`vX.Y.Z`) that point to a commit already merged into `main`. The release workflow runs workflow linting, Python linting, static typing, unit tests, MicroK8s integration tests, and native amd64/arm64 builds before requesting approval for the protected `stable` environment. It then publishes both architectures and their matching OCI resource revisions to `latest/stable`.

To release a merged commit:

```shell
git tag -a v1.2.3 -m "Release charm v1.2.3"
git push origin v1.2.3
```

To republish an existing release tag, use **Actions > Publish stable release > Run workflow** and enter the exact tag. This is intentionally limited to existing strict SemVer tags reachable from `main`; it cannot publish arbitrary commits or images.

### Repository setup

Before enabling publication, a repository administrator must create the `stable` GitHub environment and configure a required reviewer. Create a package-scoped Charmhub token with `package-manage` permission limited to the `reductstore-k8s` package and `latest/stable` channel. Store it only as the `CHARMHUB_TOKEN` environment secret on `stable`, then rotate it before it expires. No other Actions secret is used for publication.

The release workflow derives the workload image from the tagged `charmcraft.yaml` and rejects floating `latest` images. The existing `v1.0.0` tag is the sole compatibility exception: its source metadata is asserted to contain `reduct/store:latest`, but the runner temporarily uses `reduct/store:v1.20.11` for testing and publication. Future releases must pin their reviewed image in `charmcraft.yaml`.

### Recovery Commands

Use these commands only to inspect or recover a known Charmhub revision; normal publishing is performed by the release workflow:

```shell
charmcraft login
charmcraft status reductstore-k8s
charmcraft release reductstore-k8s \
  --revision=<CHARM_REVISION> \
  --channel=latest/stable \
  --resource=reductstore-image:<RESOURCE_REVISION>
```

Charm and resource revisions are independent. A rerun can safely recover a partial two-architecture release because Charmhub deduplicates matching uploads; confirm the final channel map with `charmcraft status reductstore-k8s`.

## Other resources

- [Project website](https://www.reduct.store)
- [Documentation](https://www.reduct.store/docs)

See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
