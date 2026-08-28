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

  // คำนวณผลรวมจำนวนที่ "ใช้ไป" ของทุก key ในรอบเดียว (O(n) แทนที่จะวนซ้ำต่อแถวแบบเดิมที่เป็น O(n^2)
  // เมื่อมีหลายสิบแถว — ทุก querySelector ในลูปซ้อนคือต้นเหตุที่หน้าค่อยๆ ช้าลงตามจำนวนแถว)
  function computeConsumedTotals() {
    var totals = {};      // key -> รวมจำนวนทุกแถวใหม่
    var perSelect = new WeakMap(); // sel -> {key, qty} ของแถวตัวเอง (ไว้หักออกตอนใช้)
    getAllSelects().forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var key = sel.value;
      var q   = getQty(sel);
      perSelect.set(sel, { key: key, qty: q });
      if (key && q > 0) totals[key] = (totals[key] || 0) + q;
    });
    return { totals: totals, perSelect: perSelect };
  }

  // ผลรวมที่ "แถวอื่น" ใช้ไป (ไม่รวมแถวตัวเอง) แยกตาม key ของสินค้าทุกตัว — หัก contribution
  // ของ sel เองออกจาก totals ที่คำนวณไว้แล้วครั้งเดียว แทนการวนแถวทั้งหมดใหม่ทุกครั้ง
  function getConsumedFor(sel, computed) {
    var own = computed.perSelect.get(sel);
    if (!own || !own.key || own.qty <= 0) return computed.totals;
    var out = {};
    for (var k in computed.totals) out[k] = computed.totals[k];
    out[own.key] -= own.qty;
    if (out[own.key] <= 0) delete out[own.key];
    return out;
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
    var computed = computeConsumedTotals();
    getAllSelects().forEach(function (sel) {
      if (!isNewRow(sel)) return;
      var currentKey = sel.value;
      var consumed   = getConsumedFor(sel, computed);
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
        var effective = info.base_remaining - (consumed[key] || 0) * (info.factor || 1);
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

  // debounce กลาง — กันไม่ให้พิมพ์ตัวเลขในช่องจำนวนทีละตัวอักษรแล้ว rebuild dropdown ทุก keystroke
  var updateDebounceTimer = null;
  function updateDropdownsDebounced() {
    if (updateDebounceTimer) clearTimeout(updateDebounceTimer);
    updateDebounceTimer = setTimeout(function () { updateDropdowns(true); }, 200);
  }

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
          inp.addEventListener('input', updateDropdownsDebounced);
        }
      } else {
        console.warn('[SmartInline] qty input NOT FOUND:', formPrefix + '-' + idx + '-' + qtyField);
      }
    }
  }

  // คืนจำนวนแถวใหม่ที่เพิ่งถูก bind ในรอบนี้ — ใช้ให้ interval รู้ว่ามีอะไรเปลี่ยนจริงไหม
  // ก่อนจะยอมเสียเวลา rebuild dropdown ทั้งหมดซ้ำ (แถวที่ bind ไปแล้วไม่ต้องรีเช็กทุกรอบ)
  function bindAll() {
    var newlyBound = 0;
    getAllSelects().forEach(function (sel) {
      if (isNewRow(sel) && !bound.has(sel)) {
        bindSelect(sel);
        newlyBound++;
      }
    });
    return newlyBound;
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

    // ใช้ interval แค่เป็น fallback คอยจับแถวใหม่ที่ Unfold เพิ่มเข้ามาโดย event 'formset:added'
    // ไม่ยิง (เคยเกิดปัญหานี้มาก่อน) — ถ้าไม่มีแถวใหม่จริง ไม่ต้อง rebuild dropdown ทั้งหน้าซ้ำ
    // เพราะยิ่งมีหลายสิบแถว ยิ่งเสียเวลามาก ทั้งที่ไม่มีอะไรเปลี่ยน
    setInterval(function () {
      if (bindAll() > 0) updateDropdowns(false);
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
  var submitted = false;

  document.addEventListener('submit', function (e) {
    if (submitted) {
      e.preventDefault();
      return;
    }
    submitted = true;

    // ใช้ CSS แทน disabled เพราะ disabled จะทำให้ค่าปุ่ม (_continue/_addanother)
    // ไม่ถูกส่งใน POST แล้ว Django ไม่รู้จะ redirect ไปไหน
    // ไม่ต้องมี timeout เพราะ save สำเร็จหรือ error หน้าโหลดใหม่ทั้งนั้น JS รีเซ็ตเอง
    var btns = document.querySelectorAll('input[type="submit"], button[type="submit"]');
    btns.forEach(function (btn) {
      btn.style.opacity       = '0.5';
      btn.style.cursor        = 'not-allowed';
      btn.style.pointerEvents = 'none';
    });
  }, true);
})();
