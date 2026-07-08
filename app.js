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
const uploadReviewForm = document.querySelector("#uploadReviewForm");
const cancelUploadButton = document.querySelector("#cancelUploadButton");
const receiptList = document.querySelector("#receiptList");
const toast = document.querySelector("#toast");
const navLinks = document.querySelectorAll(".nav-list a[data-page]");
const appPages = document.querySelectorAll(".app-page");
const topbarEyebrow = document.querySelector(".topbar .eyebrow");
const topbarHeading = document.querySelector(".topbar h1");

let vendorsCache = [];

const LOCAL_STORAGE_KEY = "billpilot.local.v1";
const useLocalMode =
  window.location.hostname.endsWith("github.io") || window.location.protocol === "file:";

async function api(path, options = {}) {
  if (useLocalMode) {
    return localApi(path, options);
  }

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

function formatMoney(cents) {
  const sign = cents < 0 ? "-" : "";
  const value = Math.abs(cents) / 100;
  return cents % 100 === 0
    ? `${sign}$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
    : `${sign}$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function centsFromAmount(value) {
  const amount = Number(String(value || "0").replace("$", "").replace(",", ""));
  if (Number.isNaN(amount) || amount < 0) {
    throw new Error("Amount must be a positive number.");
  }
  return Math.round(amount * 100);
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysIso(days) {
  const next = new Date();
  next.setDate(next.getDate() + days);
  return next.toISOString().slice(0, 10);
}

function dueLabel(dateText) {
  const today = todayIso();
  const tomorrow = addDaysIso(1);
  if (dateText === today) return "Today";
  if (dateText === tomorrow) return "Tomorrow";
  const date = new Date(`${dateText}T00:00:00`);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function cleanFileName(filename) {
  return filename
    .replace(/\.[^.]+$/, "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .trim();
}

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function detectUploadFields(file) {
  const baseName = cleanFileName(file.name);
  const amountMatch = baseName.match(/(?:\$|amount\s*)?(\d+(?:\.\d{2})?)/i);
  const amount = amountMatch?.[1] || "";
  const vendorName = titleCase(
    baseName
      .replace(/\b(inv|invoice|bill|statement|amount)\b/gi, "")
      .replace(/\d+(?:\.\d{2})?/g, "")
      .replace(/\s+/g, " ")
      .trim() || "Uploaded Vendor",
  );

  return {
    vendorName,
    amount,
    dueDate: addDaysIso(7),
    invoiceNumber: `UPLOAD-${Date.now()}`,
  };
}

function statusLabel(status) {
  const labels = {
    approval_needed: "Approval needed",
    ready_to_pay: "Ready to pay",
    scheduled: "Scheduled",
    autopay_on: "AutoPay on",
    paid: "Paid",
  };
  return labels[status] || status.replaceAll("_", " ");
}

function createSeedData() {
  return {
    nextAccountId: 4,
    nextVendorId: 5,
    nextBillId: 5,
    nextReceiptId: 5,
    accounts: [
      {
        id: 1,
        name: "Operating Checking",
        institution: "Demo Bank",
        accountType: "checking",
        balanceCents: 8426000,
        lastSyncedAt: new Date().toISOString(),
      },
      {
        id: 2,
        name: "Tax Savings",
        institution: "Demo Bank",
        accountType: "savings",
        balanceCents: 1840000,
        lastSyncedAt: new Date().toISOString(),
      },
      {
        id: 3,
        name: "Business Rewards Card",
        institution: "Demo Card",
        accountType: "credit_card",
        balanceCents: -321000,
        lastSyncedAt: new Date().toISOString(),
      },
    ],
    vendors: [
      {
        id: 1,
        name: "City Electric",
        category: "Electric Utility",
        accountNumber: "CE-884921",
        website: "https://example.com/city-electric",
        autopay: false,
        paymentMethod: "Operating Checking",
        schedule: "Pay 2 days early",
        maxPaymentCents: 250000,
      },
      {
        id: 2,
        name: "Metro Water",
        category: "Water",
        accountNumber: "MW-102938",
        website: "https://example.com/metro-water",
        autopay: true,
        paymentMethod: "Operating Checking",
        schedule: "Pay on due date",
        maxPaymentCents: 120000,
      },
      {
        id: 3,
        name: "Frontier Internet",
        category: "Internet",
        accountNumber: "FI-72891",
        website: "https://example.com/frontier-internet",
        autopay: true,
        paymentMethod: "Business Credit Card",
        schedule: "Pay 3 days early",
        maxPaymentCents: 60000,
      },
      {
        id: 4,
        name: "Restaurant Supply Co.",
        category: "Food Supplier",
        accountNumber: "RSC-558201",
        website: "https://example.com/restaurant-supply",
        autopay: false,
        paymentMethod: "Operating Checking",
        schedule: "Manual approval",
        maxPaymentCents: 800000,
      },
    ],
    bills: [
      {
        id: 1,
        vendorId: 1,
        amountCents: 192000,
        dueDate: todayIso(),
        invoice: "INV-4481",
        status: "approval_needed",
        source: "pdf_upload",
      },
      {
        id: 2,
        vendorId: 2,
        amountCents: 92000,
        dueDate: todayIso(),
        invoice: "MW-2026-0708",
        status: "ready_to_pay",
        source: "vendor_portal",
      },
      {
        id: 3,
        vendorId: 4,
        amountCents: 674000,
        dueDate: addDaysIso(2),
        invoice: "RSC-88214",
        status: "scheduled",
        source: "business_email",
      },
      {
        id: 4,
        vendorId: 3,
        amountCents: 41200,
        dueDate: addDaysIso(6),
        invoice: "FI-72891",
        status: "autopay_on",
        source: "vendor_portal",
      },
    ],
    receipts: [
      { id: 1, bill_id: 1, vendor_name: "City Electric", document_type: "Invoice PDF" },
      { id: 2, bill_id: null, vendor_name: "Landlord LLC", document_type: "Payment Confirmation" },
      { id: 3, bill_id: 3, vendor_name: "Restaurant Supply Co.", document_type: "Invoice" },
      { id: 4, bill_id: 2, vendor_name: "Metro Water", document_type: "Statement PDF" },
    ],
  };
}

function getLocalData() {
  const saved = window.localStorage.getItem(LOCAL_STORAGE_KEY);
  if (saved) {
    return JSON.parse(saved);
  }
  const seeded = createSeedData();
  saveLocalData(seeded);
  return seeded;
}

function saveLocalData(data) {
  window.localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(data));
}

function localBillRows(data) {
  return data.bills
    .map((bill) => {
      const vendor = data.vendors.find((item) => item.id === bill.vendorId);
      return {
        id: bill.id,
        vendor: vendor?.name || "Unknown Vendor",
        category: vendor?.category || "Uncategorized",
        amount: formatMoney(bill.amountCents),
        amountCents: bill.amountCents,
        dueDate: bill.dueDate,
        due: dueLabel(bill.dueDate),
        invoice: bill.invoice,
        status: bill.status,
        statusLabel: statusLabel(bill.status),
        source: bill.source,
        warning: bill.status === "approval_needed",
      };
    })
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate) || b.amountCents - a.amountCents);
}

function localDashboard(data) {
  const bills = data.bills;
  const cashCents = data.accounts
    .filter((account) => ["checking", "savings"].includes(account.accountType))
    .reduce((sum, account) => sum + account.balanceCents, 0);
  const weekEnd = addDaysIso(7);
  const dueTodayCents = bills
    .filter((bill) => bill.dueDate === todayIso() && bill.status !== "paid")
    .reduce((sum, bill) => sum + bill.amountCents, 0);
  const dueWeekCents = bills
    .filter((bill) => bill.dueDate >= todayIso() && bill.dueDate <= weekEnd && bill.status !== "paid")
    .reduce((sum, bill) => sum + bill.amountCents, 0);
  const paidCents = bills
    .filter((bill) => bill.status === "paid")
    .reduce((sum, bill) => sum + bill.amountCents, 0);
  const monthlyCents = bills.reduce((sum, bill) => sum + bill.amountCents, 0);

  return {
    cashBalance: formatMoney(cashCents),
    dueToday: formatMoney(dueTodayCents),
    dueThisWeek: formatMoney(dueWeekCents),
    paidBills: formatMoney(paidCents),
    monthlySpending: formatMoney(monthlyCents),
    projectedCashAfterWeek: formatMoney(cashCents - dueWeekCents),
    recommendation:
      "Review approval-needed bills first. Approved bills can be marked paid in demo mode.",
  };
}

async function localApi(path, options = {}) {
  const method = options.method || "GET";
  const data = getLocalData();
  const payload = options.body ? JSON.parse(options.body) : {};

  if (method === "GET" && path === "/api/dashboard") return localDashboard(data);
  if (method === "GET" && path === "/api/bills") return localBillRows(data);
  if (method === "GET" && path === "/api/vendors") {
    return data.vendors
      .map((vendor) => ({ ...vendor, limit: formatMoney(vendor.maxPaymentCents) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }
  if (method === "GET" && path === "/api/receipts") return data.receipts;

  if (method === "POST" && path === "/api/vendors") {
    const vendor = {
      id: data.nextVendorId++,
      name: payload.companyName,
      category: payload.category,
      accountNumber: payload.accountNumber || "Manual",
      website: payload.website || "https://example.com",
      autopay: false,
      paymentMethod: payload.paymentMethod || "Operating Checking",
      schedule: payload.paymentSchedule || "Manual approval",
      maxPaymentCents: centsFromAmount(payload.maxPayment || 0),
    };
    data.vendors.push(vendor);
    saveLocalData(data);
    return { ok: true, vendorId: vendor.id };
  }

  if (method === "POST" && path === "/api/bills") {
    const bill = {
      id: data.nextBillId++,
      vendorId: Number(payload.vendorId),
      amountCents: centsFromAmount(payload.amount),
      dueDate: payload.dueDate,
      invoice: payload.invoiceNumber,
      status: payload.status || "approval_needed",
      source: "manual_entry",
    };
    data.bills.push(bill);
    saveLocalData(data);
    return { ok: true, billId: bill.id };
  }

  if (method === "POST" && path === "/api/accounts") {
    const account = {
      id: data.nextAccountId++,
      name: payload.name,
      institution: payload.institution,
      accountType: payload.accountType,
      balanceCents: centsFromAmount(payload.balance),
      lastSyncedAt: new Date().toISOString(),
    };
    data.accounts.push(account);
    saveLocalData(data);
    return { ok: true, accountId: account.id };
  }

  if (method === "POST" && path === "/api/pay-approved") {
    const payable = data.bills.filter((bill) =>
      ["ready_to_pay", "scheduled", "autopay_on"].includes(bill.status),
    );
    const totalPaid = payable.reduce((sum, bill) => sum + bill.amountCents, 0);
    payable.forEach((bill) => {
      bill.status = "paid";
      const vendor = data.vendors.find((item) => item.id === bill.vendorId);
      data.receipts.unshift({
        id: data.nextReceiptId++,
        bill_id: bill.id,
        vendor_name: vendor?.name || "Unknown Vendor",
        document_type: "Payment Confirmation",
      });
    });
    const account = data.accounts.find((item) => ["checking", "savings"].includes(item.accountType));
    if (account) account.balanceCents -= totalPaid;
    saveLocalData(data);
    return { ok: true, paidCount: payable.length, totalPaid: formatMoney(totalPaid) };
  }

  if (method === "POST" && path === "/api/bill-detections") {
    const vendorName = payload.vendorName || titleCase(cleanFileName(payload.filename || "Uploaded Invoice"));
    let vendor = data.vendors.find((item) => item.name.toLowerCase() === vendorName.toLowerCase());
    if (!vendor) {
      vendor = {
        id: data.nextVendorId++,
        name: vendorName,
        category: "Uploaded Invoice",
        accountNumber: "Detected",
        website: "https://example.com",
        autopay: false,
        paymentMethod: "Operating Checking",
        schedule: "Manual approval",
        maxPaymentCents: 500000,
      };
      data.vendors.push(vendor);
    }
    const bill = {
      id: data.nextBillId++,
      vendorId: vendor.id,
      amountCents: centsFromAmount(payload.amount || 250),
      dueDate: payload.dueDate || addDaysIso(7),
      invoice: payload.invoiceNumber || `UPLOAD-${Date.now()}`,
      status: "approval_needed",
      source: "pdf_upload",
    };
    data.bills.push(bill);
    data.receipts.unshift({
      id: data.nextReceiptId++,
      bill_id: bill.id,
      vendor_name: vendor.name,
      document_type: "Uploaded Invoice",
    });
    saveLocalData(data);
    return { ok: true, billId: bill.id, vendor: vendor.name, amount: formatMoney(bill.amountCents) };
  }

  const autopayMatch = path.match(/^\/api\/vendors\/(\d+)\/autopay$/);
  if (method === "POST" && autopayMatch) {
    const vendor = data.vendors.find((item) => item.id === Number(autopayMatch[1]));
    if (!vendor) throw new Error("Vendor not found.");
    vendor.autopay = Boolean(payload.enabled);
    saveLocalData(data);
    return { ok: true, vendorId: vendor.id, autopay: vendor.autopay };
  }

  const payMatch = path.match(/^\/api\/bills\/(\d+)\/pay$/);
  if (method === "POST" && payMatch) {
    const bill = data.bills.find((item) => item.id === Number(payMatch[1]));
    if (!bill) throw new Error("Bill not found.");
    if (bill.status !== "paid") {
      const account = data.accounts.find((item) => ["checking", "savings"].includes(item.accountType));
      if (account) account.balanceCents -= bill.amountCents;
      const vendor = data.vendors.find((item) => item.id === bill.vendorId);
      data.receipts.unshift({
        id: data.nextReceiptId++,
        bill_id: bill.id,
        vendor_name: vendor?.name || "Unknown Vendor",
        document_type: "Payment Confirmation",
      });
    }
    bill.status = "paid";
    saveLocalData(data);
    return { ok: true, billId: bill.id, status: "paid" };
  }

  if (method === "POST" && path === "/api/assistant") {
    const question = String(payload.question || "").toLowerCase();
    const bills = localBillRows(data);
    if (question.includes("unpaid") || question.includes("invoice")) {
      const unpaid = bills.filter((bill) => bill.status !== "paid");
      const total = unpaid.reduce((sum, bill) => sum + bill.amountCents, 0);
      return { answer: `There are ${unpaid.length} unpaid invoice(s), totaling ${formatMoney(total)}.` };
    }
    if (question.includes("cash")) {
      const dashboard = localDashboard(data);
      return {
        answer: `Current cash is ${dashboard.cashBalance}. After this week's unpaid bills, projected cash is ${dashboard.projectedCashAfterWeek}.`,
      };
    }
    if (question.includes("utility")) {
      const utilityTotal = bills
        .filter((bill) => /utility|water|internet|gas|phone/i.test(bill.category))
        .reduce((sum, bill) => sum + bill.amountCents, 0);
      return { answer: `Utility spend currently tracked is ${formatMoney(utilityTotal)}.` };
    }
    return {
      answer:
        "I can answer questions about unpaid invoices, utility spend, due dates, projected cash, vendor limits, and receipt records.",
    };
  }

  throw new Error("This action is not available.");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3200);
}

function showPage(pageId, updateHash = true) {
  const page = document.querySelector(`#${pageId}`);
  if (!page) {
    return;
  }

  appPages.forEach((item) => item.classList.toggle("active-page", item.id === pageId));
  navLinks.forEach((link) => link.classList.toggle("active", link.dataset.page === pageId));

  topbarEyebrow.textContent = page.dataset.title || "BillPilot AI";
  topbarHeading.textContent = page.dataset.heading || "Manage bills, cash, vendors, and payments.";

  if (updateHash) {
    const activeLink = [...navLinks].find((link) => link.dataset.page === pageId);
    if (activeLink) {
      window.history.replaceState(null, "", activeLink.getAttribute("href"));
    }
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
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

navLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    showPage(link.dataset.page);
  });
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
  showPage("settings-page");
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

invoiceUpload.addEventListener("change", () => {
  const file = invoiceUpload.files[0];
  if (!file) {
    return;
  }

  const detected = detectUploadFields(file);
  uploadReviewForm.elements.filename.value = file.name;
  uploadReviewForm.elements.vendorName.value = detected.vendorName;
  uploadReviewForm.elements.amount.value = detected.amount;
  uploadReviewForm.elements.dueDate.value = detected.dueDate;
  uploadReviewForm.elements.invoiceNumber.value = detected.invoiceNumber;
  uploadReviewForm.classList.remove("hidden");
  uploadReviewForm.elements.vendorName.focus();
  showToast("Review the detected bill details, then save.");
});

cancelUploadButton.addEventListener("click", () => {
  uploadReviewForm.reset();
  uploadReviewForm.classList.add("hidden");
  invoiceUpload.value = "";
});

uploadReviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = uploadReviewForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  const formData = new FormData(uploadReviewForm);

  try {
    const response = await api("/api/bill-detections", {
      method: "POST",
      body: JSON.stringify({
        filename: formData.get("filename"),
        vendorName: formData.get("vendorName"),
        amount: formData.get("amount"),
        dueDate: formData.get("dueDate"),
        invoiceNumber: formData.get("invoiceNumber"),
      }),
    });
    await loadApp();
    uploadReviewForm.reset();
    uploadReviewForm.classList.add("hidden");
    invoiceUpload.value = "";
    showToast(`Saved ${response.vendor} invoice for ${response.amount}.`);
  } catch (error) {
    showToast(error.message);
  } finally {
    submitButton.disabled = false;
  }
});

loadApp().catch(() => {
  addMessage("Start the backend with python3 server.py to load live BillPilot data.", "bot");
});

const initialLink = [...navLinks].find((link) => link.getAttribute("href") === window.location.hash);
showPage(initialLink?.dataset.page || "dashboard-page", false);
