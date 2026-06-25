import hashlib
import hmac
import base64
import os
import requests
from collections import defaultdict
from django.db.models import Sum, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Greatest, Coalesce  # kept for potential reuse

from .models import Product, ProductCategory

LINE_OWNER_USER_ID = os.environ.get('LINE_OWNER_USER_ID', '')
REPLY_URL = 'https://api.line.me/v2/bot/message/reply'
def _report_webview_url(report_type: str) -> str:
    from django.conf import settings
    base_url = os.environ.get('BASE_URL', '').rstrip('/')
    token = hmac.new(settings.SECRET_KEY.encode(), report_type.encode(), hashlib.sha256).hexdigest()[:20]
    return f'{base_url}/report/stock/?type={report_type}&token={token}'

_ACTIVE_PO = ['Draft', 'Pending', 'Confirmed', 'Ordered', 'Paid', 'Loaded', 'Departed', 'Arrived', 'Received', 'Partially Received']
_ACTIVE_SO = ['Draft', 'Confirmed', 'Shipped']
_ACTIVE_PD = ['Draft', 'Started', 'Finished']


# ── Core ─────────────────────────────────────────────────────────────────────

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    mac = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(mac).decode('utf-8'), signature)


def reply_message(reply_token, messages, access_token: str):
    import logging
    resp = requests.post(REPLY_URL,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'},
        json={'replyToken': reply_token, 'messages': messages},
        timeout=10)
    if resp.status_code != 200:
        logging.getLogger('line_webhook').error(
            'LINE reply failed %s: %s', resp.status_code, resp.text[:300]
        )


def handle_event(event, access_token: str):
    if event.get('type') != 'message' or event['message'].get('type') != 'text':
        return
    user_id = event['source'].get('userId', '')
    reply_token = event['replyToken']
    text = event['message']['text'].strip()

    if not LINE_OWNER_USER_ID:
        reply_message(reply_token, [{'type': 'text', 'text': f'Your User ID:\n{user_id}'}], access_token)
        return
    if user_id != LINE_OWNER_USER_ID:
        return

    t = text.lower()
    if t in ['report', 'สต็อก', 'สต๊อก', 'stock', 'สต']:
        _handle_report_menu(reply_token, access_token)
    elif t in ['ต้นทุนสต๊อก', 'ต้นทุน']:
        _handle_cost_stock(reply_token, access_token)
    elif t in ['มูลค่าสต๊อก', 'มูลค่า', 'value', 'มูลค่าสต็อก']:
        _handle_sale_stock(reply_token, access_token)
    elif t in ['product report', 'product']:
        _handle_product_report(reply_token, access_token)
    elif t in ['package report', 'package']:
        _handle_package_report(reply_token, access_token)
    elif t in ['new product', 'newproduct']:
        _handle_new_product_menu(reply_token, access_token)
    elif t in ['non supplier']:
        _handle_check_list(reply_token, 'non_supplier', access_token)
    elif t in ['no cost']:
        _handle_check_list(reply_token, 'no_cost', access_token)
    elif t in ['non price contract']:
        _handle_check_list(reply_token, 'no_contract', access_token)
    elif t in ['no sale price']:
        _handle_check_list(reply_token, 'no_sale', access_token)
    elif t.startswith('full:'):
        _handle_full_report(reply_token, t[5:].strip(), access_token)
    elif text.startswith('กลุ่ม:'):
        _handle_category(reply_token, text[len('กลุ่ม:'):].strip(), access_token)
    elif t.startswith('ค้นหา '):
        _handle_search(reply_token, text[len('ค้นหา '):].strip(), access_token)
    else:
        _handle_help(reply_token, access_token)


# ── Report Menu ───────────────────────────────────────────────────────────────

