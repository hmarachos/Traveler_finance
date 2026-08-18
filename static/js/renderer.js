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
  keepFamilySelectsDifferent,
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

  // Hero metrics - только главные
  qs("#totalExpenses").textContent = money(totals.expenses_minor, trip.currency);
  qs("#totalPaid").textContent = money(totals.paid_minor, trip.currency);
  qs("#familyCount").textContent = totals.families_count;
  qs("#memberCount").textContent = totals.members_count;

  // Balance Overview (кто кому должен)
  renderBalanceOverview(familyStats, trip.currency);

  // Family cards - Minimalist & Informative
  const familyCardsEl = qs("#familyCards");
  if (familyCardsEl) {
    familyCardsEl.innerHTML = familyStats
      .map((stat) => {
        const balance = stat.expense_balance_minor;
        
        // Фактическая потрата = оплачено расходов - полученные переводы + отправленные переводы
        const transferBalance = stat.transfers_sent_minor - stat.transfers_received_minor;
        const advanceBalance = stat.advances_sent_minor - stat.advances_received_minor;
        const actualSpent = stat.expense_paid_minor + transferBalance + advanceBalance;
        
        let statusBadge = '';
        if (balance > 0) {
          statusBadge = `<span class="fam-status-badge positive">🟢 +${money(balance, trip.currency)}</span>`;
        } else if (balance < 0) {
          statusBadge = `<span class="fam-status-badge negative">🔴 -${money(Math.abs(balance), trip.currency)}</span>`;
        } else {
          statusBadge = `<span class="fam-status-badge neutral">⚪ В балансе</span>`;
        }

        return `
          <article class="family-card">
            <div class="family-card-header">
              <div class="family-name-group">
                <strong class="family-name">${stat.family.name}</strong>
                <span class="family-members-count">${stat.family.members_count} чел.</span>
              </div>
              ${statusBadge}
            </div>
            <div class="family-card-body">
              <div class="spent-label">Фактические траты</div>
              <div class="spent-value">${money(actualSpent, trip.currency)}</div>
            </div>
          </article>
        `;
      })
      .join("");
  }

  // Families list
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

  // Settlements - ОСТАВЛЕНО (главная аналитика - кто кому должен)
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

  // Loan obligations - ОСТАВЛЕНО (если займы есть)
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
  updateState({ loans });

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
                  ? `<div class="loan-actions">
                      <button data-repay="${loan.id}">Вернуть часть</button>
                      <button class="secondary" data-edit-loan="${loan.id}">Редактировать</button>
                      <button class="danger" data-delete-loan="${loan.id}">Удалить</button>
                    </div>`
                  : `<div class="loan-actions">
                      <button class="secondary" data-edit-loan="${loan.id}">Редактировать</button>
                      <button class="danger" data-delete-loan="${loan.id}">Удалить</button>
                    </div>`
              }
            </article>
          `
          )
          .join("")
      : emptyState("Займов пока нет");
  }
}

/**
 * Get date group label for an entry
 */
function getDateGroupLabel(dateString) {
  const date = new Date(dateString);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const isToday = date.toDateString() === today.toDateString();
  const isYesterday = date.toDateString() === yesterday.toDateString();

  if (isToday) return "Сегодня";
  if (isYesterday) return "Вчера";

  // Format date as "DD.MM.YYYY"
  return date.toLocaleDateString("ru-RU");
}

/**
 * Render journal/transaction log
 */
export function renderJournal(items) {
  const currency = state.trip?.currency || "EUR";

  // Save journal items to state for editing
  updateState({ journal: items });

  // Extract unique categories from expenses
  const categories = new Set();
  items.forEach(entry => {
    if (entry.type === 'expense') {
      // Extract category from meta (format: "Оплатили: Family · Category · split_method")
      const metaParts = entry.meta.split(' · ');
      if (metaParts.length >= 2) {
        const category = metaParts[1];
        categories.add(category);
      }
    }
  });

  // Populate category filter
  const categoryFilter = qs('#categoryFilter');
  if (categoryFilter && categories.size > 0) {
    const sortedCategories = Array.from(categories).sort();
    const filterOptions = sortedCategories
      .map(cat => `<option value="${cat}">${cat}</option>`)
      .join('');
    categoryFilter.innerHTML = '<option value="">Все категории</option>' + filterOptions;
    
    // Reset filter when journal updates
    categoryFilter.value = '';
  }

  // Group items by date
  const groupedItems = {};
  items.forEach(entry => {
    const dateLabel = getDateGroupLabel(entry.created_at);
    if (!groupedItems[dateLabel]) {
      groupedItems[dateLabel] = [];
    }
    groupedItems[dateLabel].push(entry);
  });

  // Sort dates: today, yesterday, then descending by date
  const sortedDates = Object.keys(groupedItems).sort((a, b) => {
    const dateA = new Date(a);
    const dateB = new Date(b);
    return dateB - dateA;
  });

  // Render grouped journal
  const journalListEl = qs("#journalList");
  if (journalListEl) {
    if (items.length === 0) {
      journalListEl.innerHTML = emptyState("Операций пока нет");
    } else {
      journalListEl.innerHTML = sortedDates
        .map(
          (dateLabel) => `
          <section class="journal-date-group">
            <h3 class="journal-date-header">${dateLabel}</h3>
            <div class="timeline">
              ${groupedItems[dateLabel]
                .map((entry) => renderOperationCard(entry, currency))
                .join("")}
            </div>
          </section>
        `
        )
        .join("");
    }
  }
}

/**
 * Render individual operation card
 */
export function renderOperationCard(entry, currency) {
  const icons = {
    expense: "💳",
    transfer: "💸",
    advance: "⚡",
    loan: "🤝",
    loan_repayment: "↩️",
  };
  const icon = icons[entry.type] || "📄";
  const typeLabel = getTransactionLabel(entry.type);

  let categoryPill = "";
  let metaDetail = entry.meta || "";

  if (entry.type === "expense") {
    const metaParts = entry.meta.split(" · ");
    if (metaParts.length >= 2) {
      metaDetail = metaParts[0].trim();
      categoryPill = metaParts[1].trim();
      if (metaParts.length >= 3) {
        metaDetail += ` · ${metaParts[2].trim()}`;
      }
    }
  }

  const formattedAmount = money(entry.amount_minor, currency);
  const remainingChip =
    entry.remaining_amount_minor !== undefined
      ? `<span class="card-remaining-chip">остаток ${money(entry.remaining_amount_minor, currency)}</span>`
      : "";

  return `
    <article class="timeline-item clickable type-${entry.type}" data-entry-id="${entry.id}" data-entry-type="${entry.type}">
      <div class="card-top-row">
        <div class="card-badges">
          <span class="op-badge type-${entry.type}">
            <span class="badge-icon">${icon}</span>
            <span class="badge-label">${typeLabel}</span>
          </span>
          ${categoryPill ? `<span class="category-pill">${categoryPill}</span>` : ""}
        </div>
        <div class="card-amount type-${entry.type}">${formattedAmount}</div>
      </div>
      <div class="card-main-row">
        <h4 class="card-title-text">${entry.title || typeLabel}</h4>
      </div>
      <div class="card-bottom-row">
        <span class="card-meta-detail">${metaDetail}</span>
        ${remainingChip}
        <span class="card-author">👤 ${entry.author || "Система"}</span>
      </div>
    </article>
  `;
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
    syncFamilyPair("#transferForm", "from_family_id", "to_family_id");
    syncFamilyPair("#loanForm", "lender_family_id", "borrower_family_id");
    syncFamilyPair("#editTransferForm", "from_family_id", "to_family_id");
    syncFamilyPair("#editLoanForm", "lender_family_id", "borrower_family_id");
  }
}

function syncFamilyPair(formSelector, firstName, secondName) {
  const form = qs(formSelector);
  if (form) keepFamilySelectsDifferent(form, firstName, secondName, secondName);
}

/**
 * Sync trip dropdown and edit form
 */
export function syncTripControls() {
  const form = qs("#tripEditForm");
  if (state.trip && form) {
    form.elements.name.value = state.trip.name;
    form.elements.currency.value = state.trip.currency;
    form.elements.access_code.value = state.trip.access_code;
  }
  
  // Render trips list on settings page
  renderTripsList();
  renderTripUsers();
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
                <p class="meta">${trip.currency}</p>
              </div>
              <button class="secondary" data-switch-trip="${trip.id}">Открыть</button>
            </div>
          `)
          .join("")
      : emptyState("Путешествий пока нет");
  }
}

