const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  const text = await response.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }

  if (!response.ok) {
    const detail = data?.detail || data || `HTTP ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}

export const api = {
  projects: {
    list: () => request("/projects"),
    get: (id) => request(`/projects/${id}`),
    create: (payload) => request("/projects", { method: "POST", body: JSON.stringify(payload) }),
    update: (id, payload) => request(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    remove: (id) => request(`/projects/${id}`, { method: "DELETE" }),
  },
  conversations: {
    list: () => request("/conversations"),
    get: (id) => request(`/conversations/${id}`),
    create: (payload) => request("/conversations", { method: "POST", body: JSON.stringify(payload) }),
    update: (id, payload) => request(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  },
};

export { API_BASE_URL };
