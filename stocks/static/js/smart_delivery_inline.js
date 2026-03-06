(function () {
  'use strict';

  var data = window.SMART_INLINE_DATA;
  if (!data) {
    console.log('[SmartInline] no SMART_INLINE_DATA, skipping');
    return;
  }

  var formPrefix  = data.form_prefix;
  var selectField = data.select_field || 'product';
  var qtyField    = data.qty_field;
  var itemsData   = data.items;
  var bound = new WeakSet();

  console.log('[SmartInline] init prefix=' + formPrefix + ' field=' + selectField, itemsData);

  var idxPattern = new RegExp('-([0-9]+)-' + selectField + '$');

  // ── helpers ──────────────────────────────────────────────

  function getAllSelects() {
    return Array.prototype.slice.call(
      document.querySelectorAll(
        'select[name^="' + formPrefix + '-"][name$="-' + selectField + '"]'
      )
    );
  }

  function getRowIndex(sel) {
    var m = sel.name.match(idxPattern);
    return m ? m[1] : null;
  }

  function isNewRow(sel) {
    var idx = getRowIndex(sel);
    if (idx === null) return false;
    var idInput = document.querySelector(
      'input[name="' + formPrefix + '-' + idx + '-id"]'
    );
    return idInput && idInput.value === '';
  }

  function getQty(sel) {
    var idx = getRowIndex(sel);
    if (idx === null) return 0;
    var inp = document.querySelector(
      'input[name="' + formPrefix + '-' + idx + '-' + qtyField + '"]'
    );
    return inp ? (parseFloat(inp.value) || 0) : 0;
  }

  function getConsumed(excludeSel) {
    var totals = {};
    getAllSelects().forEach(function (sel) {
      if (sel === excludeSel || !isNewRow(sel)) return;
      var key = sel.value;
      var q   = getQty(sel);
      if (key && q > 0) totals[key] = (totals[key] || 0) + q;
    });
    return totals;
  }

  // ── core update ───────────────────────────────────────────

  function updateDropdowns() {
    var sels = getAllSelects();
    sels.forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var currentKey = sel.value;
      var consumed   = getConsumed(sel);

      for (var i = 0; i < sel.options.length; i++) {
        var opt = sel.options[i];
        var key = opt.value;
        if (!key) continue;
        var info = itemsData[key];
        if (!info) continue;

        var effective = info.base_remaining - (consumed[key] || 0);
        opt.text = effective > 0
          ? info.name + ' (\u0e40\u0e2b\u0e25\u0e37\u0e2d ' + effective + ')'
          : info.name + ' \u2713 \u0e04\u0e23\u0e1a';

        opt.style.display = (effective <= 0 && key !== currentKey) ? 'none' : '';
      }
    });
  }

  // ── binding ───────────────────────────────────────────────

  function bindSelect(sel) {
    if (bound.has(sel)) return;
    bound.add(sel);
    sel.addEventListener('change', updateDropdowns);

    var idx = getRowIndex(sel);
    if (idx !== null) {
      var inp = document.querySelector(
        'input[name="' + formPrefix + '-' + idx + '-' + qtyField + '"]'
      );
      if (inp && !bound.has(inp)) {
        bound.add(inp);
        inp.addEventListener('input', updateDropdowns);
      }
    }
  }

  function bindAll() {
    getAllSelects().forEach(function (sel) {
      if (isNewRow(sel)) bindSelect(sel);
    });
  }

  // ── detect new rows (3 methods) ───────────────────────────

  // 1. Django formset:added event
  document.addEventListener('formset:added', function () {
    setTimeout(function () { bindAll(); updateDropdowns(); }, 0);
  });

  // 2. MutationObserver (debounced)
  var debounceTimer;
  var observer = new MutationObserver(function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      bindAll();
      updateDropdowns();
    }, 80);
  });

  // 3. Polling every 500ms (guaranteed fallback)
  setInterval(function () {
    bindAll();
    updateDropdowns();
  }, 500);

  // ── init ──────────────────────────────────────────────────

  function init() {
    var container = document.getElementById(formPrefix + '-group') || document.body;
    observer.observe(container, { childList: true, subtree: true });
    bindAll();
    updateDropdowns();
    console.log('[SmartInline] ready, selects found=' + getAllSelects().length);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
