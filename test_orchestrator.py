import asyncio
import json
import sqlite3
import pytest
import websockets
import multiprocessing
import time
import os

from orchestrator import main, DB_FILE

def run_server():
    asyncio.run(main())

@pytest.fixture(scope="module")
def server():
    # Start the orchestrator in a separate process
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    p = multiprocessing.Process(target=run_server)
    p.start()
    time.sleep(1) # Wait for server to start
    yield
    p.terminate()
    p.join()
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

@pytest.mark.asyncio
async def test_websocket_connection_and_command_flow(server):
    uri = "ws://127.0.0.1:8799"

    # Client 1: GM Chat Simulator
    async with websockets.connect(uri) as gm_client:
        # Client 2: GitHub Chat Simulator
        async with websockets.connect(uri) as github_client:

            # 1. GM sends a dispatch command
            dispatch_msg = {
                "type": "COMMAND_DISPATCH",
                "target_project": "GITHUB",
                "instruction": "Fix the bugs."
            }
            await gm_client.send(json.dumps(dispatch_msg))

            # 2. Both clients should receive the broadcasted EXECUTE command
            # The GitHub client checks it and sees it's for them.
            github_recv = json.loads(await github_client.recv())
            assert github_recv["type"] == "EXECUTE"
            assert github_recv["target_project"] == "GITHUB"
            command_id = github_recv["command_id"]

            # (GM client also receives the broadcast, which its content.js would ignore since its conversation_id doesn't match)
            gm_recv = json.loads(await gm_client.recv())
            assert gm_recv["command_id"] == command_id

            # Check Database for PENDING receipt
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT delivery_status, execution_status FROM receipts WHERE command_id=?", (command_id,))
            row = cursor.fetchone()
            assert row[0] == "PENDING"
            assert row[1] == "PENDING"
            conn.close()

            # 3. GitHub client acknowledges receipt
            await github_client.send(json.dumps({"type": "ACK", "command_id": command_id}))
            await asyncio.sleep(0.5) # Wait for DB update

            # Check Database for DELIVERED status
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT delivery_status FROM receipts WHERE command_id=?", (command_id,))
            assert cursor.fetchone()[0] == "DELIVERED"
            conn.close()

            # 4. GitHub client sends RESULT
            await github_client.send(json.dumps({
                "type": "RESULT",
                "command_id": command_id,
                "result": "Bugs fixed successfully."
            }))

            # 5. GM client should receive GM_RESULT
            gm_result = json.loads(await gm_client.recv())
            assert gm_result["type"] == "GM_RESULT"
            assert gm_result["result"] == "Bugs fixed successfully."

            # 6. Check Database for COMPLETED status
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT execution_status FROM receipts WHERE command_id=?", (command_id,))
            assert cursor.fetchone()[0] == "COMPLETED"
            conn.close()

            # 7. Test Loop Prevention (Sending RESULT again should be ignored)
            # Send same result again
            await github_client.send(json.dumps({
                "type": "RESULT",
                "command_id": command_id,
                "result": "Bugs fixed successfully (duplicate)."
            }))

            # We expect no new broadcast. We can test this by waiting with a short timeout.
            try:
                await asyncio.wait_for(gm_client.recv(), timeout=1.0)
                assert False, "Received a GM_RESULT broadcast when it should have been blocked by loop guard"
            except asyncio.TimeoutError:
                pass # Expected
