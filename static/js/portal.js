function bindImagePreview(input, imgEl, wrapEl) {
  if (!input || !imgEl) return;
  input.addEventListener("change", () => {
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      imgEl.src = e.target.result;
      imgEl.style.display = "block";
      if (wrapEl) wrapEl.style.display = "block";
    };
    reader.readAsDataURL(file);
  });
}

function bindEventDateValidation(form) {
  if (!form) return;
  const starts = form.querySelector('[name="starts_at"]');
  const ends = form.querySelector('[name="ends_at"]');
  if (!starts || !ends) return;

  const syncConstraints = () => {
    if (starts.value) {
      ends.min = starts.value;
    } else {
      ends.removeAttribute("min");
    }
  };

  const validateRange = () => {
    if (!starts.value || !ends.value) return true;
    const startMs = new Date(starts.value).getTime();
    const endMs = new Date(ends.value).getTime();
    if (Number.isNaN(startMs) || Number.isNaN(endMs)) return true;
    if (endMs < startMs) {
      ends.setCustomValidity("End cannot be before start (same day: end time must be after start time).");
      return false;
    }
    ends.setCustomValidity("");
    return true;
  };

  starts.addEventListener("change", () => {
    syncConstraints();
    validateRange();
  });
  ends.addEventListener("change", validateRange);
  ends.addEventListener("input", validateRange);
  form.addEventListener("submit", (e) => {
    syncConstraints();
    if (!validateRange()) {
      e.preventDefault();
      ends.reportValidity();
    }
  });
  syncConstraints();
}

const eventModal = document.getElementById("portal-event-modal");
const eventForm = document.getElementById("portal-event-form");
const eventModalTitle = document.getElementById("portal-event-modal-title");
const eventIdInput = document.getElementById("portal-event-id");
const posterPreview = document.getElementById("event-poster-preview");
const posterPreviewWrap = document.getElementById("event-poster-preview-wrap");
const posterInput = eventForm?.querySelector('[name="poster"]');

bindEventDateValidation(eventForm);

function openEventModal(mode = "add", data = {}) {
  if (!eventModal) return;
  eventModal.classList.remove("hidden");
  eventModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  eventModalTitle.textContent = mode === "edit" ? "Edit event" : "Add event";
  eventIdInput.value = data.id || "";

  const map = {
    title: "title",
    description: "description",
    venue: "venue",
    location: "location",
    category: "category",
    starts_at: "starts",
    ends_at: "ends",
    ticket_price: "price",
    available_seats: "seats",
    slots_left: "slots",
    status: "status",
    lineup: "lineup",
  };
  Object.entries(map).forEach(([field, key]) => {
    const el = eventForm.querySelector(`[name="${field}"]`);
    if (!el) return;
    if (el.type === "checkbox") el.checked = data.featured === true || data.featured === "1";
    else if (data[key] !== undefined) el.value = data[key];
  });

  const ends = eventForm.querySelector('[name="ends_at"]');
  const starts = eventForm.querySelector('[name="starts_at"]');
  if (starts?.value) ends.min = starts.value;

  if (data.poster && posterPreview) {
    posterPreview.src = data.poster;
    posterPreview.style.display = "block";
    if (posterPreviewWrap) posterPreviewWrap.style.display = "block";
  } else if (posterPreview) {
    posterPreview.src = "";
    posterPreview.style.display = "none";
    if (posterPreviewWrap) posterPreviewWrap.style.display = "none";
  }
}

function closeEventModal() {
  if (!eventModal) return;
  eventModal.classList.add("hidden");
  eventModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  eventForm?.reset();
  eventIdInput.value = "";
}

document.querySelectorAll("[data-open-event-modal]").forEach((btn) => {
  btn.addEventListener("click", () => openEventModal("add"));
});

eventModal?.querySelectorAll("[data-portal-modal-close]").forEach((el) => {
  el.addEventListener("click", closeEventModal);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeEventModal();
});

bindImagePreview(posterInput, posterPreview, posterPreviewWrap);

const logoInput = document.querySelector('[name="logo"]');
const logoPreview = document.getElementById("site-logo-preview");
bindImagePreview(logoInput, logoPreview);

const faviconInput = document.querySelector('[name="favicon"]');
const faviconPreview = document.getElementById("site-favicon-preview");
bindImagePreview(faviconInput, faviconPreview);

const heroInput = document.querySelector('[name="hero_image"]');
const heroPreview = document.getElementById("site-hero-preview");
bindImagePreview(heroInput, heroPreview);

const editDataEl = document.getElementById("edit-event-data");
if (editDataEl) {
  try {
    const editData = JSON.parse(editDataEl.textContent);
    if (editData) openEventModal("edit", editData);
  } catch (e) {}
}
