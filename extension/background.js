// Background service worker for extension
console.log("GM Integrator Background Service Worker Loaded.");

// Background workers in Manifest V3 can become inactive. We set up an alarm
// to ensure the service worker stays alive if needed for future central connection management.
chrome.runtime.onInstalled.addListener(() => {
  console.log("GM Integrator installed.");
  chrome.alarms.create("keepAlive", { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "keepAlive") {
    console.debug("GM Integrator: Service Worker Keep-Alive");
  }
});

// Future-proofing: We can use the background script to relay messages
// if we move the WebSocket connection out of the content scripts.
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "PING") {
        sendResponse({status: "PONG"});
    }
});
