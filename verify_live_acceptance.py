import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
import websockets

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(PROJECT_DIR, "receipts.db")
PY_EXE = os.path.join(PROJECT_DIR, ".venv", "Scripts", "python.exe")
SERVER_SCRIPT = os.path.join(PROJECT_DIR, "orchestrator.py")
URI = "ws://127.0.0.1:8799"

async def run_live_acceptance():
    print("=" * 60)
    print("  PROJECT GENERAL MANAGER - LIVE ACCEPTANCE TEST SUITE")
    print("=" * 60)

    # 1. Clean previous test DB
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print("[SETUP] Cleaned previous receipts.db for fresh verification.")
        except Exception as e:
            print(f"[SETUP WARNING] Could not remove DB: {e}")

    # 2. Launch Orchestrator Server on port 8799
    print("[STEP 1] Starting orchestrator.py on ws://127.0.0.1:8799 ...")
    server_proc = subprocess.Popen([PY_EXE, SERVER_SCRIPT], cwd=PROJECT_DIR)
    time.sleep(2.0)

    try:
        # Verify port is listening
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = s.connect_ex(("127.0.0.1", 8799))
        s.close()
        assert res == 0, "[FAIL] Server is not listening on port 8799!"
        print(f"[STEP 1 PASS] Orchestrator is running with PID {server_proc.pid} on port 8799.")

        # 3. Test Unauthorized Origin Rejection
        print("[STEP 2] Testing unauthorized origin rejection (Security Check)...")
        rejected = False
        try:
            async with websockets.connect(URI, origin="https://unauthorized-evil-site.com") as bad_ws:
                await bad_ws.recv()
        except websockets.exceptions.ConnectionClosed as cc:
            rejected = True
            print(f"[STEP 2 PASS] Unauthorized origin closed by server with code {cc.code}: {cc.reason}")
        except Exception as e:
            rejected = True
            print(f"[STEP 2 PASS] Connection failed for unauthorized origin: {e}")
        assert rejected, "Unauthorized origin was NOT rejected!"

        # 4. Connect GM Client & GitHub Project Client
        print("[STEP 3] Connecting GM Client & GitHub Tab Client with authorized origin...")
        async with websockets.connect(URI, origin="https://chatgpt.com") as gm_client:
            gm_cfg = json.loads(await gm_client.recv())
            assert gm_cfg["type"] == "CONFIG"
            print(f"[CLIENT GM] Connected. GM Target Conv: {gm_cfg['gm_conversation_id']}")

            # Register GM
            await gm_client.send(json.dumps({
                "type": "REGISTER",
                "client_type": "GENERAL_MANAGER_TAB",
                "conversation_id": "6ae6dd41-105c-83e9-90ac-378e51c5e5af"
            }))
            gm_reg = json.loads(await gm_client.recv())
            assert gm_reg["type"] == "REGISTERED"
            print("[CLIENT GM] Registered successfully.")

            async with websockets.connect(URI, origin="https://chatgpt.com") as gh_client:
                gh_cfg = json.loads(await gh_client.recv())
                assert gh_cfg["type"] == "CONFIG"
                print("[CLIENT GITHUB] Connected.")

                # Register GitHub Client
                await gh_client.send(json.dumps({
                    "type": "REGISTER",
                    "client_type": "PROJECT_TAB",
                    "conversation_id": "6ae6e433-1550-83ea-aedc-461ec36d966d"
                }))
                gh_reg = json.loads(await gh_client.recv())
                assert gh_reg["type"] == "REGISTERED"
                print("[CLIENT GITHUB] Registered with conversation_id: 6ae6e433-1550-83ea-aedc-461ec36d966d")

                # 5. Dispatch Live Acceptance Command
                test_cmd_id = "acceptance-live-20261101-001"
                dispatch_payload = {
                    "protocol": "PROJECT_MANAGER_V1",
                    "command_id": test_cmd_id,
                    "source": "GENERAL_MANAGER",
                    "target_project": "GITHUB",
                    "action": "DISPATCH",
                    "instruction": "اختبار اتصال من المدير العام. أكّد الاستلام فقط، دون تعديل أي ملف أو مستودع.",
                    "requires_reply": True
                }
                print(f"[STEP 4] GM dispatching command: {test_cmd_id} ...")
                await gm_client.send(json.dumps(dispatch_payload))

                # GitHub receives command
                exec_cmd = json.loads(await gh_client.recv())
                await gm_client.recv()  # GM receives broadcast
                assert exec_cmd["type"] == "EXECUTE"
                assert exec_cmd["command_id"] == test_cmd_id
                assert exec_cmd["target_project"] == "GITHUB"
                assert exec_cmd["target_conversation_id"] == "6ae6e433-1550-83ea-aedc-461ec36d966d"
                print(f"[STEP 4 PASS] GitHub client received EXECUTE command: {exec_cmd['instruction']}")

                # 6. Verify SQLite PENDING state
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT delivery_status, execution_status FROM receipts WHERE command_id = ?", (test_cmd_id,))
                row_pending = c.fetchone()
                assert row_pending == ("PENDING", "PENDING")
                conn.close()
                print(f"[STEP 5 PASS] SQLite initial receipt verified: {row_pending}")

                # 7. GitHub Client sends ACK
                print("[STEP 6] GitHub client sending ACK...")
                await gh_client.send(json.dumps({"type": "ACK", "command_id": test_cmd_id}))
                await asyncio.sleep(0.4)

                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT delivery_status, dispatched_at FROM receipts WHERE command_id = ?", (test_cmd_id,))
                row_ack = c.fetchone()
                assert row_ack[0] == "DELIVERED"
                conn.close()
                print(f"[STEP 6 PASS] SQLite receipt updated to DELIVERED at {row_ack[1]}")

                # 8. GitHub Client sends RESULT
                result_text = "تم تأكيد استلام أمر الاختبار من المدير العام بنجاح. جاهز للتعليمات القادمة."
                print(f"[STEP 7] GitHub client replying with RESULT: '{result_text}' ...")
                await gh_client.send(json.dumps({
                    "type": "RESULT",
                    "command_id": test_cmd_id,
                    "result": result_text
                }))

                # GM receives result
                gm_result = json.loads(await gm_client.recv())
                assert gm_result["type"] == "GM_RESULT"
                assert gm_result["command_id"] == test_cmd_id
                assert gm_result["project_id"] == "GITHUB"
                assert gm_result["result"] == result_text
                # Consume broadcast on github client
                await gh_client.recv()
                print(f"[STEP 7 PASS] GM successfully received GM_RESULT back!")

                # 9. Verify SQLite COMPLETED state
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT execution_status, result_received_at FROM receipts WHERE command_id = ?", (test_cmd_id,))
                row_comp = c.fetchone()
                assert row_comp[0] == "COMPLETED"
                conn.close()
                print(f"[STEP 8 PASS] SQLite receipt updated to COMPLETED at {row_comp[1]}")

                # 10. Loop Guard: Re-sending exact same command_id must be blocked
                print("[STEP 9] Testing Loop Guard deduplication with duplicate command_id...")
                await gm_client.send(json.dumps(dispatch_payload))
                with pytest_like_timeout():
                    # gh_client should not receive anything
                    try:
                        await asyncio.wait_for(gh_client.recv(), timeout=1.0)
                        assert False, "Loop Guard failed! Duplicate command was dispatched."
                    except asyncio.TimeoutError:
                        print("[STEP 9 PASS] Loop Guard successfully blocked duplicate command_id!")

                # 11. Reconnection Resilience: Disconnect GitHub client and reconnect
                print("[STEP 10] Testing Reconnection Resilience...")
            # GitHub client disconnected here

            # Reconnect GitHub client
            async with websockets.connect(URI, origin="https://chatgpt.com") as gh_client_new:
                await gh_client_new.recv()  # CONFIG
                await gh_client_new.send(json.dumps({
                    "type": "REGISTER",
                    "client_type": "PROJECT_TAB",
                    "conversation_id": "6ae6e433-1550-83ea-aedc-461ec36d966d"
                }))
                reg_ack = json.loads(await gh_client_new.recv())
                assert reg_ack["type"] == "REGISTERED"
                print("[STEP 10 PASS] GitHub tab reconnected and registered seamlessly.")

        # 12. Duplicate Server Run Prevention (Check start_gm.bat protection)
        print("[STEP 11] Testing duplicate server startup prevention...")
        proc_duplicate = subprocess.Popen([PY_EXE, SERVER_SCRIPT], cwd=PROJECT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.0)
        # Attempt to bind to 8799 should fail for duplicate
        poll_res = proc_duplicate.poll()
        assert poll_res is not None or proc_duplicate.returncode is not None, "Duplicate server should exit or fail to bind!"
        print(f"[STEP 11 PASS] Duplicate server prevented with exit code: {proc_duplicate.returncode}")

    finally:
        # 13. Stop Server via stop_gm.bat logic
        print("[STEP 12] Stopping server cleanly...")
        server_proc.terminate()
        server_proc.wait(timeout=3)
        time.sleep(0.5)

        s_check = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port_state = s_check.connect_ex(("127.0.0.1", 8799))
        s_check.close()
        assert port_state != 0, "Port 8799 should be released!"
        print("[STEP 12 PASS] Server stopped cleanly. Port 8799 released.")

    # 14. Print Final Execution Receipt from Database
    print("\n" + "=" * 60)
    print("  FINAL EXECUTION RECEIPT FROM SQLITE (receipts.db)")
    print("=" * 60)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT command_id, project_id, conversation_id, instruction_preview, created_at, dispatched_at, delivery_status, execution_status, result_received_at FROM receipts")
    rows = c.fetchall()
    for row in rows:
        print(f"Command ID:        {row[0]}")
        print(f"Project ID:        {row[1]}")
        print(f"Conversation ID:   {row[2]}")
        print(f"Instruction:       {row[3]}")
        print(f"Created At:        {row[4]}")
        print(f"Dispatched At:     {row[5]}")
        print(f"Delivery Status:   {row[6]}")
        print(f"Execution Status:  {row[7]}")
        print(f"Result Received:   {row[8]}")
    conn.close()
    print("=" * 60)
    print("  ALL 12 ACCEPTANCE VERIFICATION STEPS PASSED 100%!")
    print("=" * 60)

class pytest_like_timeout:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

if __name__ == "__main__":
    asyncio.run(run_live_acceptance())
