(function () {
    'use strict';

    // M1 สมุดบัญชี: แสดงกลุ่มช่อง "บัญชีเครดิต" / "บัญชีแฟคตอริ่ง" เฉพาะเมื่อเลือกประเภทนั้น
    document.addEventListener('DOMContentLoaded', function () {
        var typeField = document.getElementById('id_account_type');
        if (!typeField) return;

        function groupOf(fieldId) {
            var el = document.getElementById(fieldId);
            return el ? el.closest('fieldset') : null;
        }

        var groups = {CREDIT: groupOf('id_credit_limit'), FACTORING: groupOf('id_advance_percent')};

        function toggle() {
            Object.keys(groups).forEach(function (type) {
                if (groups[type]) groups[type].style.display = typeField.value === type ? '' : 'none';
            });
        }

        typeField.addEventListener('change', toggle);
        toggle();
    });
})();