export function renderTripUsers() {
  const list = qs("#tripUsersList");
  if (!list) return;

  const currentUserId = state.user?.id;
  list.innerHTML = state.tripUsers?.length
    ? state.tripUsers
        .map((user) => `
          <div class="list-item family-row">
            <div>
              <strong>${user.username}</strong>
              <p class="meta">${user.role === "owner" ? "Владелец" : "Участник"}</p>
            </div>
            ${
              user.role === "owner" || user.id === currentUserId
                ? ""
                : `<button class="danger" data-remove-trip-user="${user.id}">Удалить</button>`
            }
          </div>
        `)
        .join("")
    : emptyState("Пользователей пока нет");
}

/**
 * Render balance overview - кто кому должен
 */
export function renderBalanceOverview(familyStats, currency) {
  // Calculate net balance for each family
  const balances = familyStats.map((stat) => {
    const expenseBalance = stat.expense_balance_minor;
    const transferBalance = stat.transfers_sent_minor - stat.transfers_received_minor;
    const advanceBalance = stat.advances_sent_minor - stat.advances_received_minor;
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
          <div class="balance-icon-circle">✓</div>
          <div class="balance-text">
            <p class="balance-title">Все расчеты завершены</p>
            <p class="balance-desc">Расходы между семьями полностью сбалансированы</p>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = payments
        .map(
          (p) => `
        <div class="balance-card payment">
          <div class="balance-flow">
            <span class="fam-pill from">${p.from}</span>
            <span class="flow-arrow">➔</span>
            <span class="fam-pill to">${p.to}</span>
          </div>
          <div class="balance-amount-pill">${money(p.amount, currency)}</div>
        </div>
      `
        )
        .join("");
    }
  }
}

