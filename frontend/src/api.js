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


async function streamRequest(path, payload, onChunk) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const data = text ? JSON.parse(text) : null;
      detail = data?.detail || data || detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (!response.body) throw new Error("Streaming não suportado pelo navegador.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const consume = async (value, done) => {
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      const lines = event.split("\n");
      let eventName = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) eventName = line.slice(7);
        if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (eventName === "error") throw new Error(data || "Erro durante o streaming.");
      if (data === "[DONE]") return true;
      if (data) {
        let chunk = data;
        try { chunk = JSON.parse(data); } catch {}
        onChunk(String(chunk));
      }
    }
    return false;
  };

  while (true) {
    const { value, done } = await reader.read();
    const finished = await consume(value, done);
    if (finished || done) break;
  }
}

export const api = {
  models: {
    list: () => request("/models"),
    get: (id) => request(`/models/${id}`),
    create: (payload) => request("/models", { method: "POST", body: JSON.stringify(payload) }),
  },
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
    messages: (id) => request(`/conversations/${id}/messages`),
    chat: (id, content) => request(`/conversations/${id}/chat`, { method: "POST", body: JSON.stringify({ content }) }),
    stream: (id, content, onChunk) => streamRequest(`/conversations/${id}/chat/stream`, { content }, onChunk),
  },
  memories: {
    list: (projectId) => request(`/memories?project_id=${projectId}`),
    create: (payload) => request("/memories", { method: "POST", body: JSON.stringify(payload) }),
    update: (id, payload) => request(`/memories/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
    remove: (id) => request(`/memories/${id}`, { method: "DELETE" }),
  },
};

export { API_BASE_URL };
