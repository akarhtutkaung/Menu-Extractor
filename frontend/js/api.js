import { API_BASE } from "./config.js";

/**
 * Sends a PDF file to the backend extraction API.
 *
 * @param {File} file
 * @returns {Promise<object>} Parsed MenuResponse JSON
 * @throws {Error} with a user-facing message on failure
 */
export async function extractMenu(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/extract`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let message = `Server error (${response.status})`;
    try {
      const body = await response.json();
      if (body && body.message) {
        message = body.message;
      }
    } catch {
      // ignore JSON parse errors — keep the default message
    }
    throw new Error(message);
  }

  return response.json();
}
