(function () {
    'use strict';

    // ช่อง input type="number" (ราคา/จำนวน ฯลฯ) — เลื่อนลูกกลิ้งเมาส์ทับช่องแล้ว browser จะเพิ่ม/ลดค่าเอง
    // ทำให้ตัวเลขเปลี่ยนโดยไม่ตั้งใจ → ยกเลิก wheel event ของช่องนั้น (preventDefault) แล้วเลื่อนหน้าเว็บให้เอง
    // หน้าเว็บจึงยังเลื่อนขึ้นลงได้ตามปกติ (แก้ค่าได้เฉพาะการพิมพ์ตัวเลขจากคีย์บอร์ดเท่านั้น)
    function isNumberInput(el) {
        return !!el && el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'number';
    }

    function canScroll(el, dx, dy) {
        var st = getComputedStyle(el);
        if (dy && /(auto|scroll|overlay)/.test(st.overflowY) && el.scrollHeight > el.clientHeight) {
            if (dy < 0 ? el.scrollTop > 0 : el.scrollTop + el.clientHeight < el.scrollHeight) return true;
        }
        if (dx && /(auto|scroll|overlay)/.test(st.overflowX) && el.scrollWidth > el.clientWidth) {
            if (dx < 0 ? el.scrollLeft > 0 : el.scrollLeft + el.clientWidth < el.scrollWidth) return true;
        }
        return false;
    }

    function scrollFor(el, dx, dy) {
        for (var node = el.parentElement; node && node !== document.body && node !== document.documentElement; node = node.parentElement) {
            if (canScroll(node, dx, dy)) {
                node.scrollBy(dx, dy);
                return;
            }
        }
        window.scrollBy(dx, dy);
    }

    document.addEventListener('wheel', function (e) {
        var el = e.target;
        if (!isNumberInput(el)) return;
        if (e.ctrlKey) return; // ctrl+ลูกกลิ้ง = ซูมหน้าเว็บ ปล่อยไว้
        e.preventDefault();
        var unit = e.deltaMode === 1 ? 16 : (e.deltaMode === 2 ? window.innerHeight : 1);
        scrollFor(el, e.deltaX * unit, e.deltaY * unit);
    }, { capture: true, passive: false });

    // ปิดการกดลูกศรขึ้น/ลงเพิ่ม/ลดค่าในช่องตัวเลขด้วย
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
        if (!isNumberInput(e.target)) return;
        e.preventDefault();
    }, true);
}());
