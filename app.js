const billList = document.querySelector("#billList");
const vendorGrid = document.querySelector("#vendorGrid");
const form = document.querySelector("#assistantForm");
const input = document.querySelector("#assistantInput");
const chatWindow = document.querySelector("#chatWindow");
const metricCards = document.querySelectorAll(".metric-card");
const aiNote = document.querySelector("#aiNote");
const billForm = document.querySelector("#billForm");
const vendorForm = document.querySelector("#vendorForm");
const accountForm = document.querySelector("#accountForm");
const billVendorSelect = billForm.querySelector("[name='vendorId']");
const connectAccountButton = document.querySelector("#connectAccountButton");
const payApprovedButton = document.querySelector("#payApprovedButton");
const uploadPdfButton = document.querySelector("#uploadPdfButton");
const invoiceUpload = document.querySelector("#invoiceUpload");
const receiptList = document.querySelector("#receiptList");
const toast = document.querySelector("#toast");

let vendorsCache = [];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || `API request failed: ${response.status}`);
  }

  return response.json();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3200);
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
  vendorsCache = vendors;
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

  billVendorSelect.innerHTML = vendors
    .map((vendor) => `<option value="${vendor.id}">${vendor.name}</option>`)
    .join("");
}

function renderReceipts(receipts) {
  receiptList.innerHTML = receipts
    .map(
      (receipt) => `
        <li>
          <span>${receipt.vendor_name}</span>
          <strong>${receipt.document_type}</strong>
        </li>
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
  const [dashboard, bills, vendors, receipts] = await Promise.all([
    api("/api/dashboard"),
    api("/api/bills"),
    api("/api/vendors"),
    api("/api/receipts"),
  ]);

  renderDashboard(dashboard);
  renderBills(bills);
  renderVendors(vendors);
  renderReceipts(receipts);
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
    showToast(`AutoPay ${enabled ? "enabled" : "disabled"}.`);
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
  showToast("Bill marked paid in local demo mode.");
});

vendorForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = vendorForm.querySelector("button");
  submitButton.disabled = true;
  const formData = new FormData(vendorForm);

  try {
    await api("/api/vendors", {
      method: "POST",
      body: JSON.stringify({
        companyName: formData.get("companyName"),
        category: formData.get("category"),
        accountNumber: formData.get("accountNumber"),
        website: formData.get("website"),
        paymentMethod: formData.get("paymentMethod"),
        paymentSchedule: formData.get("paymentSchedule"),
        maxPayment: formData.get("maxPayment"),
      }),
    });

    vendorForm.reset();
    vendorForm.elements.paymentMethod.value = "Operating Checking";
    vendorForm.elements.paymentSchedule.value = "Manual approval";
    await loadApp();
    showToast("Vendor saved.");
  } catch (error) {
    showToast(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

billForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = billForm.querySelector("button");
  submitButton.disabled = true;
  const formData = new FormData(billForm);

  try {
    await api("/api/bills", {
      method: "POST",
      body: JSON.stringify({
        vendorId: formData.get("vendorId"),
        amount: formData.get("amount"),
        dueDate: formData.get("dueDate"),
        invoiceNumber: formData.get("invoiceNumber"),
        status: formData.get("status"),
      }),
    });

    billForm.reset();
    if (vendorsCache.length) {
      billVendorSelect.value = vendorsCache[0].id;
    }
    await loadApp();
    showToast("Bill saved.");
  } catch (error) {
    showToast(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

accountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = accountForm.querySelector("button");
  submitButton.disabled = true;
  const formData = new FormData(accountForm);

  try {
    await api("/api/accounts", {
      method: "POST",
      body: JSON.stringify({
        name: formData.get("name"),
        institution: formData.get("institution"),
        accountType: formData.get("accountType"),
        balance: formData.get("balance"),
      }),
    });
    accountForm.reset();
    await loadApp();
    showToast("Account connected in local demo mode.");
  } catch (error) {
    showToast(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

connectAccountButton.addEventListener("click", () => {
  document.querySelector("#settings").scrollIntoView({ behavior: "smooth", block: "start" });
  accountForm.elements.name.focus();
});

payApprovedButton.addEventListener("click", async () => {
  payApprovedButton.disabled = true;

  try {
    const response = await api("/api/pay-approved", { method: "POST" });
    await loadApp();
    showToast(`${response.paidCount} approved bill(s) marked paid.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    payApprovedButton.disabled = false;
  }
});

uploadPdfButton.addEventListener("click", () => {
  invoiceUpload.click();
});

invoiceUpload.addEventListener("change", async () => {
  const file = invoiceUpload.files[0];
  if (!file) {
    return;
  }

  uploadPdfButton.disabled = true;

  try {
    const response = await api("/api/bill-detections", {
      method: "POST",
      body: JSON.stringify({ filename: file.name }),
    });
    await loadApp();
    showToast(`Detected ${response.vendor} invoice for ${response.amount}.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    invoiceUpload.value = "";
    uploadPdfButton.disabled = false;
  }
});

loadApp().catch(() => {
  addMessage("Start the backend with python3 server.py to load live BillPilot data.", "bot");
});
