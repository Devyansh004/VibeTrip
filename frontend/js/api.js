/**
 * VibeTrip Agent - Backend API Client
 */

const API_BASE = (() => {
  const isDirectFastAPI = window.location.port === '8000';

  if (isDirectFastAPI && window.location.origin && window.location.origin !== 'null') {
    return window.location.origin;
  }

  // Use deployed Render backend for the Vercel frontend
  return 'https://vibetrip-0o8v.onrender.com';
})();


class VibeTripAPI {
  constructor() {
    this.baseUrl = API_BASE;
  }

  getHeaders() {
    return {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...(options.headers || {}),
      },
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        const errorMsg = data?.error?.message || data?.detail || `API request failed (${response.status})`;
        const error = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'} ${endpoint}]:`, err);
      throw err;
    }
  }

  async getHealth() {
    return this.request('/api/health');
  }

  async planTrip(payload) {
    return this.request('/api/plan', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async personalizeTrip(payload) {
    return this.request('/api/plan/personalize', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async searchPlaces(searchParams) {
    return this.request('/api/places/search', {
      method: 'POST',
      body: JSON.stringify(searchParams),
    });
  }
}

window.api = new VibeTripAPI();
