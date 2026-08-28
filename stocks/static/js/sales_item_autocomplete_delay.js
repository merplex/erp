(function () {
    'use strict';

    // ---- SalesItemInline: ใส่ debounce ให้ช่อง autocomplete (บาร์โค้ด/สินค้า/บอม) ----
    // ปัญหา: admin/js/autocomplete.js ของ Django ไม่ได้ตั้งค่า ajax.delay เอาไว้เลย —
    // Select2 จะยิง request ค้นหาไปเซิร์ฟเวอร์ทันทีทุกครั้งที่กดแป้นพิมพ์ 1 ตัวอักษร (ไม่มี debounce)
    // พอในฟอร์มมีแถวเยอะขึ้นเรื่อยๆ (เปรมเพิ่มเป็นร้อยแถว) ยิ่งพิมพ์เลขบาร์โค้ดแถวหลังๆ ยิ่งรู้สึกอืด
    // เพราะทุกตัวอักษรที่พิมพ์ = 1 request + 1 รอบ render dropdown ผลลัพธ์ใหม่ทั้งก้อน
    //
    // ที่นี่ destroy() แล้วสร้าง select2 ใหม่ทับเฉพาะ ajax config เดิมของ Django (เพิ่มแค่ delay)
    // ค่าอื่นๆ (theme/width/placeholder ฯลฯ) select2 อ่านจาก data-* attribute บน <select> เองอยู่แล้ว
    // ไม่ได้มาจาก JS option ตรงนี้ — เหมือนที่ django/contrib/admin/static/admin/js/autocomplete.js ทำ
    //
    // ต้อง "รอให้ autocomplete.js ของ Django init ของหน้าเสร็จก่อน" (มันโหลดทีหลังไฟล์นี้ในลำดับ Media
    // ของ ModelAdmin แต่ init จริงตอน DOMContentLoaded) — ใช้ setTimeout(...,0) ดันให้ไปรันหลังจบ
    // ready-handler ทุกตัวในติ๊กเดียวกันแน่ๆ (ทั้งของ Django และของเราเอง ไม่ว่าใครลงทะเบียนก่อนหลัง)

    var DELAY_MS = 300;

    function djangoAjaxData(el) {
        return function (params) {
            return {
                term: params.term,
                page: params.page,
                app_label: el.dataset.appLabel,
                model_name: el.dataset.modelName,
                field_name: el.dataset.fieldName,
            };
        };
    }

    function addDelay($, el) {
        var $el = $(el);
        if (!$el.hasClass('admin-autocomplete')) return;
        if (!$el.data('select2')) return; // ยังไม่ถูก Django init จริง (เช่นแถว template ว่าง) ข้ามไป
        if ($el.data('soDelayApplied')) return;
        $el.select2('destroy');
        $el.select2({
            ajax: {
                delay: DELAY_MS,
                data: djangoAjaxData(el),
            },
        });
        $el.data('soDelayApplied', true);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var $ = window.django && django.jQuery;
        if (!$) return;

        function applyToAll(root) {
            (root || document).querySelectorAll('select.admin-autocomplete').forEach(function (el) {
                addDelay($, el);
            });
        }

        setTimeout(function () { applyToAll(document); }, 0);

        document.addEventListener('formset:added', function (event) {
            setTimeout(function () { applyToAll(event.target); }, 0);
        });
    });
}());
