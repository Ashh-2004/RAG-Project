export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (res.ok) {
      const data = await res.json();
      return data.status === 'healthy';
    }
    return false;
  } catch (err) {
    return false;
  }
}

export async function fetchEmployees() {
  try {
    const res = await fetch(`${API_BASE_URL}/employees`);
    if (res.ok) {
      const data = await res.json();
      return data.data || [];
    }
    return [];
  } catch (err) {
    console.error('Failed to fetch live employees:', err);
    return [];
  }
}

export async function sendChatMessage(prompt, empId, history = [], actorRole = 'EMPLOYEE') {
  const formattedHistory = history.map((msg) => ({
    role: msg.sender === 'user' ? 'user' : 'assistant',
    content: msg.text || ''
  }));

  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      prompt: prompt,
      emp_id: empId,
      actor_role: actorRole,
      history: formattedHistory,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Server error: ${response.status}`);
  }

  return await response.json();
}
