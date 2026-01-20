"""
🌍 HONESTWORLD v23.0 - ULTIMATE PERFECT EDITION
Smart AI • 20 Fair Laws • Learning System • Premium Features
"""

import streamlit as st
import google.generativeai as genai
import json
import re
import sqlite3
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import requests
from datetime import datetime, timedelta
import uuid
import urllib.parse
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import os

st.set_page_config(page_title="HonestWorld", page_icon="🌍", layout="centered", initial_sidebar_state="collapsed")

VERSION = "23.0"
LOCAL_DB = Path.home() / "honestworld_v23.db"

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# THE 20 INTEGRITY LAWS - FAIR & EVIDENCE-BASED
INTEGRITY_LAWS = {
    1: {"name": "Water-Down Deception", "points": -15, "category": "ingredients", "applies_to": ["food", "cosmetics", "household"], "description": "Product claims 'premium/luxury' but #1 ingredient is water/cheap filler", "tip": "Check if the first ingredient matches the premium price"},
    2: {"name": "Fairy Dusting", "points": -12, "category": "ingredients", "applies_to": ["food", "cosmetics"], "description": "Hero ingredient advertised on front is below position #5", "tip": "Ingredients are listed by quantity - first = most"},
    3: {"name": "Split Sugar Trick", "points": -18, "category": "ingredients", "applies_to": ["food"], "description": "Sugar split into 3+ names to hide total amount", "tip": "Add up ALL sugar types - they're often the real #1 ingredient"},
    4: {"name": "Low-Fat Trap", "points": -10, "category": "ingredients", "applies_to": ["food"], "description": "Claims 'low fat' but compensates with high sugar", "tip": "Low-fat often means high sugar - check nutrition label"},
    5: {"name": "Natural Fallacy", "points": -10, "category": "ingredients", "applies_to": ["food", "cosmetics", "household"], "description": "Claims 'natural' but contains synthetic ingredients", "tip": "'Natural' is unregulated - look for actual certifications"},
    6: {"name": "Made-With Loophole", "points": -8, "category": "ingredients", "applies_to": ["food", "cosmetics"], "description": "'Made with real X' but X is minimal in list", "tip": "'Made with' only requires a tiny amount"},
    7: {"name": "Serving Size Trick", "points": -10, "category": "packaging", "applies_to": ["food"], "description": "Unrealistically small serving size", "tip": "Check servings per container - you probably eat more"},
    8: {"name": "Slack Fill", "points": -8, "category": "packaging", "applies_to": ["food", "cosmetics", "household"], "description": "Package is mostly air/empty space", "tip": "Check net weight, not package size"},
    9: {"name": "Spec Inflation", "points": -15, "category": "electronics", "applies_to": ["electronics"], "description": "'Up to X speed/capacity' unrealistic claims", "tip": "'Up to' means maximum under perfect conditions"},
    10: {"name": "Compatibility Lie", "points": -12, "category": "electronics", "applies_to": ["electronics"], "description": "'Universal' with hidden exceptions", "tip": "Check compatibility list in fine print"},
    11: {"name": "Military Grade Myth", "points": -10, "category": "electronics", "applies_to": ["electronics", "household"], "description": "Claims 'military grade' without MIL-STD cert", "tip": "Real military spec products cite the MIL-STD number"},
    12: {"name": "Battery Fiction", "points": -12, "category": "electronics", "applies_to": ["electronics"], "description": "Unrealistic battery life claims", "tip": "Battery life tested with screen dim and minimal use"},
    13: {"name": "Clinical Ghost", "points": -12, "category": "beauty", "applies_to": ["cosmetics"], "description": "'Clinically proven' without study citation", "tip": "Real clinical proof includes study size and methodology"},
    14: {"name": "Concentration Trick", "points": -10, "category": "beauty", "applies_to": ["cosmetics"], "description": "Active ingredient too diluted to be effective", "tip": "Effective concentrations: Vitamin C 10-20%, Retinol 0.3-1%"},
    15: {"name": "Free Trap", "points": -15, "category": "services", "applies_to": ["services"], "description": "'Free' requires credit card or hidden purchase", "tip": "'Free trial' usually auto-charges - set cancel reminder"},
    16: {"name": "Unlimited Lie", "points": -18, "category": "services", "applies_to": ["services", "electronics"], "description": "'Unlimited' with caps or throttling", "tip": "'Unlimited' almost never means truly unlimited"},
    17: {"name": "Lifetime Illusion", "points": -10, "category": "services", "applies_to": ["services", "electronics"], "description": "'Lifetime warranty' with extensive exclusions", "tip": "'Lifetime' often means limited with many exclusions"},
    18: {"name": "Photo vs Reality", "points": -12, "category": "packaging", "applies_to": ["food"], "description": "Package photo much better than actual product", "tip": "Package photos are styled - read actual contents"},
    19: {"name": "Fake Certification", "points": -15, "category": "claims", "applies_to": ["food", "cosmetics", "electronics", "household"], "description": "Claims certification without proper logo/number", "tip": "Real certifications show certifier's logo and ID number"},
    20: {"name": "Name Trick", "points": -10, "category": "claims", "applies_to": ["food", "cosmetics"], "description": "Product name implies ingredient not present", "tip": "'Honey Oat' doesn't mean it contains much honey or oat"}
}

SCORE_THRESHOLDS = {'EXCEPTIONAL': 90, 'BUY': 75, 'CAUTION': 50}

def get_verdict(score):
    if score >= 90: return "EXCEPTIONAL"
    elif score >= 75: return "BUY"
    elif score >= 50: return "CAUTION"
    return "AVOID"

