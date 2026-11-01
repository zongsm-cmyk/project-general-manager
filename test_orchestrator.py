import asyncio
import json
import multiprocessing
import os
import sqlite3
import subprocess
import time
import pytest
import websockets

import orchestrator
from orchestrator import (
    main, init_db, save_receipt, get_receipt, load_registry,
    resolve_project, recover_pending_tasks, pending_commands,
    DB_FILE, LOCAL_REGISTRY_FILE
)

TEST_PORT = 8798
TEST_URI = f"ws://127.0.0.1:{TEST_PORT}"

def run_test_server():
    """Runs orchestrator server on a dedicated test port."""
    os.environ["GM_ORCHESTRATOR_PORT"] = str(TEST_PORT)
    asyncio.run(main(host="127.0.0.1", port=TEST_PORT))

@pytest.fixture(scope="module")
def server():
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

    p = multiprocessing.Process(target=run_test_server)
    p.daemon = True
    p.start()
    time.sleep(1.2)  # Allow server to bind and start listening
    yield
    p.terminate()
    p.join(timeout=2)
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except Exception:
            pass
    if os.path.exists(LOCAL_REGISTRY_FILE):
        try:
            os.remove(LOCAL_REGISTRY_FILE)
        except Exception:
            pass

# -------------------------------------------------------------
# 1. Chrome Extension & Manifest Verification
# -------------------------------------------------------------
def test_chrome_extension_manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "extension", "manifest.json")
    assert os.path.exists(manifest_path), "manifest.json does not exist"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "General Manager Project Integrator"
    assert "https://chatgpt.com/*" in manifest.get("host_permissions", [])

    # Check background worker file
    bg_file = manifest.get("background", {}).get("service_worker")
    assert bg_file, "Service worker missing in manifest"
    bg_path = os.path.join(os.path.dirname(__file__), "extension", bg_file)
    assert os.path.exists(bg_path), f"Background service worker file not found at {bg_path}"

    # Check content script file
    cs_list = manifest.get("content_scripts", [])
    assert len(cs_list) > 0, "No content scripts declared"
    cs_file = cs_list[0].get("js", [])[0]
    cs_path = os.path.join(os.path.dirname(__file__), "extension", cs_file)
    assert os.path.exists(cs_path), f"Content script file not found at {cs_path}"

def test_extension_javascript_syntax():
    """Verify JavaScript syntax of background.js and content.js using node."""
    for script_name in ["background.js", "content.js"]:
        path = os.path.join(os.path.dirname(__file__), "extension", script_name)
        result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        assert result.returncode == 0, f"Syntax error in {script_name}: {result.stderr}"

# -------------------------------------------------------------
# 2. SQLite Database & Storage
# -------------------------------------------------------------
def test_database_operations():
    init_db()
    test_id = "test-cmd-001"
    receipt = {
        "command_id": test_id,
        "project_id": "GITHUB",
        "conversation_id": "test-conv-123",
        "instruction_preview": "Test database write",
        "created_at": "2026-11-01T12:00:00Z",
        "dispatched_at": "",
        "delivery_status": "PENDING",
        "execution_status": "PENDING",
        "result_received_at": "",
        "error_details": ""
    }
    save_receipt(receipt)
    fetched = get_receipt(test_id)
    assert fetched is not None
    assert fetched["command_id"] == test_id
    assert fetched["delivery_status"] == "PENDING"
    assert fetched["execution_status"] == "PENDING"

    # Update receipt
    receipt["delivery_status"] = "DELIVERED"
    receipt["execution_status"] = "COMPLETED"
    save_receipt(receipt)
    updated = get_receipt(test_id)
    assert updated["delivery_status"] == "DELIVERED"
    assert updated["execution_status"] == "COMPLETED"

def test_task_recovery():
    init_db()
    uncompleted_id = "test-cmd-recoverable"
    receipt = {
        "command_id": uncompleted_id,
        "project_id": "GITHUB",
        "conversation_id": "test-conv-123",
        "instruction_preview": "Recoverable task",
        "created_at": "2026-11-01T12:00:00Z",
        "dispatched_at": "",
        "delivery_status": "PENDING",
        "execution_status": "PENDING",
        "result_received_at": "",
        "error_details": ""
    }
    save_receipt(receipt)
    recovered = recover_pending_tasks()
    assert recovered >= 1
    assert uncompleted_id in pending_commands

