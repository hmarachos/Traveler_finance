/**
 * Application state management
 */

export const state = {
  tripId: Number(localStorage.getItem("travelerFinanceTripId")) || null,
  trip: null,
  trips: [],
  families: [],
  summary: null,
  journal: [],
};

/**
 * Update state and persist to localStorage if needed
 */
export function updateState(updates) {
  Object.assign(state, updates);
  
  if (updates.tripId) {
    localStorage.setItem("travelerFinanceTripId", updates.tripId);
  }
}

/**
 * Clear trip-specific state
 */
export function clearTripState() {
  state.trip = null;
  state.families = [];
  state.summary = null;
}
