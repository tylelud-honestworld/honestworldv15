"""
🌍 HONESTWORLD v21.0 - ULTIMATE PREMIUM
=======================================
$500M Quality App - Everything Working

FEATURES:
✅ Balanced, realistic scoring (not too strict, not too lenient)
✅ Alternative product recommendations
✅ Share images for Instagram/TikTok
✅ Barcode scanning with AI fallback
✅ Cloud database (Supabase)
✅ Location-based retailers
✅ Allergy/profile alerts
✅ Score consistency (cached scores)
✅ Friendly language ("Watch" not "Harmful")
✅ Full ingredient analysis
"""

import streamlit as st
import google.generativeai as genai
import json
import re
import sqlite3
from PIL import Image, ImageDraw, ImageFont
import requests
from datetime import datetime, timedelta
import uuid
import urllib.parse
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import os

# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(page_title="HonestWorld", page_icon="🌍", layout="centered", initial_sidebar_state="collapsed")

LOCAL_DB = Path.home() / "honestworld_v21.db"

def get_secret(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except:
        return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "AIzaSyCnUy-L-Bv4wlm9h1lSDY7GQKtD3g5XWtM")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# =============================================================================
# SCORING THRESHOLDS
# =============================================================================
SCORE_BUY = 75      # 75+ = Good to buy
SCORE_CAUTION = 50  # 50-74 = Check first
# Below 50 = Not recommended

def get_verdict(score):
    if score >= SCORE_BUY:
        return "BUY"
    elif score >= SCORE_CAUTION:
        return "CAUTION"
    else:
        return "AVOID"

# =============================================================================
# PRODUCT NAME NORMALIZATION
# =============================================================================
def normalize_product_name(name):
    """Normalize product name for consistent matching."""
    if not name:
        return ""
    n = name.lower().strip()
    remove_words = ['the', 'new', 'original', 'classic']
    for w in remove_words:
        n = re.sub(rf'\b{w}\b', '', n)
    n = ' '.join(n.split())
    return n

def get_cached_product_score(product_name):
    """Check if we've seen this product before."""
    if not product_name:
        return None
    
    name_lower = normalize_product_name(product_name)
    
    # Check cloud
    if supa_ok():
        result = supa_request("GET", "products", params={
            "product_name_lower": f"eq.{name_lower}",
            "select": "product_name,brand,avg_score,scan_count"
        })
        if result and len(result) > 0:
            return {'product_name': result[0].get('product_name'), 'score': int(result[0].get('avg_score', 0))}
        
        result = supa_request("GET", "products", params={
            "product_name_lower": f"ilike.%{name_lower[:20]}%",
            "select": "product_name,brand,avg_score",
            "limit": "1"
        })
        if result and len(result) > 0:
            return {'product_name': result[0].get('product_name'), 'score': int(result[0].get('avg_score', 0))}
    
    # Check local
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product, brand, score FROM scans WHERE LOWER(product) LIKE ? ORDER BY ts DESC LIMIT 1', 
                  (f'%{name_lower[:15]}%',))
        r = c.fetchone()
        conn.close()
        if r:
            return {'product_name': r[0], 'score': r[2]}
    except:
        pass
    
    return None

