const billList = document.querySelector("#billList");
const vendorGrid = document.querySelector("#vendorGrid");
const form = document.querySelector("#assistantForm");
const input = document.querySelector("#assistantInput");
const chatWindow = document.querySelector("#chatWindow");
const metricCards = document.querySelectorAll(".metric-card");
const aiNote = document.querySelector("#aiNote");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

function renderDashboard(dashboard) {
  const values = [
    ["Cash balance", dashboard.cashBalance, `Projected ${dashboard.projectedCashAfterWeek} after scheduled bills this week.`],
    ["Due today", dashboard.dueToday, "Bills waiting for approval or payment."],
    ["Due this week", dashboard.dueThisWeek, "Open bills across utilities, rent, and suppliers."],
    ["Monthly spending", dashboard.monthlySpending, `${dashboard.paidBills} has already been paid.`],
  ];

  metricCards.forEach((card, index) => {
    const [label, value, detail] = values[index];
    card.querySelector("span").textContent = label;
    card.querySelector("strong").textContent = value;
    card.querySelector("p").textContent = detail;
  });

  aiNote.textContent = dashboard.recommendation;
}

function renderBills(bills) {
  billList.innerHTML = bills
    .map(
      (bill) => `
        <div class="bill-row">
          <div>
            <h3>${bill.vendor}</h3>
            <p>${bill.category} • Due ${bill.due} • ${bill.invoice}</p>
          </div>
          <span class="amount">${bill.amount}</span>
          <button
            class="status ${bill.warning ? "warning" : ""}"
            data-pay-bill="${bill.id}"
            ${bill.status === "paid" ? "disabled" : ""}
          >${bill.statusLabel}</button>
        </div>
      `,
    )
    .join("");
}

function renderVendors(vendors) {
  vendorGrid.innerHTML = vendors
    .map(
      (vendor) => `
        <div class="vendor-card">
          <div>
            <h3>${vendor.name}</h3>
            <p>${vendor.category} • ${vendor.schedule} • ${vendor.limit} max</p>
          </div>
          <button
            class="toggle ${vendor.autopay ? "on" : ""}"
            data-vendor-id="${vendor.id}"
            aria-label="Toggle AutoPay for ${vendor.name}"
          ></button>
        </div>
      `,
    )
    .join("");
}

function addMessage(text, type) {
  const message = document.createElement("div");
  message.className = `message ${type}`;
  message.textContent = text;
  chatWindow.appendChild(message);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function loadApp() {
  const [dashboard, bills, vendors] = await Promise.all([
    api("/api/dashboard"),
    api("/api/bills"),
    api("/api/vendors"),
  ]);

  renderDashboard(dashboard);
  renderBills(bills);
  renderVendors(vendors);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();

  if (!question) {
    return;
  }

  addMessage(question, "user");
  input.value = "";

  try {
    const response = await api("/api/assistant", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    addMessage(response.answer, "bot");
  } catch (error) {
    addMessage("I could not reach the BillPilot backend. Start server.py and try again.", "bot");
  }
});

vendorGrid.addEventListener("click", async (event) => {
  if (!event.target.classList.contains("toggle")) {
    return;
  }

  const button = event.target;
  const enabled = !button.classList.contains("on");
  button.disabled = true;

  try {
    await api(`/api/vendors/${button.dataset.vendorId}/autopay`, {
      method: "POST",
      body: JSON.stringify({ enabled }),
    });
    button.classList.toggle("on", enabled);
  } finally {
    button.disabled = false;
  }
});

billList.addEventListener("click", async (event) => {
  const billId = event.target.dataset.payBill;
  if (!billId || event.target.disabled) {
    return;
  }

  event.target.disabled = true;
  await api(`/api/bills/${billId}/pay`, { method: "POST" });
  await loadApp();
});

loadApp().catch(() => {
  addMessage("Start the backend with python3 server.py to load live BillPilot data.", "bot");
});
