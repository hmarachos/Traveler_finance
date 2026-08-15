/**
 * API communication module
 */

import { state } from "./state.js";

/**
 * Make API request
 */
export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  
  const payload = await response.json();
  
  if (!response.ok) {
    throw new Error(payload.error || "Ошибка запроса");
  }
  
  return payload;
}

/**
 * Fetch all trips
 */
export function getTrips() {
  return api("/api/trips").then(p => p.trips);
}

/**
 * Fetch single trip
 */
export function getTrip(tripId) {
  return api(`/api/trips/${tripId}`).then(p => p.trip);
}

/**
 * Create new trip
 */
export function createTrip(data) {
  return api("/api/trips", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Update trip
 */
export function updateTrip(tripId, data) {
  return api(`/api/trips/${tripId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Delete trip
 */
export function deleteTrip(tripId) {
  return api(`/api/trips/${tripId}`, { method: "DELETE" });
}

/**
 * Get trip summary
 */
export function getTripSummary(tripId) {
  return api(`/api/trips/${tripId}/summary`);
}

/**
 * Get expense categories
 */
export function getCategories() {
  return api(`/api/trips/${state.tripId}/categories`).then(p => p.categories);
}

/**
 * Get families for trip
 */
export function getFamilies(tripId) {
  return api(`/api/trips/${tripId}/families`).then(p => p.families);
}

/**
 * Create family
 */
export function createFamily(tripId, data) {
  return api(`/api/trips/${tripId}/families`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Update family
 */
export function updateFamily(tripId, familyId, data) {
  return api(`/api/trips/${tripId}/families/${familyId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Delete family
 */
export function deleteFamily(tripId, familyId) {
  return api(`/api/trips/${tripId}/families/${familyId}`, {
    method: "DELETE",
  });
}

/**
 * Create expense
 */
export function createExpense(tripId, data) {
  return api(`/api/trips/${tripId}/expenses`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete expense
 */
export function deleteExpense(tripId, expenseId) {
  return api(`/api/trips/${tripId}/expenses/${expenseId}`, {
    method: "DELETE",
  });
}

/**
 * Update expense
 */
export function updateExpense(tripId, expenseId, data) {
  return api(`/api/trips/${tripId}/expenses/${expenseId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Create transfer
 */
export function createTransfer(tripId, data) {
  return api(`/api/trips/${tripId}/transfers`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete transfer
 */
export function deleteTransfer(tripId, transferId) {
  return api(`/api/trips/${tripId}/transfers/${transferId}`, {
    method: "DELETE",
  });
}

/**
 * Update transfer
 */
export function updateTransfer(tripId, transferId, data) {
  return api(`/api/trips/${tripId}/transfers/${transferId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Get loans for trip
 */
export function getLoans(tripId) {
  return api(`/api/trips/${tripId}/loans`).then(p => p.loans);
}

/**
 * Create loan
 */
export function createLoan(tripId, data) {
  return api(`/api/trips/${tripId}/loans`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete loan
 */
export function deleteLoan(tripId, loanId) {
  return api(`/api/trips/${tripId}/loans/${loanId}`, {
    method: "DELETE",
  });
}

/**
 * Update loan
 */
export function updateLoan(tripId, loanId, data) {
  return api(`/api/trips/${tripId}/loans/${loanId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Add loan repayment
 */
export function addLoanRepayment(tripId, loanId, data) {
  return api(`/api/trips/${tripId}/loans/${loanId}/repayments`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Get journal for trip
 */
export function getJournal(tripId) {
  return api(`/api/trips/${tripId}/journal`).then(p => p.items);
}
