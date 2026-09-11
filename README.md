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

## Configuration

The charm configures ReductStore with the following options:

- `instance-name`: a stable ReductStore instance name. When unset, it is derived as `<model>-<application>`.
- `log-level`: one of `info`, `debug`, `warning`, `error`, or `critical`. The default is `info`.
- `api-base-path`: the path at which the ReductStore API and UI are served. When unset, it is derived as `/<model>-<application>`. Values are normalized to start with `/` and have no trailing `/` (except `/` itself).

For example:

```shell
juju config reductstore-k8s instance-name=production-reductstore
juju config reductstore-k8s log-level=debug
juju config reductstore-k8s api-base-path=/reductstore
```

## Relations

Both relations are optional. Without them, ReductStore remains available to workloads in the Kubernetes cluster.

### Ingress

Integrate with an ingress provider such as `traefik-k8s` to expose the ReductStore API and UI outside the cluster:

```shell
juju integrate reductstore-k8s:ingress traefik-k8s:ingress
juju status reductstore-k8s --watch 2s
```

The ingress URL is combined with `api-base-path` for the public API URL and with `/ui/dashboard` for the UI URL. It also provides the value used for ReductStore's `RS_PUBLIC_URL` setting and for the Catalogue entry.

### Catalogue

Integrate with `catalogue-k8s` to publish a ReductStore entry with links to the UI, REST API, and server information endpoint:

```shell
juju integrate reductstore-k8s:catalogue catalogue-k8s:catalogue
```

If `reductstore-k8s` already exists in the model, update it instead of deploying another application:

```shell
juju refresh reductstore-k8s --channel latest/edge
```

Refreshing preserves the application's configuration, relations, and persistent storage.

## Limitations and deviations

- This is a Kubernetes charm. It does not support machine models.
- The charm defines one filesystem storage volume mounted at `/data`, with a minimum size of 10GiB. Select the storage class and requested size using Juju storage configuration for the target Kubernetes cluster.
- The ReductStore image is pinned in `charmcraft.yaml`. Use the upstream [ReductStore documentation](https://www.reduct.store/docs) for application-specific configuration and API behavior not exposed by the charm.
- When an ingress URL is issued or revoked, the charm replans the workload so ReductStore receives the current `RS_PUBLIC_URL` without requiring a configuration change.

## Publishing

Each merge to `main` is published to `latest/edge`. Stable releases are published from strict final SemVer tags (`vX.Y.Z`) that point to a commit already merged into `main`. The release workflow runs workflow linting, Python linting, static typing, unit tests, MicroK8s integration tests, and native amd64/arm64 builds before requesting approval for the protected `stable` environment. It then publishes both architectures and their matching OCI resource revisions to `latest/stable`.

To release a merged commit:

```shell
git tag -a v1.2.3 -m "Release charm v1.2.3"
git push origin v1.2.3
```

To republish an existing release tag, use **Actions > Publish release > Run workflow** and enter the exact tag. This is intentionally limited to existing strict SemVer tags reachable from `main`; it cannot publish arbitrary commits or images.

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

## Security

Security fixes are provided through the latest stable `reductstore-k8s` channel. To report a vulnerability privately, follow the [ReductStore security policy](https://github.com/reductstore/reductstore/security/policy), which provides private GitHub Security Advisory and email reporting channels. Do not report vulnerabilities in public issues, pull requests, or discussions.

## Other resources

- [Project website](https://www.reduct.store)
- [ReductStore application documentation](https://www.reduct.store/docs)

See the [Juju SDK documentation](https://juju.is/docs/sdk) for more information about developing and improving charms.
