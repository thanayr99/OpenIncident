export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const AUTH_TOKEN_STORAGE_KEY = "openincident_auth_token";

function readStoredAuthToken() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getAuthToken() {
  return readStoredAuthToken();
}

export function setAuthToken(token) {
  if (typeof window === "undefined") return;
  if (!token) {
    clearAuthToken();
    return;
  }
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}

export async function apiRequest(path, options = {}) {
  const { skipAuth = false, headers: optionHeaders, ...requestOptions } = options;
  const authToken = skipAuth ? null : getAuthToken();
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(optionHeaders || {}),
      },
      ...requestOptions,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Unknown network error";
    throw new Error(
      `Cannot reach backend at ${API_BASE_URL}. Start the API server and verify ${API_BASE_URL}/health. ${detail}`,
    );
  }

  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    const detail = typeof data === "object" && data?.detail ? data.detail : text;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}
