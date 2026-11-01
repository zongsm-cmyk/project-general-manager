/**
 * General Manager Project Integrator - Content Script
 * Injected into chatgpt.com tabs to bridge the General Manager conversation
 * with individual project conversations over a local WebSocket orchestrator.
 */

let ws = null;
const WS_URL = "ws://127.0.0.1:8799";
let gmConversationId = "6ae6dd41-105c-83e9-90ac-378e51c5e5af";

let reconnectDelay = 2000;
const MAX_RECONNECT_DELAY = 15000;
let isReconnecting = false;

function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        return;
    }

    try {
        ws = new WebSocket(WS_URL);
    } catch (e) {
        console.warn("[GM Integrator] WebSocket creation failed:", e);
        scheduleReconnect();
        return;
    }

    ws.onopen = () => {
        console.log("[GM Integrator] Connected to Orchestrator at " + WS_URL);
        reconnectDelay = 2000;
        isReconnecting = false;
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "CONFIG") {
                if (data.gm_conversation_id) {
                    gmConversationId = data.gm_conversation_id;
                }
            } else if (data.type === "EXECUTE") {
                handleExecuteCommand(data);
            } else if (data.type === "GM_RESULT") {
                handleGMResult(data);
            }
        } catch (err) {
            console.error("[GM Integrator] Error processing message from orchestrator:", err);
        }
    };

    ws.onclose = () => {
        scheduleReconnect();
    };

    ws.onerror = () => {
        // Handled in onclose
    };
}

function scheduleReconnect() {
    if (isReconnecting) return;
    isReconnecting = true;
    setTimeout(() => {
        isReconnecting = false;
        reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
        connectWebSocket();
    }, reconnectDelay);
}

function sendToOrchestrator(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(payload));
        return true;
    }
    return false;
}

function getConversationIdFromUrl() {
    const match = window.location.pathname.match(/\/c\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : null;
}

function getChatInput() {
    return document.querySelector('#prompt-textarea') ||
           document.querySelector('div[contenteditable="true"]') ||
           document.querySelector('textarea[data-id="root"]') ||
           document.querySelector('textarea');
}

function getSendButton() {
    return document.querySelector('button[data-testid="send-button"]') ||
           document.querySelector('button[aria-label="Send message"]') ||
           document.querySelector('button[aria-label="Send prompt"]') ||
           document.querySelector('button[data-testid="fruitjuice-send-button"]');
}

function isGenerating() {
    return document.querySelector('button[aria-label="Stop generating"]') !== null ||
           document.querySelector('button[data-testid="stop-button"]') !== null;
}

async function injectText(inputField, text) {
    inputField.focus();

    if (inputField.tagName === 'TEXTAREA') {
        inputField.value = text;
        inputField.dispatchEvent(new Event('input', { bubbles: true }));
        inputField.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
        // Contenteditable (ProseMirror)
        let inserted = false;
        try {
            inserted = document.execCommand('insertText', false, text);
        } catch (e) {
            inserted = false;
        }

        if (!inserted || !inputField.innerText.trim()) {
            inputField.textContent = text;
            inputField.dispatchEvent(new InputEvent('input', { bubbles: true }));
        }
    }
}

async function handleExecuteCommand(data) {
    const currentConvId = getConversationIdFromUrl();

    // 1. Verify target conversation ID match
    if (!currentConvId || currentConvId !== data.target_conversation_id) {
        return;
    }

    console.log(`[GM Integrator] Received command ${data.command_id} for this project tab.`);

    // 2. Acknowledge Receipt immediately
    sendToOrchestrator({
        type: "ACK",
        command_id: data.command_id
    });

    // 3. Wait until ChatGPT is idle (max 60 seconds)
    const startIdleWait = Date.now();
    while (isGenerating()) {
        if (Date.now() - startIdleWait > 60000) {
            sendToOrchestrator({
                type: "ERROR",
                command_id: data.command_id,
                error: "Timeout waiting for previous generation to finish."
            });
            return;
        }
        await new Promise(r => setTimeout(r, 1000));
    }

    // 4. Find Input Field
    const inputField = getChatInput();
    if (!inputField) {
        console.error("[GM Integrator] Could not locate chat input element.");
        sendToOrchestrator({
            type: "ERROR",
            command_id: data.command_id,
            error: "Chat input field not found in DOM."
        });
        return;
    }

    // 5. Inject Instruction
    await injectText(inputField, data.instruction);
    await new Promise(r => setTimeout(r, 500));

    // 6. Click Send Button or dispatch Enter
    const sendBtn = getSendButton();
    if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
    } else {
        inputField.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter',
            code: 'Enter',
            which: 13,
            keyCode: 13,
            bubbles: true
        }));
    }

    // 7. Wait for generation to start (up to 10 seconds)
    let genStarted = false;
    for (let i = 0; i < 20; i++) {
        await new Promise(r => setTimeout(r, 500));
        if (isGenerating()) {
            genStarted = true;
            break;
        }
    }

    // 8. Wait for generation to finish (up to 180 seconds)
    const startGenWait = Date.now();
    while (isGenerating()) {
        if (Date.now() - startGenWait > 180000) {
            sendToOrchestrator({
                type: "ERROR",
                command_id: data.command_id,
                error: "Timeout waiting for model response generation."
            });
            return;
        }
        await new Promise(r => setTimeout(r, 1000));
    }

    // Settle DOM
    await new Promise(r => setTimeout(r, 1000));

    // 9. Capture Assistant Response
    const messages = document.querySelectorAll('div[data-message-author-role="assistant"]');
    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        const resultText = lastMessage.innerText.trim();

        sendToOrchestrator({
            type: "RESULT",
            command_id: data.command_id,
            result: resultText
        });
        console.log(`[GM Integrator] Sent RESULT for command ${data.command_id}.`);
    } else {
        sendToOrchestrator({
            type: "ERROR",
            command_id: data.command_id,
            error: "Assistant message element not found after generation."
        });
    }
}

