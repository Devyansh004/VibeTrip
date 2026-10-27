/**
 * VibeTrip Agent - Saved Trips Management
 */

document.addEventListener('DOMContentLoaded', async () => {
  await loadSavedTrips();
});

let tripToDelete = null;

async function loadSavedTrips() {
  const container = document.getElementById('savedTripsContainer');
  const emptyState = document.getElementById('emptyState');
  const statusNotice = document.getElementById('savedTripsNotice');
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 48px; color: var(--color-text-muted);">
      <div class="loading-spinner-ring" style="width: 40px; height: 40px; margin: 0 auto 16px; position: static;"></div>
      <p>Loading your saved journeys...</p>
    </div>
  `;

  let trips = [];

  // Read saved trips from localStorage
  try {
    const local = localStorage.getItem('vibetrip_guest_trips');
    if (local) {
      const parsed = JSON.parse(local);
      trips = Array.isArray(parsed) ? parsed.filter(t => t && typeof t === 'object') : [];
    }
  } catch (e) {
    console.warn('Error reading trips from localStorage:', e);
    trips = [];
  }

  if (statusNotice) {
    statusNotice.innerHTML = `
      <span class="integration-pill success">
        Personal Collection (${trips.length} saved)
      </span>
    `;
  }

  if (!trips || trips.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = trips.map(trip => `
    <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
      <div>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="place-category">${trip.duration_days} Days</span>
          <span style="font-size: 0.78rem; color: var(--color-text-muted);">
            ${trip.created_at ? new Date(trip.created_at).toLocaleDateString() : 'Recent'}
          </span>
        </div>
        <h3 style="font-family: var(--font-serif); font-size: 1.5rem; color: var(--color-text); margin-bottom: 8px;">
          ${window.escapeHtml(trip.title || `${trip.destination} Vibe Trip`)}
        </h3>
        <p style="color: var(--color-text-secondary); font-size: 0.9rem; margin-bottom: 16px;">
          📍 ${window.escapeHtml(trip.destination)}
        </p>
        ${trip.budget ? `
          <p style="font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 20px;">
            Estimated Budget: <strong>${trip.currency || 'USD'} ${trip.budget}</strong>
          </p>
        ` : ''}
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 16px; border-top: 1px solid var(--color-border-subtle);">
        <a href="trip-details.html?id=${trip.id}" class="btn btn-primary btn-sm">
          View Itinerary →
        </a>
        <button class="btn btn-outline btn-sm delete-btn" data-id="${trip.id}" data-title="${window.escapeHtml(trip.title || trip.destination)}" style="color: var(--color-error);">
          Delete
        </button>
      </div>
    </div>
  `).join('');

  // Attach delete modal handlers
  document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      tripToDelete = {
        id: btn.dataset.id,
        title: btn.dataset.title,
      };
      document.getElementById('deleteTripTitle').textContent = `"${tripToDelete.title}"`;
      window.openModal('deleteModal');
    });
  });
}

// Delete confirmation handling
document.addEventListener('DOMContentLoaded', () => {
  const confirmBtn = document.getElementById('confirmDeleteBtn');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', async () => {
      if (!tripToDelete) return;

      try {
        // Remove from local storage
        const local = JSON.parse(localStorage.getItem('vibetrip_guest_trips') || '[]');
        const updated = local.filter(t => t.id !== tripToDelete.id);
        localStorage.setItem('vibetrip_guest_trips', JSON.stringify(updated));

        window.closeModal('deleteModal');
        window.showToast('Trip deleted successfully.', 'info');
        tripToDelete = null;
        await loadSavedTrips();
      } catch (err) {
        console.error('Delete failed:', err);
        window.showToast(err.message || 'Failed to delete trip', 'error');
      }
    });
  }
});
