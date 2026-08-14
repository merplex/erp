(function () {
    'use strict';

    // ช่อง input (จำนวน/ราคา ฯลฯ) ที่พิมพ์ตัวเลขเกินความกว้างกล่อง จะโดนตัดบางส่วน
    // พอเอาเมาส์ไปวาง (ไม่ได้กำลังพิมพ์อยู่) ให้เลื่อนเนื้อหาไปทางซ้ายเพื่อโชว์ให้เห็นครบ
    // แล้วเลื่อนกลับตำแหน่งเดิมตอนเมาส์ออก
    function isTextualInput(el) {
        if (!el || el.tagName !== 'INPUT') return false;
        var type = (el.type || 'text').toLowerCase();
        return type === 'number' || type === 'text';
    }

    document.addEventListener('mouseover', function (e) {
        var el = e.target;
        if (!isTextualInput(el)) return;
        if (document.activeElement === el) return; // กำลังพิมพ์อยู่ ปล่อยให้ browser จัดการเอง
        if (el.scrollWidth > el.clientWidth) {
            el.scrollLeft = el.scrollWidth;
        }
    }, true);

    document.addEventListener('mouseout', function (e) {
        var el = e.target;
        if (!isTextualInput(el)) return;
        if (document.activeElement === el) return;
        el.scrollLeft = 0;
    }, true);
}());
