const API_BASE = '/api';

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return await res.json();
  } catch (err) {
    return { status: 'error', message: err.message };
  }
}

export async function ingestDocument(file, concepts) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('concepts', concepts);

  const res = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Document ingestion failed');
  }
  return data;
}

export async function generateQuestionPaper(payload) {
  const res = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || 'Question paper generation failed');
  }
  return data;
}
