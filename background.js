const RULESET_ID = "ad_rules";
const DEFAULT_SETTINGS = { enabled: true, whitelist: [] };
const tabBlockCounts = new Map();

async function getSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

async function applyRulesetState(settings) {
  await chrome.declarativeNetRequest.updateEnabledRulesets({
    enableRulesetIds: settings.enabled ? [RULESET_ID] : [],
    disableRulesetIds: settings.enabled ? [] : [RULESET_ID],
  });
  await rebuildAllowRules(settings.whitelist);
}

async function rebuildAllowRules(whitelist) {
  const existing = await chrome.declarativeNetRequest.getSessionRules();
  const removeRuleIds = existing.map((rule) => rule.id);
  const addRules = whitelist.map((domain, index) => ({
    id: 1000 + index,
    priority: 100,
    action: { type: "allow" },
    condition: {
      requestDomains: [domain],
      resourceTypes: [
        "main_frame", "sub_frame", "script", "image", "xmlhttprequest",
        "media", "websocket", "other",
      ],
    },
  }));
  await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds, addRules });
}

function setBadge(tabId, count) {
  chrome.action.setBadgeText({ tabId, text: count > 0 ? String(count) : "" });
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#3d5afe" });
}

chrome.runtime.onInstalled.addListener(async () => {
  const settings = await getSettings();
  await applyRulesetState(settings);
});

chrome.runtime.onStartup.addListener(async () => {
  const settings = await getSettings();
  await applyRulesetState(settings);
});

chrome.storage.onChanged.addListener(async (changes, area) => {
  if (area !== "sync") return;
  if (changes.enabled || changes.whitelist) {
    const settings = await getSettings();
    await applyRulesetState(settings);
  }
});

chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) {
    tabBlockCounts.set(details.tabId, 0);
    setBadge(details.tabId, 0);
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabBlockCounts.delete(tabId);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "POPUP_BLOCKED" && sender.tab?.id != null) {
    const tabId = sender.tab.id;
    const current = (tabBlockCounts.get(tabId) || 0) + 1;
    tabBlockCounts.set(tabId, current);
    setBadge(tabId, current);
    chrome.storage.local.get({ totalBlocked: 0 }, ({ totalBlocked }) => {
      chrome.storage.local.set({ totalBlocked: totalBlocked + 1 });
    });
  }
  if (message?.type === "GET_TAB_COUNT" && sender.tab?.id != null) {
    sendResponse({ count: tabBlockCounts.get(sender.tab.id) || 0 });
  }
  if (message?.type === "GET_ACTIVE_TAB_COUNT") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tabId = tabs[0]?.id;
      sendResponse({ count: tabId != null ? tabBlockCounts.get(tabId) || 0 : 0, tabId });
    });
    return true;
  }
  return undefined;
});
