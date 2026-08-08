/**
 * Utility functions
 */

/**
 * Format minor currency units to localized string
 */
export function money(minor, currency = "EUR") {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
  }).format((minor || 0) / 100);
}

/**
 * Query selector shortcut
 */
export function qs(selector, root = document) {
  return root.querySelector(selector);
}

/**
 * Query selector all shortcut
 */
export function qsa(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

/**
 * Show toast notification
 */
export function toast(message) {
  const el = qs("#toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

/**
 * Get CSS class based on numeric value sign
 */
export function signedClass(value) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "";
}

/**
 * Extract form data to object
 */
export function formPayload(form) {
  return Object.fromEntries(new FormData(form).entries());
}

/**
 * Get label for transaction type
 */
export function getTransactionLabel(type) {
  const labels = {
    expense: "Расход",
    transfer: "Перевод",
    advance: "Аванс",
    loan: "Заем",
    loan_repayment: "Возврат займа",
  };
  return labels[type] || type;
}

/**
 * Generate HTML option tags for families
 */
export function familiesOptions(families, selectedId = "") {
  return families
    .map(
      (family) =>
        `<option value="${family.id}" ${String(family.id) === String(selectedId) ? "selected" : ""}>${family.name}</option>`
    )
    .join("");
}

/**
 * Generate HTML for empty state
 */
export function emptyState(text) {
  return `<div class="empty">${text}</div>`;
}

/**
 * Generate HTML for list item
 */
export function listItem(title, amount, meta = "") {
  return `<div class="list-item"><p class="line"><span>${title}</span><span class="amount">${amount}</span></p>${meta ? `<p class="meta">${meta}</p>` : ""}</div>`;
}
