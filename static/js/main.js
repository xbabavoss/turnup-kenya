// Mobile menu
const menuToggle = document.querySelector("[data-menu-toggle]");
const mobileNav = document.querySelector("[data-mobile-nav]");
const iconMenu = document.querySelector("[data-icon-menu]");
const iconClose = document.querySelector("[data-icon-close]");

if (menuToggle && mobileNav) {
  menuToggle.addEventListener("click", () => {
    const open = mobileNav.classList.toggle("open");
    if (iconMenu) iconMenu.classList.toggle("hidden", open);
    if (iconClose) iconClose.classList.toggle("hidden", !open);
    menuToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  });
}

// Purchase modal
const modal = document.getElementById("purchase-modal");
const purchaseForm = document.getElementById("purchase-form");
const modalEventName = document.getElementById("modal-event-name");
const modalEventPrice = document.getElementById("modal-event-price");
const paymentLoading = document.getElementById("payment-loading-overlay");
const paymentResultModal = document.getElementById("payment-result-modal");
const paymentResultTitle = document.getElementById("payment-result-title");
const paymentResultMessage = document.getElementById("payment-result-message");
const paymentResultBtn = document.getElementById("payment-result-btn");
const paymentSuccessIcon = document.getElementById("payment-result-success-icon");
const paymentErrorIcon = document.getElementById("payment-result-error-icon");
const purchaseSubmitBtn = document.getElementById("purchase-submit-btn");

let pollTimer = null;

function openPurchaseModal({ slug, title, price, canBuy }) {
  if (!modal || !purchaseForm) return;
  if (canBuy === "0" || canBuy === 0) {
    alert("This preview event is not available for purchase yet. Add it in admin to go live.");
    return;
  }
  modalEventName.textContent = title;
  modalEventPrice.textContent = `KES ${price}`;
  purchaseForm.action = `/events/${slug}/buy/`;
  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  document.getElementById("purchase-email")?.focus();
}

function closePurchaseModal() {
  if (!modal) return;
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  const loadingOpen = paymentLoading && !paymentLoading.classList.contains("hidden");
  const resultOpen = paymentResultModal && !paymentResultModal.classList.contains("hidden");
  if (!loadingOpen && !resultOpen) {
    document.body.style.overflow = "";
  }
}

function showPaymentLoading(message) {
  if (!paymentLoading) return;
  const msgEl = document.getElementById("payment-loading-message");
  if (msgEl && message) msgEl.textContent = message;
  paymentLoading.classList.remove("hidden");
  paymentLoading.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function hidePaymentLoading() {
  paymentLoading?.classList.add("hidden");
  paymentLoading?.setAttribute("aria-hidden", "true");
}

function showPaymentResult({ success, title, message, redirectHome }) {
  hidePaymentLoading();
  closePurchaseModal();
  if (!paymentResultModal) return;

  paymentSuccessIcon?.classList.toggle("hidden", !success);
  paymentErrorIcon?.classList.toggle("hidden", success);
  if (paymentResultTitle) paymentResultTitle.textContent = title;
  if (paymentResultMessage) paymentResultMessage.textContent = message;

  paymentResultModal.classList.remove("hidden");
  paymentResultModal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";

  if (paymentResultBtn) {
    paymentResultBtn.onclick = () => {
      paymentResultModal.classList.add("hidden");
      paymentResultModal.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      if (redirectHome) window.location.href = "/";
    };
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function pollPaymentStatus(statusUrl, email) {
  stopPolling();
  let attempts = 0;
  const maxAttempts = 90;

  pollTimer = setInterval(async () => {
    attempts += 1;
    if (attempts > maxAttempts) {
      stopPolling();
      hidePaymentLoading();
      showPaymentResult({
        success: false,
        title: "Payment timed out",
        message: "We did not receive confirmation in time. If you completed M-Pesa, check your email or try again.",
        redirectHome: false,
      });
      return;
    }

    try {
      const res = await fetch(statusUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const data = await res.json();

      if (data.status === "completed") {
        stopPolling();
        hidePaymentLoading();
        const addr = email || data.email || "your email";
        const emailNote = data.email_sent
          ? `Your ticket PDF has been sent to ${addr}.`
          : `Your ticket is being emailed to ${addr}. Check spam in a few minutes if it does not arrive.`;
        showPaymentResult({
          success: true,
          title: "Payment successful",
          message: emailNote,
          redirectHome: true,
        });
      } else if (data.status === "failed") {
        stopPolling();
        hidePaymentLoading();
        showPaymentResult({
          success: false,
          title: "Payment failed",
          message: data.error || "Payment was not completed. Please try again.",
          redirectHome: false,
        });
      }
    } catch (err) {
      console.error(err);
    }
  }, 3000);
}

purchaseForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!purchaseForm.action) return;

  const email = document.getElementById("purchase-email")?.value?.trim();
  const formData = new FormData(purchaseForm);

  if (purchaseSubmitBtn) {
    purchaseSubmitBtn.disabled = true;
  }

  showPaymentLoading("Sending M-Pesa request to your phone…");

  try {
    const res = await fetch(purchaseForm.action, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      },
      credentials: "same-origin",
    });
    let data = {};
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      const text = await res.text();
      if (text) data = { error: text.slice(0, 200) };
    }

    if (!res.ok || !data.ok) {
      hidePaymentLoading();
      const fallback =
        res.status === 403
          ? "Request blocked (CSRF). Open the site via your ngrok URL and add it to CSRF_TRUSTED_ORIGINS in .env."
          : "Something went wrong. Please check your details and try again.";
      showPaymentResult({
        success: false,
        title: res.status === 403 ? "Access denied" : "Could not start payment",
        message: data.error || fallback,
        redirectHome: false,
      });
      return;
    }

    showPaymentLoading(data.message || "Enter your M-Pesa PIN on your phone to complete payment.");
    pollPaymentStatus(data.status_url, email);
  } catch (err) {
    hidePaymentLoading();
    showPaymentResult({
      success: false,
      title: "Network error",
      message: "Could not reach the server. Check your connection and try again.",
      redirectHome: false,
    });
  } finally {
    if (purchaseSubmitBtn) purchaseSubmitBtn.disabled = false;
  }
});

document.querySelectorAll("[data-buy-open]").forEach((btn) => {
  btn.addEventListener("click", () => {
    openPurchaseModal({
      slug: btn.dataset.slug,
      title: btn.dataset.title,
      price: btn.dataset.price,
      canBuy: btn.dataset.canBuy ?? "1",
    });
  });
});

modal?.querySelectorAll("[data-modal-close]").forEach((el) => {
  el.addEventListener("click", closePurchaseModal);
});

paymentResultModal?.querySelectorAll("[data-payment-result-close]").forEach((el) => {
  el.addEventListener("click", () => {
    paymentResultModal.classList.add("hidden");
    document.body.style.overflow = "";
  });
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closePurchaseModal();
    if (!paymentLoading?.classList.contains("hidden")) return;
    paymentResultModal?.classList.add("hidden");
    document.body.style.overflow = "";
  }
});

// Scroll reveal
document.querySelectorAll(".fade-up").forEach((el) => {
  const observer = new IntersectionObserver(
    (entries) => entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add("show")),
    { threshold: 0.1 }
  );
  observer.observe(el);
});
