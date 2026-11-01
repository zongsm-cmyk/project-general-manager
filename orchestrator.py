import asyncio
import json
import uuid
from datetime import datetime
import os
import sqlite3
import websockets

# Configuration
REGISTRY_FILE = "registry.json"
DB_FILE = "receipts.db"

# Initialize Database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            command_id TEXT PRIMARY KEY,
            project_id TEXT,
            conversation_id TEXT,
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO receipts
        (command_id, project_id, conversation_id, created_at, dispatched_at, delivery_status, execution_status, result_received_at, error_details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        receipt.get('command_id'),
        receipt.get('project_id'),
        receipt.get('conversation_id'),
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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM receipts WHERE command_id = ?', (command_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            'command_id': row[0],
            'project_id': row[1],
            'conversation_id': row[2],
            'created_at': row[3],
            'dispatched_at': row[4],
            'delivery_status': row[5],
            'execution_status': row[6],
            'result_received_at': row[7],
            'error_details': row[8]
        }
    return None

def load_registry():
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

connected_clients = set()
pending_commands = {}

async def handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "COMMAND_DISPATCH":
                # From General Manager
                target_project = data.get("target_project")
                instruction = data.get("instruction")

                registry = load_registry()
                project_info = registry.get(target_project)

                if not project_info:
                    print(f"Project {target_project} not found in registry.")
                    continue

                command_id = str(uuid.uuid4())
                target_conversation_id = project_info["target_conversation_id"]

                command = {
                    "type": "EXECUTE",
                    "command_id": command_id,
                    "target_project": target_project,
                    "target_conversation_id": target_conversation_id,
                    "instruction": instruction,
                    "action": "DISPATCH"
                }

                receipt = {
                    "command_id": command_id,
                    "project_id": target_project,
                    "conversation_id": target_conversation_id,
                    "created_at": datetime.now().isoformat(),
                    "dispatched_at": "",
                    "delivery_status": "PENDING",
                    "execution_status": "PENDING",
                    "result_received_at": "",
                    "error_details": ""
                }
                save_receipt(receipt)
                pending_commands[command_id] = command

                # Broadcast to extension (which runs in all tabs)
                for client in connected_clients:
                    try:
                        await client.send(json.dumps(command))
                    except websockets.exceptions.ConnectionClosed:
                        pass

            elif msg_type == "ACK":
                command_id = data.get("command_id")
                receipt = get_receipt(command_id)
                if receipt:
                    receipt["delivery_status"] = "DELIVERED"
                    receipt["dispatched_at"] = datetime.now().isoformat()
                    save_receipt(receipt)

            elif msg_type == "RESULT":
                command_id = data.get("command_id")
                result_text = data.get("result")
                receipt = get_receipt(command_id)
                if receipt:
                    if receipt["execution_status"] == "COMPLETED":
                        print("Loop guard: Result already processed.")
                        continue
                    receipt["execution_status"] = "COMPLETED"
                    receipt["result_received_at"] = datetime.now().isoformat()
                    save_receipt(receipt)

                    # Return result to GM
                    # We broadcast this, extension will pick it up if it's the GM tab
                    for client in connected_clients:
                        try:
                            await client.send(json.dumps({
                                "type": "GM_RESULT",
                                "command_id": command_id,
                                "project_id": receipt["project_id"],
                                "result": result_text
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            pass

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def main():
    init_db()
    print("Starting Orchestrator WebSocket server on ws://127.0.0.1:8799")
    # Bind to localhost (127.0.0.1) only for security to prevent external access
    async with websockets.serve(handler, "127.0.0.1", 8799):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