def _handle_report_menu(reply_token, access_token):
    def _btn(emoji, title, subtitle, msg):
        return {
            'type': 'box', 'layout': 'horizontal', 'paddingAll': '12px',
            'backgroundColor': '#f8f9fa', 'cornerRadius': '8px',
            'action': {'type': 'message', 'label': title, 'text': msg},
            'contents': [
                {'type': 'text', 'text': emoji, 'size': 'xl', 'flex': 1, 'gravity': 'center'},
                {'type': 'box', 'layout': 'vertical', 'flex': 9, 'paddingStart': '8px', 'contents': [
                    {'type': 'text', 'text': title, 'weight': 'bold', 'size': 'sm', 'color': '#1a1a2e'},
                    {'type': 'text', 'text': subtitle, 'size': 'xxs', 'color': '#888888'},
                ]},
                {'type': 'text', 'text': '›', 'size': 'lg', 'color': '#cccccc', 'align': 'end', 'flex': 1, 'gravity': 'center'},
            ],
        }

    bubble = {
        'type': 'bubble',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#1a1a2e', 'paddingAll': '15px',
            'contents': [
                {'type': 'text', 'text': '📊 Dashboard Report', 'weight': 'bold', 'size': 'lg', 'color': '#ffffff'},
                {'type': 'text', 'text': 'เลือกรายงานที่ต้องการ', 'size': 'xs', 'color': '#aaaaaa'},
            ],
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'spacing': 'md', 'paddingAll': '12px',
            'contents': [
                _btn('💰', 'ต้นทุนสต๊อก', 'มูลค่าต้นทุน × จำนวนสต๊อก เรียงมากสุด', 'ต้นทุนสต๊อก'),
                _btn('💲', 'มูลค่าสต๊อก', 'มูลค่าขาย × จำนวนสต๊อก เรียงมากสุด', 'มูลค่าสต๊อก'),
                _btn('📦', 'Product Report', 'สต๊อก + Forecast + ต้นทุน + ขาย แยก Tag', 'product report'),
                _btn('📋', 'Package Report', 'สต๊อก + Forecast + ต้นทุน แยก Tag', 'package report'),
                _btn('🆕', 'New Product', 'ตรวจสอบสินค้าที่ยังข้อมูลไม่ครบ', 'new product'),
            ],
        },
    }
    reply_message(reply_token, [{'type': 'flex', 'altText': '📊 เลือกรายงาน', 'contents': bubble}], access_token)


# ── ต้นทุนสต๊อก ───────────────────────────────────────────────────────────────

def _handle_cost_stock(reply_token, access_token):
    products = list(Product.objects.filter(is_product=True).select_related('category'))
    products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.buy_price or 0), reverse=True)

    grand = sum(float(p.stock_quantity or 0) * float(p.buy_price or 0) for p in products)
    show = products[:20]
    rest = len(products) - len(show)

    rows = []
    for p in show:
        val = float(p.stock_quantity or 0) * float(p.buy_price or 0)
        rows.append({
            'type': 'box', 'layout': 'horizontal', 'margin': 'xs',
            'contents': [
                {'type': 'text', 'text': p.name[:22], 'size': 'xs', 'flex': 5, 'wrap': True, 'color': '#333333'},
                {'type': 'text', 'text': f'{p.stock_quantity:,}', 'size': 'xs', 'flex': 2, 'align': 'end', 'color': '#666666'},
                {'type': 'text', 'text': f'{val:,.0f}฿', 'size': 'xs', 'flex': 3, 'align': 'end', 'weight': 'bold', 'color': '#111111'},
            ],
        })

    body_contents = [
        {'type': 'box', 'layout': 'horizontal', 'contents': [
            {'type': 'text', 'text': 'สินค้า', 'size': 'xxs', 'flex': 5, 'color': '#aaaaaa'},
            {'type': 'text', 'text': 'ชิ้น', 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#aaaaaa'},
            {'type': 'text', 'text': 'ต้นทุน', 'size': 'xxs', 'flex': 3, 'align': 'end', 'color': '#aaaaaa'},
        ]},
        {'type': 'separator', 'margin': 'sm'},
        *rows,
    ]
    if rest > 0:
        body_contents.append({'type': 'text', 'text': f'· · · และอีก {rest} รายการ', 'size': 'xxs', 'color': '#aaaaaa', 'margin': 'sm', 'align': 'center'})

    bubble = {
        'type': 'bubble', 'size': 'mega',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#1a3a2e', 'paddingAll': '12px',
            'contents': [
                {'type': 'text', 'text': '💰 ต้นทุนสต๊อก', 'weight': 'bold', 'color': '#ffffff'},
                {'type': 'text', 'text': f'รวม {grand:,.0f} ฿  |  {len(products)} รายการ', 'size': 'xs', 'color': '#aaaaaa'},
            ],
        },
        'body': {'type': 'box', 'layout': 'vertical', 'paddingAll': '12px', 'contents': body_contents},
        'footer': {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '8px',
            'contents': [{'type': 'button', 'style': 'secondary', 'height': 'sm',
                'action': {'type': 'uri', 'label': '📋 ดูทั้งหมด', 'uri': _report_webview_url('cost')}}],
        } if rest > 0 and os.environ.get('BASE_URL') else None,
    }
    if bubble['footer'] is None:
        bubble.pop('footer')

    reply_message(reply_token, [{'type': 'flex', 'altText': f'💰 ต้นทุนสต๊อก {grand:,.0f} ฿', 'contents': bubble}], access_token)


