import asyncio
import json
import uuid
from datetime import datetime, timezone
import os
import re
import signal
import sqlite3
import sys
import websockets

# Configuration
REGISTRY_FILE = "registry.json"
LOCAL_REGISTRY_FILE = "registry.local.json"
DB_FILE = "receipts.db"
DEFAULT_PORT = 8799
DEFAULT_HOST = "127.0.0.1"

# Allowed WebSocket origins (ChatGPT and Chrome Extensions)
ALLOWED_ORIGIN_PATTERNS = [
    re.compile(r"^https://chatgpt\.com$"),
    re.compile(r"^chrome-extension://[a-z0-9]+$"),
    re.compile(r"^null$"),
]

connected_clients = set()
pending_commands = {}

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            command_id TEXT PRIMARY KEY,
            project_id TEXT,
            conversation_id TEXT,
            instruction_preview TEXT,
            created_at TEXT,
            dispatched_at TEXT,
            delivery_status TEXT,
            execution_status TEXT,
            result_received_at TEXT,
            error_details TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_receipt(receipt):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO receipts
        (command_id, project_id, conversation_id, instruction_preview, created_at, dispatched_at,
         delivery_status, execution_status, result_received_at, error_details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        receipt.get('command_id'),
        receipt.get('project_id'),
        receipt.get('conversation_id'),
        receipt.get('instruction_preview', '')[:120],
        receipt.get('created_at'),
        receipt.get('dispatched_at'),
        receipt.get('delivery_status'),
        receipt.get('execution_status'),
        receipt.get('result_received_at'),
        receipt.get('error_details')
    ))
    conn.commit()
    conn.close()

def get_receipt(command_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM receipts WHERE command_id = ?', (command_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'command_id': row[0],
            'project_id': row[1],
            'conversation_id': row[2],
            'instruction_preview': row[3],
            'created_at': row[4],
            'dispatched_at': row[5],
            'delivery_status': row[6],
            'execution_status': row[7],
            'result_received_at': row[8],
            'error_details': row[9]
        }
    return None

