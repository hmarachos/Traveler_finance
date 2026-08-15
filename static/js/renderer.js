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

  // Balance Overview (кто кому должен)
  renderBalanceOverview(familyStats, trip.currency);

  // Family cards (only update if element exists)
  const familyCardsEl = qs("#familyCards");
  if (familyCardsEl) {
    familyCardsEl.innerHTML = familyStats
      .map((stat) => {
        const balance = stat.expense_balance_minor;
        const transferBalance = stat.transfers_received_minor - stat.transfers_sent_minor;
        const advanceBalance = stat.advances_received_minor - stat.advances_sent_minor;
        const loanBalance = stat.loan_receivable_minor - stat.loan_payable_minor;
        const totalBalance = balance + transferBalance + advanceBalance + loanBalance;

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
              ${transferBalance !== 0 ? `<p class="line"><span>Переводы</span><span class="${signedClass(transferBalance)}">${money(transferBalance, trip.currency)}</span></p>` : ''}
              ${advanceBalance !== 0 ? `<p class="line"><span>Авансы</span><span class="${signedClass(advanceBalance)}">${money(advanceBalance, trip.currency)}</span></p>` : ''}
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
              <p class="line" style="border-top: 1px solid var(--line); margin-top: 8px; padding-top: 8px;">
                <span><strong>Итоговый баланс</strong></span>
                <span class="${signedClass(totalBalance)}" style="font-weight: bold;">${money(totalBalance, trip.currency)}</span>
              </p>
            </div>
          </article>
        `;
      })
      .join("");
  }

  // Families list (only update if element exists)
  const familiesListEl = qs("#familiesList");
  if (familiesListEl) {
    familiesListEl.innerHTML = state.families
      .map(
        (family) => `
        <div class="list-item family-row" data-family-id="${family.id}">
          <div>
            <strong>${family.name}</strong>
            <p class="meta">${family.members_count} участников</p>
            <form class="family-edit-form hidden" data-family-edit="${family.id}">
              <div class="inline-form">
                <label>
                  <input type="text" name="name" value="${family.name}" placeholder="Название семьи" required />
                </label>
                <label>
                  <input type="number" name="members_count" value="${family.members_count}" min="1" step="1" placeholder="Участники" required />
                </label>
                <button type="submit" class="secondary">Сохранить</button>
                <button type="button" class="danger" data-cancel-edit="${family.id}">Отмена</button>
              </div>
            </form>
          </div>
          <div class="family-actions">
            <button class="secondary" data-edit-family="${family.id}">Редактировать</button>
            <button class="danger" data-delete-family="${family.id}">Удалить</button>
          </div>
        </div>
      `
      )
      .join("");
  }

  // Settlements (only update if element exists)
  const settlementsEl = qs("#settlements");
  if (settlementsEl) {
    settlementsEl.innerHTML = settlements.length
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
  }

  // Loan obligations (only update if element exists)
  const loanObligationsEl = qs("#loanObligations");
  if (loanObligationsEl) {
    loanObligationsEl.innerHTML = loanObligations.length
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
  }

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

  const loansListEl = qs("#loansList");
  if (loansListEl) {
    loansListEl.innerHTML = loans.length
      ? loans
          .map(
            (loan) => `
            <article class="card" data-loan-id="${loan.id}">
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
}

/**
 * Render journal/transaction log
 */
export function renderJournal(items) {
  const currency = state.trip?.currency || "EUR";

  // Save journal items to state for editing
  updateState({ journal: items });

  const journalListEl = qs("#journalList");
  if (journalListEl) {
    journalListEl.innerHTML = items.length
      ? items
          .map(
            (entry) => `
            <article class="timeline-item clickable" data-entry-id="${entry.id}" data-entry-type="${entry.type}">
              <p class="line">
                <span>${getTransactionLabel(entry.type)} · ${entry.title}</span>
                <span>${money(entry.amount_minor, currency)}</span>
              </p>
              <p class="meta">
                ${new Date(entry.created_at).toLocaleDateString("ru-RU")} · ${entry.meta}${
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
}

/**
 * Sync select element options with families
 */
export function syncSelectElements() {
  const selects = qsa("select[name$='family_id']");
  if (selects.length > 0 && state.families.length > 0) {
    selects.forEach((select) => {
      select.innerHTML = familiesOptions(state.families, select.value);
    });
  }
}

/**
 * Sync trip dropdown and edit form
 */
export function syncTripControls() {
  const select = qs("#tripSelect");
  if (select) {
    select.innerHTML = state.trips
      .map((trip) => `<option value="${trip.id}">${trip.name}</option>`)
      .join("");
    select.value = String(state.tripId || "");
  }

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
  
  const tripsListEl = qs("#tripsList");
  if (tripsListEl) {
    tripsListEl.innerHTML = state.trips.length
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
}

/**
 * Render balance overview - кто кому должен
 */
export function renderBalanceOverview(familyStats, currency) {
  // Calculate net balance for each family
  const balances = familyStats.map((stat) => {
    const expenseBalance = stat.expense_balance_minor;
    const transferBalance = stat.transfers_received_minor - stat.transfers_sent_minor;
    const advanceBalance = stat.advances_received_minor - stat.advances_sent_minor;
    const loanBalance = stat.loan_receivable_minor - stat.loan_payable_minor;
    const netBalance = expenseBalance + transferBalance + advanceBalance + loanBalance;

    return {
      id: stat.family.id,
      name: stat.family.name,
      balance: netBalance,
    };
  });

  // Separate debtors and creditors
  const debtors = balances.filter((b) => b.balance < 0).sort((a, b) => a.balance - b.balance);
  const creditors = balances.filter((b) => b.balance > 0).sort((a, b) => b.balance - a.balance);

  // Generate settled payments
  const payments = [];
  let debtorIdx = 0;
  let creditorIdx = 0;
  let debtorRemaining = Math.abs(debtors[0]?.balance || 0);
  let creditorRemaining = creditors[0]?.balance || 0;

  while (debtorIdx < debtors.length && creditorIdx < creditors.length) {
    const amount = Math.min(debtorRemaining, creditorRemaining);
    if (amount > 0) {
      payments.push({
        from: debtors[debtorIdx].name,
        to: creditors[creditorIdx].name,
        amount,
      });
    }

    debtorRemaining -= amount;
    creditorRemaining -= amount;

    if (debtorRemaining === 0) {
      debtorIdx++;
      debtorRemaining = Math.abs(debtors[debtorIdx]?.balance || 0);
    }
    if (creditorRemaining === 0) {
      creditorIdx++;
      creditorRemaining = creditors[creditorIdx]?.balance || 0;
    }
  }

  // Render
  const container = qs("#balanceOverview");
  if (container) {
    if (payments.length === 0) {
      container.innerHTML = `
        <div class="balance-card balanced">
          <div class="balance-icon">✓</div>
          <div class="balance-text">
            <p class="balance-title">Все расчеты завершены</p>
            <p class="balance-desc">Никто никому не должен</p>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = payments
        .map(
          (p) => `
        <div class="balance-card payment">
          <div class="balance-from">${p.from}</div>
          <div class="balance-arrow">→</div>
          <div class="balance-to">${p.to}</div>
          <div class="balance-amount">${money(p.amount, currency)}</div>
        </div>
      `
        )
        .join("");
    }
  }
}