async function handleGMResult(data) {
    const currentConvId = getConversationIdFromUrl();
    if (currentConvId !== gmConversationId) {
        return;
    }

    console.log(`[GM Integrator] Returning result from ${data.project_id} to General Manager.`);

    // Wait until GM tab is idle
    while (isGenerating()) {
        await new Promise(r => setTimeout(r, 1000));
    }

    const inputField = getChatInput();
    if (!inputField) return;

    const reportText = `[SYSTEM REPORT - DO NOT EXECUTE - JUST ACKNOWLEDGE AND SUMMARIZE]\n` +
                       `Result from project ${data.project_id} (Command ${data.command_id}):\n` +
                       `${data.result}`;

    await injectText(inputField, reportText);
    await new Promise(r => setTimeout(r, 500));

    const sendBtn = getSendButton();
    if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
    } else {
        inputField.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', which: 13, keyCode: 13, bubbles: true }));
    }
}

const processedMessageIds = new Set();
let isFirstRun = true;

function monitorGMCommands() {
    setInterval(() => {
        const currentConvId = getConversationIdFromUrl();
        if (currentConvId !== gmConversationId) {
            return;
        }

        if (isGenerating()) return;

        const messages = document.querySelectorAll('div[data-message-author-role="assistant"]');
        if (messages.length === 0) return;

        // Skip history on first run
        if (isFirstRun) {
            for (const msg of messages) {
                const messageId = msg.getAttribute('data-message-id') || msg.innerText.substring(0, 50);
                processedMessageIds.add(messageId);
            }
            isFirstRun = false;
            return;
        }

        for (const msg of messages) {
            const messageId = msg.getAttribute('data-message-id') || msg.innerText.substring(0, 50);
            if (processedMessageIds.has(messageId)) continue;
            processedMessageIds.add(messageId);

            const msgText = msg.innerText;

            // Loop Guard: Ignore system reports
            if (msgText.includes("[SYSTEM REPORT - DO NOT EXECUTE")) {
                continue;
            }

            // Protocol Matcher: Matches JSON code blocks or direct JSON with protocol PROJECT_MANAGER_V1
            try {
                let jsonStr = null;
                const codeBlockMatch = msgText.match(/```(?:json)?\s*(\{[\s\S]*?"protocol":\s*"PROJECT_MANAGER_V1"[\s\S]*?\})\s*```/);
                if (codeBlockMatch) {
                    jsonStr = codeBlockMatch[1];
                } else {
                    const rawJsonMatch = msgText.match(/(\{[\s\S]*?"protocol":\s*"PROJECT_MANAGER_V1"[\s\S]*?\})/);
                    if (rawJsonMatch) {
                        jsonStr = rawJsonMatch[1];
                    }
                }

                if (jsonStr) {
                    const parsed = JSON.parse(jsonStr);
                    // Format A: { protocol: "PROJECT_MANAGER_V1", commands: [ { target_project, instruction } ] }
                    if (Array.isArray(parsed.commands)) {
                        for (const cmd of parsed.commands) {
                            if (cmd.target_project && cmd.instruction) {
                                sendToOrchestrator({
                                    type: "COMMAND_DISPATCH",
                                    target_project: cmd.target_project,
                                    instruction: cmd.instruction
                                });
                            }
                        }
                    }
                    // Format B: { protocol: "PROJECT_MANAGER_V1", target_project: "...", instruction: "..." }
                    else if (parsed.target_project && parsed.instruction) {
                        sendToOrchestrator({
                            type: "COMMAND_DISPATCH",
                            target_project: parsed.target_project,
                            instruction: parsed.instruction
                        });
                    }
                }
            } catch (err) {
                console.warn("[GM Integrator] Failed to parse command block:", err);
            }
        }
    }, 2000);
}

// Initialize
connectWebSocket();
monitorGMCommands();
