#!/usr/bin/env python3
# Copyright 2025-2026 ReductSoftware UG
# See LICENSE file for licensing details.

import logging
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]
TRAEFIK_APP_NAME = "traefik-k8s"
CATALOGUE_APP_NAME = "catalogue-k8s"


@pytest_asyncio.fixture(scope="module")
async def reductstore_deployed(ops_test: OpsTest) -> OpsTest:
    """Build and deploy ReductStore once for the integration module."""
    charm = await ops_test.build_charm(".")
    resources = {
        "reductstore-image": METADATA["resources"]["reductstore-image"]["upstream-source"],
    }
    if ops_test.model is None:
        raise RuntimeError("Model is not available in ops_test")
    await ops_test.model.deploy(
        charm,
        resources=resources,
        application_name=APP_NAME,
        config={"api-base-path": "/"},
    )
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME], status="active", raise_on_blocked=True, timeout=1000
    )
    return ops_test


@pytest.mark.abort_on_fail
async def test_build_and_deploy(reductstore_deployed: OpsTest):
    """Verify the deployed workload API."""
    ops_test = reductstore_deployed
    if ops_test.model is None:
        raise RuntimeError("Model is not available in ops_test")

    # API check
    status = await ops_test.model.get_status()
    unit = status["applications"][APP_NAME]["units"][f"{APP_NAME}/0"]
    address = unit["address"]

    async with aiohttp.ClientSession() as session:
        url = f"http://{address}:8383/api/v1/info"
        async with session.get(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            logger.info("ReductStore info: %s", data)
            assert "version" in data


@pytest.mark.abort_on_fail
async def test_integrate_with_ingress_and_catalogue(reductstore_deployed: OpsTest):
    """Verify both required and optional relations reach an active state."""
    ops_test = reductstore_deployed
    if ops_test.model is None:
        raise RuntimeError("Model is not available in ops_test")

    await ops_test.model.deploy(
        "traefik-k8s",
        application_name=TRAEFIK_APP_NAME,
        channel="latest/stable",
        trust=True,
    )
    await ops_test.model.deploy(
        "catalogue-k8s",
        application_name=CATALOGUE_APP_NAME,
        channel="3.0/stable",
    )
    await ops_test.model.integrate(f"{APP_NAME}:ingress", f"{TRAEFIK_APP_NAME}:ingress")
    await ops_test.model.integrate(f"{APP_NAME}:catalogue", f"{CATALOGUE_APP_NAME}:catalogue")
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, TRAEFIK_APP_NAME, CATALOGUE_APP_NAME],
        status="active",
        raise_on_blocked=True,
        timeout=1000,
    )
