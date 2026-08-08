const state = {
  tripId: Number(localStorage.getItem("travelerFinanceTripId")) || null,
  trip: null,
  trips: [],
  families: [],
  summary: null,
};

const money = (minor) => {
  const currency = state.trip?.currency || "EUR";
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency }).format((minor || 0) / 100);
};

const qs = (selector, root = document) => root.querySelector(selector);
const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Ошибка запроса");
  return payload;
}

function toast(message) {
  const el = qs("#toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function optionsHtml(selectedId = "") {
  return state.families
    .map((family) => `<option value="${family.id}" ${String(family.id) === String(selectedId) ? "selected" : ""}>${family.name}</option>`)
    .join("");
}

function syncSelects() {
  qsa("select[name$='family_id']").forEach((select) => {
    select.innerHTML = optionsHtml(select.value);
  });
}

function syncTripControls() {
  const select = qs("#tripSelect");
  select.innerHTML = state.trips.map((trip) => `<option value="${trip.id}">${trip.name}</option>`).join("");
  select.value = String(state.tripId || "");

  const form = qs("#tripEditForm");
  if (state.trip && form) {
    form.elements.name.value = state.trip.name;
    form.elements.currency.value = state.trip.currency;
    form.elements.access_code.value = state.trip.access_code;
  }
}

function signedClass(value) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "";
}

function renderSummary() {
  const { trip, totals, family_stats: familyStats, expense_settlements: settlements, loan_obligations: loanObligations } = state.summary;
  state.trip = trip;
  state.families = state.summary.families;
  qs("#tripName").textContent = trip.name;
  qs("#totalExpenses").textContent = money(totals.expenses_minor);
  qs("#totalPaid").textContent = money(totals.paid_minor);
  qs("#familyCount").textContent = totals.families_count;
  qs("#memberCount").textContent = totals.members_count;
  qs("#loanTotal").textContent = money(totals.loans_principal_minor);
  qs("#loanOpen").textContent = money(totals.loans_open_minor);
  qs("#transferTotal").textContent = money(totals.transfers_minor);
  qs("#advanceTotal").textContent = money(totals.advances_minor);

  qs("#familyCards").innerHTML = familyStats
    .map((stat) => {
      const balance = stat.expense_balance_minor;
      const total = balance + stat.loan_receivable_minor - stat.loan_payable_minor;
      return `
        <article class="card">
          <div class="card-title">
            <strong>${stat.family.name}</strong>
            <span class="badge">${stat.family.members_count} чел.</span>
          </div>
          <div class="grid-lines">
            <p class="line"><span>Оплатили расходов</span><span>${money(stat.expense_paid_minor)}</span></p>
            <p class="line"><span>Расчетная доля</span><span>${money(stat.expense_share_minor)}</span></p>
            <p class="line"><span>Баланс расходов</span><span class="${signedClass(balance)}">${money(balance)}</span></p>
            <p class="line"><span>Дали в долг</span><span>${money(stat.loans_given_minor)}</span></p>
            <p class="line"><span>Взяли в долг</span><span>${money(stat.loans_taken_minor)}</span></p>
            <p class="line"><span>Долг к получению</span><span>${money(stat.loan_receivable_minor)}</span></p>
            <p class="line"><span>Долг к возврату</span><span>${money(stat.loan_payable_minor)}</span></p>
            <p class="line"><span>Итог без переводов</span><span class="${signedClass(total)}">${money(total)}</span></p>
          </div>
        </article>
      `;
    })
    .join("");

  qs("#familiesList").innerHTML = state.families
    .map((family) => `
      <div class="list-item family-row">
        <div>
          <strong>${family.name}</strong>
          <p class="meta">${family.members_count} участников</p>
        </div>
        <button class="danger" data-delete-family="${family.id}">Удалить</button>
      </div>
    `)
    .join("");

  qs("#settlements").innerHTML = settlements.length
    ? settlements.map((s) => item(`${s.from_family_name} → ${s.to_family_name}`, money(s.amount_minor), "расходы")).join("")
    : empty("По расходам все сбалансировано");
  qs("#loanObligations").innerHTML = loanObligations.length
    ? loanObligations.map((l) => item(`${l.from_family_name} должны ${l.to_family_name}`, money(l.amount_minor), "займ")).join("")
    : empty("Открытых долгов по займам нет");
  syncSelects();
  syncTripControls();
}

