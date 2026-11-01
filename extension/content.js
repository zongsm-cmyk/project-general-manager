let ws = null;
const WS_URL = "ws://localhost:8765";

// Wait for the DOM to be ready
function connectWebSocket() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        console.log("Connected to GM Orchestrator WebSocket");
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Received from Orchestrator:", data);

        if (data.type === "EXECUTE") {
            handleExecuteCommand(data);
        } else if (data.type === "GM_RESULT") {
            handleGMResult(data);
        }
    };

    ws.onclose = () => {
        console.log("Disconnected from GM Orchestrator WebSocket. Reconnecting in 5s...");
        setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
    };
}

function getConversationIdFromUrl() {
    const match = window.location.pathname.match(/\/c\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : null;
}

// Function to find the chat input element (ProseMirror is often used by ChatGPT)
function getChatInput() {
    return document.querySelector('#prompt-textarea') || document.querySelector('div[contenteditable="true"]');
}

// Function to find the send button
function getSendButton() {
    return document.querySelector('button[data-testid="send-button"]') || document.querySelector('button[aria-label="Send message"]');
}

// Function to check if ChatGPT is currently generating a response
function isGenerating() {
    return document.querySelector('button[aria-label="Stop generating"]') !== null;
}

async function handleExecuteCommand(data) {
    const currentConvId = getConversationIdFromUrl();

    // 1. Verify this is the correct target conversation
    if (currentConvId !== data.target_conversation_id) {
        console.log(`Ignoring command ${data.command_id}. Target is ${data.target_conversation_id}, current is ${currentConvId}`);
        return;
    }

    console.log(`Executing command ${data.command_id} in conversation ${currentConvId}`);

    // 2. Acknowledge Receipt
    ws.send(JSON.stringify({
        type: "ACK",
        command_id: data.command_id
    }));

    // 3. Wait until not generating
    while (isGenerating()) {
        await new Promise(r => setTimeout(r, 1000));
    }

    // 4. Inject Instruction
    const inputField = getChatInput();
    if (!inputField) {
        console.error("Could not find chat input field");
        return;
    }

    // Simulate user typing (React/ProseMirror requires events)
    inputField.focus();
    document.execCommand('insertText', false, data.instruction);

    await new Promise(r => setTimeout(r, 500));

    // 5. Click Send
    const sendBtn = getSendButton();
    if (sendBtn) {
        sendBtn.click();
    } else {
        // Fallback: Dispatch Enter key
        inputField.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            which: 13,
            keyCode: 13,
            bubbles: true
        }));
    }

    // 6. Monitor for Completion and Capture Result
    // Wait for generation to start
    await new Promise(r => setTimeout(r, 2000));

    // Wait for generation to finish
    while (isGenerating()) {
        await new Promise(r => setTimeout(r, 1000));
    }

    // Give it a second to render final DOM
    await new Promise(r => setTimeout(r, 1000));

    // Capture the last assistant response
    const messages = document.querySelectorAll('div[data-message-author-role="assistant"]');
    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        const resultText = lastMessage.innerText;

        // Send back to Orchestrator
        ws.send(JSON.stringify({
            type: "RESULT",
            command_id: data.command_id,
            result: resultText
        }));
    } else {
        console.error("Could not find response message");
    }
}

async function handleGMResult(data) {
    const currentConvId = getConversationIdFromUrl();
    if (currentConvId !== "6ae6dd41-105c-83e9-90ac-378e51c5e5af") {
        return;
    }

    console.log(`[GM RESULT] Project ${data.project_id} completed command ${data.command_id}: ${data.result}`);

    // Inject the result as a new prompt to the GM AI so it has the context
    while (isGenerating()) {
        await new Promise(r => setTimeout(r, 1000));
    }

    const inputField = getChatInput();
    if (!inputField) return;

    const reportText = `[SYSTEM REPORT - DO NOT EXECUTE - JUST ACKNOWLEDGE AND SUMMARIZE]\nResult from ${data.project_id}:\n${data.result}`;

    inputField.focus();
    document.execCommand('insertText', false, reportText);

    await new Promise(r => setTimeout(r, 500));
    const sendBtn = getSendButton();
    if (sendBtn) {
        sendBtn.click();
    } else {
        inputField.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', which: 13, keyCode: 13, bubbles: true }));
    }
}

const processedMessageIds = new Set();
let isFirstRun = true;

async function monitorGMCommands() {
    const currentConvId = getConversationIdFromUrl();
    if (currentConvId !== "6ae6dd41-105c-83e9-90ac-378e51c5e5af") {
        return;
    }

    // Monitor for ASSISTANT messages matching a JSON protocol output
    setInterval(() => {
        if (isGenerating()) return; // Wait for it to finish generating

        const messages = document.querySelectorAll('div[data-message-author-role="assistant"]');
        if (messages.length === 0) return;

        // If first run on page load, just mark everything as processed so we don't replay history
        if (isFirstRun) {
            for (const msg of messages) {
                const messageId = msg.getAttribute('data-message-id') || msg.innerText.substring(0, 50);
                processedMessageIds.add(messageId);
            }
            isFirstRun = false;
            return;
        }

        // Process only truly new messages
        for (const msg of messages) {
            const messageId = msg.getAttribute('data-message-id') || msg.innerText.substring(0, 50);

            if (processedMessageIds.has(messageId)) continue;
            processedMessageIds.add(messageId);

            const msgText = msg.innerText;

            // GM AI is instructed to output commands in a specific code block format:
            // ```json
            // { "protocol": "PROJECT_MANAGER_V1", "commands": [ { "target_project": "GITHUB", "instruction": "..." } ] }
            // ```
            try {
                const match = msgText.match(/```json\s*(\{.*"protocol":\s*"PROJECT_MANAGER_V1".*?\})\s*```/s);
                if (match) {
                    const parsed = JSON.parse(match[1]);
                    if (parsed.commands && Array.isArray(parsed.commands)) {
                        for (const cmd of parsed.commands) {
                            console.log(`Dispatching parsed GM command to ${cmd.target_project}: ${cmd.instruction}`);
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                ws.send(JSON.stringify({
                                    type: "COMMAND_DISPATCH",
                                    target_project: cmd.target_project,
                                    instruction: cmd.instruction
                                }));
                            }
                        }
                    }
                }
            } catch (e) {
                console.error("Failed to parse GM command JSON", e);
            }
        }
    }, 2000);
}

// Start connection and monitor
connectWebSocket();
monitorGMCommands();
