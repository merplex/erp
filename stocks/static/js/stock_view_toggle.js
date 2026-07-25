// static/js/stock_view_toggle.js
// เพิ่มปุ่มสลับ view "Forecast stock" / "Timeline stock" บนหน้า C1
document.addEventListener('DOMContentLoaded', function () {
    const isTimeline = window.location.pathname.endsWith('/timeline/');

    const wrap = document.createElement('div');
    wrap.id = 'stock-view-toggle';
    wrap.style.cssText = 'display:flex;gap:6px;flex-shrink:0;flex-wrap:nowrap;align-items:center;margin-right:8px;';

    function makeBtn(label, href, active) {
        const a = document.createElement('a');
        a.href = href;
        a.textContent = label;
        a.style.cssText = [
            'display:inline-block',
            'padding:6px 14px',
            'border-radius:6px',
            'font-size:13px',
            'font-weight:600',
            'text-decoration:none',
            'white-space:nowrap',
            active ? 'background:#2563eb;color:#fff;' : 'background:#f0f4f8;color:#1e293b;border:1px solid #cbd5e1;',
        ].join(';');
        return a;
    }

    wrap.appendChild(makeBtn('📊 Forecast stock', '/admin/stocks/stockplanning/', !isTimeline));
    wrap.appendChild(makeBtn('📅 Timeline stock', '/admin/stocks/stockplanning/timeline/', isTimeline));

    // หาปุ่ม Filters: ลอง selector แบบ Alpine ก่อน (x-on:click / @click ตัวย่อ)
    // ถ้าหาไม่เจอ fallback เป็นการหา element ที่ข้อความตรงกับ "Filters" เป๊ะๆ
    // (กันเคส Unfold เปลี่ยน syntax ภายใน แล้ว selector เดิมไม่ match — เกิดปัญหานี้มาแล้วครั้งนึง)
    function findFilterBtn() {
        let btn = document.querySelector('[x-on\\:click*="filterOpen"]')
            || document.querySelector('[\\@click*="filterOpen"]');
        if (btn) return btn;
        const candidates = document.querySelectorAll('button, a, summary');
        for (const el of candidates) {
            if (el.textContent.trim() === 'Filters' || el.textContent.trim() === 'Filter') {
                return el;
            }
        }
        return null;
    }

    const searchForm = document.querySelector('#changelist-search');
    const filterBtn = findFilterBtn();

    if (filterBtn) {
        // แทรกไว้ก่อนปุ่ม Filters เลย ไม่สนว่า parent เดียวกับ search หรือไม่
        // (ตำแหน่งที่ต้องการคือ "ติดซ้ายปุ่ม Filters" เป็นหลัก)
        filterBtn.parentNode.insertBefore(wrap, filterBtn);
    } else if (searchForm) {
        searchForm.insertAdjacentElement('afterend', wrap);
    } else {
        const actionContainer = document.querySelector('.actions');
        if (actionContainer) actionContainer.appendChild(wrap);
    }
});