# ── มูลค่าสต๊อก ───────────────────────────────────────────────────────────────

def _handle_sale_stock(reply_token, access_token):
    products = list(Product.objects.filter(is_product=True).select_related('category'))
    products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.sale_price or 0), reverse=True)

    grand = sum(float(p.stock_quantity or 0) * float(p.sale_price or 0) for p in products)
    show = products[:20]
    rest = len(products) - len(show)

    rows = []
    for p in show:
        val = float(p.stock_quantity or 0) * float(p.sale_price or 0)
        rows.append({
            'type': 'box', 'layout': 'horizontal', 'margin': 'xs',
            'contents': [
                {'type': 'text', 'text': p.name[:22], 'size': 'xs', 'flex': 5, 'wrap': True, 'color': '#333333'},
                {'type': 'text', 'text': f'{p.stock_quantity:,}', 'size': 'xs', 'flex': 2, 'align': 'end', 'color': '#666666'},
                {'type': 'text', 'text': f'{val:,.0f}฿', 'size': 'xs', 'flex': 3, 'align': 'end', 'weight': 'bold', 'color': '#111111'},
            ],
        })

    body_contents = [
        {'type': 'box', 'layout': 'horizontal', 'contents': [
            {'type': 'text', 'text': 'สินค้า', 'size': 'xxs', 'flex': 5, 'color': '#aaaaaa'},
            {'type': 'text', 'text': 'ชิ้น', 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#aaaaaa'},
            {'type': 'text', 'text': 'มูลค่าขาย', 'size': 'xxs', 'flex': 3, 'align': 'end', 'color': '#aaaaaa'},
        ]},
        {'type': 'separator', 'margin': 'sm'},
        *rows,
    ]
    if rest > 0:
        body_contents.append({'type': 'text', 'text': f'· · · และอีก {rest} รายการ', 'size': 'xxs', 'color': '#aaaaaa', 'margin': 'sm', 'align': 'center'})

    bubble = {
        'type': 'bubble', 'size': 'mega',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#2e1a3a', 'paddingAll': '12px',
            'contents': [
                {'type': 'text', 'text': '💲 มูลค่าสต๊อก', 'weight': 'bold', 'color': '#ffffff'},
                {'type': 'text', 'text': f'รวม {grand:,.0f} ฿  |  {len(products)} รายการ', 'size': 'xs', 'color': '#aaaaaa'},
            ],
        },
        'body': {'type': 'box', 'layout': 'vertical', 'paddingAll': '12px', 'contents': body_contents},
        'footer': {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '8px',
            'contents': [{'type': 'button', 'style': 'secondary', 'height': 'sm',
                'action': {'type': 'uri', 'label': '📋 ดูทั้งหมด', 'uri': _report_webview_url('sale')}}],
        } if rest > 0 and os.environ.get('BASE_URL') else None,
    }
    if bubble.get('footer') is None:
        bubble.pop('footer', None)

    reply_message(reply_token, [{'type': 'flex', 'altText': f'💲 มูลค่าสต๊อก {grand:,.0f} ฿', 'contents': bubble}], access_token)


# ── Product Report ────────────────────────────────────────────────────────────

def _handle_product_report(reply_token, access_token):
    try:
        products = list(Product.objects.filter(
            is_product=True, category__name='Product'
        ).prefetch_related('tags').order_by('name'))

        if not products:
            reply_message(reply_token, [{'type': 'text', 'text': '📦 Product Report\nไม่พบสินค้าใน category "Product"'}], access_token)
            return

        forecast = _get_forecast_data(products)
        wv_url = _report_webview_url('product') if os.environ.get('BASE_URL') else None
        bubbles = _build_report_bubbles('📦 Product Report', '#1a2e3a', products, forecast, with_sale=True, webview_url=wv_url)

        if not bubbles:
            reply_message(reply_token, [{'type': 'text', 'text': '📦 Product Report\nไม่มีข้อมูล'}], access_token)
            return

        contents = bubbles[0] if len(bubbles) == 1 else {'type': 'carousel', 'contents': bubbles}
        reply_message(reply_token, [{'type': 'flex', 'altText': f'📦 Product Report ({len(products)} รายการ)', 'contents': contents}], access_token)
    except Exception as e:
        reply_message(reply_token, [{'type': 'text', 'text': f'📦 Product Report Error:\n{type(e).__name__}: {e}'}], access_token)


