(function () {
    'use strict';
    // M2 รายการเดินบัญชี: ช่อง "บริษัท/บุคคล" ขึ้นรายชื่อที่เคยพิมพ์ (ตัวทำงานอยู่ใน text_suggest.js)
    // ปุ่ม x / Shift+Delete = ลบชื่อออกจากรายการแนะนำ
    document.addEventListener('DOMContentLoaded', function () {
        if (!window.TextSuggest) return;
        window.TextSuggest.attach(document.getElementById('id_party'), {
            url: location.pathname.replace(/banktransaction\/.*$/, 'banktransaction/party-suggest/'),
            canHide: true
        });
    });
})();
