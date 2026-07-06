// MedRank — theme toggle persistence + search suggest
(function () {
  // Respect a saved theme preference if present.
  try {
    var saved = localStorage.getItem("medrank-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
  } catch (e) {}

  var input = document.getElementById("q");
  var box = document.getElementById("suggest");
  if (!input || !box) return;

  var timer = null, lastQ = "";

  function hide() { box.hidden = true; box.innerHTML = ""; }

  function renderRow(r) {
    var meta = [r.institution, r.field ? r.field.replace(/-/g, " ") : null]
      .filter(Boolean).join(" · ");
    var a = document.createElement("a");
    a.href = "/researcher/" + r.slug;
    a.innerHTML = '<div class="s-name">' + escapeHtml(r.name) + "</div>" +
      '<div class="s-meta">' + escapeHtml(meta) + "</div>";
    return a;
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function query(q) {
    fetch("/search?format=json&q=" + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (list) {
        if (input.value.trim() !== q) return;   // stale
        box.innerHTML = "";
        if (!list.length) { hide(); return; }
        list.slice(0, 8).forEach(function (r) { box.appendChild(renderRow(r)); });
        box.hidden = false;
      })
      .catch(hide);
  }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (q === lastQ) return;
    lastQ = q;
    clearTimeout(timer);
    if (q.length < 2) { hide(); return; }
    timer = setTimeout(function () { query(q); }, 140);
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      window.location = "/search?q=" + encodeURIComponent(input.value.trim());
    } else if (e.key === "Escape") { hide(); }
  });

  document.addEventListener("click", function (e) {
    if (!box.contains(e.target) && e.target !== input) hide();
  });
})();
