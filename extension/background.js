// General Manager Project Integrator - Background Service Worker (Manifest V3)
console.log("[GM Integrator] Background Service Worker Loaded.");

// Set up periodic alarm to ensure the MV3 worker stays responsive if needed
chrome.runtime.onInstalled.addListener(() => {
  console.log("[GM Integrator] Extension installed/updated.");
  chrome.alarms.create("gm_keep_alive", { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "gm_keep_alive") {
    // Keep-alive pulse
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "PING") {
    sendResponse({ status: "PONG", timestamp: Date.now() });
  }
});
