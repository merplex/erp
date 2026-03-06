(function () {
  'use strict';

  var data = window.SMART_INLINE_DATA;
  if (!data) return;

  var formPrefix = data.form_prefix;   // e.g. "salesdeliverylog_set"
  var qtyField   = data.qty_field;     // e.g. "quantity_shipped"
  var itemsData  = data.items;         // { "42": { name: "สินค้า A", base_remaining: 10 }, ... }

  // ----- helpers -----

  function getInlineRows() {
    // Returns all inline <tr> rows (both existing and new)
    var tbody = document.getElementById(formPrefix + '-group');
    if (!tbody) return [];
    return Array.prototype.slice.call(tbody.querySelectorAll('tr.form-row, tr.dynamic-' + formPrefix));
  }

  function isNewRow(row) {
    // A row is "new" (unsaved) when its hidden id input is empty
    var idInput = row.querySelector('input[name$="-id"]');
    return idInput && idInput.value === '';
  }

  function getProductSelect(row) {
    return row.querySelector('select[name$="-product"]');
  }

  function getQtyInput(row) {
    return row.querySelector('input[name$="-' + qtyField + '"]');
  }

  // Compute how many units new (unsaved) rows have already consumed per product
  function getNewEntries(excludeRow) {
    var totals = {};
    getInlineRows().forEach(function (row) {
      if (!isNewRow(row)) return;
      if (row === excludeRow) return;
      var sel = getProductSelect(row);
      var qty = getQtyInput(row);
      if (!sel || !qty) return;
      var pid = sel.value;
      var q = parseFloat(qty.value) || 0;
      if (pid && q > 0) {
        totals[pid] = (totals[pid] || 0) + q;
      }
    });
    return totals;
  }

  // ----- core update function -----

  function updateDropdowns() {
    var rows = getInlineRows();
    rows.forEach(function (row) {
      if (!isNewRow(row)) return;  // only update selects in new rows
      var sel = getProductSelect(row);
      if (!sel) return;

      var currentPid = sel.value;
      var consumed = getNewEntries(row);  // other new rows' usage

      var options = sel.options;
      for (var i = 0; i < options.length; i++) {
        var opt = options[i];
        var pid = opt.value;
        if (!pid) continue;  // blank/placeholder option

        var info = itemsData[pid];
        if (!info) continue;

        var baseRemaining = info.base_remaining;
        var usedByOthers = consumed[pid] || 0;
        var effective = baseRemaining - usedByOthers;

        // Update option label
        if (effective <= 0) {
          opt.text = info.name + ' \u2713 \u0e04\u0e23\u0e1a';  // "✓ ครบ"
        } else {
          opt.text = info.name + ' (\u0e40\u0e2b\u0e25\u0e37\u0e2d ' + effective + ')';  // "(เหลือ N)"
        }

        // Hide/show: hide only if remaining <= 0 AND it's not the currently selected value in this row
        if (effective <= 0 && pid !== currentPid) {
          opt.style.display = 'none';
        } else {
          opt.style.display = '';
        }
      }
    });
  }

  // ----- event wiring -----

  function bindRow(row) {
    var sel = getProductSelect(row);
    var qty = getQtyInput(row);
    if (sel) {
      sel.addEventListener('change', function () { updateDropdowns(); });
    }
    if (qty) {
      qty.addEventListener('input', function () { updateDropdowns(); });
    }
  }

  function bindAllRows() {
    getInlineRows().forEach(function (row) {
      if (isNewRow(row)) bindRow(row);
    });
  }

  // MutationObserver: detect when Django adds a new inline row
  function observeInlineGroup() {
    var group = document.getElementById(formPrefix + '-group');
    if (!group) return;
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType === 1) {
            // newly added row
            bindRow(node);
            updateDropdowns();
          }
        });
      });
    });
    observer.observe(group, { childList: true, subtree: false });
  }

  // ----- init -----

  function init() {
    bindAllRows();
    observeInlineGroup();
    updateDropdowns();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