# =============================================================================
# SHARE IMAGE GENERATOR
# =============================================================================
def create_share_image(product_name, brand, score, verdict, main_issue=""):
    width, height = 1080, 1080
    colors = {
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}
    }
    c = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 100)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 35)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_large = font_medium = font_small = font_tiny = ImageFont.load_default()
    
    y = 60
    draw.text((width//2, y), "HonestWorld", fill='white', anchor="mt", font=font_medium)
    y += 90
    icons = {'BUY': '✓', 'CAUTION': '!', 'AVOID': 'X', 'UNCLEAR': '?'}
    draw.text((width//2, y), icons.get(verdict, '?'), fill='white', anchor="mt", font=font_large)
    y += 130
    texts = {'BUY': 'GOOD TO BUY', 'CAUTION': 'CHECK FIRST', 'AVOID': 'AVOID THIS', 'UNCLEAR': 'UNCLEAR'}
    draw.text((width//2, y), texts.get(verdict, ''), fill='white', anchor="mt", font=font_medium)
    y += 90
    draw.text((width//2, y), f"{score}/100", fill='white', anchor="mt", font=font_large)
    y += 160
    pname = product_name[:25] + "..." if len(product_name) > 25 else product_name
    draw.text((width//2, y), pname, fill='white', anchor="mt", font=font_small)
    y += 55
    if brand:
        draw.text((width//2, y), f"by {brand[:18]}", fill='white', anchor="mt", font=font_tiny)
    draw.text((width//2, height - 55), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_small)
    draw.text((width//2, height - 20), "#HonestWorld", fill='white', anchor="mm", font=font_tiny)
    return img

def create_story_image(product_name, brand, score, verdict, main_issue=""):
    width, height = 1080, 1920
    colors = {
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}
    }
    c = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    
    try:
        font_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 55)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 45)
    except:
        font_huge = font_large = font_medium = font_small = ImageFont.load_default()
    
    y = 250
    draw.text((width//2, y), "HonestWorld", fill='white', anchor="mt", font=font_large)
    y += 160
    icons = {'BUY': '✓', 'CAUTION': '!', 'AVOID': 'X', 'UNCLEAR': '?'}
    draw.text((width//2, y), icons.get(verdict, '?'), fill='white', anchor="mt", font=font_huge)
    y += 220
    texts = {'BUY': 'GOOD TO BUY', 'CAUTION': 'CHECK FIRST', 'AVOID': 'AVOID THIS', 'UNCLEAR': 'UNCLEAR'}
    draw.text((width//2, y), texts.get(verdict, ''), fill='white', anchor="mt", font=font_large)
    y += 140
    draw.text((width//2, y), f"{score}/100", fill='white', anchor="mt", font=font_huge)
    y += 280
    pname = product_name[:22] + "..." if len(product_name) > 22 else product_name
    draw.text((width//2, y), pname, fill='white', anchor="mt", font=font_medium)
    y += 80
    if brand:
        draw.text((width//2, y), f"by {brand[:18]}", fill='white', anchor="mt", font=font_small)
    if main_issue and 'no major' not in main_issue.lower() and 'clean' not in main_issue.lower():
        y += 100
        mi = main_issue[:40] + "..." if len(main_issue) > 40 else main_issue
        draw.text((width//2, y), mi, fill='white', anchor="mt", font=font_small)
    draw.text((width//2, height - 120), "Scan products at", fill='white', anchor="mm", font=font_medium)
    draw.text((width//2, height - 55), "HonestWorld.app", fill='white', anchor="mm", font=font_large)
    return img

# =============================================================================
# BARCODE SCANNING
# =============================================================================
def try_decode_barcode(image_file):
    """Try to decode barcode using pyzbar library."""
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        barcodes = pyzbar.decode(img)
        if barcodes:
            return barcodes[0].data.decode('utf-8')
    except ImportError:
        pass
    except Exception as e:
        pass
    return None

def ai_read_barcode(image_file):
    """Use Gemini AI to read barcode numbers."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        prompt = """Look at this barcode image. Read the numbers printed below the barcode lines.
        Return ONLY the digits, nothing else. No spaces, no dashes, just the numbers.
        If you can't read it clearly, return "UNREADABLE"."""
        resp = model.generate_content([prompt, img])
        text = resp.text.strip()
        digits = re.sub(r'\D', '', text)
        if len(digits) >= 8:
            return digits
    except Exception as e:
        pass
    return None

def lookup_barcode(barcode):
    """Look up product info from barcode."""
    # Try Open Food Facts
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=5)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                return {
                    'found': True,
                    'name': p.get('product_name', ''),
                    'brand': p.get('brands', ''),
                    'ingredients': p.get('ingredients_text', ''),
                    'source': 'Open Food Facts'
                }
    except:
        pass
    
    # Try UPC Database
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=5)
        if r.ok:
            d = r.json()
            items = d.get('items', [])
            if items:
                return {
                    'found': True,
                    'name': items[0].get('title', ''),
                    'brand': items[0].get('brand', ''),
                    'ingredients': '',
                    'source': 'UPC Database'
                }
    except:
        pass
    
    return {'found': False}

# =============================================================================
# SUPABASE CLOUD DATABASE
# =============================================================================
def supa_ok():
    return bool(SUPABASE_URL and SUPABASE_KEY and SUPABASE_KEY.startswith('eyJ'))

def supa_request(method, table, data=None, params=None):
    if not supa_ok():
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        if method == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=5)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=data, timeout=5)
        elif method == "PATCH":
            r = requests.patch(url, headers=headers, json=data, params=params, timeout=5)
        if r.ok:
            return r.json() if r.text else True
    except:
        pass
    return None

def cloud_log_scan(result, city, country, user_id):
    if not supa_ok():
        return
    try:
        supa_request("POST", "scans_log", {
            "product_name": result.get('product_name', ''),
            "brand": result.get('brand', ''),
            "score": result.get('score', 0),
            "verdict": result.get('verdict', ''),
            "city": city,
            "country": country,
            "user_id": user_id
        })
    except:
        pass

def cloud_save_product(result):
    if not supa_ok():
        return
    try:
        name = result.get('product_name', '')
        name_lower = normalize_product_name(name)
        if not name_lower:
            return
        
        existing = supa_request("GET", "products", params={
            "product_name_lower": f"eq.{name_lower}",
            "select": "id,avg_score,scan_count"
        })
        
        if existing and len(existing) > 0:
            curr = existing[0]
            new_count = curr.get('scan_count', 0) + 1
            new_avg = ((curr.get('avg_score', 0) * curr.get('scan_count', 0)) + result.get('score', 0)) / new_count
            supa_request("PATCH", "products", 
                {"avg_score": round(new_avg), "scan_count": new_count},
                {"id": f"eq.{curr['id']}"})
        else:
            supa_request("POST", "products", {
                "product_name": name,
                "product_name_lower": name_lower,
                "brand": result.get('brand', ''),
                "avg_score": result.get('score', 0),
                "scan_count": 1
            })
    except:
        pass

def cloud_search(query):
    if not supa_ok():
        return []
    try:
        result = supa_request("GET", "products", params={
            "product_name": f"ilike.%{query}%",
            "select": "product_name,brand,avg_score,scan_count",
            "order": "scan_count.desc",
            "limit": "20"
        })
        return result or []
    except:
        return []

def cloud_get_stats():
    if not supa_ok():
        return {'scans': 0, 'products': 0}
    try:
        scans = supa_request("GET", "scans_log", params={"select": "id", "limit": "10000"})
        products = supa_request("GET", "products", params={"select": "id", "limit": "10000"})
        return {
            'scans': len(scans) if scans else 0,
            'products': len(products) if products else 0
        }
    except:
        return {'scans': 0, 'products': 0}

def cloud_get_recent_scans(limit=10):
    if not supa_ok():
        return []
    try:
        result = supa_request("GET", "scans_log", params={
            "select": "product_name,brand,score,verdict,city,created_at",
            "order": "created_at.desc",
            "limit": str(limit)
        })
        return result or []
    except:
        return []

# =============================================================================
# INGREDIENT CATEGORIZATION
# =============================================================================
WATCH_INGREDIENTS = [
    'paraben', 'methylparaben', 'propylparaben', 'butylparaben',
    'sulfate', 'sodium lauryl sulfate', 'sodium laureth sulfate', 'sls', 'sles',
    'phthalate', 'dibutyl phthalate', 'dbp',
    'formaldehyde', 'formalin', 'dmdm hydantoin',
    'triclosan', 'triclocarban',
    'oxybenzone', 'octinoxate',
    'toluene', 'xylene',
    'lead', 'mercury', 'arsenic',
    'coal tar', 'petroleum', 'mineral oil',
    'bha', 'bht',
    'parfum', 'fragrance', 'synthetic fragrance',
    'peg-', 'polyethylene glycol',
    'siloxane', 'cyclomethicone', 'dimethicone',
    'retinyl palmitate', 'retinol',
    'hydroquinone', 'talc',
    'aluminum', 'propylene glycol',
    'dea', 'mea', 'tea', 'diethanolamine', 'monoethanolamine', 'triethanolamine'
]

CAUTION_INGREDIENTS = [
    'alcohol denat', 'denatured alcohol', 'sd alcohol',
    'citric acid', 'benzoic acid', 'sorbic acid',
    'phenoxyethanol', 'benzyl alcohol',
    'sodium benzoate', 'potassium sorbate',
    'edta', 'disodium edta',
    'artificial color', 'fd&c', 'd&c', 'ci '
]

def categorize_ingredient(ing):
    """Categorize an ingredient as watch/caution/safe."""
    ing_lower = ing.lower().strip()
    for w in WATCH_INGREDIENTS:
        if w in ing_lower:
            return 'watch'
    for c in CAUTION_INGREDIENTS:
        if c in ing_lower:
            return 'caution'
    return 'safe'

# =============================================================================
# ALLERGENS & PROFILES
# =============================================================================
ALLERGENS = {
    "gluten": ["wheat", "barley", "rye", "gluten"], "dairy": ["milk", "lactose", "casein", "whey"],
    "nuts": ["peanut", "almond", "cashew", "walnut"], "soy": ["soy", "soya", "lecithin"],
    "eggs": ["egg", "albumin"], "fragrance": ["fragrance", "parfum"],
    "parabens": ["paraben"], "sulfates": ["sulfate", "sls", "sles"]
}
PROFILES = {
    "baby": {"name": "Baby Safe", "icon": "👶", "avoid": ["fragrance", "paraben", "sulfate"]},
    "pregnant": {"name": "Pregnancy", "icon": "🤰", "avoid": ["retinol", "salicylic", "phthalate"]},
    "sensitive": {"name": "Sensitive", "icon": "🌸", "avoid": ["fragrance", "alcohol", "sulfate"]},
    "vegan": {"name": "Vegan", "icon": "🌱", "avoid": ["carmine", "lanolin", "beeswax"]}
}

def check_alerts(ingredients, allergies, profiles):
    alerts = []
    text = ' '.join(str(i) for i in ingredients).lower()
    for a in allergies:
        if a in ALLERGENS:
            for t in ALLERGENS[a]:
                if t in text:
                    alerts.append({'name': a.upper(), 'trigger': t, 'type': 'allergy'})
                    break
    for p in profiles:
        if p in PROFILES:
            for t in PROFILES[p]['avoid']:
                if t in text:
                    alerts.append({'name': PROFILES[p]['name'], 'trigger': t, 'type': 'profile', 'icon': PROFILES[p]['icon']})
    return alerts

# =============================================================================
# LOCATION
# =============================================================================
RETAILERS = {
    "AU": ["Chemist Warehouse", "Priceline", "Woolworths", "Coles"],
    "US": ["CVS", "Walgreens", "Target", "Walmart"],
    "GB": ["Boots", "Superdrug", "Tesco"],
    "NZ": ["Chemist Warehouse", "Countdown"],
    "CA": ["Shoppers Drug Mart", "Walmart"],
    "OTHER": ["Local pharmacy", "Supermarket"]
}

def get_location():
    services = [
        ('https://ipapi.co/json/', lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))),
        ('https://ip-api.com/json/', lambda d: (d.get('city'), d.get('country'), d.get('countryCode'))),
        ('https://ipwho.is/', lambda d: (d.get('city'), d.get('country'), d.get('country_code')))
    ]
    for url, extract in services:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                d = r.json()
                city, country, code = extract(d)
                if city and city not in ['', 'Unknown', None]:
                    return {'city': city, 'country': country or '', 'code': code or 'OTHER',
                            'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
        except:
            continue
    return {'city': 'Unknown', 'country': 'Unknown', 'code': 'OTHER', 'retailers': RETAILERS['OTHER']}

# =============================================================================
# LOCAL DATABASE
# =============================================================================
def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY, scan_id TEXT, user_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        product TEXT, brand TEXT, score INTEGER, verdict TEXT, thumb BLOB, deleted INTEGER DEFAULT 0)''')
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY DEFAULT 1, 
        scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, 
        best_streak INTEGER DEFAULT 0, last_scan DATE)''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (id INTEGER PRIMARY KEY DEFAULT 1, 
        user_id TEXT, city TEXT, country TEXT)''')
    c.execute('SELECT user_id FROM user_info WHERE id=1')
    if not c.fetchone():
        c.execute('INSERT INTO user_info (id, user_id) VALUES (1, ?)', (str(uuid.uuid4()),))
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
    c.execute('SELECT city, country FROM user_info WHERE id=1')
    r = c.fetchone()
    conn.close()
    if r and r[0] and r[0] != 'Unknown':
        return {'city': r[0], 'country': r[1] or 'Unknown'}
    return None

def save_location(city, country):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE user_info SET city=?, country=? WHERE id=1', (city, country))
    conn.commit()
    conn.close()

def save_scan(result, user_id, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('INSERT INTO scans (scan_id, user_id, product, brand, score, verdict, thumb) VALUES (?,?,?,?,?,?,?)',
        (sid, user_id, result.get('product_name',''), result.get('brand',''), 
         result.get('score',0), result.get('verdict',''), thumb))
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
        c.execute('UPDATE stats SET scans=?, avoided=?, streak=?, best_streak=?, last_scan=? WHERE id=1',
            (scans + 1, avoided, streak, best, today.isoformat()))
    conn.commit()
    conn.close()
    return sid

def get_history(user_id, n=20):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT id, scan_id, ts, product, brand, score, verdict, thumb FROM scans WHERE user_id=? AND deleted=0 ORDER BY ts DESC LIMIT ?', (user_id, n))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 'score': r[5], 'verdict': r[6], 'thumb': r[7]} for r in rows]

def delete_scan(db_id, user_id):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE scans SET deleted=1 WHERE id=? AND user_id=?', (db_id, user_id))
    conn.commit()
    conn.close()

def get_all_history_admin(n=100):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT id, scan_id, ts, product, brand, score, verdict, user_id, deleted FROM scans ORDER BY ts DESC LIMIT ?', (n,))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 'score': r[5], 'verdict': r[6], 'user_id': r[7], 'deleted': r[8]} for r in rows]

def get_stats():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT scans, avoided, streak, best_streak FROM stats WHERE id=1')
    r = c.fetchone()
    conn.close()
    return {'scans': r[0], 'avoided': r[1], 'streak': r[2], 'best': r[3]} if r else {'scans': 0, 'avoided': 0, 'streak': 0, 'best': 0}

def get_allergies():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT a FROM allergies')
    r = [x[0] for x in c.fetchall()]
    conn.close()
    return r

def save_allergies(lst):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM allergies')
    for a in lst: c.execute('INSERT OR IGNORE INTO allergies VALUES (?)', (a,))
    conn.commit()
    conn.close()

def get_profiles():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT p FROM profiles')
    r = [x[0] for x in c.fetchall()]
    conn.close()
    return r

def save_profiles(lst):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM profiles')
    for p in lst: c.execute('INSERT OR IGNORE INTO profiles VALUES (?)', (p,))
    conn.commit()
    conn.close()

init_db()

# =============================================================================
# ALTERNATIVES DATABASE - EXPANDED
# =============================================================================
ALTERNATIVES = {
    # Cleansers
    "cleanser": {"name": "CeraVe Hydrating Cleanser", "why": "Fragrance-free, contains ceramides", "score": 92},
    "face wash": {"name": "Cetaphil Gentle Skin Cleanser", "why": "Dermatologist recommended, gentle", "score": 88},
    "facial": {"name": "La Roche-Posay Toleriane", "why": "Sensitive skin formula, no parabens", "score": 90},
    
    # Moisturizers
    "moisturizer": {"name": "CeraVe Moisturizing Cream", "why": "No fragrance, contains hyaluronic acid", "score": 94},
    "lotion": {"name": "Vanicream Moisturizing Lotion", "why": "Free of dyes, fragrance, parabens", "score": 95},
    "cream": {"name": "Eucerin Original Healing Cream", "why": "Fragrance-free, dermatologist recommended", "score": 91},
    
    # Sunscreen
    "sunscreen": {"name": "La Roche-Posay Anthelios", "why": "High protection, mineral formula available", "score": 89},
    "spf": {"name": "EltaMD UV Clear SPF 46", "why": "Niacinamide, fragrance-free", "score": 93},
    
    # Hair care
    "shampoo": {"name": "Free & Clear Shampoo", "why": "No sulfates, parabens, or fragrance", "score": 94},
    "conditioner": {"name": "Free & Clear Conditioner", "why": "Gentle, no common irritants", "score": 93},
    
    # Body care
    "body wash": {"name": "Dove Sensitive Skin Body Wash", "why": "Fragrance-free, hypoallergenic", "score": 87},
    "soap": {"name": "Dove Sensitive Skin Bar", "why": "Unscented, moisturizing", "score": 88},
    "deodorant": {"name": "Native Deodorant Unscented", "why": "No aluminum, parabens free", "score": 86},
    
    # Baby
    "baby": {"name": "Cetaphil Baby Wash & Shampoo", "why": "Tear-free, no parabens", "score": 91},
    
    # Default
    "default": {"name": "Check EWG.org for alternatives", "why": "Independent safety database", "score": None}
}

def get_alternative(product_name, product_type):
    """Find a better alternative product."""
    search_text = f"{product_name} {product_type or ''}".lower()
    
    # Search for matching category
    for key in ALTERNATIVES:
        if key in search_text:
            alt = ALTERNATIVES[key]
            # Don't recommend the same product
            if key not in product_name.lower() or 'cerave' not in product_name.lower():
                return alt
    
    return ALTERNATIVES['default']

# =============================================================================
# AI ANALYSIS - BALANCED SCORING
# =============================================================================
PROMPT = """Analyze this product image carefully.

IMPORTANT RULES:
1. Include FULL product name with brand (e.g., "Cetaphil Gentle Skin Cleanser")
2. List ALL visible ingredients
3. Be HONEST and BALANCED in scoring - not too harsh, not too lenient

SCORING GUIDELINES (Start at 85, then adjust):

DEDUCT points for concerning ingredients:
- Parabens (methylparaben, propylparaben, butylparaben): -5 to -8 points
- Sulfates (SLS, SLES): -5 to -8 points
- Synthetic fragrances/parfum: -5 to -10 points
- Phthalates: -10 to -15 points
- Formaldehyde releasers (DMDM hydantoin): -10 to -15 points
- Triclosan: -10 points
- Oxybenzone/Octinoxate: -8 points
- PEGs: -3 to -5 points
- Artificial colors (FD&C, D&C): -3 to -5 points
- Multiple concerning ingredients: cumulative deductions

ADD points for positive attributes:
- Fragrance-free: +5 points
- Paraben-free: +3 points
- Sulfate-free: +3 points
- Contains ceramides: +3 points
- Contains hyaluronic acid: +3 points
- Contains niacinamide: +3 points
- Dermatologist tested: +2 points
- Organic ingredients: +2 points

EXPECTED SCORE RANGES:
- 90-100: Excellent - very clean, minimal/no concerning ingredients
- 80-89: Very Good - mostly clean with 1-2 minor concerns
- 70-79: Good - some common additives, generally acceptable
- 60-69: Fair - multiple concerning ingredients
- 50-59: Caution - significant concerns
- Below 50: Avoid - serious issues

Example scores:
- Pure mineral sunscreen with no fragrance: 92-95
- Standard drugstore moisturizer with fragrance: 70-78
- Product with parabens + sulfates + fragrance: 55-65
- Product with multiple harsh chemicals: 40-50

Location: {location}
{barcode_info}
{cached_info}

OUTPUT VALID JSON ONLY:
{{
    "product_name": "<FULL name with brand>",
    "brand": "<brand>",
    "product_type": "<type: cleanser, moisturizer, sunscreen, shampoo, etc>",
    "readable": true,
    "score": <calculated score based on above guidelines>,
    "ingredients": ["<list all visible ingredients>"],
    "ingredients_to_watch": ["<concerning ingredients found>"],
    "good_ingredients": ["<beneficial ingredients found>"],
    "main_issue": "<primary concern or 'Clean formula' if none>",
    "positive": "<main positive attribute>",
    "tip": "<helpful tip for consumer>"
}}

If cannot read product clearly:
{{"readable": false, "product_name": "Unreadable", "brand": "", "score": 0}}"""

def analyze(images, loc, progress, barcode_info=None, cached_product=None):
    progress(0.2, "🔍 Reading product...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 4000})
    
    pil = [Image.open(img) for img in images]
    for img in images: img.seek(0)
    
    progress(0.5, "⚖️ Analyzing ingredients...")
    
    barcode_text = ""
    if barcode_info and barcode_info.get('found'):
        barcode_text = f"BARCODE INFO: Product: {barcode_info.get('name')}, Brand: {barcode_info.get('brand')}, Ingredients: {barcode_info.get('ingredients', '')[:500]}"
    
    cached_text = ""
    if cached_product:
        cached_text = f"NOTE: This product was previously scored {cached_product.get('score')}. Use similar score unless you find different information."
    
    prompt = PROMPT.format(
        location=f"{loc.get('city', '')}, {loc.get('country', '')}",
        barcode_info=barcode_text,
        cached_info=cached_text
    )
    
    progress(0.8, "📊 Calculating score...")
    resp = model.generate_content([prompt] + pil)
    text = resp.text.strip()
    
    result = None
    for pat in [r'```json\s*(.*?)\s*```', r'\{[\s\S]*\}']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(1) if '```' in pat else m.group(0))
                break
            except: continue
    
    if not result:
        return {"product_name": "Unreadable", "brand": "", "score": 0, "verdict": "UNCLEAR",
                "readable": False, "ingredients": [], "ingredients_to_watch": [],
                "main_issue": "Could not read image", "tip": "Take clearer photo"}
    
    # Use cached score if available (for consistency)
    if cached_product and cached_product.get('score'):
        result['score'] = cached_product['score']
    
    # Ensure score is in valid range
    score = result.get('score', 75)
    if isinstance(score, str):
        try:
            score = int(score)
        except:
            score = 75
    score = max(0, min(100, score))
    result['score'] = score
    
    # Apply verdict thresholds
    result['verdict'] = get_verdict(result['score'])
    
    if not result.get('readable', True):
        result['score'] = 0
        result['verdict'] = 'UNCLEAR'
    
    progress(1.0, "✅ Done!")
    return result

# =============================================================================
# UI HELPERS
# =============================================================================
def score_color(s):
    if s >= SCORE_BUY: return "#22c55e"
    if s >= SCORE_CAUTION: return "#f59e0b"
    return "#ef4444"

# =============================================================================
# CSS
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: #f8fafc !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 500px; }

.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280, #4b5563); }
.verdict-card { border-radius: 20px; padding: 1.25rem; text-align: center; color: white; margin: 0.75rem 0; }
.verdict-icon { font-size: 3rem; }
.verdict-text { font-size: 1.25rem; font-weight: 800; margin: 0.3rem 0; }
.verdict-score { font-size: 2.5rem; font-weight: 900; }

.stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 0.6rem; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; }

.alert-danger { background: #fef2f2; border: 2px solid #ef4444; border-radius: 10px; padding: 0.6rem; margin: 0.4rem 0; }
.alert-warning { background: #fffbeb; border: 2px solid #f59e0b; border-radius: 10px; padding: 0.6rem; margin: 0.4rem 0; }
.issue-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.4rem 0; }
.positive-box { background: #dcfce7; border-left: 4px solid #22c55e; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.4rem 0; }

.ing-summary { display: flex; gap: 0.4rem; margin: 0.4rem 0; flex-wrap: wrap; }
.ing-badge { padding: 0.3rem 0.6rem; border-radius: 15px; font-weight: 600; font-size: 0.75rem; }
.ing-watch { background: #fed7aa; color: #c2410c; }
.ing-caution { background: #fef3c7; color: #d97706; }
.ing-safe { background: #bbf7d0; color: #16a34a; }

.alt-card { background: #f0fdf4; border: 2px solid #86efac; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.history-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.6rem; background: white; border: 1px solid #e2e8f0; border-radius: 10px; margin: 0.25rem 0; }
.history-score { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.75rem; }

.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0.75rem 0.5rem; border-radius: 10px; color: white; text-decoration: none; font-weight: 600; font-size: 0.8rem; }
.share-btn span { font-size: 1.5rem; margin-bottom: 0.25rem; }

.progress-box { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; text-align: center; }
.progress-bar { height: 5px; background: #e2e8f0; border-radius: 3px; margin: 0.75rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); }

.loc-badge { background: #dbeafe; color: #2563eb; padding: 0.25rem 0.6rem; border-radius: 15px; font-size: 0.7rem; font-weight: 600; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.25rem 0.6rem; border-radius: 15px; font-size: 0.75rem; font-weight: 700; }
.tip-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 0.6rem; margin: 0.4rem 0; font-size: 0.85rem; }

.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 10px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 3px; background: #f1f5f9; padding: 3px; border-radius: 10px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 7px; font-weight: 600; font-size: 0.85rem; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }
[data-testid="stCameraInput"] video { max-height: 180px !important; border-radius: 12px; }
#MainMenu, footer, header { visibility: hidden; }
</style>
"""

# =============================================================================
# MAIN APP
# =============================================================================
st.markdown(CSS, unsafe_allow_html=True)

if 'result' not in st.session_state: st.session_state.result = None
if 'sid' not in st.session_state: st.session_state.sid = None
if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'admin' not in st.session_state: st.session_state.admin = False
if 'share_img' not in st.session_state: st.session_state.share_img = None
if 'share_story' not in st.session_state: st.session_state.share_story = None

if 'loc' not in st.session_state:
    saved = get_saved_location()
    if saved and saved.get('city') not in ['Unknown', '', None]:
        st.session_state.loc = saved
    else:
        st.session_state.loc = get_location()

loc = st.session_state.loc
user_id = get_user_id()
stats = get_stats()

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("# 🌍 HonestWorld")
with col2:
    if stats.get('streak', 0) > 0:
        st.markdown(f"<span class='streak-badge'>🔥{stats['streak']}</span>", unsafe_allow_html=True)
    if loc.get('city') and loc.get('city') != 'Unknown':
        st.markdown(f"<span class='loc-badge'>📍 {loc['city'][:12]}</span>", unsafe_allow_html=True)
    else:
        if st.button("📍 Set location", key="setloc"):
            st.session_state.show_loc = True

# Tabs
tab_names = ["📷 Scan", "🔎 Search", "📜 History", "👤 Profile"]
if st.session_state.admin:
    tab_names.append("⚙️ Admin")
tabs = st.tabs(tab_names)

# =============================================================================
# TAB: SCAN
# =============================================================================
with tabs[0]:
    if st.session_state.result:
        r = st.session_state.result
        
        if st.button("🔄 Scan Another", type="primary"):
            st.session_state.result = None
            st.session_state.sid = None
            st.session_state.imgs = []
            st.session_state.share_img = None
            st.session_state.share_story = None
            st.rerun()
        
        verdict = r.get('verdict', 'UNCLEAR')
        score = r.get('score', 0)
        product_name = r.get('product_name', 'Unknown')
        brand = r.get('brand', '')
        product_type = r.get('product_type', '')
        ingredients = r.get('ingredients', [])
        main_issue = r.get('main_issue', '')
        positive = r.get('positive', '')
        
        # Allergy/Profile alerts
        alerts = check_alerts(ingredients, get_allergies(), get_profiles())
        for a in alerts:
            cls = 'alert-danger' if a['type'] == 'allergy' else 'alert-warning'
            st.markdown(f"<div class='{cls}'>{'🚨' if a['type']=='allergy' else '⚠️'} <b>{a['name']}</b>: contains {a['trigger']}</div>", unsafe_allow_html=True)
        
        # Verdict card
        icons = {"BUY": "✓", "CAUTION": "!", "AVOID": "✗", "UNCLEAR": "?"}
        texts = {"BUY": "GOOD TO BUY", "CAUTION": "CHECK FIRST", "AVOID": "NOT RECOMMENDED", "UNCLEAR": "UNCLEAR"}
        st.markdown(f'''<div class="verdict-card verdict-{verdict.lower()}">
            <div class="verdict-icon">{icons.get(verdict, "?")}</div>
            <div class="verdict-text">{texts.get(verdict, "")}</div>
            <div class="verdict-score">{score}<span style="font-size:1rem;">/100</span></div>
        </div>''', unsafe_allow_html=True)
        
        st.markdown(f"### {product_name}")
        st.caption(f"{brand} • {product_type}")
        
        # Positive attributes (show first for good products)
        if positive and verdict == 'BUY':
            st.markdown(f"<div class='positive-box'>✨ {positive}</div>", unsafe_allow_html=True)
        
        # Main issue (only show if there's a real concern)
        if main_issue and 'clean' not in main_issue.lower() and 'minimal' not in main_issue.lower() and 'no major' not in main_issue.lower():
            st.markdown(f"<div class='issue-box'>⚠️ {main_issue}</div>", unsafe_allow_html=True)
        
        # Ingredients summary
        watch_list = r.get('ingredients_to_watch', [])
        good_list = r.get('good_ingredients', [])
        
        if ingredients:
            watch_count = len(watch_list) if watch_list else sum(1 for i in ingredients if categorize_ingredient(i) == 'watch')
            caution_count = sum(1 for i in ingredients if categorize_ingredient(i) == 'caution')
            safe_count = len(ingredients) - watch_count - caution_count
            
            st.markdown(f'''<div class="ing-summary">
                <span class="ing-badge ing-watch">👁️ {watch_count} Watch</span>
                <span class="ing-badge ing-caution">⚡ {caution_count} Note</span>
                <span class="ing-badge ing-safe">✓ {safe_count} Good</span>
            </div>''', unsafe_allow_html=True)
            
            if watch_list:
                st.markdown(f"**👁️ To watch:** {', '.join(watch_list[:5])}")
                st.caption("Common ingredients that some people prefer to avoid.")
            
            if good_list:
                st.markdown(f"**✨ Good ingredients:** {', '.join(good_list[:5])}")
            
            with st.expander("View all ingredients"):
                for ing in ingredients:
                    cat = categorize_ingredient(ing)
                    icon = '👁️' if cat == 'watch' else ('⚡' if cat == 'caution' else '✓')
                    st.markdown(f"{icon} {ing}")
        
        # Alternative recommendation - ALWAYS show for CAUTION and AVOID
        if verdict in ['CAUTION', 'AVOID']:
            alt = get_alternative(product_name, product_type)
            if alt and alt.get('name'):
                store = loc.get('retailers', ['Store'])[0]
                score_text = f" • Score: {alt['score']}/100" if alt.get('score') else ""
                st.markdown(f'''<div class="alt-card">
                    <div style="color:#16a34a;font-weight:700;font-size:1.1rem;">💡 Better Alternative</div>
                    <div style="font-weight:600;margin:0.3rem 0;">{alt['name']}</div>
                    <div style="color:#64748b;font-size:0.85rem;">{alt['why']}{score_text}</div>
                    <div style="margin-top:0.4rem;"><span class="loc-badge">📍 Available at {store}</span></div>
                </div>''', unsafe_allow_html=True)
        
        if r.get('tip'):
            st.markdown(f"<div class='tip-box'>💡 {r['tip']}</div>", unsafe_allow_html=True)
        
        # Share section
        if verdict != 'UNCLEAR':
            st.markdown("---")
            st.markdown("### 📤 Share")
            
            if st.session_state.share_img is None:
                st.session_state.share_img = create_share_image(product_name, brand, score, verdict, main_issue)
                st.session_state.share_story = create_story_image(product_name, brand, score, verdict, main_issue)
            
            def img_to_bytes(img):
                buf = BytesIO()
                img.save(buf, format='PNG')
                return buf.getvalue()
            
            col1, col2 = st.columns(2)
            with col1:
                st.image(st.session_state.share_img, width=140, caption="Post")
                st.download_button("⬇️ Download", img_to_bytes(st.session_state.share_img), 
                                   f"honestworld_{score}.png", "image/png", use_container_width=True)
            with col2:
                st.image(st.session_state.share_story, width=90, caption="Story")
                st.download_button("⬇️ Download", img_to_bytes(st.session_state.share_story),
                                   f"honestworld_story_{score}.png", "image/png", use_container_width=True, key="dl_story")
            
            share_text = f"Scanned {product_name} - {score}/100! #HonestWorld"
            enc = urllib.parse.quote(share_text)
            
            st.markdown(f'''<div class="share-grid">
                <a href="https://www.instagram.com/" target="_blank" class="share-btn" style="background:linear-gradient(45deg,#f09433,#dc2743,#bc1888);"><span>📸</span>Insta</a>
                <a href="https://www.tiktok.com/upload" target="_blank" class="share-btn" style="background:#000;"><span>🎵</span>TikTok</a>
                <a href="https://www.facebook.com/sharer/sharer.php?quote={enc}" target="_blank" class="share-btn" style="background:#4267B2;"><span>📘</span>Facebook</a>
                <a href="https://wa.me/?text={enc}" target="_blank" class="share-btn" style="background:#25D366;"><span>💬</span>WhatsApp</a>
                <a href="https://twitter.com/intent/tweet?text={enc}" target="_blank" class="share-btn" style="background:#1DA1F2;"><span>🐦</span>Twitter</a>
                <a href="https://t.me/share/url?text={enc}" target="_blank" class="share-btn" style="background:#0088cc;"><span>✈️</span>Telegram</a>
            </div>''', unsafe_allow_html=True)
            st.caption("📱 Download image → Open app → Upload")
        
        st.caption(f"ID: {st.session_state.sid}")
    
    else:
        # Scan input UI
        st.markdown(f'''<div class="stat-row">
            <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">Scans</div></div>
            <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Avoided</div></div>
            <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Streak</div></div>
        </div>''', unsafe_allow_html=True)
        
        if loc.get('city') in ['Unknown', '', None]:
            st.warning("📍 Set your location in Profile for local recommendations")
        
        mode = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
        
        imgs = []
        barcode_info = None
        
        if mode == "📷 Camera":
            if st.session_state.imgs:
                cols = st.columns(len(st.session_state.imgs) + (1 if len(st.session_state.imgs) < 3 else 0))
                for i, img in enumerate(st.session_state.imgs):
                    with cols[i]:
                        st.image(img, width=60)
                        if st.button("✕", key=f"rm{i}"):
                            st.session_state.imgs.pop(i)
                            st.rerun()
                if len(st.session_state.imgs) < 3:
                    with cols[-1]:
                        if st.button("➕"):
                            st.session_state.adding = True
                            st.rerun()
            if not st.session_state.imgs or st.session_state.get('adding'):
                cam = st.camera_input("", label_visibility="collapsed", key=f"cam{len(st.session_state.imgs)}")
                if cam:
                    st.session_state.imgs.append(cam)
                    st.session_state.adding = False
                    st.rerun()
            imgs = st.session_state.imgs
            
        elif mode == "📁 Upload":
            up = st.file_uploader("", type=['png','jpg','jpeg','webp'], accept_multiple_files=True, label_visibility="collapsed")
            if up: imgs = up[:3]
            
        else:  # Barcode mode
            st.markdown("""
            **📊 Barcode Scanning:**
            1. Point camera at the barcode
            2. Make sure numbers below barcode are visible
            3. Take photo
            """)
            bc = st.camera_input("", label_visibility="collapsed", key="bc")
            if bc:
                imgs = [bc]
                with st.spinner("Reading barcode..."):
                    barcode = try_decode_barcode(bc)
                    if not barcode:
                        barcode = ai_read_barcode(bc)
                    
                    if barcode:
                        st.success(f"✅ Barcode: {barcode}")
                        barcode_info = lookup_barcode(barcode)
                        if barcode_info.get('found'):
                            st.info(f"📦 **{barcode_info.get('name')}** by {barcode_info.get('brand')}")
                            st.session_state.barcode_info = barcode_info
                        else:
                            st.warning("Product not in database. Will analyze from image.")
                    else:
                        st.warning("Could not read barcode number. Will analyze from image.")
        
        if imgs:
            if st.button("🔍 ANALYZE", type="primary", use_container_width=True):
                prog = st.empty()
                def update(p, t):
                    prog.markdown(f"<div class='progress-box'>{t}<div class='progress-bar'><div class='progress-fill' style='width:{p*100}%;'></div></div></div>", unsafe_allow_html=True)
                
                try:
                    thumb = None
                    try:
                        imgs[0].seek(0)
                        pil = Image.open(imgs[0])
                        pil.thumbnail((80, 80))
                        buf = BytesIO()
                        pil.save(buf, format='JPEG', quality=70)
                        thumb = buf.getvalue()
                    except: pass
                    
                    for i in imgs: i.seek(0)
                    
                    # Get barcode info if available
                    bc_info = st.session_state.get('barcode_info')
                    
                    # Check for cached score first
                    cached = None
                    
                    result = analyze(imgs, loc, update, bc_info, cached)
                    
                    # Check for cached score after analysis (for product name)
                    if result.get('product_name') and result.get('verdict') != 'UNCLEAR':
                        cached = get_cached_product_score(result['product_name'])
                        if cached and cached.get('score'):
                            result['score'] = cached['score']
                            result['verdict'] = get_verdict(cached['score'])
                    
                    if result.get('verdict') != 'UNCLEAR':
                        sid = save_scan(result, user_id, thumb)
                        cloud_log_scan(result, loc.get('city', ''), loc.get('country', ''), user_id)
                        cloud_save_product(result)
                    else:
                        sid = "UNCLEAR"
                    
                    st.session_state.result = result
                    st.session_state.sid = sid
                    st.session_state.imgs = []
                    st.session_state.barcode_info = None
                    st.session_state.share_img = None
                    st.session_state.share_story = None
                    prog.empty()
                    st.rerun()
                except Exception as e:
                    prog.empty()
                    st.error(f"Error: {e}")

# =============================================================================
# TAB: SEARCH
# =============================================================================
with tabs[1]:
    st.markdown("### 🔎 Search Products")
    if supa_ok():
        st.caption(f"🌍 {cloud_get_stats().get('products', 0)} products in global database")
    q = st.text_input("", placeholder="Search any product...", label_visibility="collapsed")
    if q and len(q) >= 2:
        results = cloud_search(q)
        for p in results:
            score = int(p.get('avg_score', 0))
            verdict = get_verdict(score)
            st.markdown(f'''<div class="history-row">
                <div style="flex:1;"><b>{p.get('product_name')}</b><br/><span style="font-size:0.7rem;color:#64748b;">{p.get('brand')} • Scanned {p.get('scan_count')}x</span></div>
                <div class="history-score" style="background:{score_color(score)};">{score}</div>
            </div>''', unsafe_allow_html=True)
        if not results:
            st.info("Not found in database - scan it to add!")

# =============================================================================
# TAB: HISTORY
# =============================================================================
with tabs[2]:
    st.markdown("### 📜 Your History")
    history = get_history(user_id, 20)
    if not history:
        st.info("No scans yet - start scanning products!")
    for h in history:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f'''<div class="history-row">
                <div style="flex:1;"><b>{h['product']}</b><br/><span style="font-size:0.7rem;color:#64748b;">{h['brand']}</span></div>
                <div class="history-score" style="background:{score_color(h['score'])};">{h['score']}</div>
            </div>''', unsafe_allow_html=True)
        with col2:
            if st.button("🗑️", key=f"d{h['db_id']}"):
                delete_scan(h['db_id'], user_id)
                st.rerun()

# =============================================================================
# TAB: PROFILE
# =============================================================================
with tabs[3]:
    st.markdown("### 👤 Your Profile")
    st.markdown(f'''<div class="stat-row">
        <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">Total Scans</div></div>
        <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Avoided</div></div>
        <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Day Streak</div></div>
    </div>''', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**📍 Your Location**")
    st.caption("For local store recommendations")
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value=loc.get('city', '') if loc.get('city') != 'Unknown' else '')
    with col2:
        country = st.text_input("Country", value=loc.get('country', '') if loc.get('country') != 'Unknown' else '')
    if st.button("📍 Save Location"):
        if city:
            save_location(city, country)
            code = 'AU' if 'austral' in country.lower() else 'OTHER'
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
            st.success("✅ Location saved!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("**🛡️ Allergen Alerts**")
    st.caption("Get warned when products contain these")
    curr_a = get_allergies()
    sel_a = []
    cols = st.columns(3)
    for i, a in enumerate(ALLERGENS.keys()):
        with cols[i % 3]:
            if st.checkbox(a.title(), value=a in curr_a, key=f"a{a}"):
                sel_a.append(a)
    
    st.markdown("---")
    st.markdown("**👨‍👩‍👧 Safety Profiles**")
    st.caption("Extra warnings for specific needs")
    curr_p = get_profiles()
    sel_p = []
    for k, v in PROFILES.items():
        if st.checkbox(f"{v['icon']} {v['name']}", value=k in curr_p, key=f"p{k}"):
            sel_p.append(k)
    
    if st.button("💾 Save All Settings", type="primary"):
        save_allergies(sel_a)
        save_profiles(sel_p)
        st.success("✅ Settings saved!")
    
    st.markdown("---")
    with st.expander("🔐 Admin Access"):
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_HASH:
                st.session_state.admin = True
                st.rerun()

# =============================================================================
# TAB: ADMIN
# =============================================================================
if st.session_state.admin and len(tabs) > 4:
    with tabs[4]:
        st.markdown("### ⚙️ Admin Dashboard")
        if st.button("🚪 Logout"):
            st.session_state.admin = False
            st.rerun()
        
        st.markdown("---")
        st.markdown("**🌐 Cloud Database (Supabase)**")
        st.markdown(f"Status: {'✅ Connected' if supa_ok() else '❌ Not Connected'}")
        
        if supa_ok():
            cs = cloud_get_stats()
            st.markdown(f"**📊 Stats:** {cs.get('scans', 0)} total scans, {cs.get('products', 0)} unique products")
            
            st.markdown("**🕐 Recent Scans:**")
            for s in cloud_get_recent_scans(15):
                score = s.get('score', 0)
                st.markdown(f"• **{s.get('product_name')}** ({score}/100) - {s.get('city', 'Unknown')}")
        else:
            st.warning("Supabase not configured. Add SUPABASE_URL and SUPABASE_KEY to secrets.")
            st.code("""
# In Streamlit secrets.toml:
SUPABASE_URL = "https://yourproject.supabase.co"
SUPABASE_KEY = "eyJ..."  # Must start with eyJ (legacy format)
            """)
        
        st.markdown("---")
        st.markdown("**💾 Local Database**")
        st.markdown(f"Path: `{LOCAL_DB}`")
        local_history = get_all_history_admin(20)
        st.markdown(f"**Local records:** {len(local_history)}")
        for s in local_history[:10]:
            icon = '🗑️' if s.get('deleted') else '•'
            st.markdown(f"{icon} **{s['product']}** ({s['score']}/100)")

st.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:0.65rem;padding:0.5rem;'>🌍 v21 • {loc.get('city', 'Unknown')}</div>", unsafe_allow_html=True)
