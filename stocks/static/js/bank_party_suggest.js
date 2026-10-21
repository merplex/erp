(function () {
    'use strict';

    // M2 รายการเดินบัญชี: ช่อง "บริษัท/บุคคล" ขึ้นรายชื่อที่เคยพิมพ์แบบช่อง URL ของ browser
    // - คลิกเข้าช่อง (ยังไม่พิมพ์) = ขึ้นชื่อที่ใช้บ่อย/ล่าสุดก่อน, พิมพ์แล้ว = เหลือเฉพาะชื่อที่มีส่วนตรงกัน (ขึ้นต้นตรงก่อน)
    // - เลือกด้วยเมาส์ หรือ ↑ ↓ แล้ว Enter, Esc = ปิด
    // - ปุ่ม x หลังชื่อ = ลบชื่อออกจากรายการแนะนำ (ชื่อพิมพ์ผิด/ไม่ใช้แล้ว)
    var MAX_SHOW = 10;  // ไม่พิมพ์ = 10 ชื่อใช้บ่อย, พิมพ์แล้ว = กรองเหลือไม่เกิน 10

    function csrfToken() {
        var input = document.querySelector('input[name=csrfmiddlewaretoken]');
        if (input) return input.value;
        var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function injectStyle() {
        var css =
            '.party-suggest{position:fixed;z-index:1000;max-height:320px;' +
            'overflow-y:auto;background:#fff;border:1px solid #d1d5db;border-radius:6px;' +
            'box-shadow:0 6px 16px rgba(0,0,0,.12);font-size:14px;}' +
            '.party-suggest-item{display:flex;align-items:center;gap:8px;padding:6px 6px 6px 10px;cursor:pointer;color:#111827;}' +
            '.party-suggest-item.active,.party-suggest-item:hover{background:#eef2ff;}' +
            '.party-suggest-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}' +
            '.party-suggest-name b{font-weight:700;}' +
            '.party-suggest-x{flex:none;width:22px;height:22px;line-height:20px;text-align:center;border-radius:50%;' +
            'color:#9ca3af;font-size:16px;border:0;background:transparent;cursor:pointer;padding:0;}' +
            '.party-suggest-x:hover{background:#fee2e2;color:#dc2626;}' +
            '.dark .party-suggest{background:#1f2937;border-color:#374151;}' +
            '.dark .party-suggest-item{color:#e5e7eb;}' +
            '.dark .party-suggest-item.active,.dark .party-suggest-item:hover{background:#374151;}' +
            '.dark .party-suggest-x:hover{background:#7f1d1d;color:#fecaca;}';
        var style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var input = document.getElementById('id_party');
        if (!input || input.readOnly || input.disabled) return;

        var url = location.pathname.replace(/banktransaction\/.*$/, 'banktransaction/party-suggest/');
        var names = null;      // โหลดครั้งแรกตอนคลิกเข้าช่อง
        var shown = [];
        var active = -1;

        injectStyle();
        input.setAttribute('autocomplete', 'off');
        // ลอยไว้ที่ body แบบ fixed — ถ้าอยู่ใน fieldset จะโดนกรอบ (overflow) ตัดเหลือ 2 บรรทัด
        var box = document.createElement('div');
        box.className = 'party-suggest';
        box.style.display = 'none';
        document.body.appendChild(box);

        function place() {
            if (box.style.display === 'none') return;
            var r = input.getBoundingClientRect();
            var below = window.innerHeight - r.bottom - 8, above = r.top - 8;
            box.style.left = r.left + 'px';
            box.style.width = r.width + 'px';
            // ข้างล่างที่ว่างไม่พอ และข้างบนว่างกว่า = เปิดขึ้นด้านบนแทน
            if (below < Math.min(box.scrollHeight, 320) && above > below) {
                box.style.maxHeight = Math.min(320, above) + 'px';
                box.style.top = '';
                box.style.bottom = (window.innerHeight - r.top + 2) + 'px';
            } else {
                box.style.maxHeight = Math.min(320, Math.max(below, 120)) + 'px';
                box.style.bottom = '';
                box.style.top = (r.bottom + 2) + 'px';
            }
        }
        window.addEventListener('resize', place);
        window.addEventListener('scroll', place, true);

        function load(cb) {
            if (names) return cb();
            fetch(url, {credentials: 'same-origin'})
                .then(function (r) { return r.ok ? r.json() : {names: []}; })
                .then(function (data) { names = data.names || []; cb(); })
                .catch(function () { names = []; cb(); });
        }

        function matches(q) {
            if (!q) return names.slice(0, MAX_SHOW);
            var lq = q.toLowerCase(), starts = [], contains = [];
            names.forEach(function (n) {
                var i = n.toLowerCase().indexOf(lq);
                if (i === 0) starts.push(n);
                else if (i > 0) contains.push(n);
            });
            return starts.concat(contains).filter(function (n) { return n !== q; }).slice(0, MAX_SHOW);
        }

        function hide() {
            box.style.display = 'none';
            active = -1;
        }

        function nameNode(name, q) {
            var span = document.createElement('span');
            span.className = 'party-suggest-name';
            span.title = name;
            var i = q ? name.toLowerCase().indexOf(q.toLowerCase()) : -1;
            if (i < 0) {
                span.textContent = name;
            } else {
                var b = document.createElement('b');
                b.textContent = name.substr(i, q.length);
                span.appendChild(document.createTextNode(name.substr(0, i)));
                span.appendChild(b);
                span.appendChild(document.createTextNode(name.substr(i + q.length)));
            }
            return span;
        }

        function render() {
            var q = input.value.trim();
            shown = matches(q);
            box.innerHTML = '';
            if (!shown.length) return hide();
            shown.forEach(function (name, idx) {
                var item = document.createElement('div');
                item.className = 'party-suggest-item' + (idx === active ? ' active' : '');
                item.appendChild(nameNode(name, q));
                var x = document.createElement('button');
                x.type = 'button';
                x.className = 'party-suggest-x';
                x.title = 'ลบชื่อนี้ออกจากรายการแนะนำ';
                x.textContent = '×';
                x.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    remove(name);
                });
                item.addEventListener('mousedown', function (e) {
                    e.preventDefault();  // ไม่ให้ช่องเสีย focus ก่อนเลือก
                    pick(name);
                });
                box.appendChild(item);
            });
            box.style.display = '';
            place();
        }

        function pick(name) {
            input.value = name;
            input.dispatchEvent(new Event('change', {bubbles: true}));
            hide();
        }

        function remove(name) {
            names = names.filter(function (n) { return n !== name; });
            if (active >= shown.length - 1) active = shown.length - 2;
            render();
            var body = new FormData();
            body.append('hide', name);
            fetch(url, {method: 'POST', credentials: 'same-origin', body: body,
                        headers: {'X-CSRFToken': csrfToken()}});
        }

        input.addEventListener('focus', function () { load(render); });
        input.addEventListener('click', function () {
            if (box.style.display === 'none') load(render);
        });
        input.addEventListener('input', function () {
            active = -1;
            load(render);
        });
        input.addEventListener('blur', hide);
        input.addEventListener('keydown', function (e) {
            if (box.style.display === 'none') {
                if (e.key === 'ArrowDown') { load(render); e.preventDefault(); }
                return;
            }
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                var n = shown.length;
                active = e.key === 'ArrowDown' ? (active + 1) % n : (active <= 0 ? n - 1 : active - 1);
                render();
                var el = box.children[active];
                if (el) el.scrollIntoView({block: 'nearest'});
            } else if (e.key === 'Enter' && active >= 0) {
                e.preventDefault();  // เลือกชื่อ ไม่ submit ฟอร์ม
                pick(shown[active]);
            } else if (e.key === 'Delete' && active >= 0 && e.shiftKey) {
                e.preventDefault();  // Shift+Delete ลบชื่อที่เลือกอยู่ (เหมือน browser)
                remove(shown[active]);
            } else if (e.key === 'Escape') {
                hide();
            }
        });
    });
})();
