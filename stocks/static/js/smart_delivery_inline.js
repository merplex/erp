(function () {
  'use strict';

  var data = window.SMART_INLINE_DATA;
  if (!data) return;

  var formPrefix = data.form_prefix;
  var qtyField   = data.qty_field;
  var itemsData  = data.items;
  var bound = new WeakSet();

  // ── helpers ──────────────────────────────────────────────

  function getAllSelects() {
    return Array.prototype.slice.call(
      document.querySelectorAll('select[name^="' + formPrefix + '-"][name$="-product"]')
    );
  }

  function getRowIndex(sel) {
    var m = sel.name.match(/-(\d+)-product$/);
    return m ? m[1] : null;
  }

  function isNewRow(sel) {
    var idx = getRowIndex(sel);
    if (idx === null) return false;
    var idInput = document.querySelector('input[name="' + formPrefix + '-' + idx + '-id"]');
    return idInput && idInput.value === '';
  }

  function getQty(sel) {
    var idx = getRowIndex(sel);
    if (idx === null) return 0;
    var inp = document.querySelector('input[name="' + formPrefix + '-' + idx + '-' + qtyField + '"]');
    return inp ? (parseFloat(inp.value) || 0) : 0;
  }

  function getConsumed(excludeSel) {
    var totals = {};
    getAllSelects().forEach(function (sel) {
      if (sel === excludeSel || !isNewRow(sel)) return;
      var pid = sel.value;
      var q = getQty(sel);
      if (pid && q > 0) totals[pid] = (totals[pid] || 0) + q;
    });
    return totals;
  }

  // ── core update ───────────────────────────────────────────

  function updateDropdowns() {
    getAllSelects().forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var currentPid = sel.value;
      var consumed = getConsumed(sel);

      for (var i = 0; i < sel.options.length; i++) {
        var opt = sel.options[i];
        var pid = opt.value;
        if (!pid) continue;
        var info = itemsData[pid];
        if (!info) continue;

        var effective = info.base_remaining - (consumed[pid] || 0);
        opt.text = effective > 0
          ? info.name + ' (\u0e40\u0e2b\u0e25\u0e37\u0e2d ' + effective + ')'
          : info.name + ' \u2713 \u0e04\u0e23\u0e1a';

        opt.style.display = (effective <= 0 && pid !== currentPid) ? 'none' : '';
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

  // ── Django 4.1+ fires formset:added on the new row ────────
  document.addEventListener('formset:added', function (e) {
    if (!e.detail || e.detail.formsetName !== formPrefix) return;
    setTimeout(function () {
      bindAll();
      updateDropdowns();
    }, 0);
  });

  // ── init ──────────────────────────────────────────────────

  function init() {
    bindAll();
    updateDropdowns();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
