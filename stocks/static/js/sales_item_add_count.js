(function () {
    'use strict';

    // ---- SalesItemInline (รายการที่จะขาย): ช่องกรอก "จำนวนบรรทัด" ข้างปุ่ม Add another ----
    // กรอกตัวเลข (ค่าเริ่มต้น 1) แล้วกดปุ่ม Add another → เพิ่มแถวว่างตามจำนวนที่กรอกในครั้งเดียว
    // ไม่ได้เขียนการเพิ่มแถวเอง แค่สั่งคลิกปุ่มเดิมของ Unfold ซ้ำ (n-1) ครั้ง แต่ละแถวใหม่จึงได้ event
    // formset:added ตามปกติ (script อื่นอย่าง autocomplete/เลขลำดับแถวทำงานเหมือนกดเองทีละครั้ง)

    var PREFIX = 'items'; // related_name ของ SalesItem → SalesOrder (ดู models.py)
    var MAX_PER_CLICK = 100;

    document.addEventListener('DOMContentLoaded', function () {
        var group = document.getElementById(PREFIX + '-group'); // กล่อง inline ทั้งก้อน (Django ตั้ง id = <prefix>-group)
        var addBtn = group && group.querySelector('.form-actions .add-row');
        if (!addBtn) return; // SO ล็อคแล้ว (ไม่มีสิทธิ์เพิ่มแถว) หรือโครงสร้างหน้าไม่ตรง

        var box = document.createElement('span');
        box.className = 'so-add-count';
        box.style.cssText = 'display:inline-flex;align-items:center;gap:6px;margin-left:12px;';
        box.innerHTML = '<span style="color:#6b7280;font-size:13px;">จำนวนบรรทัด</span>';

        var input = document.createElement('input');
        input.type = 'number';
        input.min = '1';
        input.max = String(MAX_PER_CLICK);
        input.step = '1';
        input.value = '1';
        input.title = 'กดปุ่ม Add another แล้วจะเพิ่มแถวตามจำนวนนี้';
        input.className = 'border border-base-200 rounded-default px-2 py-1 bg-white dark:bg-base-900 dark:border-base-700';
        input.style.cssText = 'width:70px;';
        box.appendChild(input);

        // วางต่อท้ายปุ่ม (ปุ่มเป็น flex item ใน .form-actions) — ใส่ไว้ใน wrapper เดียวกันกับปุ่ม
        var holder = document.createElement('div');
        holder.style.cssText = 'display:flex;align-items:center;';
        addBtn.parentNode.insertBefore(holder, addBtn);
        holder.appendChild(addBtn);
        holder.appendChild(box);

        function count() {
            var n = parseInt(input.value, 10);
            if (!n || n < 1) n = 1;
            if (n > MAX_PER_CLICK) n = MAX_PER_CLICK;
            return n;
        }

        // ซ่อน/แสดงช่องตามปุ่ม (Unfold ซ่อนปุ่มด้วย class hidden เมื่อเต็ม max_num)
        function syncVisibility() {
            box.style.display = addBtn.classList.contains('hidden') ? 'none' : 'inline-flex';
        }
        new MutationObserver(syncVisibility).observe(addBtn, { attributes: true, attributeFilter: ['class'] });
        syncVisibility();

        var repeating = false;
        // ใช้ setTimeout 0 ให้คลิกแรก (ของผู้ใช้) ให้ Unfold เพิ่มแถวแรกเสร็จก่อน แล้วค่อยคลิกเพิ่มที่เหลือ
        addBtn.addEventListener('click', function () {
            if (repeating) return;
            var extra = count() - 1;
            if (extra <= 0) return;
            setTimeout(function () {
                repeating = true;
                try {
                    for (var i = 0; i < extra; i++) {
                        if (addBtn.classList.contains('hidden')) break; // ถึง max_num แล้ว
                        addBtn.click();
                    }
                } finally {
                    repeating = false;
                }
            }, 0);
        });

        // Enter ในช่องนี้ = กดปุ่ม Add another (กันไม่ให้ไป submit ฟอร์มใบสั่งขายทั้งใบ)
        input.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            addBtn.click();
        });
    });
}());
