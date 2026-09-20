(() => {
  const DEFAULT_SETTINGS = { enabled: true, whitelist: [] };
  const hostname = location.hostname;
  let settings = DEFAULT_SETTINGS;
  let ready = false;

  const AD_HIDE_SELECTORS = [
    "ins.adsbygoogle",
    "iframe[id^='google_ads_iframe']",
    "div[id^='div-gpt-ad']",
    "div[id^='google_ads_iframe']",
    "[id^='taboola-']",
    "[class*='taboola-']",
    "[id^='outbrain']",
    "[class*='outbrain']",
    "[class*='advertisement']",
    "[class*='ad-banner']",
    "[class*='ad-container']",
    "[class*='ad-wrapper']",
    "[class*='sponsored-content']",
    "[data-ad-slot]",
    "[data-google-query-id]",
    "ins[data-ad-client]",
    "iframe[src*='doubleclick.net']",
    "iframe[src*='googlesyndication.com']",
    "iframe[src*='amazon-adsystem.com']",
  ];

  function isWhitelisted() {
    return settings.whitelist.some(
      (domain) => hostname === domain || hostname.endsWith("." + domain)
    );
  }

  function reportBlocked(kind) {
    try {
      chrome.runtime.sendMessage({ type: "POPUP_BLOCKED", kind });
    } catch (e) {
      // Extension context may be invalidated during navigation; ignore.
    }
  }

  function injectCosmeticCss() {
    const style = document.createElement("style");
    style.id = "__evita_popups_cosmetic__";
    style.textContent = AD_HIDE_SELECTORS.join(",\n") + " { display: none !important; }";
    (document.head || document.documentElement).appendChild(style);
  }

  function removeCosmeticCss() {
    document.getElementById("__evita_popups_cosmetic__")?.remove();
  }

  function patchWindowOpen() {
    const nativeOpen = window.open;
    Object.defineProperty(window, "open", {
      configurable: true,
      writable: true,
      value: function patchedOpen(...args) {
        if (!settings.enabled || isWhitelisted()) {
          return nativeOpen.apply(window, args);
        }
        reportBlocked("popup");
        return null;
      },
    });
  }

  function patchNotificationSpam() {
    if (!("Notification" in window) || !Notification.requestPermission) return;
    const nativeRequest = Notification.requestPermission.bind(Notification);
    let lastGesture = 0;
    ["click", "keydown"].forEach((evt) =>
      document.addEventListener(evt, () => (lastGesture = Date.now()), {
        capture: true,
        passive: true,
      })
    );
    Notification.requestPermission = function patchedRequest(...args) {
      if (!settings.enabled || isWhitelisted()) {
        return nativeRequest(...args);
      }
      const withinGesture = Date.now() - lastGesture < 1500;
      if (withinGesture) {
        return nativeRequest(...args);
      }
      reportBlocked("notification");
      if (args[0]) {
        try {
          args[0]("denied");
        } catch (e) {
          /* ignore */
        }
      }
      return Promise.resolve("denied");
    };
  }

  function applySettings() {
    if (isWhitelisted() || !settings.enabled) {
      removeCosmeticCss();
    } else {
      injectCosmeticCss();
    }
  }

  function init(loadedSettings) {
    settings = { ...DEFAULT_SETTINGS, ...loadedSettings };
    ready = true;
    patchWindowOpen();
    patchNotificationSpam();
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", applySettings, { once: true });
    } else {
      applySettings();
    }
  }

  try {
    chrome.storage.sync.get(DEFAULT_SETTINGS, init);
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== "sync" || !ready) return;
      if (changes.enabled) settings.enabled = changes.enabled.newValue;
      if (changes.whitelist) settings.whitelist = changes.whitelist.newValue;
      applySettings();
    });
  } catch (e) {
    init(DEFAULT_SETTINGS);
  }
})();
