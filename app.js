const state = {
  categories: [],
  items: [],
  tvs: [],
  activeTvId: null,
  activeDisplay: null,
};

const adminApp = document.querySelector("#adminApp");
const displayApp = document.querySelector("#displayApp");
const toast = document.querySelector("#toast");
const activeTvSelect = document.querySelector("#activeTvSelect");
const activeTvLink = document.querySelector("#activeTvLink");
const openDisplayLink = document.querySelector("#openDisplayLink");
const pageEyebrow = document.querySelector("#pageEyebrow");
const pageHeading = document.querySelector("#pageHeading");

const menuItemForm = document.querySelector("#menuItemForm");
const categoryForm = document.querySelector("#categoryForm");
const tvForm = document.querySelector("#tvForm");
const designForm = document.querySelector("#designForm");

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

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
    throw new Error(payload.error || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 2200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function categoryName(id) {
  return state.categories.find((category) => category.id === id)?.name || "Uncategorized";
}

function getActiveTv() {
  return state.tvs.find((tv) => tv.id === state.activeTvId) || state.tvs[0];
}

async function loadAdminData() {
  const [categories, items, tvs] = await Promise.all([
    api("/api/categories"),
    api("/api/menu-items"),
    api("/api/tv-screens"),
  ]);

  state.categories = categories;
  state.items = items;
  state.tvs = tvs;

  if (!state.activeTvId || !state.tvs.some((tv) => tv.id === state.activeTvId)) {
    state.activeTvId = state.tvs[0]?.id || null;
  }

  renderAdmin();
}

function renderAdmin() {
  renderTvSelect();
  renderDashboard();
  renderMenuItems();
  renderCategoryChoices();
  renderCategories();
  renderTvScreens();
  renderTvFormChoices();
  loadDesignForm();
  renderPreviews();
}

function renderTvSelect() {
  activeTvSelect.innerHTML = state.tvs
    .map((tv) => `<option value="${tv.id}" ${tv.id === state.activeTvId ? "selected" : ""}>${escapeHtml(tv.name)}</option>`)
    .join("");

  const tv = getActiveTv();
  if (!tv) {
    activeTvLink.textContent = "No TV yet";
    openDisplayLink.removeAttribute("href");
    return;
  }

  const url = `/display/${tv.slug}`;
  activeTvLink.textContent = tv.name;
  openDisplayLink.href = url;
}

function renderDashboard() {
  document.querySelector("#itemCount").textContent = state.items.length;
  document.querySelector("#categoryCount").textContent = state.categories.length;
  document.querySelector("#tvCount").textContent = state.tvs.length;
  document.querySelector("#soldOutCount").textContent = state.items.filter((item) => !item.available).length;

  document.querySelector("#dashboardItemList").innerHTML = state.items
    .slice(0, 8)
    .map(
      (item) => `
        <div>
          <strong>${escapeHtml(item.name)} <span class="price">${money.format(item.price)}</span></strong>
          <span>${escapeHtml(categoryName(item.category_id))} - ${item.available ? "In stock" : "Out of stock"}</span>
        </div>
      `,
    )
    .join("");
}

function renderCategoryChoices() {
  const select = menuItemForm.elements.category_id;
  select.innerHTML = state.categories
    .map((category) => `<option value="${category.id}">${escapeHtml(category.name)}</option>`)
    .join("");
}

function renderMenuItems() {
  document.querySelector("#menuItemList").innerHTML = state.items
    .map(
      (item) => `
        <article class="menu-row">
          ${
            item.image_url
              ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}">`
              : `<div class="placeholder-img">Menu</div>`
          }
          <div>
            <div class="item-title">
              <strong>${escapeHtml(item.name)}</strong>
              <span class="price">${money.format(item.price)}</span>
              <span class="pill ${item.available ? "ok" : "sold"}">${item.available ? "In stock" : "Sold out"}</span>
            </div>
            <p class="item-meta">${escapeHtml(categoryName(item.category_id))} - Sort ${item.sort_order}</p>
            <p>${escapeHtml(item.description || "")}</p>
          </div>
          <div class="row-actions">
            <button class="secondary" data-action="edit-item" data-id="${item.id}">Edit</button>
            <button class="secondary" data-action="toggle-stock" data-id="${item.id}">${item.available ? "Mark out" : "Restock"}</button>
            <button data-action="delete-item" data-id="${item.id}">Delete</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderCategories() {
  document.querySelector("#categoryList").innerHTML = state.categories
    .map(
      (category) => `
        <div>
          <strong>${escapeHtml(category.name)}</strong>
          <span>Sort order ${category.sort_order}</span>
          <div class="row-actions">
            <button class="secondary" data-action="edit-category" data-id="${category.id}">Edit</button>
            <button data-action="delete-category" data-id="${category.id}">Delete</button>
          </div>
        </div>
      `,
    )
    .join("");
}

function renderTvFormChoices(tv = null) {
  const assignedCategories = new Set(tv?.category_ids || []);
  const pinnedItems = new Set(tv?.item_ids || []);

  document.querySelector("#tvCategoryChoices").innerHTML = state.categories
    .map(
      (category) => `
        <label>
          <input type="checkbox" name="category_ids" value="${category.id}" ${assignedCategories.has(category.id) ? "checked" : ""}>
          ${escapeHtml(category.name)}
        </label>
      `,
    )
    .join("");

  document.querySelector("#tvItemChoices").innerHTML = state.items
    .map(
      (item) => `
        <label>
          <input type="checkbox" name="item_ids" value="${item.id}" ${pinnedItems.has(item.id) ? "checked" : ""}>
          ${escapeHtml(item.name)}
        </label>
      `,
    )
    .join("");
}

function renderTvScreens() {
  document.querySelector("#tvScreenList").innerHTML = state.tvs
    .map(
      (tv) => `
        <article class="tv-card">
          <div class="tv-card-head">
            <div>
              <strong>${escapeHtml(tv.name)}</strong>
              <div class="tv-url">${window.location.origin}/display/${escapeHtml(tv.slug)}</div>
            </div>
            <span class="pill ${tv.show_images ? "ok" : "sold"}">${tv.show_images ? "Images on" : "Images off"}</span>
          </div>
          <p class="muted">${tv.category_ids.length || "All"} categories assigned, ${tv.item_ids.length} pinned items.</p>
          <div class="row-actions">
            <button class="secondary" data-action="select-tv" data-id="${tv.id}">Select</button>
            <button class="secondary" data-action="edit-tv" data-id="${tv.id}">Edit</button>
            <a class="button secondary" href="/display/${tv.slug}" target="_blank" rel="noreferrer">Open</a>
            <button data-action="delete-tv" data-id="${tv.id}">Delete</button>
          </div>
        </article>
      `,
    )
    .join("");
}

async function loadDesignForm() {
  const tv = getActiveTv();
  if (!tv) return;

  const settings = await api(`/api/tv-screens/${tv.id}/settings`);
  for (const [key, value] of Object.entries(settings)) {
    if (designForm.elements[key]) {
      designForm.elements[key].value = value ?? "";
    }
  }
}

async function getDisplayDataForActiveTv() {
  const tv = getActiveTv();
  if (!tv) return null;
  return api(`/api/display/${tv.slug}`);
}

async function renderPreviews() {
  const displayData = await getDisplayDataForActiveTv();
  if (!displayData) return;

  document.querySelector("#designPreview").innerHTML = renderTvMenu(displayData, true);
  document.querySelector("#mainPreview").innerHTML = renderTvMenu(displayData, true);
}

function groupDisplayItems(displayData) {
  const groups = displayData.categories.map((category) => ({ ...category, items: [] }));
  const groupById = new Map(groups.map((group) => [group.id, group]));
  const fallback = { id: "uncategorized", name: "Other", items: [] };

  for (const item of displayData.items) {
    const group = groupById.get(item.category_id) || fallback;
    group.items.push(item);
  }

  return fallback.items.length ? [...groups, fallback] : groups;
}

function renderTvMenu(displayData, compact = false) {
  const { tv, settings } = displayData;
  const groups = groupDisplayItems(displayData).filter((group) => group.items.length);
  const titleSize = Math.max(28, compact ? settings.title_size * 0.62 : settings.title_size);
  const itemSize = Math.max(16, compact ? settings.item_size * 0.72 : settings.item_size);
  const priceSize = Math.max(16, compact ? settings.price_size * 0.72 : settings.price_size);
  const bgImage = settings.background_image_url ? `background-image: url('${escapeHtml(settings.background_image_url)}');` : "";

  return `
    <div class="tv-menu" style="background-color:${escapeHtml(settings.background_color)}; color:${escapeHtml(settings.text_color)}; ${bgImage}">
      <header class="tv-header" style="color:${escapeHtml(settings.accent_color)}">
        <div>
          <h1 style="font-size:${titleSize}px">${escapeHtml(settings.restaurant_name)}</h1>
          <p>${escapeHtml(tv.name)}</p>
        </div>
        ${settings.logo_url ? `<img class="tv-logo" src="${escapeHtml(settings.logo_url)}" alt="${escapeHtml(settings.restaurant_name)} logo">` : ""}
      </header>
      <div class="tv-grid-menu">
        ${
          groups.length
            ? groups
                .map(
                  (group) => `
                    <section class="tv-category">
                      <h2 style="color:${escapeHtml(settings.accent_color)}; font-size:${itemSize * 1.12}px">${escapeHtml(group.name)}</h2>
                      ${group.items
                        .map((item) => renderTvItem(item, tv, settings, itemSize, priceSize))
                        .join("")}
                    </section>
                  `,
                )
                .join("")
            : `<section class="tv-category"><h2>No menu items assigned yet</h2></section>`
        }
      </div>
    </div>
  `;
}

function renderTvItem(item, tv, settings, itemSize, priceSize) {
  const showImage = tv.show_images && item.image_url;
  return `
    <article class="tv-item ${showImage ? "" : "no-image"} ${item.available ? "" : "sold-out"}">
      ${showImage ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}">` : ""}
      <div>
        <h3 style="font-size:${itemSize}px">${escapeHtml(item.name)} ${item.available ? "" : `<span class="sold-badge">Sold out</span>`}</h3>
        ${item.description ? `<p style="font-size:${Math.max(14, itemSize * 0.58)}px">${escapeHtml(item.description)}</p>` : ""}
      </div>
      <strong style="color:${escapeHtml(settings.price_color)}; font-size:${priceSize}px">${money.format(item.price)}</strong>
    </article>
  `;
}

function serializeMenuItemForm() {
  return {
    name: menuItemForm.elements.name.value.trim(),
    description: menuItemForm.elements.description.value.trim(),
    category_id: menuItemForm.elements.category_id.value,
    price: Number(menuItemForm.elements.price.value),
    image_url: menuItemForm.elements.image_url.value.trim(),
    sort_order: Number(menuItemForm.elements.sort_order.value || 0),
    available: menuItemForm.elements.available.checked,
  };
}

function serializeCategoryForm() {
  return {
    name: categoryForm.elements.name.value.trim(),
    sort_order: Number(categoryForm.elements.sort_order.value || 0),
  };
}

function serializeTvForm() {
  const categoryIds = [...tvForm.querySelectorAll("[name='category_ids']:checked")].map((input) => input.value);
  const itemIds = [...tvForm.querySelectorAll("[name='item_ids']:checked")].map((input) => input.value);
  return {
    name: tvForm.elements.name.value.trim(),
    slug: slugify(tvForm.elements.slug.value || tvForm.elements.name.value),
    show_images: tvForm.elements.show_images.checked,
    show_sold_out: tvForm.elements.show_sold_out.checked,
    category_ids: categoryIds,
    item_ids: itemIds,
  };
}

function serializeDesignForm() {
  return {
    restaurant_name: designForm.elements.restaurant_name.value.trim(),
    background_color: designForm.elements.background_color.value,
    text_color: designForm.elements.text_color.value,
    accent_color: designForm.elements.accent_color.value,
    price_color: designForm.elements.price_color.value,
    title_size: Number(designForm.elements.title_size.value),
    item_size: Number(designForm.elements.item_size.value),
    price_size: Number(designForm.elements.price_size.value),
    logo_url: designForm.elements.logo_url.value.trim(),
    background_image_url: designForm.elements.background_image_url.value.trim(),
  };
}

function resetMenuForm() {
  menuItemForm.reset();
  menuItemForm.elements.id.value = "";
  menuItemForm.elements.available.checked = true;
  menuItemForm.elements.sort_order.value = "0";
  document.querySelector("#menuFormTitle").textContent = "New Item";
}

function resetCategoryForm() {
  categoryForm.reset();
  categoryForm.elements.id.value = "";
  categoryForm.elements.sort_order.value = "0";
  document.querySelector("#categoryFormTitle").textContent = "New Category";
}

function resetTvForm() {
  tvForm.reset();
  tvForm.elements.id.value = "";
  tvForm.elements.show_images.checked = true;
  tvForm.elements.show_sold_out.checked = true;
  renderTvFormChoices();
  document.querySelector("#tvFormTitle").textContent = "New TV";
}

document.body.addEventListener("click", async (event) => {
  const trigger = event.target.closest("[data-action]");
  if (!trigger) return;

  const { action, id } = trigger.dataset;

  try {
    if (action === "edit-item") {
      const item = state.items.find((entry) => entry.id === id);
      menuItemForm.elements.id.value = item.id;
      menuItemForm.elements.name.value = item.name;
      menuItemForm.elements.description.value = item.description || "";
      menuItemForm.elements.category_id.value = item.category_id;
      menuItemForm.elements.price.value = item.price;
      menuItemForm.elements.image_url.value = item.image_url || "";
      menuItemForm.elements.sort_order.value = item.sort_order;
      menuItemForm.elements.available.checked = item.available;
      document.querySelector("#menuFormTitle").textContent = "Edit Item";
    }

    if (action === "toggle-stock") {
      const item = state.items.find((entry) => entry.id === id);
      await api(`/api/menu-items/${id}/stock`, {
        method: "PATCH",
        body: JSON.stringify({ available: !item.available }),
      });
      showToast("Stock updated");
      await loadAdminData();
    }

    if (action === "delete-item" && window.confirm("Delete this menu item?")) {
      await api(`/api/menu-items/${id}`, { method: "DELETE" });
      showToast("Menu item deleted");
      await loadAdminData();
    }

    if (action === "edit-category") {
      const category = state.categories.find((entry) => entry.id === id);
      categoryForm.elements.id.value = category.id;
      categoryForm.elements.name.value = category.name;
      categoryForm.elements.sort_order.value = category.sort_order;
      document.querySelector("#categoryFormTitle").textContent = "Edit Category";
    }

    if (action === "delete-category" && window.confirm("Delete this category? Menu items in it will become uncategorized.")) {
      await api(`/api/categories/${id}`, { method: "DELETE" });
      showToast("Category deleted");
      await loadAdminData();
    }

    if (action === "select-tv") {
      state.activeTvId = id;
      renderAdmin();
    }

    if (action === "edit-tv") {
      const tv = state.tvs.find((entry) => entry.id === id);
      state.activeTvId = id;
      tvForm.elements.id.value = tv.id;
      tvForm.elements.name.value = tv.name;
      tvForm.elements.slug.value = tv.slug;
      tvForm.elements.show_images.checked = tv.show_images;
      tvForm.elements.show_sold_out.checked = tv.show_sold_out;
      renderTvFormChoices(tv);
      document.querySelector("#tvFormTitle").textContent = "Edit TV";
      renderAdmin();
    }

    if (action === "delete-tv" && window.confirm("Delete this TV profile?")) {
      await api(`/api/tv-screens/${id}`, { method: "DELETE" });
      showToast("TV deleted");
      await loadAdminData();
    }
  } catch (error) {
    showToast(error.message);
  }
});

menuItemForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = menuItemForm.elements.id.value;
  await api(id ? `/api/menu-items/${id}` : "/api/menu-items", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(serializeMenuItemForm()),
  });
  resetMenuForm();
  showToast("Menu item saved");
  await loadAdminData();
});

categoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = categoryForm.elements.id.value;
  await api(id ? `/api/categories/${id}` : "/api/categories", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(serializeCategoryForm()),
  });
  resetCategoryForm();
  showToast("Category saved");
  await loadAdminData();
});

tvForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = tvForm.elements.id.value;
  const saved = await api(id ? `/api/tv-screens/${id}` : "/api/tv-screens", {
    method: id ? "PUT" : "POST",
    body: JSON.stringify(serializeTvForm()),
  });
  state.activeTvId = saved.id;
  resetTvForm();
  showToast("TV profile saved");
  await loadAdminData();
});

designForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const tv = getActiveTv();
  if (!tv) return;

  await api(`/api/tv-screens/${tv.id}/settings`, {
    method: "PUT",
    body: JSON.stringify(serializeDesignForm()),
  });
  showToast("Design saved");
  await renderPreviews();
});

document.querySelector("#resetMenuForm").addEventListener("click", resetMenuForm);
document.querySelector("#resetCategoryForm").addEventListener("click", resetCategoryForm);
document.querySelector("#resetTvForm").addEventListener("click", resetTvForm);

activeTvSelect.addEventListener("change", async () => {
  state.activeTvId = activeTvSelect.value;
  renderTvSelect();
  await loadDesignForm();
  await renderPreviews();
});

document.querySelectorAll(".nav-list a[data-page]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const page = link.dataset.page;
    document.querySelectorAll(".nav-list a").forEach((entry) => entry.classList.toggle("active", entry === link));
    document.querySelectorAll(".app-page").forEach((entry) => entry.classList.toggle("active-page", entry.id === `${page}-page`));
    const pageElement = document.querySelector(`#${page}-page`);
    pageEyebrow.textContent = pageElement.dataset.title;
    pageHeading.textContent = pageElement.dataset.heading;
    window.location.hash = page;
  });
});

