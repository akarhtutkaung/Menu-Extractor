import { extractMenu } from "./api.js";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Initialise upload interactions.
 *
 * @param {(data: object) => void} onSuccess   called with parsed MenuResponse
 * @param {(message: string) => void} onError  called with an error message string
 * @param {() => void} onLoading               called when extraction starts
 */
export function initUploader(onSuccess, onError, onLoading) {
  const fileInput = document.getElementById("file-input");
  const dropZone = document.getElementById("drop-zone");
  const uploadError = document.getElementById("upload-error");

  function showInlineError(message) {
    uploadError.textContent = message;
    uploadError.hidden = false;
  }

  function clearInlineError() {
    uploadError.textContent = "";
    uploadError.hidden = true;
  }

  const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/jpg", "image/png"]);
  const ALLOWED_EXTENSIONS = /\.(pdf|jpg|jpeg|png)$/i;

  function validateFile(file) {
    if (!file) return "No file selected.";
    if (!ALLOWED_TYPES.has(file.type) && !ALLOWED_EXTENSIONS.test(file.name)) {
      return "Only PDF, JPG, and PNG files are supported.";
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum size is 10 MB.`;
    }
    return null;
  }

  async function handleFile(file) {
    clearInlineError();

    const validationError = validateFile(file);
    if (validationError) {
      showInlineError(validationError);
      return;
    }

    onLoading();

    try {
      const data = await extractMenu(file);
      onSuccess(data);
    } catch (err) {
      onError(err.message || "An unexpected error occurred.");
    }
  }

  // File input change
  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (file) {
      handleFile(file);
      // Reset so the same file can be resubmitted after an error
      fileInput.value = "";
    }
  });

  // Keyboard activation of the drop zone
  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  // Drag-and-drop
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", (e) => {
    if (!dropZone.contains(e.relatedTarget)) {
      dropZone.classList.remove("drag-over");
    }
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFile(file);
  });
}
