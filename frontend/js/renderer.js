/**
 * All rendering functions operate on #result-section and its children.
 * They are pure DOM manipulation — no fetch calls here.
 */

const resultSection = () => document.getElementById("result-section");
const loadingState = () => document.getElementById("loading-state");
const errorState = () => document.getElementById("error-state");
const successState = () => document.getElementById("success-state");
const menuOutput = () => document.getElementById("menu-output");
const errorMessage = () => document.getElementById("error-message");

function showSection(section) {
  resultSection().hidden = false;
  loadingState().hidden = true;
  errorState().hidden = true;
  successState().hidden = true;
  if (section) section.hidden = false;
}

/** Show a CSS spinner while the API call is in progress. */
export function renderLoading() {
  showSection(loadingState());
}

/**
 * Show an error message with a retry button.
 *
 * @param {string} message
 * @param {() => void} onRetry
 */
export function renderError(message, onRetry) {
  errorMessage().textContent = message;
  showSection(errorState());

  const retryBtn = document.getElementById("retry-btn");
  // Replace to clear any previous listener
  const fresh = retryBtn.cloneNode(true);
  retryBtn.replaceWith(fresh);
  fresh.addEventListener("click", () => {
    clearResult();
    onRetry();
  });
}

/** Show a "no items found" placeholder inside the success frame. */
export function renderEmpty() {
  menuOutput().innerHTML = `<p class="menu-empty">No menu items could be extracted from this file.</p>`;
  showSection(successState());
}

/** Reset back to upload-only state (hide result section). */
export function clearResult() {
  resultSection().hidden = true;
  menuOutput().innerHTML = "";
  loadingState().hidden = true;
  errorState().hidden = true;
  successState().hidden = true;
}

/**
 * Build and display the full digital menu from a MenuResponse object.
 *
 * @param {object} data  — MenuResponse
 */
export function renderMenu(data) {
  const card = document.createElement("div");
  card.className = "menu-card";

  // Header
  const header = document.createElement("div");
  header.className = "menu-card__header";

  const nameEl = document.createElement("h2");
  nameEl.className = "menu-card__restaurant";
  nameEl.textContent = data.restaurant_name || "Restaurant Menu";
  header.appendChild(nameEl);

  const meta = document.createElement("div");
  meta.className = "menu-card__meta";

  if (data.detected_language) {
    const langBadge = document.createElement("span");
    langBadge.className = "badge";
    langBadge.textContent =
      data.language_code
        ? `${data.detected_language} (${data.language_code})`
        : data.detected_language;
    meta.appendChild(langBadge);
  }

  const totalItems = (data.categories || []).reduce(
    (sum, cat) => sum + (cat.items ? cat.items.length : 0),
    0
  );
  if (totalItems > 0) {
    const countBadge = document.createElement("span");
    countBadge.className = "badge";
    countBadge.textContent = `${totalItems} item${totalItems !== 1 ? "s" : ""}`;
    meta.appendChild(countBadge);
  }

  header.appendChild(meta);
  card.appendChild(header);

  // Categories
  const categories = data.categories || [];
  if (categories.length === 0) {
    const empty = document.createElement("p");
    empty.className = "menu-empty";
    empty.textContent = "No menu items found.";
    card.appendChild(empty);
  } else {
    for (const category of categories) {
      card.appendChild(buildCategory(category));
    }
  }

  menuOutput().innerHTML = "";
  menuOutput().appendChild(card);
  showSection(successState());
}

function buildCategory(category) {
  const section = document.createElement("section");
  section.className = "menu-category";

  const heading = document.createElement("h3");
  heading.className = "menu-category__heading";
  heading.textContent = category.name;
  section.appendChild(heading);

  for (const item of category.items || []) {
    section.appendChild(buildItem(item));
  }

  return section;
}

function buildItem(item) {
  const div = document.createElement("div");
  div.className = "menu-item";

  const info = document.createElement("div");
  info.className = "menu-item__info";

  if (item.name_original && item.name_english) {
    // Bilingual: show original as primary, english as secondary
    const nameOriginal = document.createElement("p");
    nameOriginal.className = "menu-item__name-original";
    nameOriginal.textContent = item.name_original;
    info.appendChild(nameOriginal);

    const nameEn = document.createElement("p");
    nameEn.className = "menu-item__name-english";
    nameEn.textContent = item.name_english;
    info.appendChild(nameEn);
  } else if (item.name_english) {
    // English-only: show as primary
    const nameOriginal = document.createElement("p");
    nameOriginal.className = "menu-item__name-original";
    nameOriginal.textContent = item.name_english;
    info.appendChild(nameOriginal);
  } else if (item.name_original) {
    // Non-English only (edge case)
    const nameOriginal = document.createElement("p");
    nameOriginal.className = "menu-item__name-original";
    nameOriginal.textContent = item.name_original;
    info.appendChild(nameOriginal);
  }

  if (item.description) {
    const desc = document.createElement("p");
    desc.className = "menu-item__description";
    desc.textContent = item.description;
    info.appendChild(desc);
  }

  const allTags = item.tags || [];
  const allSizes = item.sizes || [];
  if (allTags.length > 0 || allSizes.length > 0) {
    const tagsEl = document.createElement("div");
    tagsEl.className = "menu-item__tags";

    const TAG_CONFIG = {
      "gluten-free": { label: "Gluten-Free", cls: "tag--gluten-free" },
      "spicy":       { label: "Spicy",       cls: "tag--spicy"       },
      "caffeine":    { label: "Caffeine",    cls: "tag--caffeine"    },
      "hot":         { label: "Hot",         cls: "tag--hot"         },
      "cold":        { label: "Cold",        cls: "tag--cold"        },
    };

    for (const tag of allTags) {
      const cfg = TAG_CONFIG[tag.toLowerCase()];
      if (!cfg) continue;
      const span = document.createElement("span");
      span.className = `tag ${cfg.cls}`;
      span.textContent = cfg.label;
      tagsEl.appendChild(span);
    }

    for (const size of allSizes) {
      const span = document.createElement("span");
      span.className = "tag tag--size";
      span.textContent = size;
      tagsEl.appendChild(span);
    }

    info.appendChild(tagsEl);
  }

  div.appendChild(info);

  if (item.price !== null && item.price !== undefined) {
    const priceEl = document.createElement("div");
    priceEl.className = "menu-item__price";
    priceEl.textContent = formatPrice(item.price, item.currency);
    div.appendChild(priceEl);
  }

  return div;
}

function formatPrice(price, currency) {
  if (!currency) {
    return price.toFixed(2);
  }
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(price);
  } catch {
    return `${price} ${currency}`;
  }
}
