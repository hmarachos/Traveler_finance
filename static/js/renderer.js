/**
 * UI rendering module
 */

import { state, updateState } from "./state.js";
import {
  qs,
  qsa,
  money,
  signedClass,
  familiesOptions,
  emptyState,
  listItem,
  getTransactionLabel,
} from "./utils.js";

/**
 * Render trip summary dashboard
 */
export function renderSummary() {
  const {
    trip,
    totals,
    family_stats: familyStats,
    expense_settlements: settlements,
    loan_obligations: loanObligations,
  } = state.summary;

  updateState({ trip, families: state.summary.families });

  // Header
  qs("#tripName").textContent = trip.name;

  // Hero metrics
  qs("#totalExpenses").textContent = money(totals.expenses_minor, trip.currency);
  qs("#totalPaid").textContent = money(totals.paid_minor, trip.currency);
  qs("#familyCount").textContent = totals.families_count;
  qs("#memberCount").textContent = totals.members_count;

  // Additional metrics
  qs("#loanTotal").textContent = money(totals.loans_principal_minor, trip.currency);
  qs("#loanOpen").textContent = money(totals.loans_open_minor, trip.currency);
  qs("#transferTotal").textContent = money(totals.transfers_minor, trip.currency);
  qs("#advanceTotal").textContent = money(totals.advances_minor, trip.currency);

  // Family cards
  qs("#familyCards").innerHTML = familyStats
    .map((stat) => {
      const balance = stat.expense_balance_minor;
      const total =
        balance +
        stat.loan_receivable_minor -
        stat.loan_payable_minor;

      return `
        <article class="card">
          <div class="card-title">
            <strong>${stat.family.name}</strong>
            <span class="badge">${stat.family.members_count} чел.</span>
          </div>
          <div class="grid-lines">
            <p class="line">
              <span>Оплатили расходов</span>
              <span>${money(stat.expense_paid_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Расчетная доля</span>
              <span>${money(stat.expense_share_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Баланс расходов</span>
              <span class="${signedClass(balance)}">${money(balance, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Дали в долг</span>
              <span>${money(stat.loans_given_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Взяли в долг</span>
              <span>${money(stat.loans_taken_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Долг к получению</span>
              <span>${money(stat.loan_receivable_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Долг к возврату</span>
              <span>${money(stat.loan_payable_minor, trip.currency)}</span>
            </p>
            <p class="line">
              <span>Итог без переводов</span>
              <span class="${signedClass(total)}">${money(total, trip.currency)}</span>
            </p>
          </div>
        </article>
      `;
    })
    .join("");

  // Families list
  qs("#familiesList").innerHTML = state.families
    .map(
      (family) => `
      <div class="list-item family-row">
        <div>
          <strong>${family.name}</strong>
          <p class="meta">${family.members_count} участников</p>
        </div>
        <button class="danger" data-delete-family="${family.id}">Удалить</button>
      </div>
    `
    )
    .join("");

  // Settlements
  qs("#settlements").innerHTML = settlements.length
    ? settlements
        .map((s) =>
          listItem(
            `${s.from_family_name} → ${s.to_family_name}`,
            money(s.amount_minor, trip.currency),
            "расходы"
          )
        )
        .join("")
    : emptyState("По расходам все сбалансировано");

  // Loan obligations
  qs("#loanObligations").innerHTML = loanObligations.length
    ? loanObligations
        .map((l) =>
          listItem(
            `${l.from_family_name} должны ${l.to_family_name}`,
            money(l.amount_minor, trip.currency),
            "займ"
          )
        )
        .join("")
    : emptyState("Открытых долгов по займам нет");

  syncSelectElements();
  syncTripControls();
}

/**
 * Render loans list
 */
export function renderLoans(loans) {
  const currency = state.trip?.currency || "EUR";
  const familyName = (id) =>
    state.families.find((f) => f.id === id)?.name || "Unknown";

  qs("#loansList").innerHTML = loans.length
    ? loans
        .map(
          (loan) => `
          <article class="card">
            <div class="card-title">
              <strong>${familyName(loan.borrower_family_id)} → ${familyName(loan.lender_family_id)}</strong>
              <span class="badge">${loan.status}</span>
            </div>
            <div class="grid-lines">
              <p class="line">
                <span>Первоначально</span>
                <span>${money(loan.principal_amount_minor, currency)}</span>
              </p>
              <p class="line">
                <span>Осталось</span>
                <span class="${loan.remaining_amount_minor ? "negative" : "positive"}">
                  ${money(loan.remaining_amount_minor, currency)}
                </span>
              </p>
              <p class="muted">${loan.description || "Без комментария"}</p>
              ${loan.repayments
                .map(
                  (r) =>
                    `<p class="line muted">
                    <span>${new Date(r.created_at).toLocaleDateString("ru-RU")} · возврат</span>
                    <span>${money(r.amount_minor, currency)}</span>
                  </p>`
                )
                .join("")}
            </div>
            ${
              loan.remaining_amount_minor > 0
                ? `<div class="loan-actions"><button data-repay="${loan.id}">Вернуть часть</button></div>`
                : ""
            }
          </article>
        `
        )
        .join("")
    : emptyState("Займов пока нет");
}

/**
 * Render journal/transaction log
 */
export function renderJournal(items) {
  const currency = state.trip?.currency || "EUR";

  qs("#journalList").innerHTML = items.length
    ? items
        .map(
          (entry) => `
          <article class="timeline-item">
            <p class="line">
              <span>${getTransactionLabel(entry.type)} · ${entry.title}</span>
              <span>${money(entry.amount_minor, currency)}</span>
            </p>
            <p class="meta">
              ${new Date(entry.created_at).toLocaleString("ru-RU")} · ${entry.meta}${
                entry.remaining_amount_minor !== undefined
                  ? ` · остаток ${money(entry.remaining_amount_minor, currency)}`
                  : ""
              }
            </p>
          </article>
        `
        )
        .join("")
    : emptyState("Операций пока нет");
}

/**
 * Sync select element options with families
 */
export function syncSelectElements() {
  qsa("select[name$='family_id']").forEach((select) => {
    select.innerHTML = familiesOptions(state.families, select.value);
  });
}

/**
 * Sync trip dropdown and edit form
 */
export function syncTripControls() {
  const select = qs("#tripSelect");
  select.innerHTML = state.trips
    .map((trip) => `<option value="${trip.id}">${trip.name}</option>`)
    .join("");
  select.value = String(state.tripId || "");

  const form = qs("#tripEditForm");
  if (state.trip && form) {
    form.elements.name.value = state.trip.name;
    form.elements.currency.value = state.trip.currency;
    form.elements.access_code.value = state.trip.access_code;
  }
  
  // Render trips list on settings page
  renderTripsList();
}

/**
 * Render all trips on settings page
 */
export function renderTripsList() {
  const currency = state.trip?.currency || "EUR";
  
  qs("#tripsList").innerHTML = state.trips.length
    ? state.trips
        .map((trip) => `
          <div class="list-item ${state.tripId === trip.id ? "active" : ""}">
            <div>
              <strong>${trip.name}</strong>
              <p class="meta">${trip.currency} · ${trip.access_code}</p>
            </div>
            <button class="secondary" data-switch-trip="${trip.id}">Открыть</button>
          </div>
        `)
        .join("")
    : emptyState("Путешествий пока нет");
}
