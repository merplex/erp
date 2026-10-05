// static/js/amount_comma_preview.js
// ช่องจำนวนเงิน (#id_amount): ลดความกว้างลงครึ่งหนึ่ง แล้วแสดงตัวเลขมีคอมมาคั่นทางขวาของช่อง ให้อ่านง่ายตอนพิมพ์
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
        const raw = (input.value || '').replace(/,/g, '').trim();
        const n = Number(raw);
        if (raw === '' || !isFinite(n)) {
            preview.textContent = '';
            return;
        }
        preview.textContent = n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 4});
    }

    input.addEventListener('input', update);
    update();
});