# -------------------------------------------------------------
# 3. Registry & Project Resolution
# -------------------------------------------------------------
def test_registry_resolution():
    reg = load_registry()
    assert "GM" in reg
    assert "GITHUB" in reg

    # Active project resolution
    meta, err = resolve_project("GITHUB", reg)
    assert err is None
    assert meta["key"] == "GITHUB"
    assert meta["target_conversation_id"] == "6ae6e433-1550-83ea-aedc-461ec36d966d"

    # Unconfigured project resolution
    meta_etsy, err_etsy = resolve_project("ETSY", reg)
    assert meta_etsy is None
    assert "UNCONFIGURED" in err_etsy

    # Non-existent project
    meta_none, err_none = resolve_project("NON_EXISTENT_PROJECT", reg)
    assert meta_none is None
    assert "not found" in err_none

    # Alias check
    meta_social, err_social = resolve_project("SOCIAL_MEDIA_MANAGEMENT", reg)
    assert err_social is not None  # It resolves to SOCIAL_MEDIA which is UNCONFIGURED
    assert "SOCIAL_MEDIA" in err_social

# -------------------------------------------------------------
# 4. WebSocket Full Lifecycle & Routing
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_command_lifecycle(server):
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
        # 1. GM receives initial CONFIG
        config_msg = json.loads(await gm_client.recv())
        assert config_msg["type"] == "CONFIG"
        assert config_msg["gm_conversation_id"] == "6ae6dd41-105c-83e9-90ac-378e51c5e5af"

        async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as github_client:
            await github_client.recv()  # Consume CONFIG greeting

            # 2. GM dispatches a command to GITHUB
            dispatch_msg = {
                "type": "COMMAND_DISPATCH",
                "target_project": "GITHUB",
                "instruction": "Run code inspection."
            }
            await gm_client.send(json.dumps(dispatch_msg))

            # 3. GitHub client receives EXECUTE broadcast
            recv_cmd = json.loads(await github_client.recv())
            assert recv_cmd["type"] == "EXECUTE"
            assert recv_cmd["target_project"] == "GITHUB"
            command_id = recv_cmd["command_id"]

            # Also GM client receives broadcast (its content.js filters it out by conversation_id)
            gm_broadcast = json.loads(await gm_client.recv())
            assert gm_broadcast["command_id"] == command_id

            # 4. GitHub client sends ACK
            await github_client.send(json.dumps({"type": "ACK", "command_id": command_id}))
            await asyncio.sleep(0.3)

            receipt = get_receipt(command_id)
            assert receipt["delivery_status"] == "DELIVERED"

            # 5. GitHub client sends RESULT
            await github_client.send(json.dumps({
                "type": "RESULT",
                "command_id": command_id,
                "result": "Code inspection completed: 0 errors."
            }))

            # 6. GM receives GM_RESULT
            gm_res = json.loads(await gm_client.recv())
            assert gm_res["type"] == "GM_RESULT"
            assert gm_res["command_id"] == command_id
            assert "0 errors" in gm_res["result"]

            receipt_completed = get_receipt(command_id)
            assert receipt_completed["execution_status"] == "COMPLETED"

# -------------------------------------------------------------
# 5. Loop Guard & Error Handling Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_loop_guard_duplicate_result(server):
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
        await gm_client.recv()  # CONFIG

        async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as github_client:
            await github_client.recv()  # CONFIG

            # Dispatch command
            await gm_client.send(json.dumps({
                "type": "COMMAND_DISPATCH",
                "target_project": "GITHUB",
                "instruction": "Test loop guard."
            }))
            cmd = json.loads(await github_client.recv())
            command_id = cmd["command_id"]
            await gm_client.recv()  # GM receives broadcast

            # Send first RESULT
            await github_client.send(json.dumps({
                "type": "RESULT",
                "command_id": command_id,
                "result": "Done."
            }))
            gm_res = json.loads(await gm_client.recv())
            assert gm_res["type"] == "GM_RESULT"

            # Send duplicate RESULT
            await github_client.send(json.dumps({
                "type": "RESULT",
                "command_id": command_id,
                "result": "Done again (duplicate)."
            }))

            # Verify no second GM_RESULT is broadcast
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(gm_client.recv(), timeout=1.0)

@pytest.mark.asyncio
async def test_loop_guard_system_report_ignored(server):
    """Ensure a message tagged [SYSTEM REPORT - DO NOT EXECUTE] is never dispatched."""
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
        await gm_client.recv()  # CONFIG

        # Attempt to dispatch system report
        await gm_client.send(json.dumps({
            "type": "COMMAND_DISPATCH",
            "target_project": "GITHUB",
            "instruction": "[SYSTEM REPORT - DO NOT EXECUTE - JUST ACKNOWLEDGE AND SUMMARIZE] output text"
        }))

        # No command should be broadcast
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(gm_client.recv(), timeout=1.0)

