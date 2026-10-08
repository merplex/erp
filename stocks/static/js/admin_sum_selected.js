// static/js/admin_sum_selected.js
// กล่องสรุปยอดข้างช่องค้นหา:
//   - ไม่ได้ติ๊ก หรือ ติ๊กทั้งหน้า  -> ยอดรวม "ทุกรายการตามตัวกรอง" (ทุกหน้า, server คำนวณ: <changelist>/column-totals/)
//   - ติ๊กบางรายการ                -> ยอดรวมเฉพาะที่ติ๊ก
document.addEventListener('DOMContentLoaded', function() {
    const table = document.querySelector('#result_list');
    if (!table) return;

    // 1. สร้างกล่องแสดงผล
    const summaryBox = document.createElement('div');
    summaryBox.id = 'realtime-sum-box';
    summaryBox.style.cssText = [
        'display:none',
        'align-items:center',
        'flex-wrap:wrap',
        'gap:2px 0',
        'padding:6px 14px',
        'background:#f0f4f8',
        'border:1px solid #cbd5e1',
        'border-radius:6px',
        'font-size:13px',
        'color:#1e293b',
        'flex-shrink:0',
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

    // 🎯 หัวตารางที่ต้องการให้รวมยอด (เทียบแบบไม่สนตัวพิมพ์เล็ก/ใหญ่)
    const targetLabels = [
        'สต็อกปัจจุบัน', 'แผนรับ (PO)', 'แผนส่ง (SO)', 'แผนผลิต (PD)', 'คาดการณ์ (PLAN)',
        'มูลค่ารวม', 'มูลค่า', 'รวมเงิน', 'รวมจ่าย', 'รวมยอด', 'กำไร', 'ยอดสุทธิ', 'ยอดรวมสุทธิ',
        'ค้างจ่าย', 'GET BALANCE DUE LIST', 'ยอดสุทธิ (GRAND TOTAL)', 'ค้างรับ',
        'GET BALANCE DUE DISPLAY', 'จำนวนขาย', 'ยอดขายรวม', 'ต้นทุนรวม (BUY)',
        'กำไร (vs Buy)', 'ยอดสั่งซื้อรวม', 'จำนวน', 'INCL.VAT', 'EXCL.VAT', 'ยอดDC', 'ยอดREBATE', 'get_total_display', 'เงินเข้า', 'เงินออก'
    ].map(l => l.toUpperCase());

    // คอลัมน์ที่รวมยอด: index ในแถว + ชื่อ field (จาก class "column-<field>" ที่ Django ใส่ให้หัวตาราง)
    const activeColumns = [];
    table.querySelectorAll('thead th').forEach((header, index) => {
        const text = header.innerText.trim();
        if (!targetLabels.some(label => text.toUpperCase().includes(label))) return;
        const cls = Array.from(header.classList).find(c => c.startsWith('column-'));
        activeColumns.push({ index, label: text.split('\n')[0], field: cls ? cls.slice(7) : null });
    });
    if (activeColumns.length === 0) return;

    function cellNumber(cell) {
        // เอาตัวเลขแรกของเซลล์ (มี ฿ / คอมมา / บรรทัดย่อย เช่น "หัก ต.ค. 2569" ได้)
        const match = (cell.innerText || '').replace(/,/g, '').match(/-?\d+(\.\d+)?/);
        return match ? parseFloat(match[0]) : 0;
    }

    function fmt(n) {
        return Number(n).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
    }

    function render(prefix, totals) {
        let html = `<span style="margin-right:10px;color:#64748b;">${prefix}</span>`;
        html += activeColumns.map(col => {
            const v = totals[col.field || col.label];
            return `<span style="margin-right:10px;"><span style="color:#64748b;">${col.label}:</span> `
                 + `<b>${v === undefined ? '-' : fmt(v)}</b></span>`;
        }).join('');
        summaryBox.innerHTML = html;
        summaryBox.style.display = 'flex';
    }

    // ── ยอดรวมทุกรายการตามตัวกรอง (server) ──
    let serverState = null;   // null = ยังไม่โหลด, {count, totals, too_many}
    let loading = false;

    function totalsUrl(force) {
        const params = new URLSearchParams(window.location.search);
        params.delete('p');
        activeColumns.forEach(col => { if (col.field) params.append('_col', col.field); });
        if (force) params.set('_force', '1');
        const base = window.location.pathname.replace(/\/?$/, '/');
        return base + 'column-totals/?' + params.toString();
    }

    function isFiltered() {
        // มีตัวกรอง/คำค้น (ไม่นับเลขหน้า p, การเรียง o, ตัวแปรภายในของ admin ที่ขึ้นต้นด้วย _)
        const params = new URLSearchParams(window.location.search);
        for (const [key, value] of params) {
            if (key !== 'p' && key !== 'o' && !key.startsWith('_') && value !== '') return true;
        }
        return false;
    }

    function pageTotals(rows) {
        const totals = {};
        activeColumns.forEach(col => totals[col.field || col.label] = 0);
        rows.forEach(row => {
            const cells = row.querySelectorAll('td, th');
            activeColumns.forEach(col => {
                if (cells[col.index]) totals[col.field || col.label] += cellNumber(cells[col.index]);
            });
        });
        return totals;
    }

    function loadServerTotals(force) {
        if (loading) return;
        loading = true;
        summaryBox.style.display = 'flex';
        summaryBox.innerHTML = '<span style="color:#64748b;">⏳ กำลังรวมยอดตามตัวกรอง...</span>';
        fetch(totalsUrl(force), {credentials: 'same-origin'})
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(data => { serverState = data; })
            .catch(() => { serverState = {error: true}; })
            .finally(() => { loading = false; calculateSum(); });
    }

    function showAll(rows) {
        if (serverState === null) { loadServerTotals(false); return; }
        if (serverState.error) {
            render(`หน้านี้ <b style="color:#1e293b;">${rows.length}</b> รายการ`, pageTotals(rows));
            return;
        }
        const count = Number(serverState.count).toLocaleString();
        if (serverState.too_many) {
            render(`ทั้งหมด <b style="color:#1e293b;">${count}</b> รายการ (ตามตัวกรอง)`, {});
            const btn = document.createElement('a');
            btn.href = '#';
            btn.textContent = '🧮 คำนวณยอดรวม';
            btn.style.cssText = 'color:#2563eb;font-weight:600;';
            btn.addEventListener('click', e => { e.preventDefault(); loadServerTotals(true); });
            summaryBox.appendChild(btn);
            return;
        }
        render(`ทั้งหมด <b style="color:#1e293b;">${count}</b> รายการ (ตามตัวกรอง)`, serverState.totals);
    }

    function calculateSum() {
        const rows = Array.from(table.querySelectorAll('tbody tr')).filter(r => r.querySelector('.action-select'));
        const selected = rows.filter(r => r.classList.contains('selected')
                                          || (r.querySelector('.action-select') || {}).checked);
        // ไม่ได้กรอง/ค้นหา และไม่ได้ติ๊กอะไร (หน้าแรกของเมนู) -> ไม่ต้องแสดง
        if (selected.length === 0 && !isFiltered()) {
            summaryBox.style.display = 'none';
            return;
        }
        // ไม่ได้ติ๊ก หรือ ติ๊กครบทั้งหน้า = ดูยอดรวมทั้งหมดตามตัวกรอง
        if (selected.length === 0 || selected.length === rows.length) {
            showAll(rows);
            return;
        }
        render(`เลือก <b style="color:#1e293b;">${selected.length}</b> รายการ`, pageTotals(selected));
    }

    table.addEventListener('change', function(e) {
        if (e.target.classList.contains('action-select') || e.target.id === 'action-toggle') {
            setTimeout(calculateSum, 50);
        }
    });
    calculateSum();
});