# ── Package Report ────────────────────────────────────────────────────────────

def _handle_package_report(reply_token, access_token):
    try:
        products = list(Product.objects.filter(
            is_product=True, category__name='Packaging'
        ).prefetch_related('tags').order_by('name'))

        if not products:
            reply_message(reply_token, [{'type': 'text', 'text': '📋 Package Report\nไม่พบสินค้าใน category "Packaging"'}], access_token)
            return

        forecast = _get_forecast_data(products)
        wv_url = _report_webview_url('package') if os.environ.get('BASE_URL') else None
        bubbles = _build_report_bubbles('📋 Package Report', '#2e2a1a', products, forecast, with_sale=False, webview_url=wv_url)

        if not bubbles:
            reply_message(reply_token, [{'type': 'text', 'text': '📋 Package Report\nไม่มีข้อมูล'}], access_token)
            return

        contents = bubbles[0] if len(bubbles) == 1 else {'type': 'carousel', 'contents': bubbles}
        reply_message(reply_token, [{'type': 'flex', 'altText': f'📋 Package Report ({len(products)} รายการ)', 'contents': contents}], access_token)
    except Exception as e:
        reply_message(reply_token, [{'type': 'text', 'text': f'📋 Package Report Error:\n{type(e).__name__}: {e}'}], access_token)


# ── New Product Menu ──────────────────────────────────────────────────────────

def _handle_new_product_menu(reply_token, access_token):
    def _btn(emoji, title, subtitle, msg):
        return {
            'type': 'box', 'layout': 'horizontal', 'paddingAll': '12px',
            'backgroundColor': '#f8f9fa', 'cornerRadius': '8px',
            'action': {'type': 'message', 'label': title, 'text': msg},
            'contents': [
                {'type': 'text', 'text': emoji, 'size': 'xl', 'flex': 1, 'gravity': 'center'},
                {'type': 'box', 'layout': 'vertical', 'flex': 9, 'paddingStart': '8px', 'contents': [
                    {'type': 'text', 'text': title, 'weight': 'bold', 'size': 'sm', 'color': '#1a1a2e'},
                    {'type': 'text', 'text': subtitle, 'size': 'xxs', 'color': '#888888'},
                ]},
                {'type': 'text', 'text': '›', 'size': 'lg', 'color': '#cccccc', 'align': 'end', 'flex': 1, 'gravity': 'center'},
            ],
        }

    bubble = {
        'type': 'bubble',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#3a1a1a', 'paddingAll': '15px',
            'contents': [
                {'type': 'text', 'text': '🆕 ตรวจสอบสินค้า', 'weight': 'bold', 'size': 'lg', 'color': '#ffffff'},
                {'type': 'text', 'text': 'สินค้าที่ข้อมูลยังไม่ครบ', 'size': 'xs', 'color': '#ffaaaa'},
            ],
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'spacing': 'md', 'paddingAll': '12px',
            'contents': [
                _btn('🏭', 'Non Supplier', 'ยังไม่ได้ผูกกับ Supplier', 'non supplier'),
                _btn('💸', 'No Cost', 'ยังไม่มีต้นทุน (buy_price = 0)', 'no cost'),
                _btn('📄', 'Non Price Contract', 'ยังไม่มี Price Contract', 'non price contract'),
                _btn('🏷️', 'No Sale Price', 'ยังไม่มีราคาขาย', 'no sale price'),
            ],
        },
    }
    reply_message(reply_token, [{'type': 'flex', 'altText': '🆕 ตรวจสอบสินค้า', 'contents': bubble}], access_token)


