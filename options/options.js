const DEFAULT_SETTINGS = { enabled: true, whitelist: [] };

function normalizeDomain(input) {
  return input
    .trim()
    .replace(/^https?:\/\//, "")
    .replace(/\/.*$/, "")
    .toLowerCase();
}

function renderWhitelist(whitelist) {
  const list = document.getElementById("whitelistItems");
  list.innerHTML = "";
  whitelist.forEach((domain) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = domain;
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "Quitar";
    removeBtn.className = "remove";
    removeBtn.addEventListener("click", async () => {
      const current = await chrome.storage.sync.get(DEFAULT_SETTINGS);
      const updated = current.whitelist.filter((d) => d !== domain);
      await chrome.storage.sync.set({ whitelist: updated });
      renderWhitelist(updated);
    });
    li.append(span, removeBtn);
    list.appendChild(li);
  });
}

async function init() {
  const settings = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  document.getElementById("enabledToggle").checked = settings.enabled;
  renderWhitelist(settings.whitelist);

  document.getElementById("enabledToggle").addEventListener("change", (e) => {
    chrome.storage.sync.set({ enabled: e.target.checked });
  });

  document.getElementById("addDomain").addEventListener("click", async () => {
    const input = document.getElementById("domainInput");
    const domain = normalizeDomain(input.value);
    if (!domain) return;
    const current = await chrome.storage.sync.get(DEFAULT_SETTINGS);
    if (!current.whitelist.includes(domain)) {
      const updated = [...current.whitelist, domain];
      await chrome.storage.sync.set({ whitelist: updated });
      renderWhitelist(updated);
    }
    input.value = "";
  });
}

init();
