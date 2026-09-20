const DEFAULT_SETTINGS = { enabled: true, whitelist: [] };

function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => resolve(tabs[0]));
  });
}

async function init() {
  const tab = await getActiveTab();
  const hostname = tab?.url ? new URL(tab.url).hostname : "";
  document.getElementById("siteLabel").textContent = hostname || "este sitio";

  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  const enabledToggle = document.getElementById("enabledToggle");
  enabledToggle.checked = settings.enabled;

  const isWhitelisted = settings.whitelist.includes(hostname);
  const whitelistBtn = document.getElementById("whitelistBtn");
  whitelistBtn.textContent = isWhitelisted ? "Quitar de la lista blanca" : "Permitir en este sitio";

  enabledToggle.addEventListener("change", () => {
    chrome.storage.sync.set({ enabled: enabledToggle.checked });
  });

  whitelistBtn.addEventListener("click", async () => {
    const current = await chrome.storage.sync.get(DEFAULT_SETTINGS);
    let whitelist = current.whitelist;
    if (whitelist.includes(hostname)) {
      whitelist = whitelist.filter((d) => d !== hostname);
    } else if (hostname) {
      whitelist = [...whitelist, hostname];
    }
    await chrome.storage.sync.set({ whitelist });
    whitelistBtn.textContent = whitelist.includes(hostname)
      ? "Quitar de la lista blanca"
      : "Permitir en este sitio";
  });

  chrome.runtime.sendMessage({ type: "GET_ACTIVE_TAB_COUNT" }, (response) => {
    document.getElementById("siteCount").textContent = response?.count ?? 0;
  });

  chrome.storage.local.get({ totalBlocked: 0 }, ({ totalBlocked }) => {
    document.getElementById("totalCount").textContent = totalBlocked;
  });

  document.getElementById("optionsLink").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });
}

init();