def _handle_check_list(reply_token, check_type, access_token):
    from .models import CustomerProductContract

    if check_type == 'non_supplier':
        qs = Product.objects.filter(is_product=True, product_suppliers__isnull=True)
        title = '🏭 Non Supplier'
        subtitle = 'ยังไม่ได้ผูกกับ Supplier'
        header_color = '#2e1a3a'
    elif check_type == 'no_cost':
        qs = Product.objects.filter(is_product=True, buy_price=0)
        title = '💸 No Cost'
        subtitle = 'ยังไม่มีต้นทุน'
        header_color = '#3a2a1a'
    elif check_type == 'no_contract':
        contracted_ids = CustomerProductContract.objects.values_list('product_id', flat=True).distinct()
        qs = Product.objects.filter(is_product=True).exclude(pk__in=contracted_ids)
        title = '📄 Non Price Contract'
        subtitle = 'ยังไม่มี Price Contract'
        header_color = '#1a2a3a'
    elif check_type == 'no_sale':
        qs = Product.objects.filter(is_product=True, sale_price=0)
        title = '🏷️ No Sale Price'
        subtitle = 'ยังไม่มีราคาขาย'
        header_color = '#3a1a2a'
    else:
        return

    total = qs.count()
    if total == 0:
        reply_message(reply_token, [{'type': 'text', 'text': f'✅ {title}\nไม่มีรายการที่ต้องแก้ไข'}], access_token)
        return

    # โหลดสูงสุด 300 รายการ แบ่ง 12 bubble × 25 (LINE carousel max)
    PER_BUBBLE = 25
    MAX_BUBBLES = 12
    products = list(qs.select_related('category').order_by('name')[:PER_BUBBLE * MAX_BUBBLES])

    def _make_bubble(chunk, page_label):
        rows = []
        for p in chunk:
            cat = p.category.name[:8] if p.category else '-'
            rows.append({
                'type': 'box', 'layout': 'horizontal', 'margin': 'xs',
                'contents': [
                    {'type': 'text', 'text': p.name[:26], 'size': 'xs', 'flex': 7, 'wrap': True, 'color': '#333333'},
                    {'type': 'text', 'text': cat, 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#888888'},
                ],
            })
        return {
            'type': 'bubble', 'size': 'mega',
            'header': {
                'type': 'box', 'layout': 'vertical', 'backgroundColor': header_color, 'paddingAll': '12px',
                'contents': [
                    {'type': 'text', 'text': title, 'weight': 'bold', 'color': '#ffffff'},
                    {'type': 'text', 'text': f'{subtitle} | {total} รายการ  {page_label}', 'size': 'xs', 'color': '#ffcccc'},
                ],
            },
            'body': {
                'type': 'box', 'layout': 'vertical', 'paddingAll': '12px',
                'contents': [
                    {'type': 'box', 'layout': 'horizontal', 'contents': [
                        {'type': 'text', 'text': 'ชื่อสินค้า', 'size': 'xxs', 'flex': 7, 'color': '#aaaaaa'},
                        {'type': 'text', 'text': 'กลุ่ม', 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#aaaaaa'},
                    ]},
                    {'type': 'separator', 'margin': 'sm'},
                    *rows,
                ],
            },
        }

    chunks = [products[i:i+PER_BUBBLE] for i in range(0, len(products), PER_BUBBLE)]
    total_pages = len(chunks)
    bubbles = [_make_bubble(chunk, f'({i+1}/{total_pages})' if total_pages > 1 else '') for i, chunk in enumerate(chunks)]

    if total > PER_BUBBLE * MAX_BUBBLES:
        # เพิ่ม note ที่ bubble สุดท้าย
        bubbles[-1]['body']['contents'].append(
            {'type': 'text', 'text': f'· · · และอีก {total - PER_BUBBLE*MAX_BUBBLES} รายการ', 'size': 'xxs', 'color': '#aaaaaa', 'margin': 'sm', 'align': 'center'}
        )

    if len(bubbles) == 1:
        contents = bubbles[0]
    else:
        contents = {'type': 'carousel', 'contents': bubbles}

    reply_message(reply_token, [{'type': 'flex', 'altText': f'{title} {total} รายการ', 'contents': contents}], access_token)


# ── Full Report (text) ────────────────────────────────────────────────────────

def _handle_full_report(reply_token, report_type, access_token):
    if report_type == 'ต้นทุน':
        products = list(Product.objects.filter(is_product=True))
        products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.buy_price or 0), reverse=True)
        grand = sum(float(p.stock_quantity or 0) * float(p.buy_price or 0) for p in products)
        lines = ['💰 ต้นทุนสต๊อก (ทั้งหมด)', '─' * 24]
        for i, p in enumerate(products, 1):
            val = float(p.stock_quantity or 0) * float(p.buy_price or 0)
            lines.append(f'{i}. {p.name[:18]}: {p.stock_quantity:,} ชิ้น = {val:,.0f}฿')
        lines += ['─' * 24, f'รวม: {grand:,.0f} ฿']
    elif report_type == 'มูลค่า':
        products = list(Product.objects.filter(is_product=True))
        products.sort(key=lambda p: float(p.stock_quantity or 0) * float(p.sale_price or 0), reverse=True)
        grand = sum(float(p.stock_quantity or 0) * float(p.sale_price or 0) for p in products)
        lines = ['💲 มูลค่าสต๊อก (ทั้งหมด)', '─' * 24]
        for i, p in enumerate(products, 1):
            val = float(p.stock_quantity or 0) * float(p.sale_price or 0)
            lines.append(f'{i}. {p.name[:18]}: {p.stock_quantity:,} ชิ้น = {val:,.0f}฿')
        lines += ['─' * 24, f'รวม: {grand:,.0f} ฿']
    else:
        lines = ['ไม่พบรายงาน']

    # ตัดให้ไม่เกิน 4900 ตัวอักษร (LINE limit 5000)
    text = '\n'.join(lines)
    if len(text) > 4900:
        text = text[:4850] + '\n...(ข้อมูลถูกตัด)'

    reply_message(reply_token, [{'type': 'text', 'text': text}], access_token)


