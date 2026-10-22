// static/js/amount_comma_preview.js
// ช่องจำนวนเงิน (#id_amount): ลดความกว้างลงครึ่งหนึ่ง แล้วแสดงตัวเลขมีคอมมาคั่นทางขวาของช่อง ให้อ่านง่ายตอนพิมพ์
// ช่องในตาราง inline ที่ติด data-comma-preview (เช่น ยอดเงินต้นที่รับใน M3): แสดงตัวเลขมีคอมมาใต้ช่อง
// ทั้งสองแบบเป็นแค่ข้อความแสดงผล ไม่ส่งไปบันทึก
function amountCommaText(value) {
    const raw = (value || '').replace(/,/g, '').trim();
    const n = Number(raw);
    if (raw === '' || !isFinite(n)) return '';
    return n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 4});
}

document.addEventListener('DOMContentLoaded', function() {
    const input = document.querySelector('#id_amount');
    if (!input) return;

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:12px;';
    input.parentNode.insertBefore(row, input);
    row.appendChild(input);
    input.style.width = '50%';
    input.style.flex = '0 0 50%';

    const preview = document.createElement('span');
    preview.style.cssText = 'font-size:15px;font-weight:600;white-space:nowrap;';
    row.appendChild(preview);

    function update() {
        preview.textContent = amountCommaText(input.value);
    }

    input.addEventListener('input', update);
    update();
});

(function() {
    // แถวที่กด "Add another" สร้างใหม่ทีหลัง -> ใช้ event delegation + หา/สร้างข้อความใต้ช่องตอนพิมพ์
    function previewOf(input) {
        let preview = input.nextElementSibling;
        if (!preview || !preview.classList.contains('comma-preview')) {
            preview = document.createElement('div');
            preview.className = 'comma-preview';
            preview.style.cssText = 'font-size:12px;font-weight:600;color:#64748b;margin-top:2px;min-height:1em;';
            input.insertAdjacentElement('afterend', preview);
        }
        return preview;
    }

    function update(input) {
        previewOf(input).textContent = amountCommaText(input.value);
    }

    document.addEventListener('input', function(e) {
        if (e.target.matches && e.target.matches('input[data-comma-preview]')) update(e.target);
    });
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('input[data-comma-preview]').forEach(update);
    });
})();
