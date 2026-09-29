#!/usr/bin/env bash

set -euo pipefail
shopt -s nullglob

for architecture in amd64 arm64; do
  docker pull --platform="linux/$architecture" "$WORKLOAD_IMAGE"
  image_id=$(docker image inspect --format='{{.Id}}' "$WORKLOAD_IMAGE")
  resource_output=$(charmcraft upload-resource reductstore-k8s reductstore-image --image="$image_id" --format json)
  resource_revision=$(printf '%s' "$resource_output" | jq -r '.revision')
  charm_files=(artifacts/*_"$architecture".charm)
  test "${#charm_files[@]}" -eq 1
  charm_output=$(charmcraft upload "${charm_files[0]}" --format json)
  charm_revision=$(printf '%s' "$charm_output" | jq -r '.revision')
  charmcraft release reductstore-k8s --revision="$charm_revision" --channel="$RELEASE_CHANNEL" --resource="reductstore-image:$resource_revision"
  printf -- "- %s: charm \`%s\`, resource \`%s\`\n" "$architecture" "$charm_revision" "$resource_revision" >> "$GITHUB_STEP_SUMMARY"
done