@pytest.mark.asyncio
async def test_unconfigured_project_rejection(server):
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
        await gm_client.recv()  # CONFIG

        # Dispatch to UNCONFIGURED project ETSY
        await gm_client.send(json.dumps({
            "type": "COMMAND_DISPATCH",
            "target_project": "ETSY",
            "instruction": "Publish new listing."
        }))

        # Expect GM_ERROR broadcast
        err_msg = json.loads(await gm_client.recv())
        assert err_msg["type"] == "GM_ERROR"
        assert "UNCONFIGURED" in err_msg["error"]

@pytest.mark.asyncio
async def test_protocol_contract_and_deduplication(server):
    """
    Test full PROJECT_MANAGER_V1 contract fields:
    command_id, source, target_project, action, instruction, requires_reply.
    Verify duplicate command_id is rejected by Loop Guard.
    """
    unique_cmd_id = "test-mandate-cmd-uuid-999"
    contract_dispatch = {
        "protocol": "PROJECT_MANAGER_V1",
        "command_id": unique_cmd_id,
        "source": "GENERAL_MANAGER",
        "target_project": "GITHUB",
        "action": "DISPATCH",
        "instruction": "Confirm receipt of this test command.",
        "requires_reply": True
    }

    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
        await gm_client.recv()  # CONFIG

        async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gh_client:
            await gh_client.recv()  # CONFIG

            # 1. Dispatch contract command
            await gm_client.send(json.dumps(contract_dispatch))

            # 2. GitHub client receives EXECUTE with full contract fields
            received = json.loads(await gh_client.recv())
            assert received["type"] == "EXECUTE"
            assert received["protocol"] == "PROJECT_MANAGER_V1"
            assert received["command_id"] == unique_cmd_id
            assert received["source"] == "GENERAL_MANAGER"
            assert received["target_project"] == "GITHUB"
            assert received["action"] == "DISPATCH"
            assert received["instruction"] == "Confirm receipt of this test command."
            assert received["requires_reply"] is True
            await gm_client.recv()  # GM broadcast

            # 3. Acknowledge and send result
            await gh_client.send(json.dumps({"type": "ACK", "command_id": unique_cmd_id}))
            await gh_client.send(json.dumps({"type": "RESULT", "command_id": unique_cmd_id, "result": "Receipt confirmed."}))
            gm_result = json.loads(await gm_client.recv())
            assert gm_result["type"] == "GM_RESULT"
            assert gm_result["command_id"] == unique_cmd_id
            assert gm_result["result"] == "Receipt confirmed."

            # Consume the broadcast on github client as well
            gh_res_broadcast = json.loads(await gh_client.recv())
            assert gh_res_broadcast["type"] == "GM_RESULT"

            # 4. Attempt to re-dispatch the exact same command_id
            await gm_client.send(json.dumps(contract_dispatch))

            # Loop Guard should block it; no new EXECUTE should reach GitHub client
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(gh_client.recv(), timeout=1.0)

@pytest.mark.asyncio
async def test_client_registration_and_reconnection(server):
    """Verify extension registration and reconnect resilience."""
    # Connect and Register
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as client:
        await client.recv()  # CONFIG
        await client.send(json.dumps({
            "type": "REGISTER",
            "client_type": "EXTENSION",
            "conversation_id": "conv-test-reconnect"
        }))
        reg_response = json.loads(await client.recv())
        assert reg_response["type"] == "REGISTERED"
        assert reg_response["status"] == "OK"
        assert reg_response["conversation_id"] == "conv-test-reconnect"

    # Simulate abrupt disconnect and reconnect
    async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as client2:
        cfg = json.loads(await client2.recv())
        assert cfg["type"] == "CONFIG"
        # Can register again cleanly
        await client2.send(json.dumps({
            "type": "REGISTER",
            "client_type": "EXTENSION",
            "conversation_id": "conv-test-reconnect"
        }))
        reg_response2 = json.loads(await client2.recv())
        assert reg_response2["status"] == "OK"


