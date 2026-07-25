// static/js/stock_view_toggle.js
// เพิ่มปุ่มสลับ view "Forecast stock" / "Timeline stock" บนหน้า C1
document.addEventListener('DOMContentLoaded', function () {
    const isTimeline = window.location.pathname.endsWith('/timeline/');

    const wrap = document.createElement('div');
    wrap.id = 'stock-view-toggle';
    wrap.style.cssText = 'display:flex;gap:6px;flex-shrink:0;';

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

    // unfold layout: #changelist-search อยู่ใน flex-row เดียวกับปุ่ม filter (เหมือน admin_sum_selected.js)
    const searchForm = document.querySelector('#changelist-search');
    const filterBtn = document.querySelector('[x-on\\:click*="filterOpen"]');

    if (searchForm && filterBtn && searchForm.parentNode.contains(filterBtn)) {
        searchForm.parentNode.insertBefore(wrap, filterBtn);
    } else if (searchForm) {
        searchForm.insertAdjacentElement('afterend', wrap);
    } else {
        const actionContainer = document.querySelector('.actions');
        if (actionContainer) actionContainer.appendChild(wrap);
    }
});
