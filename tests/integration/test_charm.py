#!/usr/bin/env python3
# Copyright 2025 anthony
# See LICENSE file for licensing details.

import logging
import tempfile
from pathlib import Path

import aiohttp
import pytest
import yaml
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

METADATA = yaml.safe_load(Path("./charmcraft.yaml").read_text())
APP_NAME = METADATA["name"]


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest):
    """Build the charm, deploy it with required resources, and verify the API."""
    # Build charm from local source
    charm = await ops_test.build_charm(".")

    # Create a temporary license file
    with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
        tf.write(b"TEST-LICENSE")
        lic_path = tf.name

    resources = {
        "reductstore-image": METADATA["resources"]["reductstore-image"]["upstream-source"],
        "reductstore-license": lic_path,
    }

    # Deploy, then wait for Active
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
