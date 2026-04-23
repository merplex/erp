(function () {
  'use strict';

  var formPrefix, selectField, qtyField, itemsData;
  var bound = new WeakSet();
  var idxPattern;
  var snapshots = new WeakMap();

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

  // ── snapshot ──────────────────────────────────────────────

  function snapshotOptions(sel) {
    if (snapshots.has(sel)) return;
    var opts = [];
    for (var i = 0; i < sel.options.length; i++) {
      opts.push({ value: sel.options[i].value, text: sel.options[i].text });
    }
    snapshots.set(sel, opts);
    console.log('[SmartInline] snapshot', sel.name, '→', opts.length, 'options');
  }

  // ── core update ───────────────────────────────────────────

  function updateDropdowns(fromEvent) {
    var $ = window.django && window.django.jQuery;
    getAllSelects().forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var currentKey = sel.value;
      var consumed   = getConsumed(sel);
      var opts = snapshots.get(sel);

      if (!opts) {
        console.warn('[SmartInline] NO SNAPSHOT for', sel.name, '— skipping');
        return;
      }

      var removedCount = 0;

      // Rebuild options จาก snapshot
      while (sel.options.length > 0) sel.remove(0);

      opts.forEach(function (o) {
        var key = o.value;
        if (!key) {
          sel.add(new Option(o.text, ''));
          return;
        }
        var info = itemsData[key];
        if (!info) {
          sel.add(new Option(o.text, key, false, key === currentKey));
          return;
        }
        var effective = info.base_remaining - (consumed[key] || 0);
        if (effective <= 0 && key !== currentKey) {
          removedCount++;
          return; // ซ่อน
        }
        var text = effective > 0
          ? info.name + ' (\u0e40\u0e2b\u0e25\u0e37\u0e2d ' + effective + ')'
          : info.name + ' \u2713 \u0e04\u0e23\u0e1a';
        sel.add(new Option(text, key, false, key === currentKey));
      });

      if (fromEvent) {
        console.log('[SmartInline] update', sel.name,
          '| currentKey:', currentKey,
          '| consumed:', JSON.stringify(consumed),
          '| removed:', removedCount);
      }

      // Trigger Select2 refresh ถ้าใช้อยู่
      if ($ && $(sel).data('select2')) {
        $(sel).trigger('change.select2');
      }
    });
  }

  // ── binding ───────────────────────────────────────────────

  function bindSelect(sel) {
    snapshotOptions(sel);
    if (bound.has(sel)) return;
    bound.add(sel);
    sel.addEventListener('change', function () { updateDropdowns(true); });

    var idx = getRowIndex(sel);
    if (idx !== null) {
      var inp = document.querySelector(
        'input[name="' + formPrefix + '-' + idx + '-' + qtyField + '"]'
      );
      if (inp) {
        console.log('[SmartInline] bound qty input:', inp.name);
        if (!bound.has(inp)) {
          bound.add(inp);
          inp.addEventListener('input', function () { updateDropdowns(true); });
        }
      } else {
        console.warn('[SmartInline] qty input NOT FOUND:', formPrefix + '-' + idx + '-' + qtyField);
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

    document.addEventListener('formset:added', function () {
      setTimeout(function () { bindAll(); updateDropdowns(true); }, 50);
    });

    setInterval(function () {
      bindAll();
      updateDropdowns(false);
    }, 500);

    bindAll();
    updateDropdowns(true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// ── ป้องกัน double-submit ─────────────────────────────────────
(function () {
  'use strict';
  function preventDoubleSubmit() {
    var form = document.getElementById('changelist-form') ||
               document.querySelector('form#content-main form') ||
               document.querySelector('form[method="post"]');
    if (!form) return;

    form.addEventListener('submit', function () {
      var btns = form.querySelectorAll('input[type="submit"], button[type="submit"]');
      btns.forEach(function (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor  = 'not-allowed';
        var orig = btn.value || btn.textContent;
        if (btn.value) btn.value = 'กำลังบันทึก...';
        else btn.textContent = 'กำลังบันทึก...';
        // คืนสภาพหลัง 15 วิ เผื่อ server error แล้วยังกดได้
        setTimeout(function () {
          btn.disabled = false;
          btn.style.opacity = '';
          btn.style.cursor  = '';
          if (btn.value) btn.value = orig;
          else btn.textContent = orig;
        }, 15000);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', preventDoubleSubmit);
  } else {
    preventDoubleSubmit();
  }
})();