/**
 * Setup journal category filter
 */
export function setupJournalFilter() {
  const categoryFilter = qs('#categoryFilter');
  const journalList = qs('#journalList');
  
  if (!categoryFilter || !journalList) return;
  
  categoryFilter.addEventListener('change', () => {
    const selectedCategory = categoryFilter.value;
    const items = state.journal || [];
    const currency = state.trip?.currency || "EUR";
    
    // Filter items
    const filteredItems = selectedCategory 
      ? items.filter(entry => {
          if (entry.type === 'expense') {
            const metaParts = entry.meta.split(' · ');
            if (metaParts.length >= 2) {
              const category = metaParts[1];
              return category === selectedCategory;
            }
          }
          return false;
        })
      : items;
    
    // Group filtered items by date
    const groupedItems = {};
    filteredItems.forEach(entry => {
      const dateLabel = getDateGroupLabel(entry.created_at);
      if (!groupedItems[dateLabel]) {
        groupedItems[dateLabel] = [];
      }
      groupedItems[dateLabel].push(entry);
    });

    // Sort dates: today, yesterday, then descending by date
    const sortedDates = Object.keys(groupedItems).sort((a, b) => {
      const dateA = new Date(a);
      const dateB = new Date(b);
      return dateB - dateA;
    });
    
    // Re-render grouped filtered list
    if (filteredItems.length === 0) {
      journalList.innerHTML = emptyState("Операций с этой категорией нет");
    } else {
      journalList.innerHTML = sortedDates
        .map(
          (dateLabel) => `
          <section class="journal-date-group">
            <h3 class="journal-date-header">${dateLabel}</h3>
            <div class="timeline">
              ${groupedItems[dateLabel]
                .map((entry) => renderOperationCard(entry, currency))
                .join("")}
            </div>
          </section>
        `
        )
        .join("");
    }
  });
}

/**
 * Display current user information in settings
 */
export function renderUserInfo() {
  const usernameElement = qs("#currentUsername");
  if (usernameElement && state.user) {
    usernameElement.textContent = state.user.username;
  }
}

/**
 * Initialize user information display
 */
export function initUserInfo() {
  renderUserInfo();
}