# ── สต็อกตามกลุ่ม ──────────────────────────────────────────────────────────

def _handle_category(reply_token, category_name, access_token):
    try:
        category = ProductCategory.objects.get(name__iexact=category_name)
    except ProductCategory.DoesNotExist:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่พบกลุ่ม "{category_name}"'}], access_token)
        return

    products = list(Product.objects.filter(category=category, is_product=True).order_by('name'))
    if not products:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่มีสินค้าในกลุ่ม {category_name}'}], access_token)
        return

    bubbles = [_product_bubble(p) for p in products[:10]]
    reply_message(reply_token, [{
        'type': 'flex',
        'altText': f'สต็อกกลุ่ม {category_name} ({len(products)} รายการ)',
        'contents': {'type': 'carousel', 'contents': bubbles},
    }], access_token)


# ── ค้นหา ───────────────────────────────────────────────────────────────────

def _handle_search(reply_token, keyword, access_token):
    products = list(Product.objects.filter(name__icontains=keyword, is_product=True).order_by('name')[:10])
    if not products:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่พบสินค้าที่ค้นหา "{keyword}"'}], access_token)
        return
    bubbles = [_product_bubble(p) for p in products]
    reply_message(reply_token, [{
        'type': 'flex',
        'altText': f'ค้นหา "{keyword}" พบ {len(products)} รายการ',
        'contents': {'type': 'carousel', 'contents': bubbles},
    }], access_token)


# ── Help ─────────────────────────────────────────────────────────────────────

def _handle_help(reply_token, access_token):
    reply_message(reply_token, [{'type': 'text', 'text': (
        '📋 คำสั่งที่ใช้ได้:\n'
        '• report — เมนูรายงาน\n'
        '• ต้นทุนสต๊อก — เรียงตามต้นทุน\n'
        '• มูลค่าสต๊อก — เรียงตามมูลค่าขาย\n'
        '• product report — แยกตาม Tag\n'
        '• package report — แยกตาม Tag\n'
        '• new product — ตรวจสอบข้อมูลไม่ครบ\n'
        '• ค้นหา [ชื่อ] — ค้นหาสินค้า\n'
        '• กลุ่ม:[ชื่อ] — สต็อกตามกลุ่ม'
    )}], access_token)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_forecast_data(products):
    from .models import PurchaseItem, SalesItem, ProductionOrder, ProductionMaterialUsage

    if not products:
        return {}

    ids = [p.pk for p in products]

    def _bulk_sum(qs, key, field_a, field_b):
        result = {}
        for row in qs.values(key, field_a, field_b):
            k = row[key]
            a = float(row[field_a] or 0)
            b = float(row[field_b] or 0)
            result[k] = result.get(k, 0.0) + max(0.0, a - b)
        return {k: int(round(v)) for k, v in result.items()}

    po = _bulk_sum(PurchaseItem.objects.filter(product__in=ids, purchase_order__status__in=_ACTIVE_PO), 'product', 'quantity_ordered', 'quantity_received')
    so = _bulk_sum(SalesItem.objects.filter(product__in=ids, sales_order__status__in=_ACTIVE_SO), 'product', 'quantity_ordered', 'quantity_shipped')
    pd_r = _bulk_sum(ProductionOrder.objects.filter(product__in=ids, status__in=_ACTIVE_PD), 'product', 'quantity_planned', 'quantity_actual')
    pd_u = _bulk_sum(ProductionMaterialUsage.objects.filter(raw_material__in=ids, production_order__status__in=_ACTIVE_PD), 'raw_material', 'actual_qty_to_use', 'used_so_far')

    result = {}
    for p in products:
        fore = (p.stock_quantity or 0) + po.get(p.pk, 0) - so.get(p.pk, 0) + pd_r.get(p.pk, 0) - pd_u.get(p.pk, 0)
        result[p.pk] = {
            'forecast': fore,
            'cost_value': fore * float(p.buy_price or 0),
            'sale_value': fore * float(p.sale_price or 0),
        }
    return result