function item(title, amount, meta = "") {
  return `<div class="list-item"><p class="line"><span>${title}</span><span class="amount">${amount}</span></p>${meta ? `<p class="meta">${meta}</p>` : ""}</div>`;
}

function empty(text) {
  return `<div class="empty">${text}</div>`;
}

async function loadSummary() {
  if (!state.tripId) return;
  state.summary = await api(`/api/trips/${state.tripId}/summary`);
  renderSummary();
}

async function loadLoans() {
  if (!state.tripId) return;
  const payload = await api(`/api/trips/${state.tripId}/loans`);
  const familyName = (id) => state.families.find((f) => f.id === id)?.name || "Unknown";
  qs("#loansList").innerHTML = payload.loans.length
    ? payload.loans
        .map((loan) => `
          <article class="card">
            <div class="card-title">
              <strong>${familyName(loan.borrower_family_id)} → ${familyName(loan.lender_family_id)}</strong>
              <span class="badge">${loan.status}</span>
            </div>
            <div class="grid-lines">
              <p class="line"><span>Первоначально</span><span>${money(loan.principal_amount_minor)}</span></p>
              <p class="line"><span>Осталось</span><span class="${loan.remaining_amount_minor ? "negative" : "positive"}">${money(loan.remaining_amount_minor)}</span></p>
              <p class="muted">${loan.description || "Без комментария"}</p>
              ${loan.repayments.map((r) => `<p class="line muted"><span>${new Date(r.created_at).toLocaleDateString("ru-RU")} · возврат</span><span>${money(r.amount_minor)}</span></p>`).join("")}
            </div>
            ${loan.remaining_amount_minor > 0 ? `<div class="loan-actions"><button data-repay="${loan.id}">Вернуть часть</button></div>` : ""}
          </article>
        `)
        .join("")
    : empty("Займов пока нет");
}

async function loadJournal() {
  if (!state.tripId) return;
  const payload = await api(`/api/trips/${state.tripId}/journal`);
  qs("#journalList").innerHTML = payload.items.length
    ? payload.items
        .map((entry) => `
          <article class="timeline-item">
            <p class="line"><span>${label(entry.type)} · ${entry.title}</span><span>${money(entry.amount_minor)}</span></p>
            <p class="meta">${new Date(entry.created_at).toLocaleString("ru-RU")} · ${entry.meta}${entry.remaining_amount_minor !== undefined ? ` · остаток ${money(entry.remaining_amount_minor)}` : ""}</p>
          </article>
        `)
        .join("")
    : empty("Операций пока нет");
}

function label(type) {
  return {
    expense: "Расход",
    transfer: "Перевод",
    advance: "Аванс",
    loan: "Заем",
    loan_repayment: "Возврат займа",
  }[type] || type;
}

async function refreshAll() {
  await loadTrips();
  await loadSummary();
  await Promise.all([loadLoans(), loadJournal()]);
}

async function loadTrips() {
  const payload = await api("/api/trips");
  state.trips = payload.trips;
  if (!state.trips.length) {
    throw new Error("Нет доступных путешествий");
  }
  if (!state.tripId || !state.trips.some((trip) => trip.id === state.tripId)) {
    state.tripId = state.trips[0].id;
    localStorage.setItem("travelerFinanceTripId", state.tripId);
  }
  syncTripControls();
}

