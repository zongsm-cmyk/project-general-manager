// Background service worker for extension
console.log("GM Integrator Background Service Worker Loaded.");

// The background worker could handle WebSocket connection persistence,
// but for simplicity in this implementation, we handle it directly in the content script
// because content scripts are directly tied to the specific chat tabs we want to monitor.
// However, a robust implementation might use the background script to maintain a single
// websocket connection and route messages to specific tabs via chrome.tabs.sendMessage.

// For now, this is a placeholder to satisfy manifest requirements and allow future scaling.
chrome.runtime.onInstalled.addListener(() => {
  console.log("GM Integrator installed.");
});