def _fmt(n):
    """แสดงตัวเลขสูงสุด 4 หลักนัยสำคัญ ใช้ K / M แทน"""
    n = float(n)
    if n >= 1_000_000:
        v = n / 1_000_000
        s = f'{v:.3f}M' if v < 10 else (f'{v:.2f}M' if v < 100 else f'{v:.1f}M')
    elif n >= 1_000:
        v = n / 1_000
        s = f'{v:.3f}K' if v < 10 else (f'{v:.2f}K' if v < 100 else f'{v:.1f}K')
    else:
        s = str(int(round(n)))
    return s


def _col_header(with_sale=True):
    cols = [
        {'type': 'text', 'text': 'สินค้า', 'size': 'xxs', 'flex': 4, 'color': '#aaaaaa'},
        {'type': 'text', 'text': 'สต๊อก', 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#aaaaaa'},
        {'type': 'text', 'text': 'Fore', 'size': 'xxs', 'flex': 2, 'align': 'end', 'color': '#aaaaaa'},
        {'type': 'text', 'text': 'ทุน฿', 'size': 'xxs', 'flex': 3, 'align': 'end', 'color': '#aaaaaa'},
    ]
    if with_sale:
        cols.append({'type': 'text', 'text': 'ขาย฿', 'size': 'xxs', 'flex': 3, 'align': 'end', 'color': '#aaaaaa'})
    return {'type': 'box', 'layout': 'horizontal', 'margin': 'sm', 'contents': cols}


def _build_report_bubbles(report_title, header_color, products, forecast, with_sale, webview_url=None):
    """1 bubble แสดงยอดรวมต่อ tag ทุก tag + ปุ่ม ดูรายละเอียด → webview"""
    tag_groups = defaultdict(list)
    for p in products:
        tags = list(p.tags.all())
        if tags:
            for tg in tags:
                tag_groups[tg.name].append(p)
        else:
            tag_groups['Non Tag'].append(p)

    def _sort_key(k):
        return (1, k) if k == 'Non Tag' else (0, k)

    grand_curr = grand_cost = grand_sale = 0

    # helper: box wrapper ที่ centering ด้วย justifyContent (แทน align ที่ไม่แน่นอนใน LINE)
    def _cbox(text, flex, color, size='xxs', bold=False):
        t = {'type': 'text', 'text': text, 'size': size, 'color': color}
        if bold:
            t['weight'] = 'bold'
        return {'type': 'box', 'layout': 'horizontal', 'flex': flex,
                'justifyContent': 'center', 'contents': [t]}

    # col header
    hdr_contents = [
        {'type': 'text', 'text': 'Tag / กลุ่ม', 'size': 'xxs', 'flex': 5, 'color': '#888888'},
        _cbox('ชิ้น', 3, '#888888'),
        _cbox('ต้นทุน฿', 4, '#888888'),
    ]
    if with_sale:
        hdr_contents.append(_cbox('ขาย฿', 4, '#888888'))

    body_rows = [
        {'type': 'box', 'layout': 'horizontal', 'margin': 'sm', 'contents': hdr_contents},
        {'type': 'separator', 'margin': 'sm'},
    ]

    for tag_name in sorted(tag_groups.keys(), key=_sort_key):
        tprods = tag_groups[tag_name]
        t_curr = t_cost = t_sale = 0
        for p in tprods:
            fd = forecast.get(p.pk, {})
            t_curr += int(p.stock_quantity or 0)
            t_cost += fd.get('cost_value', 0.0)
            t_sale += fd.get('sale_value', 0.0)
        grand_curr += t_curr; grand_cost += t_cost; grand_sale += t_sale

        row_contents = [
            {'type': 'text', 'text': f'{tag_name} ({len(tprods)})', 'size': 'xxs', 'flex': 5,
             'color': '#333333', 'weight': 'bold'},
            _cbox(_fmt(t_curr), 3, '#555555'),
            _cbox(_fmt(t_cost), 4, '#FF8C00'),
        ]
        if with_sale:
            row_contents.append(_cbox(_fmt(t_sale), 4, '#28a745'))

        row_box = {'type': 'box', 'layout': 'horizontal', 'margin': 'xs',
                   'paddingAll': '4px', 'contents': row_contents}
        if webview_url:
            row_box['action'] = {'type': 'uri', 'label': tag_name, 'uri': webview_url}
        body_rows.append(row_box)

    # grand total
    body_rows.append({'type': 'separator', 'margin': 'md'})
    gt_contents = [
        {'type': 'text', 'text': f'รวม ({len(products)})', 'size': 'xs', 'flex': 5,
         'color': '#1a1a2e', 'weight': 'bold'},
        _cbox(_fmt(grand_curr), 3, '#1a1a2e', size='xs', bold=True),
        _cbox(_fmt(grand_cost), 4, '#FF8C00', size='xs', bold=True),
    ]
    if with_sale:
        gt_contents.append(_cbox(_fmt(grand_sale), 4, '#28a745', size='xs', bold=True))
    body_rows.append({'type': 'box', 'layout': 'horizontal', 'margin': 'sm', 'contents': gt_contents})

    bubble = {
        'type': 'bubble', 'size': 'mega',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': header_color, 'paddingAll': '12px',
            'contents': [
                {'type': 'text', 'text': report_title, 'weight': 'bold', 'color': '#ffffff', 'size': 'md'},
                {'type': 'text', 'text': f'{len(products)} รายการ · แยกตาม Tag', 'size': 'xxs', 'color': '#aaaaaa'},
            ],
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '12px', 'spacing': 'none',
            'contents': body_rows,
        },
    }

    if webview_url:
        bubble['footer'] = {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '10px',
            'contents': [{'type': 'button', 'style': 'primary', 'color': header_color, 'height': 'sm',
                          'action': {'type': 'uri', 'label': '📋 ดูรายละเอียดทั้งหมด', 'uri': webview_url}}],
        }

    return [bubble]