menuItemForm.elements.name.addEventListener("input", () => {
  if (!menuItemForm.elements.sort_order.value) {
    menuItemForm.elements.sort_order.value = String(state.items.length + 1);
  }
});

tvForm.elements.name.addEventListener("input", () => {
  if (!tvForm.elements.id.value) {
    tvForm.elements.slug.value = slugify(tvForm.elements.name.value);
  }
});

async function loadDisplayRoute(slug) {
  adminApp.classList.add("hidden");
  displayApp.classList.remove("hidden");
  document.body.classList.add("display-mode");

  async function refresh() {
    try {
      state.activeDisplay = await api(`/api/display/${slug}`);
      document.title = `${state.activeDisplay.tv.name} - TV Menu`;
      displayApp.innerHTML = renderTvMenu(state.activeDisplay);
    } catch (error) {
      displayApp.innerHTML = `<div class="tv-menu"><h1>Display not found</h1><p>${escapeHtml(error.message)}</p></div>`;
    }
  }

  await refresh();
  window.setInterval(refresh, 8000);
}

async function boot() {
  const displayMatch = window.location.pathname.match(/^\/display\/([^/]+)$/);
  if (displayMatch) {
    await loadDisplayRoute(displayMatch[1]);
    return;
  }

  await loadAdminData();
  const hash = window.location.hash.replace("#", "");
  if (hash) {
    document.querySelector(`.nav-list a[data-page="${hash}"]`)?.click();
  }
}

boot().catch((error) => showToast(error.message));
