(function () {
    'use strict';
    // O4 เครื่องจักร: ช่อง "ประเภทเครื่องจักร" ขึ้นประเภทที่เคยกรอกไว้ พิมพ์แล้วกรองเหลือที่ตรงกัน (ตัวทำงานอยู่ใน text_suggest.js)
    document.addEventListener('DOMContentLoaded', function () {
        if (!window.TextSuggest) return;
        window.TextSuggest.attach(document.getElementById('id_machine_type'), {
            url: location.pathname.replace(/machine\/.*$/, 'machine/type-suggest/'),
            canHide: false
        });
    });
})();
