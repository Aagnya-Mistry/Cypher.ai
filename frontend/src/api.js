const API_BASE_URL = 'http://localhost:8000/api/v1';

export async function uploadComplianceReport(file, apiKey) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/agent1/process`, {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
    },
    body: formData,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Upload failed');
  }

  return response.json();
}

export async function getAgent2Domains(apiKey) {
  const response = await fetch(`${API_BASE_URL}/agent2/domains`, {
    headers: {
      'x-api-key': apiKey,
    },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Failed to load domains');
  }

  return response.json();
}

export async function runAgent2Chat(payload, apiKey) {
  const response = await fetch(`${API_BASE_URL}/agent2/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Agent 2 request failed');
  }

  return response.json();
}

export async function scoreAgent3Domain(payload, apiKey) {
  const response = await fetch(`${API_BASE_URL}/agent3/score-domain`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Agent 3 domain scoring failed');
  }

  return response.json();
}

export async function getAgent3Report(reportName, apiKey) {
  const query = new URLSearchParams({ report_name: reportName });
  const response = await fetch(`${API_BASE_URL}/agent3/report?${query.toString()}`, {
    headers: {
      'x-api-key': apiKey,
    },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Agent 3 report generation failed');
  }

  return response.json();
}

export async function downloadAgent3ReportExcel(reportName, apiKey) {
  const query = new URLSearchParams({ report_name: reportName });
  const response = await fetch(`${API_BASE_URL}/agent3/report/excel?${query.toString()}`, {
    headers: {
      'x-api-key': apiKey,
    },
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || 'Agent 3 Excel download failed');
  }

  return response.blob();
}
