import hashlib
import hmac
import base64
import json
import os
import requests
from .models import Product, ProductCategory

LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', '')
LINE_OWNER_USER_ID = os.environ.get('LINE_OWNER_USER_ID', '')

REPLY_URL = 'https://api.line.me/v2/bot/message/reply'


def verify_signature(body: bytes, signature: str) -> bool:
    mac = hmac.new(LINE_CHANNEL_SECRET.encode('utf-8'), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode('utf-8')
    return hmac.compare_digest(expected, signature)


def reply_message(reply_token, messages):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}',
    }
    requests.post(REPLY_URL, headers=headers, json={
        'replyToken': reply_token,
        'messages': messages,
    }, timeout=10)


def handle_event(event):
    if event.get('type') != 'message':
        return
    if event['message'].get('type') != 'text':
        return

    user_id = event['source'].get('userId', '')
    reply_token = event['replyToken']
    text = event['message']['text'].strip()

    # ถ้ายังไม่ตั้ง owner → ตอบ user id กลับ (ใช้ตอน setup ครั้งแรก)
    if not LINE_OWNER_USER_ID:
        reply_message(reply_token, [{'type': 'text', 'text': f'Your User ID:\n{user_id}'}])
        return

    # ตรวจสิทธิ์
    if user_id != LINE_OWNER_USER_ID:
        return

    text_lower = text.lower()

    if text_lower in ['report', 'สต็อก', 'สต๊อก', 'stock', 'สต']:
        _handle_stock_menu(reply_token)
    elif text.startswith('กลุ่ม:'):
        _handle_category(reply_token, text[len('กลุ่ม:'):].strip())
    elif text_lower.startswith('ค้นหา '):
        _handle_search(reply_token, text[len('ค้นหา '):].strip())
    elif text_lower in ['มูลค่า', 'value', 'มูลค่าสต็อก']:
        _handle_total_value(reply_token)
    else:
        _handle_help(reply_token)


# ── Menu หลัก ──────────────────────────────────────────────────────────────

def _handle_stock_menu(reply_token):
    categories = list(ProductCategory.objects.order_by('name'))
    items = []
    for cat in categories[:12]:  # Line limit 13 quick reply items
        items.append({
            'type': 'action',
            'action': {
                'type': 'message',
                'label': cat.name[:20],
                'text': f'กลุ่ม:{cat.name}',
            },
        })
    items.append({
        'type': 'action',
        'action': {'type': 'message', 'label': '💰 มูลค่ารวม', 'text': 'มูลค่า'},
    })

    reply_message(reply_token, [{
        'type': 'text',
        'text': '📦 เลือกกลุ่มสินค้าที่ต้องการดูสต็อก:',
        'quickReply': {'items': items},
    }])


# ── สต็อกตามกลุ่ม ──────────────────────────────────────────────────────────

def _handle_category(reply_token, category_name):
    try:
        category = ProductCategory.objects.get(name__iexact=category_name)
    except ProductCategory.DoesNotExist:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่พบกลุ่ม "{category_name}"'}])
        return

    products = list(
        Product.objects.filter(category=category, is_product=True).order_by('name')
    )
    if not products:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่มีสินค้าในกลุ่ม {category_name}'}])
        return

    bubbles = [_product_bubble(p) for p in products[:10]]

    reply_message(reply_token, [{
        'type': 'flex',
        'altText': f'สต็อกกลุ่ม {category_name} ({len(products)} รายการ)',
        'contents': {'type': 'carousel', 'contents': bubbles},
    }])


# ── ค้นหาตามชื่อ ────────────────────────────────────────────────────────────

def _handle_search(reply_token, keyword):
    products = list(
        Product.objects.filter(name__icontains=keyword, is_product=True).order_by('name')[:10]
    )
    if not products:
        reply_message(reply_token, [{'type': 'text', 'text': f'ไม่พบสินค้าที่ค้นหา "{keyword}"'}])
        return

    bubbles = [_product_bubble(p) for p in products]

    reply_message(reply_token, [{
        'type': 'flex',
        'altText': f'ค้นหา "{keyword}" พบ {len(products)} รายการ',
        'contents': {'type': 'carousel', 'contents': bubbles},
    }])


# ── มูลค่าสต็อกรวมทุกกลุ่ม ──────────────────────────────────────────────────

