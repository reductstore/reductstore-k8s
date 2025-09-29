# Copyright 2025 anthony
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import json

import ops
import ops.pebble
from charms.catalogue_k8s.v1.catalogue import CatalogueConsumer
from ops import testing
from ops.testing import Relation, State

from charm import ReductstoreCharm


def test_reductstore_pebble_ready():
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)

    state_in = testing.State(containers={container})

    state_out = ctx.run(ctx.on.pebble_ready(container), state_in)
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


def test_config_changed_valid_can_connect():
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    state_in = testing.State(
        containers={container},
        config={"log-level": "debug", "license-path": "/custom.lic", "api-base-path": "/newbase"},
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

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


def test_config_changed_invalid():
    ctx = testing.Context(ReductstoreCharm)
    container = testing.Container("reductstore", can_connect=True)
    invalid_level = "foobar"
    state_in = testing.State(
        containers={container}, config={"log-level": invalid_level, "license-path": "/x.lic"}
    )

    state_out = ctx.run(ctx.on.config_changed(), state_in)

    assert isinstance(state_out.unit_status, testing.BlockedStatus)
    assert invalid_level in state_out.unit_status.message


def test_catalogue_updated_on_ingress_ready(monkeypatch):
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
        out = mgr.run()
        charm = mgr.charm
        assert charm._stored.ingress_url == "http://example.test/"
        assert isinstance(out.unit_status, testing.ActiveStatus)

    assert len(seen) >= 1
    assert seen[-1].url == f"http://example.test/{out.model.name}-{charm.app.name}/ui/dashboard"
    assert seen[-1].name == "ReductStore"


def test_catalogue_cleared_on_ingress_revoked(monkeypatch):
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
        state = mgr.run()
        charm = mgr.charm
        assert mgr.charm._stored.ingress_url == "http://example.test/"
        assert isinstance(state.unit_status, testing.ActiveStatus)

    rel_in_state = state.get_relation(ingress_rel.id)

    with ctx(ctx.on.relation_broken(rel_in_state), state) as mgr:
        out = mgr.run()
        charm = mgr.charm
        assert charm._stored.ingress_url == ""
        assert isinstance(out.unit_status, testing.MaintenanceStatus)

    assert len(seen) >= 2
    assert seen[-1].url == ""
