const API_ROOT = "/api";
let csrfReady;

function cookie(name) {
  return document.cookie.split("; ").find((row) => row.startsWith(`${name}=`))?.split("=")[1] || "";
}

async function prepareCsrf() {
  if (!csrfReady) {
    csrfReady = fetch(`${API_ROOT}/auth/csrf/`, { credentials: "include" }).then((response) => {
      if (!response.ok) throw new Error("Could not initialise secure session.");
    });
  }
  return csrfReady;
}

export async function request(path, options = {}) {
  await prepareCsrf();
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers };
  const csrf = cookie("csrftoken");
  if (csrf) headers["X-CSRFToken"] = csrf;
  const response = await fetch(`${API_ROOT}${path}`, { credentials: "include", ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object"
      ? Object.values(payload).flat().join(" ")
      : contentType.includes("text/html")
        ? "The server could not complete this request. Check the backend terminal for details."
        : payload;
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
