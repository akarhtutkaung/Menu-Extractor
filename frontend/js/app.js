import { initUploader } from "./uploader.js";
import {
  renderLoading,
  renderError,
  renderMenu,
  renderEmpty,
  clearResult,
} from "./renderer.js";

// Holds the most recent successful MenuResponse for copy/download actions
let _lastMenuData = null;

function onLoading() {
  clearResult();
  renderLoading();
}

function onSuccess(data) {
  _lastMenuData = data;
  const hasItems =
    data.categories &&
    data.categories.some((c) => c.items && c.items.length > 0);

  if (!hasItems) {
    renderEmpty();
  } else {
    renderMenu(data);
  }
}

function onError(message) {
  renderError(message, resetToIdle);
}

function resetToIdle() {
  _lastMenuData = null;
  clearResult();
  // Re-focus the drop zone so keyboard users can continue
  const dropZone = document.getElementById("drop-zone");
  if (dropZone) dropZone.focus();
}

// Copy JSON to clipboard
document.getElementById("copy-btn").addEventListener("click", async () => {
  if (!_lastMenuData) return;
  const json = JSON.stringify(_lastMenuData, null, 2);
  try {
    await navigator.clipboard.writeText(json);
    const btn = document.getElementById("copy-btn");
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => {
      btn.textContent = original;
    }, 1800);
  } catch {
    // Clipboard API unavailable — silently ignore
  }
});

// Download JSON file
document.getElementById("download-btn").addEventListener("click", () => {
  if (!_lastMenuData) return;
  const json = JSON.stringify(_lastMenuData, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const name = _lastMenuData.restaurant_name
    ? _lastMenuData.restaurant_name.replace(/[^a-z0-9]/gi, "_").toLowerCase()
    : "menu";
  a.download = `${name}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// New upload button
document.getElementById("new-upload-btn").addEventListener("click", resetToIdle);

// Initialise uploader last (depends on DOM above being wired)
initUploader(onSuccess, onError, onLoading);