def recover_pending_tasks():
    """Load pending or uncompleted commands into memory upon startup."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT command_id, project_id, conversation_id, instruction_preview FROM receipts WHERE execution_status IN ('PENDING', 'IN_PROGRESS')")
    rows = cursor.fetchall()
    recovered_count = 0
    for row in rows:
        pending_commands[row[0]] = {
            "command_id": row[0],
            "target_project": row[1],
            "target_conversation_id": row[2],
            "instruction": row[3],
            "recovered": True
        }
        recovered_count += 1
    conn.close()
    if recovered_count > 0:
        print(f"[RECOVERY] Recovered {recovered_count} unfinished commands from SQLite database.")
    return recovered_count

def load_registry():
    registry = {}
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load {REGISTRY_FILE}: {e}")

    # Local overrides (untracked in git) for private conversation IDs
    if os.path.exists(LOCAL_REGISTRY_FILE):
        try:
            with open(LOCAL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                local_reg = json.load(f)
                registry.update(local_reg)
        except Exception as e:
            print(f"[WARNING] Failed to load {LOCAL_REGISTRY_FILE}: {e}")

    return registry

def resolve_project(target_project_key, registry):
    """Normalize and resolve project entry from registry."""
    if not target_project_key:
        return None, "Target project name cannot be empty."

    key_normalized = target_project_key.strip().upper()
    # Normalize common alias
    if key_normalized == "SOCIAL_MEDIA_MANAGEMENT":
        key_normalized = "SOCIAL_MEDIA"

    # Search in registry
    project_info = None
    matched_key = None
    for k, v in registry.items():
        if k.strip().upper() == key_normalized:
            project_info = v
            matched_key = k
            break

    if not project_info:
        return None, f"Project '{target_project_key}' not found in registry.json."

    status = (project_info.get("status") or "").upper()
    if status != "ACTIVE":
        return None, f"Project '{matched_key}' is '{status}'. Commands are blocked until confirmed."

    conv_id = project_info.get("target_conversation_id")
    if not conv_id or "PLEASE_REPLACE" in str(conv_id) or "UNCONFIGURED" in str(conv_id).upper():
        return None, f"Project '{matched_key}' conversation ID is not configured."

    return {
        "key": matched_key,
        "name": project_info.get("project_name", matched_key),
        "target_conversation_id": conv_id
    }, None

def is_allowed_origin(origin):
    """Check if the WebSocket origin is permitted."""
    if not origin:
        # Direct local connections (e.g. tests or python scripts)
        return True
    for pattern in ALLOWED_ORIGIN_PATTERNS:
        if pattern.match(origin):
            return True
    return False

async def safe_broadcast(message_dict):
    """Broadcast JSON message to all connected clients, dropping dead sockets."""
    payload = json.dumps(message_dict)
    dead_clients = set()
    for client in list(connected_clients):
        try:
            await client.send(payload)
        except websockets.exceptions.ConnectionClosed:
            dead_clients.add(client)
        except Exception as e:
            print(f"[ERROR] Error broadcasting to client: {e}")
            dead_clients.add(client)
    for dc in dead_clients:
        connected_clients.discard(dc)

async def handler(websocket):
    # Origin validation for CSRF/cross-origin safety
    origin = getattr(websocket, "origin", None)
    if hasattr(websocket, "request") and websocket.request and hasattr(websocket.request, "headers"):
        origin = websocket.request.headers.get("Origin", origin)

    if not is_allowed_origin(origin):
        print(f"[SECURITY] Rejected unauthorized origin: {origin}")
        await websocket.close(1008, "Policy violation: Unauthorized origin")
        return

    connected_clients.add(websocket)
    # Send configuration/greeting
    try:
        registry = load_registry()
        active_projects = {k: v.get("status", "") for k, v in registry.items()}
        gm_conv_id = registry.get("GM", {}).get("target_conversation_id", "6ae6dd41-105c-83e9-90ac-378e51c5e5af")
        await websocket.send(json.dumps({
            "type": "CONFIG",
            "gm_conversation_id": gm_conv_id,
            "active_projects": active_projects,
            "server_time": datetime.now(timezone.utc).isoformat()
        }))
    except Exception:
        pass

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception as e:
                print(f"[WARNING] Invalid JSON received: {e}")
                await websocket.send(json.dumps({"type": "ERROR", "error": "Invalid JSON format"}))
                continue

            msg_type = data.get("type")

            if msg_type == "COMMAND_DISPATCH":
                target_project = data.get("target_project")
                instruction = data.get("instruction", "")

                # Loop Guard 1: Detect system reports mistakenly re-dispatched
                if "[SYSTEM REPORT - DO NOT EXECUTE" in instruction:
                    print("[LOOP GUARD] Ignored command containing system report tag.")
                    continue

                registry = load_registry()
                project_meta, error_msg = resolve_project(target_project, registry)

                if error_msg:
                    print(f"[DISPATCH REJECTED] {error_msg}")
                    error_receipt = {
                        "command_id": str(uuid.uuid4()),
                        "project_id": str(target_project),
                        "conversation_id": "NONE",
                        "instruction_preview": instruction[:80],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "dispatched_at": "",
                        "delivery_status": "FAILED",
                        "execution_status": "REJECTED",
                        "result_received_at": "",
                        "error_details": error_msg
                    }
                    save_receipt(error_receipt)
                    await safe_broadcast({
                        "type": "GM_ERROR",
                        "target_project": target_project,
                        "error": error_msg
                    })
                    continue

                command_id = str(uuid.uuid4())
                target_conversation_id = project_meta["target_conversation_id"]

                command = {
                    "type": "EXECUTE",
                    "command_id": command_id,
                    "target_project": project_meta["key"],
                    "target_conversation_id": target_conversation_id,
                    "instruction": instruction,
                    "action": "DISPATCH"
                }

                receipt = {
                    "command_id": command_id,
                    "project_id": project_meta["key"],
                    "conversation_id": target_conversation_id,
                    "instruction_preview": instruction[:80],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "dispatched_at": "",
                    "delivery_status": "PENDING",
                    "execution_status": "PENDING",
                    "result_received_at": "",
                    "error_details": ""
                }
                save_receipt(receipt)
                pending_commands[command_id] = command

                print(f"[DISPATCH] Command {command_id[:8]} -> {project_meta['key']} (Conv: {target_conversation_id[:8]}...)")
                await safe_broadcast(command)

            elif msg_type == "ACK":
                command_id = data.get("command_id")
                receipt = get_receipt(command_id)
                if receipt:
                    receipt["delivery_status"] = "DELIVERED"
                    receipt["dispatched_at"] = datetime.now(timezone.utc).isoformat()
                    save_receipt(receipt)
                    print(f"[ACK] Command {command_id[:8]} delivered to target tab.")

            elif msg_type == "RESULT":
                command_id = data.get("command_id")
                result_text = data.get("result", "")
                receipt = get_receipt(command_id)
                if receipt:
                    # Loop Guard 2: Prevent duplicate results
                    if receipt["execution_status"] == "COMPLETED":
                        print(f"[LOOP GUARD] Result already completed for command {command_id[:8]}. Ignoring duplicate.")
                        continue

                    receipt["execution_status"] = "COMPLETED"
                    receipt["result_received_at"] = datetime.now(timezone.utc).isoformat()
                    save_receipt(receipt)
                    pending_commands.pop(command_id, None)

                    print(f"[RESULT] Command {command_id[:8]} completed by {receipt['project_id']}.")
                    gm_result_msg = {
                        "type": "GM_RESULT",
                        "command_id": command_id,
                        "project_id": receipt["project_id"],
                        "result": result_text
                    }
                    await safe_broadcast(gm_result_msg)
                else:
                    print(f"[WARNING] Received RESULT for unknown command_id: {command_id}")

            elif msg_type == "ERROR":
                command_id = data.get("command_id")
                error_details = data.get("error", "Unknown error")
                receipt = get_receipt(command_id)
                if receipt:
                    receipt["execution_status"] = "FAILED"
                    receipt["error_details"] = error_details
                    save_receipt(receipt)
                    pending_commands.pop(command_id, None)
                    print(f"[CLIENT ERROR] Command {command_id[:8]} failed: {error_details}")
                    await safe_broadcast({
                        "type": "GM_ERROR",
                        "command_id": command_id,
                        "project_id": receipt["project_id"],
                        "error": error_details
                    })

            elif msg_type == "STATUS_QUERY":
                # Diagnostic ping
                registry = load_registry()
                await websocket.send(json.dumps({
                    "type": "STATUS_RESPONSE",
                    "clients_connected": len(connected_clients),
                    "pending_commands_count": len(pending_commands),
                    "projects_loaded": len(registry)
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[UNEXPECTED ERROR] Handler exception: {e}")
    finally:
        connected_clients.discard(websocket)

async def main(host=None, port=None):
    init_db()
    recover_pending_tasks()
    
    server_host = host or os.environ.get("GM_ORCHESTRATOR_HOST", DEFAULT_HOST)
    server_port = int(port or os.environ.get("GM_ORCHESTRATOR_PORT", str(DEFAULT_PORT)))

    print(f"==================================================")
    print(f"  Project General Manager - Orchestrator Server  ")
    print(f"  Binding: ws://{server_host}:{server_port}         ")
    print(f"==================================================")

    async with websockets.serve(handler, server_host, server_port):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Orchestrator stopped gracefully.")
        sys.exit(0)
