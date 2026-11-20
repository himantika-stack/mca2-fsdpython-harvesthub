const rawBaseUrl = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/+$/, "");
export const API_ROOT = rawBaseUrl ? `${rawBaseUrl}/api` : "/api";

let inMemoryCsrfToken = "";
let csrfPromise = null;

export function cookie(name) {
  if (typeof document === "undefined") return "";
  return document.cookie.split("; ").find((row) => row.startsWith(`${name}=`))?.split("=")[1] || "";
}

export async function prepareCsrf() {
  if (!csrfPromise) {
    csrfPromise = fetch(`${API_ROOT}/auth/csrf/`, { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to initialize session (${response.status}).`);
        }
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await response.json().catch(() => ({}));
          if (data && data.csrfToken) {
            inMemoryCsrfToken = data.csrfToken;
          }
        }
      })
      .catch((err) => {
        csrfPromise = null; // Allow retry on subsequent attempts
        throw err;
      });
  }
  return csrfPromise;
}

export async function request(path, options = {}) {
  // Try to initialise CSRF token; if it fails (e.g. backend booting up or offline), continue to let fetch surface detailed error
  try {
    await prepareCsrf();
  } catch (e) {
    // Session token retrieval warning logged silently
  }

  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };

  const csrf = inMemoryCsrfToken || cookie("csrftoken");
  if (csrf) {
    headers["X-CSRFToken"] = csrf;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_ROOT}${normalizedPath}`, {
    credentials: "include",
    ...options,
    headers,
  });

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok || !isJson) {
    let detail = "The request could not be completed.";
    if (isJson && typeof payload === "object" && payload !== null) {
      detail = Object.entries(payload)
        .map(([key, val]) => {
          const valStr = Array.isArray(val) ? val.join(" ") : String(val);
          return key === "detail" || key === "non_field_errors" ? valStr : `${key}: ${valStr}`;
        })
        .join(" ");
    } else if (contentType.includes("text/html")) {
      detail = `API returned HTML instead of JSON (${response.status} ${response.statusText}). Check API URL configuration and backend status.`;
    } else if (typeof payload === "string" && payload.trim()) {
      detail = payload;
    }
    throw new Error(detail || "The request could not be completed.");
  }

  return payload;
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body: JSON.stringify(body) }),
  patch: (path, body) => request(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: (path, body) => request(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: "DELETE" }),
};
