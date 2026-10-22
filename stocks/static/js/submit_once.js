// กันบันทึกซ้ำ: ทุกฟอร์ม POST ได้รหัส _once ประจำหน้า — กดซ้ำ/เน็ตช้าแล้วเบราว์เซอร์ส่งฟอร์มเดิมซ้ำ
// จะส่งรหัสเดิม ฝั่งเซิร์ฟเวอร์ (stocks.middleware.SubmitOnceMiddleware) ทำงานแค่ครั้งแรก ที่เหลือรอผลแล้วไม่บันทึกซ้ำ
// หน้าที่ส่งฟอร์มเองโดยไม่ได้บันทึก (เช่น เปลี่ยนวันที่แล้วโหลดตัวอย่างใหม่) เรียก window.submitOnceRenew(form) ก่อนส่ง
(function () {
    function newToken() {
        if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
        return Date.now().toString(36) + Math.random().toString(36).slice(2);
    }

    function stamp(form) {
        var input = form.querySelector('input[name="_once"]');
        if (!input) {
            input = document.createElement('input');
            input.type = 'hidden';
            input.name = '_once';
            form.appendChild(input);
        }
        input.value = newToken();
    }

    function stampAll() {
        document.querySelectorAll('form').forEach(function (form) {
            if ((form.getAttribute('method') || '').toLowerCase() === 'post') stamp(form);
        });
    }

    window.submitOnceRenew = stamp;
    document.addEventListener('DOMContentLoaded', stampAll);
    // กดย้อนกลับมาหน้าเดิม (หน้าจาก cache) = ตั้งใจส่งใหม่ -> รหัสใหม่
    window.addEventListener('pageshow', function (e) { if (e.persisted) stampAll(); });
})();
