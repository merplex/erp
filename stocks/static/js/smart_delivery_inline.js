(function () {
  'use strict';

  // !! ต้องตรวจสอบ SMART_INLINE_DATA ใน DOMContentLoaded เท่านั้น !!
  // JS โหลดจาก <head> → ถ้าตรวจตอนนี้จะได้ undefined เพราะ body ยัง render ไม่ครบ

  var formPrefix, selectField, qtyField, itemsData;
  var bound = new WeakSet();
  var idxPattern;
  var snapshots = new WeakMap(); // select → [{value, text}, ...]

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

  // ── snapshot (ถ่าย option ดั้งเดิมก่อน modify ใดๆ) ───────

  function snapshotOptions(sel) {
    if (snapshots.has(sel)) return; // snapshot ครั้งเดียว
    var opts = [];
    for (var i = 0; i < sel.options.length; i++) {
      opts.push({ value: sel.options[i].value, text: sel.options[i].text });
    }
    snapshots.set(sel, opts);
  }

  // ── core update ───────────────────────────────────────────
  // แทนที่จะ display:none (ไม่ทำงานใน Select2)
  // → ลบ option ออก DOM จริงๆ แล้ว trigger Select2 refresh

  function updateDropdowns() {
    var $ = window.django && window.django.jQuery;
    getAllSelects().forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var currentKey = sel.value;
      var consumed   = getConsumed(sel);
      var opts = snapshots.get(sel);
      if (!opts) return;

      // Rebuild options จาก snapshot
      while (sel.options.length > 0) sel.remove(0);

      opts.forEach(function (o) {
        var key = o.value;
        if (!key) {
          // blank option — แสดงเสมอ
          sel.add(new Option(o.text, ''));
          return;
        }
        var info = itemsData[key];
        if (!info) {
          // ไม่อยู่ใน items_data — แสดงตามเดิม
          sel.add(new Option(o.text, key, false, key === currentKey));
          return;
        }
        var effective = info.base_remaining - (consumed[key] || 0);
        if (effective <= 0 && key !== currentKey) return; // ซ่อน (ไม่ add)
        var text = effective > 0
          ? info.name + ' (\u0e40\u0e2b\u0e25\u0e37\u0e2d ' + effective + ')'
          : info.name + ' \u2713 \u0e04\u0e23\u0e1a';
        sel.add(new Option(text, key, false, key === currentKey));
      });

      // Trigger Select2 refresh ถ้าใช้อยู่
      if ($ && $(sel).data('select2')) {
        $(sel).trigger('change.select2');
      }
    });
  }

  // ── binding ───────────────────────────────────────────────

  function bindSelect(sel) {
    snapshotOptions(sel); // snapshot ก่อนเสมอ (ก่อน modify ใดๆ)
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

  // ── init ─────────────────────────────────────────────────

  function init() {
    var data = window.SMART_INLINE_DATA;
    if (!data) {
      console.log('[SmartInline] no SMART_INLINE_DATA at DOMContentLoaded');
      return;
    }

    formPrefix  = data.form_prefix;
    selectField = data.select_field || 'product';
    qtyField    = data.qty_field;
    itemsData   = data.items;
    idxPattern  = new RegExp('-([0-9]+)-' + selectField + '$');

    console.log('[SmartInline] ready prefix=' + formPrefix + ' selects=' + getAllSelects().length, itemsData);

    // เมื่อกด "Add another"
    document.addEventListener('formset:added', function () {
      setTimeout(function () { bindAll(); updateDropdowns(); }, 50);
    });

    // polling fallback
    setInterval(function () {
      bindAll();
      updateDropdowns();
    }, 500);

    bindAll();
    updateDropdowns();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