def get_verdict_display(verdict):
    return {'EXCEPTIONAL': {'icon': '⭐', 'text': 'EXCEPTIONAL', 'color': '#06b6d4'},
            'BUY': {'icon': '✓', 'text': 'GOOD TO BUY', 'color': '#22c55e'},
            'CAUTION': {'icon': '!', 'text': 'CHECK FIRST', 'color': '#f59e0b'},
            'AVOID': {'icon': '✗', 'text': 'NOT RECOMMENDED', 'color': '#ef4444'},
            'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}}.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})

PRODUCT_TYPES = {
    "food": {"keywords": ["nutrition facts", "calories", "serving size", "ingredients:", "sugar", "protein", "carbohydrate", "fat", "sodium", "vitamin", "snack", "cereal", "drink", "beverage"], "laws": [1, 2, 3, 4, 5, 6, 7, 8, 18, 19, 20]},
    "cosmetics": {"keywords": ["skin", "hair", "moisturizer", "cleanser", "shampoo", "conditioner", "lotion", "cream", "serum", "sunscreen", "spf", "makeup", "dermatologist", "paraben", "sulfate", "fragrance"], "laws": [1, 2, 5, 6, 8, 13, 14, 19, 20]},
    "electronics": {"keywords": ["battery", "usb", "cable", "charger", "wireless", "bluetooth", "wifi", "mah", "watt", "volt", "gb", "tb", "processor", "device"], "laws": [9, 10, 11, 12, 16, 17, 19]},
    "services": {"keywords": ["subscription", "monthly", "annual", "plan", "trial", "free", "unlimited", "membership", "warranty"], "laws": [15, 16, 17, 19]},
    "household": {"keywords": ["cleaner", "detergent", "soap", "cleaning", "household", "laundry", "dish", "disinfectant"], "laws": [1, 5, 8, 11, 19, 20]}
}

WATCH_INGREDIENTS = {
    "paraben": {"severity": "high", "points": -8}, "methylparaben": {"severity": "high", "points": -8},
    "propylparaben": {"severity": "high", "points": -8}, "sodium lauryl sulfate": {"severity": "medium", "points": -6},
    "sodium laureth sulfate": {"severity": "medium", "points": -6}, "fragrance": {"severity": "medium", "points": -8},
    "parfum": {"severity": "medium", "points": -8}, "phthalate": {"severity": "high", "points": -12},
    "dmdm hydantoin": {"severity": "high", "points": -15}, "quaternium-15": {"severity": "high", "points": -15},
    "triclosan": {"severity": "high", "points": -12}, "oxybenzone": {"severity": "medium", "points": -8},
    "high fructose corn syrup": {"severity": "high", "points": -10}, "trans fat": {"severity": "high", "points": -12},
    "hydrogenated": {"severity": "high", "points": -10}, "red 40": {"severity": "medium", "points": -5},
    "yellow 5": {"severity": "medium", "points": -5}, "blue 1": {"severity": "medium", "points": -5},
}

HEALTH_PROFILES = {
    "diabetes": {"name": "Diabetes", "icon": "🩺", "watch_ingredients": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin"]},
    "baby": {"name": "Baby Safe", "icon": "👶", "watch_ingredients": ["fragrance", "parfum", "alcohol", "retinol", "salicylic", "essential oil", "menthol"]},
    "pregnancy": {"name": "Pregnancy", "icon": "🤰", "watch_ingredients": ["retinol", "retinoid", "salicylic acid", "benzoyl peroxide", "hydroquinone", "phthalate"]},
    "sensitive": {"name": "Sensitive Skin", "icon": "🌸", "watch_ingredients": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate"]},
    "vegan": {"name": "Vegan", "icon": "🌱", "watch_ingredients": ["gelatin", "lanolin", "carmine", "beeswax", "collagen", "keratin", "silk", "honey", "milk", "whey"]},
    "glutenfree": {"name": "Gluten-Free", "icon": "🌾", "watch_ingredients": ["wheat", "barley", "rye", "oat", "gluten", "malt"]},
    "heartcondition": {"name": "Heart Health", "icon": "❤️", "watch_ingredients": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat"]},
    "allergyprone": {"name": "Allergy Prone", "icon": "🤧", "watch_ingredients": ["fragrance", "nut", "peanut", "soy", "milk", "egg", "wheat", "shellfish"]}
}

ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "flour", "malt"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy"]},
    "fragrance": {"name": "Fragrance", "icon": "🌺", "triggers": ["fragrance", "parfum", "perfume"]},
    "sulfates": {"name": "Sulfates", "icon": "🧴", "triggers": ["sulfate", "sls", "sles", "sodium lauryl"]},
    "parabens": {"name": "Parabens", "icon": "⚗️", "triggers": ["paraben", "methylparaben", "propylparaben"]}
}

ALTERNATIVES = {
    "cleanser": {"name": "CeraVe Hydrating Cleanser", "why": "Fragrance-free, ceramides", "score": 92},
    "moisturizer": {"name": "CeraVe Moisturizing Cream", "why": "Ceramides, hyaluronic acid, fragrance-free", "score": 94},
    "sunscreen": {"name": "EltaMD UV Clear SPF 46", "why": "Zinc oxide, niacinamide, fragrance-free", "score": 93},
    "shampoo": {"name": "Free & Clear Shampoo", "why": "No sulfates, fragrance, parabens", "score": 94},
    "conditioner": {"name": "Free & Clear Conditioner", "why": "Gentle formula for sensitive scalps", "score": 93},
    "body wash": {"name": "Dove Sensitive Skin Body Wash", "why": "Hypoallergenic, fragrance-free option", "score": 87},
    "deodorant": {"name": "Native Deodorant (Unscented)", "why": "No aluminum, parabens, sulfates", "score": 86},
    "baby": {"name": "Cetaphil Baby Daily Lotion", "why": "Pediatrician tested, no parabens", "score": 91},
    "cereal": {"name": "Nature's Path Organic Cereals", "why": "USDA organic, no artificial colors", "score": 85},
    "snack": {"name": "RXBAR or Larabar", "why": "Simple ingredients, no added sugar", "score": 82},
    "default": {"name": "Search EWG.org database", "why": "Independent safety ratings for 80,000+ products", "score": None}
}

def get_alternative(product_name, product_type):
    search_text = f"{product_name} {product_type or ''}".lower()
    for key in ALTERNATIVES:
        if key in search_text and ALTERNATIVES[key]['name'].lower() not in search_text:
            return ALTERNATIVES[key]
    return ALTERNATIVES['default']

RETAILERS = {
    "AU": ["Chemist Warehouse", "Priceline Pharmacy", "Woolworths", "Coles"],
    "US": ["CVS Pharmacy", "Walgreens", "Target", "Walmart", "Whole Foods"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's"],
    "NZ": ["Chemist Warehouse", "Countdown", "Unichem"],
    "CA": ["Shoppers Drug Mart", "Walmart", "London Drugs"],
    "OTHER": ["Local pharmacy", "Health food store", "Online retailers"]
}

def get_location():
    for url, extract in [('https://ipapi.co/json/', lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))),
                          ('https://ip-api.com/json/', lambda d: (d.get('city'), d.get('country'), d.get('countryCode')))]:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                d = r.json()
                city, country, code = extract(d)
                if city and city not in ['', 'Unknown', None]:
                    return {'city': city, 'country': country or '', 'code': code or 'OTHER', 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
        except: continue
    return {'city': 'Unknown', 'country': 'Unknown', 'code': 'OTHER', 'retailers': RETAILERS['OTHER']}
# DATABASE WITH LEARNING SYSTEM
def normalize_product_name(name):
    return re.sub(r'[^\w\s]', '', name.lower()).strip() if name else ""

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT, product_type TEXT, score INTEGER, verdict TEXT, ingredients TEXT, violations TEXT, thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS learned_products (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name_lower TEXT UNIQUE, product_name TEXT, brand TEXT, product_type TEXT, avg_score REAL, scan_count INTEGER DEFAULT 1, ingredients TEXT, violations TEXT, last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (barcode TEXT PRIMARY KEY, product_name TEXT, brand TEXT, ingredients TEXT, product_type TEXT, score INTEGER, source TEXT, ai_data TEXT, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE)''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (id INTEGER PRIMARY KEY DEFAULT 1, user_id TEXT, city TEXT, country TEXT, country_code TEXT)''')
    c.execute('SELECT user_id FROM user_info WHERE id=1')
    if not c.fetchone(): c.execute('INSERT INTO user_info (id, user_id) VALUES (1, ?)', (str(uuid.uuid4()),))
    conn.commit()
    conn.close()

def get_user_id():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT user_id FROM user_info WHERE id=1')
    r = c.fetchone()
    conn.close()
    return r[0] if r else str(uuid.uuid4())

def get_saved_location():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT city, country, country_code FROM user_info WHERE id=1')
    r = c.fetchone()
    conn.close()
    if r and r[0] and r[0] not in ['Unknown', '']:
        code = r[2] or 'OTHER'
        return {'city': r[0], 'country': r[1] or 'Unknown', 'code': code, 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
    return None

def save_location(city, country):
    code = 'AU' if country and 'austral' in country.lower() else 'US' if country and ('united states' in country.lower() or 'usa' in country.lower()) else 'GB' if country and 'united kingdom' in country.lower() else 'NZ' if country and 'zealand' in country.lower() else 'CA' if country and 'canada' in country.lower() else 'OTHER'
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE user_info SET city=?, country=?, country_code=? WHERE id=1', (city, country, code))
    conn.commit()
    conn.close()
    return code

def learn_product(result):
    try:
        name = result.get('product_name', '')
        name_lower = normalize_product_name(name)
        if not name_lower or len(name_lower) < 3: return
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT avg_score, scan_count FROM learned_products WHERE product_name_lower = ?', (name_lower,))
        existing = c.fetchone()
        if existing:
            old_avg, count = existing
            new_count = count + 1
            new_avg = ((old_avg * count) + result.get('score', 70)) / new_count
            c.execute('UPDATE learned_products SET avg_score=?, scan_count=?, last_scanned=CURRENT_TIMESTAMP, ingredients=?, violations=? WHERE product_name_lower=?', (new_avg, new_count, json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), name_lower))
        else:
            c.execute('INSERT INTO learned_products (product_name_lower, product_name, brand, product_type, avg_score, ingredients, violations) VALUES (?,?,?,?,?,?,?)', (name_lower, name, result.get('brand', ''), result.get('product_type', ''), result.get('score', 70), json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', []))))
        conn.commit()
        conn.close()
    except: pass

def get_learned_product(product_name):
    try:
        name_lower = normalize_product_name(product_name)
        if not name_lower: return None
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, product_type, avg_score, scan_count, ingredients, violations FROM learned_products WHERE product_name_lower = ?', (name_lower,))
        r = c.fetchone()
        conn.close()
        if r: return {'product_name': r[0], 'brand': r[1], 'product_type': r[2], 'score': int(r[3]), 'scan_count': r[4], 'ingredients': json.loads(r[5]) if r[5] else [], 'violations': json.loads(r[6]) if r[6] else []}
    except: pass
    return None

def cache_barcode(barcode, data, score):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO barcode_cache (barcode, product_name, brand, ingredients, product_type, score, source, ai_data, last_updated) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)', (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''), data.get('product_type', ''), score, data.get('source', ''), json.dumps(data.get('ai_data', {}))))
        conn.commit()
        conn.close()
    except: pass

def get_cached_barcode(barcode):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, ingredients, product_type, score, source, ai_data FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]: return {'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 'product_type': r[3], 'score': r[4], 'source': r[5], 'ai_data': json.loads(r[6]) if r[6] else {}, 'cached': True}
    except: pass
    return None

def save_scan(result, user_id, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('INSERT INTO scans (scan_id, user_id, product, brand, product_type, score, verdict, ingredients, violations, thumb) VALUES (?,?,?,?,?,?,?,?,?,?)', (sid, user_id, result.get('product_name',''), result.get('brand',''), result.get('product_type', ''), result.get('score',0), result.get('verdict',''), json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), thumb))
    today = datetime.now().date()
    c.execute('SELECT scans, avoided, streak, best_streak, last_scan FROM stats WHERE id=1')
    r = c.fetchone()
    if r:
        scans, avoided, streak, best, last = r
        if last:
            try:
                ld = datetime.strptime(last, '%Y-%m-%d').date()
                streak = streak + 1 if ld == today - timedelta(days=1) else (streak if ld == today else 1)
            except: streak = 1
        else: streak = 1
        best = max(best, streak)
        if result.get('verdict') == 'AVOID': avoided += 1
        c.execute('UPDATE stats SET scans=?, avoided=?, streak=?, best_streak=?, last_scan=? WHERE id=1', (scans + 1, avoided, streak, best, today.isoformat()))
    conn.commit()
    conn.close()
    learn_product(result)
    return sid

def get_history(user_id, n=20):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT id, scan_id, ts, product, brand, score, verdict, thumb, favorite FROM scans WHERE user_id=? AND deleted=0 ORDER BY ts DESC LIMIT ?', (user_id, n))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 'score': r[5], 'verdict': r[6], 'thumb': r[7], 'favorite': r[8]} for r in rows]

def get_stats():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT scans, avoided, streak, best_streak FROM stats WHERE id=1')
    r = c.fetchone()
    conn.close()
    return {'scans': r[0], 'avoided': r[1], 'streak': r[2], 'best_streak': r[3]} if r else {'scans': 0, 'avoided': 0, 'streak': 0, 'best_streak': 0}

def get_allergies():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT a FROM allergies')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_allergies(allergies):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM allergies')
    for a in allergies: c.execute('INSERT OR IGNORE INTO allergies (a) VALUES (?)', (a,))
    conn.commit()
    conn.close()

def get_profiles():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT p FROM profiles')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_profiles(profiles):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM profiles')
    for p in profiles: c.execute('INSERT OR IGNORE INTO profiles (p) VALUES (?)', (p,))
    conn.commit()
    conn.close()

def toggle_favorite(db_id, current):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE scans SET favorite = ? WHERE id = ?', (0 if current else 1, db_id))
    conn.commit()
    conn.close()

# CLOUD DATABASE
def supa_ok(): return bool(SUPABASE_URL and SUPABASE_KEY)

def supa_request(method, table, data=None, params=None):
    if not supa_ok(): return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}
        if method == "GET": r = requests.get(url, headers=headers, params=params, timeout=5)
        elif method == "POST": r = requests.post(url, headers=headers, json=data, timeout=5)
        elif method == "PATCH": r = requests.patch(url, headers=headers, json=data, params=params, timeout=5)
        else: return None
        return r.json() if r.ok and r.text else (True if r.ok else None)
    except: pass
    return None

def cloud_log_scan(result, city, country, user_id):
    if supa_ok():
        try: supa_request("POST", "scans_log", {"product_name": result.get('product_name', ''), "brand": result.get('brand', ''), "score": result.get('score', 0), "verdict": result.get('verdict', ''), "city": city, "country": country, "user_id": user_id})
        except: pass

def cloud_save_product(result):
    if not supa_ok(): return
    try:
        name = result.get('product_name', '')
        name_lower = normalize_product_name(name)
        if not name_lower: return
        existing = supa_request("GET", "products", params={"product_name_lower": f"eq.{name_lower}", "select": "id,avg_score,scan_count"})
        if existing and len(existing) > 0:
            curr = existing[0]
            new_count = curr.get('scan_count', 0) + 1
            new_avg = ((curr.get('avg_score', 0) * curr.get('scan_count', 0)) + result.get('score', 0)) / new_count
            supa_request("PATCH", "products", {"avg_score": round(new_avg), "scan_count": new_count}, {"id": f"eq.{curr['id']}"})
        else:
            supa_request("POST", "products", {"product_name": name, "product_name_lower": name_lower, "brand": result.get('brand', ''), "avg_score": result.get('score', 0), "scan_count": 1})
    except: pass

def cloud_get_product(product_name):
    if not supa_ok(): return None
    try:
        name_lower = normalize_product_name(product_name)
        result = supa_request("GET", "products", params={"product_name_lower": f"eq.{name_lower}", "select": "product_name,brand,avg_score,scan_count"})
        if result and len(result) > 0: return {'product_name': result[0].get('product_name'), 'brand': result[0].get('brand', ''), 'score': int(result[0].get('avg_score', 70)), 'scan_count': result[0].get('scan_count', 1)}
    except: pass
    return None
# SMART BARCODE SCANNING - SEARCHES INTERNET
def preprocess_barcode_image(image):
    try:
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        return enhancer.enhance(2.0).filter(ImageFilter.SHARPEN)
    except: return image

def try_decode_barcode_pyzbar(image_file):
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        barcodes = pyzbar.decode(img)
        if barcodes: return barcodes[0].data.decode('utf-8')
        barcodes = pyzbar.decode(preprocess_barcode_image(img))
        if barcodes: return barcodes[0].data.decode('utf-8')
    except: pass
    return None

def ai_read_barcode(image_file):
    if not GEMINI_API_KEY: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        resp = model.generate_content(["Look at this barcode image. Find and read the numbers below the barcode lines. Return ONLY the digits, no spaces or text. If unreadable, return: UNREADABLE", img])
        text = resp.text.strip()
        if 'UNREADABLE' in text.upper(): return None
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14: return digits
    except: pass
    return None

def lookup_barcode_databases(barcode):
    # Try Open Food Facts
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=5)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                return {'found': True, 'name': p.get('product_name', '') or p.get('product_name_en', ''), 'brand': p.get('brands', ''), 'ingredients': p.get('ingredients_text', '') or p.get('ingredients_text_en', ''), 'categories': p.get('categories', ''), 'nutrition': p.get('nutriments', {}), 'source': 'Open Food Facts'}
    except: pass
    # Try Open Beauty Facts
    try:
        r = requests.get(f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json", timeout=5)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                return {'found': True, 'name': p.get('product_name', ''), 'brand': p.get('brands', ''), 'ingredients': p.get('ingredients_text', ''), 'source': 'Open Beauty Facts'}
    except: pass
    # Try UPC Item DB
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=5)
        if r.ok:
            d = r.json()
            items = d.get('items', [])
            if items:
                item = items[0]
                return {'found': True, 'name': item.get('title', ''), 'brand': item.get('brand', ''), 'description': item.get('description', ''), 'ingredients': '', 'source': 'UPC Item DB'}
    except: pass
    return {'found': False}

def ai_search_product_info(product_name, brand, barcode=None):
    if not GEMINI_API_KEY or not product_name: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.2, "max_output_tokens": 4096})
        search_query = f"{brand} {product_name}" if brand else product_name
        prompt = f"""You are a product research expert. Research this product thoroughly:
Product: {search_query}
{f"Barcode: {barcode}" if barcode else ""}

Based on your knowledge, provide accurate product information. RESPOND IN JSON:
{{"product_name": "Full name with brand", "brand": "Brand name", "product_type": "food/cosmetics/electronics/household/services", "description": "Brief description", "ingredients": ["ingredient1", "ingredient2"] or [], "claims": ["claim1", "claim2"], "known_concerns": ["concern1"] or [], "positive_aspects": ["positive1"] or [], "reputation": "Good/Mixed/Poor/Unknown", "confidence": "high/medium/low"}}"""
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        for pattern in [r'```json\s*(.*?)\s*```', r'\{[\s\S]*\}']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try: return json.loads(match.group(1) if '```' in pattern else match.group(0))
                except: continue
    except: pass
    return None

def smart_barcode_lookup(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.1, "🔍 Checking cache...")
    cached = get_cached_barcode(barcode)
    if cached and cached.get('score'):
        if progress_callback: progress_callback(1.0, "✅ Found in cache!")
        return cached
    if progress_callback: progress_callback(0.25, "🌐 Searching databases...")
    db_result = lookup_barcode_databases(barcode)
    if progress_callback: progress_callback(0.5, "🤖 AI analyzing product...")
    ai_result = ai_search_product_info(db_result.get('name', '') if db_result.get('found') else f"barcode {barcode}", db_result.get('brand', ''), barcode)
    if db_result.get('found'):
        if ai_result:
            if not db_result.get('ingredients') and ai_result.get('ingredients'):
                db_result['ingredients'] = ', '.join(ai_result['ingredients'])
            db_result['ai_data'] = ai_result
            db_result['claims'] = ai_result.get('claims', [])
            db_result['known_concerns'] = ai_result.get('known_concerns', [])
            db_result['positive_aspects'] = ai_result.get('positive_aspects', [])
            db_result['reputation'] = ai_result.get('reputation', 'Unknown')
            db_result['product_type'] = ai_result.get('product_type', '')
        if progress_callback: progress_callback(1.0, "✅ Product found!")
        return db_result
    if ai_result and ai_result.get('confidence') in ['high', 'medium']:
        if progress_callback: progress_callback(1.0, "✅ Found via AI search!")
        return {'found': True, 'name': ai_result.get('product_name', ''), 'brand': ai_result.get('brand', ''), 'ingredients': ', '.join(ai_result.get('ingredients', [])), 'product_type': ai_result.get('product_type', ''), 'claims': ai_result.get('claims', []), 'known_concerns': ai_result.get('known_concerns', []), 'positive_aspects': ai_result.get('positive_aspects', []), 'reputation': ai_result.get('reputation', 'Unknown'), 'source': 'AI Research', 'ai_data': ai_result, 'confidence': ai_result.get('confidence', 'low')}
    if progress_callback: progress_callback(1.0, "⚠️ Limited info found")
    return {'found': False}

# SHARE IMAGE GENERATION
def create_share_image(product_name, brand, score, verdict, main_issue=""):
    width, height = 1080, 1080
    colors = {'EXCEPTIONAL': {'bg': '#06b6d4', 'bg2': '#0891b2'}, 'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'}, 'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'}, 'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'}, 'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}}
    c = colors.get(verdict, colors['CAUTION'])
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 100)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except: font_title = font_score = font_product = font_footer = ImageFont.load_default()
    y = 50
    draw.text((width//2, y), "🌍 HonestWorld", fill='white', anchor="mt", font=font_title)
    y += 100
    display = get_verdict_display(verdict)
    draw.text((width//2, y), display['icon'], fill='white', anchor="mt", font=font_score)
    y += 120
    draw.text((width//2, y), display['text'], fill='white', anchor="mt", font=font_title)
    y += 80
    draw.text((width//2, y), f"{score}/100", fill='white', anchor="mt", font=font_score)
    y += 150
    pname = product_name[:30] + "..." if len(product_name) > 30 else product_name
    draw.text((width//2, y), pname, fill='white', anchor="mt", font=font_product)
    y += 50
    if brand: draw.text((width//2, y), f"by {brand[:25]}", fill='white', anchor="mt", font=font_product)
    draw.text((width//2, height - 60), "Scan at HonestWorld.app #HonestWorld", fill='white', anchor="mm", font=font_footer)
    return img

def create_story_image(product_name, brand, score, verdict, main_issue=""):
    width, height = 1080, 1920
    colors = {'EXCEPTIONAL': {'bg': '#06b6d4', 'bg2': '#0891b2'}, 'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'}, 'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'}, 'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'}, 'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}}
    c = colors.get(verdict, colors['CAUTION'])
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except: font_title = font_score = font_product = font_footer = ImageFont.load_default()
    y = 200
    draw.text((width//2, y), "🌍 HonestWorld", fill='white', anchor="mt", font=font_title)
    y += 180
    display = get_verdict_display(verdict)
    draw.text((width//2, y), display['icon'], fill='white', anchor="mt", font=font_score)
    y += 200
    draw.text((width//2, y), display['text'], fill='white', anchor="mt", font=font_title)
    y += 120
    draw.text((width//2, y), f"{score}/100", fill='white', anchor="mt", font=font_score)
    y += 250
    pname = product_name[:28] + "..." if len(product_name) > 28 else product_name
    draw.text((width//2, y), pname, fill='white', anchor="mt", font=font_product)
    y += 70
    if brand: draw.text((width//2, y), f"by {brand[:22]}", fill='white', anchor="mt", font=font_product)
    draw.text((width//2, height - 120), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    return img

def image_to_bytes(img, format='PNG'):
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()

def check_health_alerts(ingredients, user_allergies, user_profiles):
    alerts = []
    if not ingredients: return alerts
    ing_text = ' '.join(ingredients).lower() if isinstance(ingredients, list) else ingredients.lower()
    for allergy_key in user_allergies:
        if allergy_key in ALLERGENS:
            allergen = ALLERGENS[allergy_key]
            for trigger in allergen['triggers']:
                if trigger in ing_text:
                    alerts.append({'type': 'allergy', 'name': allergen['name'], 'icon': allergen['icon'], 'trigger': trigger, 'severity': 'high'})
                    break
    for profile_key in user_profiles:
        if profile_key in HEALTH_PROFILES:
            profile = HEALTH_PROFILES[profile_key]
            for ingredient in profile['watch_ingredients']:
                if ingredient in ing_text:
                    alerts.append({'type': 'profile', 'name': profile['name'], 'icon': profile['icon'], 'trigger': ingredient, 'severity': 'medium'})
                    break
    return alerts
# AI ANALYSIS - 20 LAWS, FAIR SCORING, LEARNING
ANALYSIS_PROMPT = """You are HonestWorld's integrity analyzer. Analyze this product FAIRLY using the 20 Integrity Laws.

## THE 20 INTEGRITY LAWS (Apply ONLY with clear evidence)
**INGREDIENT LAWS (1-6):** Water-Down(-15), Fairy Dusting(-12), Split Sugar(-18), Low-Fat Trap(-10), Natural Fallacy(-10), Made-With Loophole(-8)
**PACKAGING LAWS (7,8,18):** Serving Trick(-10), Slack Fill(-8), Photo vs Reality(-12)
**ELECTRONICS LAWS (9-12):** Spec Inflation(-15), Compatibility Lie(-12), Military Grade Myth(-10), Battery Fiction(-12)
**BEAUTY LAWS (13-14):** Clinical Ghost(-12), Concentration Trick(-10)
**SERVICE LAWS (15-17):** Free Trap(-15), Unlimited Lie(-18), Lifetime Illusion(-10)
**GENERAL LAWS (19-20):** Fake Certification(-15), Name Trick(-10)

## FAIR SCORING:
1. START at 85 (assume decent until proven otherwise)
2. ONLY deduct with CLEAR EVIDENCE
3. Consider product category norms (water in lotion is normal)
4. Give CREDIT for good practices (+3 to +5)
5. Same product = same score always

## INGREDIENT SCORING:
Cosmetics: parabens(-8), sulfates(-6), fragrance(-8), phthalates(-12), formaldehyde releasers(-15)
Food: trans fats(-12), excessive sodium, hidden sugars, artificial colors(-5 each)
BONUSES: Certified organic(+5), Fragrance-free(+4), EWG Verified(+3), Short ingredient list(+2)

## CONTEXT:
Location: {location}
{barcode_info}

## OUTPUT (Valid JSON):
{{"product_name": "Full name", "brand": "Brand", "product_type": "food/cosmetics/electronics/household/services", "readable": true, "score": <0-100>, "violations": [{{"law": <num>, "name": "Name", "points": <neg>, "evidence": "Specific"}}], "ingredients": ["list"], "ingredients_to_watch": ["concerning"], "good_ingredients": ["beneficial"], "main_issue": "Primary concern or 'Clean formula'", "positive": "Main positive", "tip": "Consumer tip", "confidence": "high/medium/low"}}

BE FAIR: Most products 65-85. Reserve <50 for genuinely deceptive. Reserve >90 for exceptional."""

def analyze_product(images, location, progress_callback, barcode_info=None):
    progress_callback(0.1, "🔍 Reading product...")
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "brand": "", "score": 0, "verdict": "UNCLEAR", "readable": False, "ingredients": [], "main_issue": "Please add GEMINI_API_KEY", "tip": "Add in Streamlit secrets"}
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 4096})
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    progress_callback(0.3, "🧠 Checking learned products...")
    barcode_text = ""
    if barcode_info and barcode_info.get('found'):
        barcode_text = f"\nBARCODE DATA:\n- Product: {barcode_info.get('name', '')}\n- Brand: {barcode_info.get('brand', '')}\n- Ingredients: {barcode_info.get('ingredients', '')[:1000]}\n- Source: {barcode_info.get('source', '')}\n{f'- Claims: {chr(44).join(barcode_info.get(chr(99)+chr(108)+chr(97)+chr(105)+chr(109)+chr(115), []))}' if barcode_info.get('claims') else ''}\n{f'- Known concerns: {chr(44).join(barcode_info.get(chr(107)+chr(110)+chr(111)+chr(119)+chr(110)+chr(95)+chr(99)+chr(111)+chr(110)+chr(99)+chr(101)+chr(114)+chr(110)+chr(115), []))}' if barcode_info.get('known_concerns') else ''}"
    progress_callback(0.5, "⚖️ Applying 20 integrity laws...")
    prompt = ANALYSIS_PROMPT.format(location=f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}", barcode_info=barcode_text)
    progress_callback(0.7, "📊 Calculating fair score...")
    try:
        response = model.generate_content([prompt] + pil_images)
        text = response.text.strip()
        result = None
        for pattern in [r'```json\s*(.*?)\s*```', r'\{[\s\S]*\}']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1) if '```' in pattern else match.group(0))
                    break
                except: continue
        if not result:
            return {"product_name": "Parse Error", "brand": "", "score": 0, "verdict": "UNCLEAR", "readable": False, "ingredients": [], "violations": [], "main_issue": "Could not parse AI response", "tip": "Try clearer photo"}
        score = result.get('score', 75)
        if isinstance(score, str):
            try: score = int(re.sub(r'[^\d]', '', score))
            except: score = 75
        score = max(0, min(100, score))
        result['score'] = score
        result['verdict'] = get_verdict(score)
        if result.get('product_name'):
            learned = get_learned_product(result['product_name'])
            if learned and learned.get('scan_count', 0) >= 2:
                learned_weight = min(learned['scan_count'] * 0.15, 0.6)
                result['score'] = int(score * (1 - learned_weight) + learned['score'] * learned_weight)
                result['verdict'] = get_verdict(result['score'])
            cloud_product = cloud_get_product(result['product_name'])
            if cloud_product and cloud_product.get('scan_count', 0) >= 3:
                cloud_weight = min(cloud_product['scan_count'] * 0.1, 0.4)
                result['score'] = int(result['score'] * (1 - cloud_weight) + cloud_product['score'] * cloud_weight)
                result['verdict'] = get_verdict(result['score'])
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        progress_callback(1.0, "✅ Analysis complete!")
        return result
    except Exception as e:
        return {"product_name": "Analysis Error", "brand": "", "score": 0, "verdict": "UNCLEAR", "readable": False, "ingredients": [], "violations": [], "main_issue": f"Error: {str(e)[:100]}", "tip": "Please try again"}

# CSS STYLES
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 500px; }
.verdict-exceptional { background: linear-gradient(135deg, #06b6d4, #0891b2); }
.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280, #4b5563); }
.verdict-card { border-radius: 24px; padding: 1.5rem; text-align: center; color: white; margin: 1rem 0; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
.verdict-icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
.verdict-text { font-size: 1.3rem; font-weight: 800; letter-spacing: 1px; margin: 0.3rem 0; }
.verdict-score { font-size: 3rem; font-weight: 900; }
.stat-row { display: flex; gap: 0.5rem; margin: 0.75rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.75rem; text-align: center; }
.stat-val { font-size: 1.4rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; }
.alert-danger { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 2px solid #ef4444; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.alert-warning { background: linear-gradient(135deg, #fffbeb, #fef3c7); border: 2px solid #f59e0b; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.issue-box { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.75rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.positive-box { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.75rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.tip-box { background: linear-gradient(135deg, #eff6ff, #dbeafe); border: 1px solid #bfdbfe; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.violation-box { background: linear-gradient(135deg, #fef2f2, #fecaca); border-left: 4px solid #ef4444; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.3rem 0; font-size: 0.85rem; }
.ing-summary { display: flex; gap: 0.5rem; margin: 0.5rem 0; flex-wrap: wrap; }
.ing-badge { padding: 0.35rem 0.7rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
.ing-watch { background: #fed7aa; color: #c2410c; }
.ing-good { background: #bbf7d0; color: #16a34a; }
.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }
.alt-score { display: inline-block; background: #22c55e; color: white; padding: 0.2rem 0.5rem; border-radius: 8px; font-weight: 700; font-size: 0.8rem; }
.history-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.7rem; background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }
.history-score { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.8rem; }
.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn { display: flex; flex-direction: column; align-items: center; padding: 0.75rem; border-radius: 12px; color: white; text-decoration: none; font-weight: 600; font-size: 0.8rem; }
.share-btn span { font-size: 1.5rem; margin-bottom: 0.25rem; }
.progress-box { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; text-align: center; }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 1rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }
.loc-badge { background: #dbeafe; color: #2563eb; padding: 0.3rem 0.7rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.7rem; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }
[data-testid="stCameraInput"] video { max-height: 200px !important; border-radius: 16px; }
#MainMenu, footer, header { visibility: hidden; }
.law-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.75rem; margin: 0.3rem 0; }
.law-title { font-weight: 700; color: #1e293b; }
.law-points { color: #ef4444; font-weight: 700; }
.law-desc { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }
</style>
"""
# MAIN APPLICATION
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    if 'result' not in st.session_state: st.session_state.result = None
    if 'scan_id' not in st.session_state: st.session_state.scan_id = None
    if 'admin' not in st.session_state: st.session_state.admin = False
    if 'barcode_info' not in st.session_state: st.session_state.barcode_info = None
    if 'barcode_num' not in st.session_state: st.session_state.barcode_num = None
    
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        st.session_state.loc = saved if saved and saved.get('city') not in ['Unknown', '', None] else get_location()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🌍 HonestWorld")
        st.markdown(f"<span class='loc-badge'>📍 {st.session_state.loc.get('city', 'Unknown')}</span>", unsafe_allow_html=True)
    with col2:
        stats = get_stats()
        if stats['streak'] > 0:
            st.markdown(f"<span class='streak-badge'>🔥 {stats['streak']} day{'s' if stats['streak'] > 1 else ''}</span>", unsafe_allow_html=True)
    
    st.markdown(f"<div class='stat-row'><div class='stat-box'><div class='stat-val'>{stats['scans']}</div><div class='stat-lbl'>Scans</div></div><div class='stat-box'><div class='stat-val'>{stats['avoided']}</div><div class='stat-lbl'>Avoided</div></div><div class='stat-box'><div class='stat-val'>{stats['best_streak']}</div><div class='stat-lbl'>Best Streak</div></div></div>", unsafe_allow_html=True)
    
    tab_scan, tab_history, tab_profile, tab_laws = st.tabs(["📷 Scan", "📋 History", "👤 Profile", "⚖️ Laws"])
    
    with tab_scan:
        input_method = st.radio("Scan method:", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
        images = []
        barcode_info = None
        
        if input_method == "📷 Camera":
            st.markdown("**Point at product** (back of package for best results)")
            cam_img = st.camera_input("Take photo", label_visibility="collapsed")
            if cam_img:
                images = [cam_img]
                st.success("✅ Photo captured!")
                if st.checkbox("Add another photo"):
                    cam_img2 = st.camera_input("Take another", label_visibility="collapsed", key="cam2")
                    if cam_img2: images.append(cam_img2)
        
        elif input_method == "📁 Upload":
            uploaded = st.file_uploader("Upload images", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
            if uploaded:
                images = uploaded[:3]
                st.success(f"✅ {len(images)} image(s) uploaded!")
        
        else:
            st.markdown("**📊 Smart Barcode Scanner**")
            st.caption("Searches internet databases for full product info")
            barcode_img = st.camera_input("Point at barcode", label_visibility="collapsed", key="barcode_cam")
            if barcode_img:
                with st.spinner("🔍 Reading barcode..."):
                    barcode_num = try_decode_barcode_pyzbar(barcode_img)
                    if not barcode_num: barcode_num = ai_read_barcode(barcode_img)
                    if barcode_num:
                        st.success(f"✅ Barcode: {barcode_num}")
                        st.session_state.barcode_num = barcode_num
                        progress_placeholder = st.empty()
                        def update_progress(pct, msg):
                            progress_placeholder.markdown(f"<div class='progress-box'><div style='font-size: 2rem;'>🔍</div><div style='font-weight: 600; margin: 0.5rem 0;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div></div>", unsafe_allow_html=True)
                        barcode_info = smart_barcode_lookup(barcode_num, update_progress)
                        progress_placeholder.empty()
                        if barcode_info.get('found'):
                            st.success(f"✅ Found: **{barcode_info.get('name', '')}** by {barcode_info.get('brand', '')}")
                            with st.expander("📋 Product details", expanded=True):
                                if barcode_info.get('ingredients'): st.markdown(f"**Ingredients:** {barcode_info.get('ingredients', '')[:300]}...")
                                if barcode_info.get('claims'): st.markdown(f"**Claims:** {', '.join(barcode_info.get('claims', [])[:5])}")
                                if barcode_info.get('known_concerns'): st.markdown(f"**Known concerns:** {', '.join(barcode_info.get('known_concerns', []))}")
                                st.caption(f"Source: {barcode_info.get('source', 'Unknown')}")
                            st.session_state.barcode_info = barcode_info
                            images = [barcode_img]
                        else: st.warning("⚠️ Product not found. Try photo scan.")
                    else: st.error("❌ Could not read barcode. Try again or use photo scan.")
        
        if images:
            if st.button("🔍 ANALYZE PRODUCT", use_container_width=True, type="primary"):
                progress_placeholder = st.empty()
                def update_progress(pct, msg):
                    progress_placeholder.markdown(f"<div class='progress-box'><div style='font-size: 2.5rem;'>{'🔍' if pct < 0.5 else '⚖️' if pct < 0.8 else '✨'}</div><div style='font-weight: 600; margin: 0.5rem 0;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div></div>", unsafe_allow_html=True)
                bi = st.session_state.get('barcode_info') or barcode_info
                result = analyze_product(images, st.session_state.loc, update_progress, bi)
                progress_placeholder.empty()
                if result.get('readable', True) and result.get('score', 0) > 0:
                    thumb = None
                    try:
                        images[0].seek(0)
                        img = Image.open(images[0])
                        img.thumbnail((100, 100))
                        buf = BytesIO()
                        img.save(buf, format='JPEG', quality=60)
                        thumb = buf.getvalue()
                    except: pass
                    scan_id = save_scan(result, user_id, thumb)
                    cloud_log_scan(result, st.session_state.loc.get('city', ''), st.session_state.loc.get('country', ''), user_id)
                    cloud_save_product(result)
                    if bi and bi.get('found') and st.session_state.get('barcode_num'):
                        cache_barcode(st.session_state.barcode_num, bi, result.get('score', 70))
                    st.session_state.result = result
                    st.session_state.scan_id = scan_id
                    st.session_state.barcode_info = None
                    st.session_state.barcode_num = None
                    st.rerun()
                else: st.error("❌ Could not analyze. Try a clearer photo.")
        
        if st.session_state.result:
            result = st.session_state.result
            score = result.get('score', 0)
            verdict = result.get('verdict', 'UNCLEAR')
            display = get_verdict_display(verdict)
            st.markdown(f"<div class='verdict-card verdict-{verdict.lower()}'><div class='verdict-icon'>{display['icon']}</div><div class='verdict-text'>{display['text']}</div><div class='verdict-score'>{score}<span>/100</span></div></div>", unsafe_allow_html=True)
            st.markdown(f"### {result.get('product_name', 'Unknown Product')}")
            if result.get('brand'): st.markdown(f"*by {result.get('brand')}*")
            alerts = check_health_alerts(result.get('ingredients', []), get_allergies(), get_profiles())
            for alert in alerts:
                css_class = 'alert-danger' if alert['severity'] == 'high' else 'alert-warning'
                st.markdown(f"<div class='{css_class}'><strong>{alert['icon']} {alert['name']} {'Alert' if alert['severity'] == 'high' else 'Warning'}!</strong><br>Contains: {alert['trigger']}</div>", unsafe_allow_html=True)
            violations = result.get('violations', [])
            if violations:
                with st.expander(f"⚖️ Law Violations ({len(violations)})", expanded=True):
                    for v in violations:
                        st.markdown(f"<div class='violation-box'><strong>Law {v.get('law', '?')}: {v.get('name', 'Unknown')}</strong> <span class='law-points'>({v.get('points', 0)} pts)</span><br><span style='color: #64748b;'>{v.get('evidence', '')}</span></div>", unsafe_allow_html=True)
            if result.get('main_issue') and result.get('main_issue') != "Clean formula":
                st.markdown(f"<div class='issue-box'>⚠️ <strong>Main Concern:</strong> {result.get('main_issue')}</div>", unsafe_allow_html=True)
            if result.get('positive'):
                st.markdown(f"<div class='positive-box'>✅ <strong>Positive:</strong> {result.get('positive')}</div>", unsafe_allow_html=True)
            with st.expander("🧪 Ingredients"):
                if result.get('ingredients_to_watch'):
                    st.markdown("**⚠️ Watch:**")
                    st.markdown("<div class='ing-summary'>" + " ".join([f"<span class='ing-badge ing-watch'>{i}</span>" for i in result.get('ingredients_to_watch', [])[:6]]) + "</div>", unsafe_allow_html=True)
                if result.get('good_ingredients'):
                    st.markdown("**✅ Good:**")
                    st.markdown("<div class='ing-summary'>" + " ".join([f"<span class='ing-badge ing-good'>{i}</span>" for i in result.get('good_ingredients', [])[:6]]) + "</div>", unsafe_allow_html=True)
                if result.get('ingredients'): st.markdown("**All:** " + ", ".join(result.get('ingredients', [])[:20]))
            if result.get('tip'):
                st.markdown(f"<div class='tip-box'>💡 <strong>Tip:</strong> {result.get('tip')}</div>", unsafe_allow_html=True)
            if verdict in ['CAUTION', 'AVOID']:
                alt = get_alternative(result.get('product_name', ''), result.get('product_type', ''))
                alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
                retailers_text = ', '.join(st.session_state.loc.get('retailers', [])[:3])
                st.markdown(f"<div class='alt-card'><strong>💚 Better Alternative:</strong><br><span style='font-size: 1.1rem; font-weight: 600;'>{alt['name']}</span> {alt_score_html}<br><span style='color: #16a34a;'>{alt['why']}</span><br><span style='font-size: 0.85rem; color: #64748b;'>Available at: {retailers_text}</span></div>", unsafe_allow_html=True)
            st.markdown("### 📤 Share Result")
            share_img = create_share_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict, result.get('main_issue', ''))
            story_img = create_story_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict, result.get('main_issue', ''))
            col1, col2 = st.columns(2)
            with col1: st.download_button("📥 Post (1080x1080)", data=image_to_bytes(share_img), file_name=f"honestworld_{score}.png", mime="image/png", use_container_width=True)
            with col2: st.download_button("📥 Story (1080x1920)", data=image_to_bytes(story_img), file_name=f"honestworld_story_{score}.png", mime="image/png", use_container_width=True)
            share_text = f"🌍 Scanned {result.get('product_name', 'a product')} - Score: {score}/100 ({verdict}) #HonestWorld"
            encoded_text = urllib.parse.quote(share_text)
            st.markdown(f"<div class='share-grid'><a href='https://twitter.com/intent/tweet?text={encoded_text}' target='_blank' class='share-btn' style='background: #1DA1F2;'><span>𝕏</span>Twitter</a><a href='https://www.facebook.com/sharer/sharer.php?quote={encoded_text}' target='_blank' class='share-btn' style='background: #4267B2;'><span>📘</span>Facebook</a><a href='https://wa.me/?text={encoded_text}' target='_blank' class='share-btn' style='background: #25D366;'><span>💬</span>WhatsApp</a><a href='https://t.me/share/url?text={encoded_text}' target='_blank' class='share-btn' style='background: #0088cc;'><span>✈️</span>Telegram</a><a href='https://www.instagram.com/' target='_blank' class='share-btn' style='background: linear-gradient(45deg, #f09433, #e6683c, #dc2743);'><span>📸</span>Instagram</a><a href='https://www.tiktok.com/' target='_blank' class='share-btn' style='background: #000;'><span>🎵</span>TikTok</a></div>", unsafe_allow_html=True)
            if st.button("🔄 Scan Another Product", use_container_width=True):
                st.session_state.result = None
                st.session_state.scan_id = None
                st.rerun()
    
    with tab_history:
        history = get_history(user_id, 30)
        if not history: st.info("📋 No scans yet. Start scanning products!")
        else:
            for item in history:
                score = item['score']
                color = '#06b6d4' if score >= 90 else '#22c55e' if score >= 75 else '#f59e0b' if score >= 50 else '#ef4444'
                fav_icon = "⭐" if item['favorite'] else ""
                col1, col2, col3 = st.columns([0.8, 3, 0.5])
                with col1: st.markdown(f"<div class='history-score' style='background: {color};'>{score}</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"**{fav_icon}{item['product'][:30]}**")
                    st.caption(f"{item['brand']} • {item['ts'][:10]}")
                with col3:
                    if st.button("⭐" if not item['favorite'] else "★", key=f"fav_{item['db_id']}"):
                        toggle_favorite(item['db_id'], item['favorite'])
                        st.rerun()
    
    with tab_profile:
        st.markdown("### ⚙️ Settings")
        st.markdown("**📍 Location**")
        col1, col2 = st.columns(2)
        with col1: city = st.text_input("City", value=st.session_state.loc.get('city', ''))
        with col2: country = st.text_input("Country", value=st.session_state.loc.get('country', ''))
        if st.button("Update Location"):
            code = save_location(city, country)
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
            st.success("✅ Location updated!")
        st.markdown("---")
        st.markdown("**🏥 Health Profiles**")
        current_profiles = get_profiles()
        new_profiles = st.multiselect("Select profiles", options=list(HEALTH_PROFILES.keys()), default=current_profiles, format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}")
        if new_profiles != current_profiles:
            save_profiles(new_profiles)
            st.success("✅ Profiles updated!")
        st.markdown("---")
        st.markdown("**🚨 Allergen Alerts**")
        current_allergies = get_allergies()
        new_allergies = st.multiselect("Select allergens", options=list(ALLERGENS.keys()), default=current_allergies, format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}")
        if new_allergies != current_allergies:
            save_allergies(new_allergies)
            st.success("✅ Allergies updated!")
        st.markdown("---")
        st.markdown("**🔐 Admin**")
        admin_pw = st.text_input("Admin password", type="password")
        if admin_pw and hashlib.sha256(admin_pw.encode()).hexdigest() == ADMIN_HASH:
            st.session_state.admin = True
            st.success("✅ Admin access granted!")
        if st.session_state.admin:
            st.markdown("### 📊 Admin Dashboard")
            conn = sqlite3.connect(LOCAL_DB)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM scans')
            total_scans = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM learned_products')
            learned = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM barcode_cache')
            cached = c.fetchone()[0]
            conn.close()
            st.markdown(f"**Local:** {total_scans} scans, {learned} products learned, {cached} barcodes cached")
            st.markdown(f"**Cloud:** {'🟢 Connected' if supa_ok() else '🔴 Not configured'}")
    
    with tab_laws:
        st.markdown("### ⚖️ The 20 Integrity Laws")
        st.caption("Fair, evidence-based scoring system")
        categories = {"🧪 Ingredients": [1, 2, 3, 4, 5, 6], "📦 Packaging": [7, 8, 18], "📱 Electronics": [9, 10, 11, 12], "💄 Beauty": [13, 14], "📋 Services": [15, 16, 17], "🏷️ Claims": [19, 20]}
        for cat_name, law_nums in categories.items():
            with st.expander(cat_name, expanded=False):
                for num in law_nums:
                    if num in INTEGRITY_LAWS:
                        law = INTEGRITY_LAWS[num]
                        st.markdown(f"<div class='law-card'><span class='law-title'>Law {num}: {law['name']}</span> <span class='law-points'>{law['points']} pts</span><div class='law-desc'>{law['description']}</div><div style='font-size: 0.8rem; color: #059669; margin-top: 0.3rem;'>💡 {law['tip']}</div></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"<center style='color: #94a3b8; font-size: 0.8rem;'>🌍 HonestWorld v{VERSION} • Fair & Accurate • Learning System Active</center>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