def _handle_total_value(reply_token):
    categories = ProductCategory.objects.order_by('name')
    rows = []
    grand_total = 0

    for cat in categories:
        products = Product.objects.filter(category=cat, is_product=True)
        cat_value = sum(p.stock_quantity * p.buy_price for p in products)
        cat_qty = sum(p.stock_quantity for p in products)
        grand_total += cat_value
        rows.append({
            'type': 'box',
            'layout': 'horizontal',
            'contents': [
                {'type': 'text', 'text': cat.name, 'size': 'sm', 'color': '#555555', 'flex': 4, 'wrap': True},
                {'type': 'text', 'text': f'{cat_qty:,}', 'size': 'sm', 'color': '#888888', 'align': 'end', 'flex': 2},
                {'type': 'text', 'text': f'{cat_value:,.0f}฿', 'size': 'sm', 'color': '#111111', 'align': 'end', 'flex': 3},
            ],
            'margin': 'sm',
        })

    bubble = {
        'type': 'bubble',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': '#1a1a2e',
            'paddingAll': '15px',
            'contents': [
                {'type': 'text', 'text': '💰 มูลค่าสต็อกรวม', 'weight': 'bold', 'size': 'lg', 'color': '#ffffff'},
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '15px',
            'spacing': 'none',
            'contents': [
                # header row
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'contents': [
                        {'type': 'text', 'text': 'กลุ่ม', 'size': 'xs', 'color': '#aaaaaa', 'flex': 4},
                        {'type': 'text', 'text': 'ชิ้น', 'size': 'xs', 'color': '#aaaaaa', 'align': 'end', 'flex': 2},
                        {'type': 'text', 'text': 'มูลค่า', 'size': 'xs', 'color': '#aaaaaa', 'align': 'end', 'flex': 3},
                    ],
                },
                {'type': 'separator', 'margin': 'sm'},
                *rows,
                {'type': 'separator', 'margin': 'md'},
                {
                    'type': 'box',
                    'layout': 'horizontal',
                    'margin': 'md',
                    'contents': [
                        {'type': 'text', 'text': 'รวมทั้งหมด', 'weight': 'bold', 'size': 'md', 'flex': 5},
                        {'type': 'text', 'text': f'{grand_total:,.0f} ฿', 'weight': 'bold', 'size': 'md', 'color': '#27ACB2', 'align': 'end', 'flex': 4},
                    ],
                },
            ],
        },
    }

    reply_message(reply_token, [{
        'type': 'flex',
        'altText': f'มูลค่าสต็อกรวม {grand_total:,.0f} บาท',
        'contents': bubble,
    }])


# ── Help ────────────────────────────────────────────────────────────────────

def _handle_help(reply_token):
    reply_message(reply_token, [{
        'type': 'text',
        'text': (
            '📋 คำสั่งที่ใช้ได้:\n'
            '• สต็อก — ดูสต็อกตามกลุ่ม\n'
            '• ค้นหา [ชื่อ] — ค้นหาสินค้า\n'
            '• มูลค่า — มูลค่าสต็อกรวมทุกกลุ่ม'
        ),
    }])


# ── Flex Bubble สินค้า ──────────────────────────────────────────────────────

def _product_bubble(product):
    value = product.stock_quantity * product.buy_price
    stock_color = '#27ACB2' if product.stock_quantity > 0 else '#FF5551'
    category_name = product.category.name if product.category else '-'

    return {
        'type': 'bubble',
        'size': 'kilo',
        'header': {
            'type': 'box',
            'layout': 'vertical',
            'backgroundColor': '#f0f4f8',
            'paddingAll': '10px',
            'contents': [
                {'type': 'text', 'text': category_name, 'size': 'xxs', 'color': '#888888'},
                {'type': 'text', 'text': product.name, 'weight': 'bold', 'size': 'sm', 'color': '#1a1a2e', 'wrap': True},
            ],
        },
        'body': {
            'type': 'box',
            'layout': 'vertical',
            'paddingAll': '12px',
            'spacing': 'sm',
            'contents': [
                _info_row('📦 สต็อก', f'{product.stock_quantity:,} ชิ้น', stock_color),
                _info_row('💵 ราคาทุน', f'{product.buy_price:,.2f} ฿', '#333333'),
                {'type': 'separator'},
                _info_row('💰 มูลค่า', f'{value:,.0f} ฿', '#FF8C00'),
            ],
        },
    }


def _info_row(label, value, value_color='#111111'):
    return {
        'type': 'box',
        'layout': 'horizontal',
        'contents': [
            {'type': 'text', 'text': label, 'size': 'xs', 'color': '#888888', 'flex': 3},
            {'type': 'text', 'text': value, 'size': 'xs', 'weight': 'bold', 'color': value_color, 'align': 'end', 'flex': 4},
        ],
    }