# -------------------------------------------------------------
# 6. Multi-Project Routing Verification
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_project_routing(server):
    """
    Simulate 3 project tabs simultaneously:
    - GM (Command Center)
    - GITHUB (Target A)
    - KAGGLE_CONFIGURED (Target B via local override)
    Verify messages only execute in the designated project.
    """
    # Write a temporary active project to registry.local.json
    local_override = {
        "KAGGLE_TEST": {
            "project_name": "Kaggle Test",
            "target_conversation_id": "conv-kaggle-test-uuid",
            "status": "ACTIVE"
        }
    }
    with open(LOCAL_REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(local_override, f)

    try:
        async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as gm_client:
            await gm_client.recv()  # CONFIG

            async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as github_client:
                await github_client.recv()  # CONFIG

                async with websockets.connect(TEST_URI, origin="https://chatgpt.com") as kaggle_client:
                    await kaggle_client.recv()  # CONFIG

                    # Send command strictly targeting KAGGLE_TEST
                    await gm_client.send(json.dumps({
                        "type": "COMMAND_DISPATCH",
                        "target_project": "KAGGLE_TEST",
                        "instruction": "Submit model predictions."
                    }))

                    # Read broadcast on both clients
                    msg_gh = json.loads(await github_client.recv())
                    msg_kg = json.loads(await kaggle_client.recv())
                    await gm_client.recv()  # GM broadcast

                    assert msg_gh["target_project"] == "KAGGLE_TEST"
                    assert msg_kg["target_project"] == "KAGGLE_TEST"
                    assert msg_kg["target_conversation_id"] == "conv-kaggle-test-uuid"

                    # Only Kaggle client matches conversation ID and responds
                    kaggle_cmd_id = msg_kg["command_id"]
                    await kaggle_client.send(json.dumps({
                        "type": "RESULT",
                        "command_id": kaggle_cmd_id,
                        "result": "Predictions submitted: Score 0.94"
                    }))

                    # GM receives the Kaggle result
                    gm_result = json.loads(await gm_client.recv())
                    assert gm_result["type"] == "GM_RESULT"
                    assert gm_result["project_id"] == "KAGGLE_TEST"
                    assert "Score 0.94" in gm_result["result"]
    finally:
        if os.path.exists(LOCAL_REGISTRY_FILE):
            os.remove(LOCAL_REGISTRY_FILE)

# -------------------------------------------------------------
# 7. Origin Security Check
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_origin_rejected(server):
    """Ensure random websites cannot connect to the local orchestrator."""
    with pytest.raises(Exception):
        async with websockets.connect(TEST_URI, origin="http://malicious-website.com") as ws:
            await ws.recv()

# -------------------------------------------------------------
# 8. Windows Scripts Integrity
# -------------------------------------------------------------
def test_windows_scripts_exist():
    base_dir = os.path.dirname(__file__)
    start_bat = os.path.join(base_dir, "start_gm.bat")
    stop_bat = os.path.join(base_dir, "stop_gm.bat")

    assert os.path.exists(start_bat), "start_gm.bat not found"
    assert os.path.exists(stop_bat), "stop_gm.bat not found"

    with open(start_bat, "r", encoding="utf-8") as f:
        content = f.read()
        assert "8799" in content
        assert ".venv" in content
        assert "orchestrator.log" in content

    with open(stop_bat, "r", encoding="utf-8") as f:
        content = f.read()
        assert "8799" in content
        assert "taskkill" in content

# -------------------------------------------------------------
# 9. Server Port Lifecycle & Resource Usage
# -------------------------------------------------------------
def test_server_port_lifecycle_and_resources():
    import socket
    import sys

    py_exe = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
    script = os.path.join(os.path.dirname(__file__), "orchestrator.py")

    # Start orchestrator process on default port 8799
    proc = subprocess.Popen([py_exe, script], cwd=os.path.dirname(__file__))
    try:
        time.sleep(1.5)

        # Check port 8799 is open
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = s.connect_ex(("127.0.0.1", 8799))
        s.close()
        assert res == 0, "Port 8799 was not opened by orchestrator"

        # Check resource usage via psutil or Windows tasklist
        tasklist_res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {proc.pid}", "/FO", "CSV"],
            capture_output=True,
            text=True
        )
        assert str(proc.pid) in tasklist_res.stdout, "Process was not found in tasklist"

    finally:
        proc.terminate()
        proc.wait(timeout=3)

    # Ensure port 8799 is released
    time.sleep(0.5)
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    res2 = s2.connect_ex(("127.0.0.1", 8799))
    s2.close()
    assert res2 != 0, "Port 8799 should be closed after process termination"

