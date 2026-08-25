#!/usr/bin/env python3
# Copyright 2025-2026 ReductSoftware UG
# See LICENSE file for licensing details.

"""Kubernetes charm for ReductStore."""

import json
import logging
from typing import cast
from urllib.parse import urlsplit, urlunsplit

import ops
from charms.catalogue_k8s.v1.catalogue import CatalogueConsumer, CatalogueItem
from charms.traefik_k8s.v2.ingress import (
    IngressPerAppReadyEvent,
    IngressPerAppRequirer,
    IngressPerAppRevokedEvent,
)
from ops import StoredState

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class ReductstoreCharm(ops.CharmBase):
    """Charm for ReductStore."""

    _stored = StoredState()

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        # Persist last known ingress URL
        self._stored.set_default(ingress_url="")

        # Observe pebble  config
        framework.observe(self.on["reductstore"].pebble_ready, self._on_reductstore_pebble_ready)
        framework.observe(self.on.config_changed, self._on_config_changed)

        # Setup ingress (Traefik)
        self.ingress = IngressPerAppRequirer(self, port=8383, strip_prefix=False)
        self.framework.observe(self.ingress.on.ready, self._on_ingress_ready)
        self.framework.observe(self.ingress.on.revoked, self._on_ingress_revoked)

        # Setup catalogue consumer
        self.catalogue = CatalogueConsumer(charm=self)

        framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

    def _on_reductstore_pebble_ready(self, event: ops.PebbleReadyEvent):
        container = event.workload
        container.add_layer("reductstore", self._pebble_layer, combine=True)
        container.replan()
        self.unit.status = ops.ActiveStatus()
        self.catalogue.update_item(self._catalogue_item)

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        log_level = cast(str, self.model.config["log-level"]).lower()
        logger.debug("config-changed: requested log-level=%s", log_level)
        if log_level not in VALID_LOG_LEVELS:
            self.unit.status = ops.BlockedStatus(f"invalid log level: '{log_level}'")
            return
        container = self.unit.get_container("reductstore")
        try:
            container.add_layer("reductstore", self._pebble_layer, combine=True)
            container.replan()
        except ops.pebble.ConnectionError:
            self.unit.status = ops.MaintenanceStatus("waiting for Pebble API")
            event.defer()
            return
        self.unit.status = ops.ActiveStatus()
        logger.debug(
            "config-changed: ingress_url=%s external_api_url=%s external_ui_url=%s",
            self._stored.ingress_url,
            self.external_api_url,
            self.external_ui_url,
        )
        self.catalogue.update_item(self._catalogue_item)

    def _on_ingress_ready(self, event: IngressPerAppReadyEvent):
        logger.debug("ingress.ready: raw event.url=%s", event.url)
        self._stored.ingress_url = event.url
        logger.debug(
            "ingress.ready: stored ingress_url=%s, \
                api_base_path=%s, external_api_url=%s, external_ui_url=%s",
            self._stored.ingress_url,
            self._api_base_path(),
            self.external_api_url,
            self.external_ui_url,
        )
        self.catalogue.update_item(self._catalogue_item)
        logger.info("Ingress is ready: %s", event.url)
        self.unit.status = ops.ActiveStatus(f"Ingress at {event.url}")

    def _on_ingress_revoked(self, event: IngressPerAppRevokedEvent):
        logger.debug(
            "ingress.revoked: clearing stored ingress_url (was: %s)", self._stored.ingress_url
        )
        self._stored.ingress_url = ""
        logger.debug(
            "ingress.revoked: stored ingress_url=%s, external_api_url=%s, external_ui_url=%s",
            self._stored.ingress_url,
            self.external_api_url,
            self.external_ui_url,
        )
        self.catalogue.update_item(self._catalogue_item)
        logger.warning("Ingress revoked")
        self.unit.status = ops.MaintenanceStatus("Waiting for ingress")

    def _api_base_path(self) -> str:
        path = cast(
            str, self.model.config.get("api-base-path") or f"/{self.model.name}-{self.app.name}"
        )
        if path and not path.startswith("/"):
            path = "/" + path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        logger.debug("computed api_base_path=%s", path)
        return path

    @property
    def _instance_name(self) -> str:
        configured = cast(str, self.model.config.get("instance-name") or "").strip()
        return configured or f"{self.model.name}-{self.app.name}"

    def _public_ui_url(self, base_url: str) -> str:
        parts = urlsplit(base_url)
        path = f"{self._api_base_path()}/ui/dashboard"
        url = parts._replace(path=path, query="", fragment="").geturl()
        logger.debug("public_ui_url: base=%s -> %s", base_url, url)
        return url

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent):
        """Handle charm upgrade by restoring ingress state and updating catalogue."""
        self._restore_ingress_state()
        self.catalogue.update_item(self._catalogue_item)
        self.unit.status = ops.ActiveStatus()

    def _restore_ingress_state(self):
        """Restore ingress URL from relation data if the ingress relation exists."""
        if not self.ingress.relations:
            logger.debug("No ingress relations found during upgrade")
            return

        for relation in self.ingress.relations:
            if not relation.app:
                continue

            try:
                ingress_data = relation.data[relation.app].get("ingress")
                if ingress_data:
                    data = json.loads(ingress_data)
                    url = data.get("url")
                    if url:
                        self._stored.ingress_url = url
                        logger.info("Restored ingress URL from relation: %s", url)
                        return
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to parse ingress data from relation: %s", e)
                continue

        logger.debug("No valid ingress URL found in relations during upgrade")

    @property
    def external_ui_url(self) -> str:
        """Return the externally reachable UI URL, if known."""
        if not self._stored.ingress_url:
            logger.debug("external_ui_url: no ingress_url stored yet")
            return ""
        url = self._public_ui_url(self._stored.ingress_url)
        logger.debug("external_ui_url=%s", url)
        return url

    @property
    def external_api_url(self) -> str:
        """Return the externally reachable API URL, if known."""
        if not self._stored.ingress_url:
            logger.debug("external_api_url: no ingress_url stored yet")
            return ""
        parts = urlsplit(self._stored.ingress_url)
        path = self._api_base_path()
        url = urlunsplit((parts.scheme, parts.netloc, path or "/", "", ""))
        logger.debug("external_api_url=%s", url)
        return url

    @property
    def _catalogue_item(self) -> CatalogueItem:
        api_url = self.external_api_url
        ui_url = self.external_ui_url
        endpoints = {}
        if ui_url:
            endpoints["UI"] = ui_url
        if api_url:
            base = api_url.rstrip("/")
            endpoints.update(
                {
                    "REST API": api_url,
                    "Server Info": f"{base}/api/v1/info",
                }
            )
        logger.debug(
            "catalogue item: ui_url=%s api_url=%s endpoints=%s", ui_url, api_url, endpoints
        )
        return CatalogueItem(
            name="ReductStore",
            url=ui_url,
            icon="database",
            description=(
                "ReductStore is a time series object store for high-frequency unstructured data."
            ),
            api_docs="https://www.reduct.store/docs",
            api_endpoints=endpoints,
        )

    @property
    def _pebble_layer(self) -> ops.pebble.LayerDict:
        log_level = cast(str, self.model.config["log-level"])
        return {
            "summary": "ReductStore layer",
            "description": "Pebble config layer for ReductStore",
            "services": {
                "reductstore": {
                    "override": "replace",
                    "summary": "ReductStore server",
                    "command": "reductstore",
                    "startup": "enabled",
                    "environment": {
                        "RS_INSTANCE_NAME": self._instance_name,
                        "RS_INSTANCE_ROLE": "PRIMARY",
                        "RS_LOG_LEVEL": str(log_level).upper(),
                        "RS_PORT": "8383",
                        "RS_DATA_PATH": "/data",
                        "RS_PUBLIC_URL": self.external_api_url or "",
                        "RS_API_BASE_PATH": self._api_base_path(),
                    },
                }
            },
        }


if __name__ == "__main__":
    ops.main(ReductstoreCharm)
