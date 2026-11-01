# Project General Manager Integrator

This repository contains the local orchestration layer designed to link a central "General Manager" ChatGPT conversation to multiple specific project conversations (e.g., GitHub, Etsy) within the same browser, avoiding the need for paid APIs.

> [!WARNING]
> **Repository Visibility Alert**: This repository is currently set to **PUBLIC**.
> Please change it to **PRIVATE** in your GitHub repository settings before adding any sensitive data or specific project prompts. Never commit session tokens or personal IDs.

## Architecture

The system uses a combination of:
1.  **Local Python WebSocket Server (`orchestrator.py`)**: Acts as a lightweight command router and loop guard, saving execution receipts in a local SQLite database (`receipts.db`).
2.  **Custom Chrome Extension (Unpacked)**: A small script injected into `chatgpt.com` tabs that communicates with the local WebSocket server to read GM commands, execute them in target project tabs, and report results back.

## Setup Instructions

### 1. Python Server
1. Ensure Python 3.10+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the orchestrator server:
   ```bash
   python orchestrator.py
   ```
   *(The server runs securely bound to `127.0.0.1` on port `8799`)*

### 2. Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in the top right).
3. Click **Load unpacked** and select the `extension` folder located in this repository.

### 3. Project Configuration
1. Open `registry.json` in a text editor.
2. Replace `PLEASE_REPLACE_WITH_REAL_ID` with the actual Conversation IDs of your target ChatGPT projects. You can find this ID in the URL of the chat (e.g., `chatgpt.com/c/THIS-IS-THE-ID`).
3. Ensure the GM project ID is also correctly set.

## Usage

1. Start the Python server.
2. Open Chrome and ensure the extension is active.
3. Open your GM Chat and your Target Project Chats in separate tabs.
4. When the GM AI generates a JSON block containing commands (matching the `PROJECT_MANAGER_V1` protocol), the extension will capture it, send it through the local socket, and the target tab will automatically execute the instruction and return the result.

## Stopping the System

- Stop the Python server by pressing `Ctrl+C` in the terminal.
- The extension will automatically attempt to reconnect in the background and remain dormant until the server is restarted. If you wish to fully disable it, turn it off in `chrome://extensions/`.

## Running Tests

Run the automated test suite to verify the orchestration logic and loop prevention:
```bash
pytest test_orchestrator.py -v
```