function formPayload(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function wireForms() {
  qs("#tripEditForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api(`/api/trips/${state.tripId}`, { method: "PUT", body: JSON.stringify(formPayload(form)) });
      await refreshAll();
      toast("Путешествие сохранено");
    } catch (error) {
      toast(error.message);
    }
  });

  qs("#tripCreateForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const created = await api("/api/trips", { method: "POST", body: JSON.stringify(formPayload(form)) });
      state.tripId = created.id;
      localStorage.setItem("travelerFinanceTripId", state.tripId);
      form.reset();
      form.elements.currency.value = "EUR";
      await refreshAll();
      toast("Путешествие создано");
    } catch (error) {
      toast(error.message);
    }
  });

  qs("#familyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api(`/api/trips/${state.tripId}/families`, { method: "POST", body: JSON.stringify(formPayload(form)) });
      form.reset();
      qs("#familyForm [name='members_count']").value = 1;
      await refreshAll();
      toast("Семья добавлена");
    } catch (error) {
      toast(error.message);
    }
  });

  qs("#expenseForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    await api(`/api/trips/${state.tripId}/expenses`, { method: "POST", body: JSON.stringify(formPayload(form)) });
    form.reset();
    await refreshAll();
    toast("Расход добавлен");
  });

  qs("#transferForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    await api(`/api/trips/${state.tripId}/transfers`, { method: "POST", body: JSON.stringify(formPayload(form)) });
    form.reset();
    await refreshAll();
    toast("Перевод сохранен");
  });

  qs("#loanForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    await api(`/api/trips/${state.tripId}/loans`, { method: "POST", body: JSON.stringify(formPayload(form)) });
    form.reset();
    await refreshAll();
    toast("Заем создан");
  });

  qs("#repayForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = formPayload(form);
    await api(`/api/trips/${state.tripId}/loans/${payload.loan_id}/repayments`, { method: "POST", body: JSON.stringify(payload) });
    qs("#repayDialog").close();
    form.reset();
    await refreshAll();
    toast("Возврат сохранен");
  });
}

function wireNavigation() {
  qsa(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      qsa(".tab").forEach((b) => b.classList.toggle("active", b === button));
      qsa(".view").forEach((view) => view.classList.toggle("active", view.id === button.dataset.view));
      if (button.dataset.view === "loans") loadLoans();
      if (button.dataset.view === "journal") loadJournal();
    });
  });

  qsa(".segmented button").forEach((button) => {
    button.addEventListener("click", () => {
      qsa(".segmented button").forEach((b) => b.classList.toggle("active", b === button));
      qsa(".entry-form").forEach((form) => form.classList.toggle("active", form.id === button.dataset.form));
    });
  });

  document.body.addEventListener("click", (event) => {
    const repayButton = event.target.closest("[data-repay]");
    if (repayButton) {
      qs("#repayForm [name='loan_id']").value = repayButton.dataset.repay;
      qs("#repayDialog").showModal();
      return;
    }

    const deleteFamilyButton = event.target.closest("[data-delete-family]");
    if (deleteFamilyButton) {
      const family = state.families.find((item) => String(item.id) === String(deleteFamilyButton.dataset.deleteFamily));
      if (!family || !confirm(`Удалить семью "${family.name}"?`)) return;
      api(`/api/trips/${state.tripId}/families/${family.id}`, { method: "DELETE" })
        .then(refreshAll)
        .then(() => toast("Семья удалена"))
        .catch((error) => toast(error.message));
    }
  });

  qs("#tripSelect").addEventListener("change", async (event) => {
    state.tripId = Number(event.currentTarget.value);
    localStorage.setItem("travelerFinanceTripId", state.tripId);
    await refreshAll();
    toast("Путешествие открыто");
  });

  qs("#deleteTripBtn").addEventListener("click", async () => {
    if (!state.trip || !confirm(`Удалить путешествие "${state.trip.name}"? Финансовая история будет скрыта вместе с ним.`)) return;
    try {
      await api(`/api/trips/${state.tripId}`, { method: "DELETE" });
      localStorage.removeItem("travelerFinanceTripId");
      state.tripId = null;
      await refreshAll();
      toast("Путешествие удалено");
    } catch (error) {
      toast(error.message);
    }
  });

  qs("#refreshBtn").addEventListener("click", () => refreshAll().then(() => toast("Обновлено")));
}

async function init() {
  wireNavigation();
  wireForms();
  await refreshAll();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
}

init().catch((error) => toast(error.message));
