(function () {
    'use strict';
    // เมนูที่เป็นหน้าเดี่ยวนอก Django admin (O5 แผนงานผลิต) เปิดในแท็บใหม่
    var LINKS = ['/production-plan/'];
    document.addEventListener('DOMContentLoaded', function () {
        LINKS.forEach(function (href) {
            document.querySelectorAll('a[href="' + href + '"]').forEach(function (a) {
                a.target = '_blank';
                a.rel = 'noopener';
            });
        });
    });
})();