def _product_bubble(product):
    value = (product.stock_quantity or 0) * float(product.buy_price or 0)
    stock_color = '#27ACB2' if (product.stock_quantity or 0) > 0 else '#FF5551'
    category_name = product.category.name if product.category else '-'
    return {
        'type': 'bubble', 'size': 'kilo',
        'header': {
            'type': 'box', 'layout': 'vertical', 'backgroundColor': '#f0f4f8', 'paddingAll': '10px',
            'contents': [
                {'type': 'text', 'text': category_name, 'size': 'xxs', 'color': '#888888'},
                {'type': 'text', 'text': product.name, 'weight': 'bold', 'size': 'sm', 'color': '#1a1a2e', 'wrap': True},
            ],
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'paddingAll': '12px', 'spacing': 'sm',
            'contents': [
                _info_row('📦 สต็อก', f'{product.stock_quantity:,} ชิ้น', stock_color),
                _info_row('💵 ราคาทุน', f'{float(product.buy_price or 0):,.2f} ฿', '#333333'),
                {'type': 'separator'},
                _info_row('💰 มูลค่า', f'{value:,.0f} ฿', '#FF8C00'),
            ],
        },
    }


def _info_row(label, value, value_color='#111111'):
    return {
        'type': 'box', 'layout': 'horizontal',
        'contents': [
            {'type': 'text', 'text': label, 'size': 'xs', 'color': '#888888', 'flex': 3},
            {'type': 'text', 'text': value, 'size': 'xs', 'weight': 'bold', 'color': value_color, 'align': 'end', 'flex': 4},
        ],
    }
