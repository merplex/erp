// static/js/admin_sum_selected.js
document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('#result_list');
    if (!table) return;

    // 1. สร้างกล่องแสดงผล (ซ่อนก่อน)
    const summaryBox = document.createElement('div');
    summaryBox.id = 'realtime-sum-box';
    summaryBox.style.cssText = [
        'display:none',
        'align-items:center',
        'padding:6px 14px',
        'background:#f0f4f8',
        'border:1px solid #cbd5e1',
        'border-radius:6px',
        'font-size:13px',
        'color:#1e293b',
        'flex-shrink:0',
        'white-space:nowrap',
    ].join(';');

    // 2. หาตำแหน่งวาง
    //    unfold layout: #changelist-search อยู่ใน flex-row เดียวกับปุ่ม filter
    const searchForm = document.querySelector('#changelist-search');
    const filterBtn  = document.querySelector('[x-on\\:click*="filterOpen"]');

    if (searchForm && filterBtn && searchForm.parentNode.contains(filterBtn)) {
        // unfold: แทรกระหว่าง search กับ filter
        searchForm.parentNode.insertBefore(summaryBox, filterBtn);
    } else if (searchForm) {
        // มี search แต่ไม่มี filter → วางหลัง search
        searchForm.insertAdjacentElement('afterend', summaryBox);
    } else {
        // fallback: ใส่ใน .actions เหมือน template เดิม
        const actionContainer = document.querySelector('.actions');
        if (actionContainer) actionContainer.appendChild(summaryBox);
    }

    // 🎯 หัวตารางที่ต้องการให้รวมยอด
    const targetLabels = [
        'สต็อกปัจจุบัน', 'แผนรับ (PO)', 'แผนส่ง (SO)', 'แผนผลิต (PD)', 'คาดการณ์ (PLAN)',
        'มูลค่ารวม', 'มูลค่า', 'รวมเงิน', 'รวมจ่าย', 'รวมยอด', 'กำไร', 'ยอดสุทธิ',
        'ค้างจ่าย', 'GET BALANCE DUE LIST', 'ยอดสุทธิ (GRAND TOTAL)', 'ค้างรับ',
        'GET BALANCE DUE DISPLAY', 'จำนวนขาย', 'ยอดขายรวม', 'ต้นทุนรวม (BUY)',
        'กำไร (vs Buy)', 'จำนวน', 'INCL.VAT', 'EXCL.VAT', 'ยอดDC', 'ยอดREBATE', 'get_total_display'
    ];

    function calculateSum() {
        const headers = table.querySelectorAll('thead th');
        const activeColumns = [];

        headers.forEach((header, index) => {
            const text = header.innerText.trim();
            if (targetLabels.some(label => text.includes(label))) {
                activeColumns.push({ index, label: text });
            }
        });

        const selectedRows = table.querySelectorAll('tbody tr.selected');

        if (selectedRows.length === 0 || activeColumns.length === 0) {
            summaryBox.style.display = 'none';
            return;
        }

        const totals = {};
        activeColumns.forEach(col => totals[col.label] = 0);

        selectedRows.forEach(row => {
            const cells = row.querySelectorAll('td, th');
            activeColumns.forEach(col => {
                if (cells[col.index]) {
                    const val = parseFloat(cells[col.index].innerText.replace(/,/g, '').trim()) || 0;
                    totals[col.label] += val;
                }
            });
        });

        let html = `<span style="margin-right:10px;color:#64748b;">เลือก <b style="color:#1e293b;">${selectedRows.length}</b> รายการ</span>`;
        html += Object.entries(totals).map(([label, sum]) =>
            `<span style="margin-right:10px;"><span style="color:#64748b;">${label}:</span> <b>${sum.toLocaleString(undefined, {minimumFractionDigits: 2})}</b></span>`
        ).join('');

        summaryBox.innerHTML = html;
        summaryBox.style.display = 'flex';
    }

    table.addEventListener('change', function(e) {
        if (e.target.classList.contains('action-select') || e.target.id === 'action-toggle') {
            setTimeout(calculateSum, 50);
        }
    });
});
