# Copyright 2025 anthony
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json
from pathlib import Path

import ops
import ops.pebble
from charms.catalogue_k8s.v1.catalogue import CatalogueConsumer
from ops import testing
from ops.model import ModelError
from ops.testing import Relation, State

from charm import ReductstoreCharm


def _stub_license_fetch(monkeypatch, charm, tmp_path: Path, content: bytes = b"LICENSE"):
    """Monkeypatch charm.model.resources.fetch to return a real temp file path."""
    lic = tmp_path / "license.key"
    lic.write_bytes(content)

    def _fake_fetch(name: str):
        assert name == "reductstore-license"
        return str(lic)

    monkeypatch.setattr(charm.model.resources, "fetch", _fake_fetch, raising=False)


def _stub_license_fetch_missing(monkeypatch, charm):
    """Monkeypatch fetch to raise as if no resource was attached."""

    def _raise_missing(name: str):
        raise ModelError("resource not found")

    monkeypatch.setattr(charm.model.resources, "fetch", _raise_missing, raising=False)


def test_reductstore_pebble_ready(monkeypatch, tmp_path):
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    state_in = testing.State(containers={container})

    with ctx(ctx.on.pebble_ready(container), state_in) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        state_out = mgr.run()

    model_name = state_out.model.name
    app_name = "reductstore-k8s"
    updated_plan = state_out.get_container(container.name).plan
    expected_plan = {
        "services": {
            "reductstore": {
                "override": "replace",
                "summary": "ReductStore server",
                "command": "reductstore",
                "startup": "enabled",
                "environment": {
                    "RS_LOG_LEVEL": "INFO",
                    "RS_PORT": "8383",
                    "RS_DATA_PATH": "/data",
                    "RS_LICENSE_PATH": "/reduct.lic",
                    "RS_API_BASE_PATH": f"/{model_name}-{app_name}",
                },
            }
        },
    }

    assert expected_plan == updated_plan
    assert (
        state_out.get_container(container.name).service_statuses["reductstore"]
        == ops.pebble.ServiceStatus.ACTIVE
    )
    assert state_out.unit_status == testing.ActiveStatus()


def test_config_changed_valid_can_connect(monkeypatch, tmp_path):
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    state_in = testing.State(
        containers={container},
        config={"log-level": "debug", "license-path": "/custom.lic", "api-base-path": "/newbase"},
    )

    with ctx(ctx.on.config_changed(), state_in) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        state_out = mgr.run()

    updated_plan = state_out.get_container(container.name).plan
    assert updated_plan.services["reductstore"].command == "reductstore"
    assert updated_plan.services["reductstore"].environment == {
        "RS_LOG_LEVEL": "DEBUG",
        "RS_PORT": "8383",
        "RS_DATA_PATH": "/data",
        "RS_LICENSE_PATH": "/custom.lic",
        "RS_API_BASE_PATH": "/newbase",
    }
    assert state_out.unit_status == testing.ActiveStatus()


def test_config_changed_valid_cannot_connect():
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=False)
    state_in = testing.State(
        containers={container}, config={"log-level": "debug", "license-path": "/x.lic"}
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.MaintenanceStatus)


def test_config_changed_invalid(monkeypatch, tmp_path):
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    invalid_level = "foobar"
    state_in = testing.State(
        containers={container}, config={"log-level": invalid_level, "license-path": "/x.lic"}
    )

    with ctx(ctx.on.config_changed(), state_in) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        state_out = mgr.run()

    assert isinstance(state_out.unit_status, testing.BlockedStatus)
    assert invalid_level in state_out.unit_status.message


def test_catalogue_updated_on_ingress_ready(monkeypatch, tmp_path):
    seen = []

    def fake_update(self, item):
        seen.append(item)

    monkeypatch.setattr(CatalogueConsumer, "update_item", fake_update, raising=True)

    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    ingress_rel = Relation(
        "ingress",
        remote_app_name="traefik",
        remote_app_data={"ingress": json.dumps({"url": "http://example.test"})},
    )
    state_in = State(containers={container}, relations={ingress_rel}, leader=True)

    with ctx(ctx.on.relation_changed(ingress_rel), state_in) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        out = mgr.run()
        charm = mgr.charm
        assert charm._stored.ingress_url == "http://example.test/"
        assert isinstance(out.unit_status, testing.ActiveStatus)

    assert len(seen) >= 1
    assert seen[-1].url == f"http://example.test/{out.model.name}-{charm.app.name}/ui/dashboard"
    assert seen[-1].name == "ReductStore"


def test_catalogue_cleared_on_ingress_revoked(monkeypatch, tmp_path):
    seen = []

    def fake_update(self, item):
        seen.append(item)

    monkeypatch.setattr(CatalogueConsumer, "update_item", fake_update, raising=True)

    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    ingress_rel = Relation(
        "ingress",
        remote_app_name="traefik",
        remote_app_data={"ingress": json.dumps({"url": "http://example.test"})},
    )
    state = State(containers={container}, relations={ingress_rel}, leader=True)

    with ctx(ctx.on.relation_changed(ingress_rel), state) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        state = mgr.run()
        charm = mgr.charm
        assert mgr.charm._stored.ingress_url == "http://example.test/"
        assert isinstance(state.unit_status, testing.ActiveStatus)

    rel_in_state = state.get_relation(ingress_rel.id)

    with ctx(ctx.on.relation_broken(rel_in_state), state) as mgr:
        _stub_license_fetch(monkeypatch, mgr.charm, tmp_path)
        out = mgr.run()
        charm = mgr.charm
        assert charm._stored.ingress_url == ""
        assert isinstance(out.unit_status, testing.MaintenanceStatus)

    assert len(seen) >= 2
    assert seen[-1].url == ""


def test_blocked_when_license_missing(monkeypatch):
    """If the license resource isn't attached yet, charm should block with clear instruction."""
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    state_in = testing.State(containers={container})

    with ctx(ctx.on.pebble_ready(container), state_in) as mgr:
        _stub_license_fetch_missing(monkeypatch, mgr.charm)
        out = mgr.run()

    assert isinstance(out.unit_status, testing.BlockedStatus)
    assert "reductstore-license" in out.unit_status.message
