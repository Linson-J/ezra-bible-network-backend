// Small progressive enhancements. Every page works without this file.
(function () {
  "use strict";
  var root = document.documentElement;

  // Theme: dark by default (matches the app), remembered per browser.
  function setTheme(t) {
    root.dataset.theme = t;
    try { localStorage.setItem("ezra-theme", t); } catch (e) {}
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = t === "light" ? "#F6F2E9" : "#0E0B2A";
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () { setTheme(root.dataset.theme === "light" ? "dark" : "light"); });
  });
  if (root.dataset.theme === "light") setTheme("light");

  // Toasts: auto-dismiss.
  document.querySelectorAll(".toast").forEach(function (t, i) {
    function close() { t.classList.add("leaving"); setTimeout(function () { t.remove(); }, 300); }
    t.querySelector(".toast-x").addEventListener("click", close);
    setTimeout(close, 4500 + i * 600);
  });

  // Confirmations via a styled <dialog> instead of window.confirm.
  var dialog = document.getElementById("confirm-dialog");
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-confirm]");
    if (!btn || btn.dataset.confirmed) return;
    if (!dialog || typeof dialog.showModal !== "function") {
      if (!window.confirm(btn.dataset.confirm)) e.preventDefault();
      return;
    }
    e.preventDefault();
    dialog.querySelector(".confirm-text").textContent = btn.dataset.confirm;
    dialog.returnValue = "";
    dialog.showModal();
    dialog.addEventListener("close", function onClose() {
      dialog.removeEventListener("close", onClose);
      if (dialog.returnValue === "ok") {
        btn.dataset.confirmed = "1";
        btn.click();
      }
    });
  });

  // Generic open/close for other dialogs.
  document.querySelectorAll("[data-open]").forEach(function (b) {
    b.addEventListener("click", function () {
      var d = document.getElementById(b.dataset.open);
      if (d) d.showModal();
    });
  });
  document.querySelectorAll("dialog [data-close]").forEach(function (b) {
    b.addEventListener("click", function () { b.closest("dialog").close(); });
  });
  document.querySelectorAll("dialog.sheet").forEach(function (d) {
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
  });

  // Character counters.
  document.querySelectorAll("[data-counter]").forEach(function (el) {
    var max = +el.dataset.counter, c = document.createElement("span");
    c.className = "counter";
    el.insertAdjacentElement("afterend", c);
    function update() {
      c.textContent = el.value.length + " / " + max;
      c.classList.toggle("over", el.value.length > max);
    }
    el.addEventListener("input", update);
    update();
  });

  // Live preview for verse forms.
  document.querySelectorAll("[data-mirror]").forEach(function (out) {
    var src = document.getElementById(out.dataset.mirror);
    if (!src) return;
    var fallback = out.textContent;
    src.addEventListener("input", function () { out.textContent = src.value.trim() || fallback; });
  });

  // Image preview for uploads.
  document.querySelectorAll('input[type="file"]').forEach(function (input) {
    var img = input.closest(".upload") && input.closest(".upload").querySelector("[data-preview]");
    if (!img) return;
    input.addEventListener("change", function () {
      var f = input.files && input.files[0];
      if (!f) return;
      img.src = URL.createObjectURL(f);
      img.hidden = false;
    });
  });
})();
