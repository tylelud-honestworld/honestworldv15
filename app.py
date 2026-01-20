"""
🌍 HONESTWORLD v18.0 - SHAREABLE IMAGES + LEGACY SUPABASE

NEW:
✅ Generates shareable image cards for Instagram/TikTok
✅ Uses Legacy Supabase JWT keys (the ones that work)
✅ Download button for share image
✅ Beautiful score cards ready to post
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
st.set_page_config(
    page_title="HonestWorld", 
    page_icon="🌍", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

LOCAL_DB = Path.home() / "honestworld_v18.db"

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
# SHAREABLE IMAGE GENERATOR
# =============================================================================
def create_share_image(product_name, brand, score, verdict, main_issue=""):
    """Generate a beautiful shareable image for social media."""
    
    # Image size (Instagram story: 1080x1920, post: 1080x1080)
    # Using square for versatility
    width, height = 1080, 1080
    
    # Colors based on verdict
    colors = {
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a', 'text': '#ffffff'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706', 'text': '#ffffff'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626', 'text': '#ffffff'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563', 'text': '#ffffff'}
    }
    
    c = colors.get(verdict, colors['CAUTION'])
    
    # Create image with gradient-like background
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    
    # Draw darker bottom half for gradient effect
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    
    # Try to load fonts, fallback to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # Draw content
    y_pos = 80
    
    # Logo/Title
    draw.text((width//2, y_pos), "🌍 HonestWorld", fill=c['text'], anchor="mt", font=font_medium)
    y_pos += 100
    
    # Verdict icon
    verdict_icons = {'BUY': '✓', 'CAUTION': '⚠', 'AVOID': '✗', 'UNCLEAR': '?'}
    draw.text((width//2, y_pos), verdict_icons.get(verdict, '?'), fill=c['text'], anchor="mt", font=font_large)
    y_pos += 150
    
    # Verdict text
    verdict_texts = {'BUY': 'GOOD TO BUY', 'CAUTION': 'USE CAUTION', 'AVOID': 'AVOID THIS', 'UNCLEAR': 'UNCLEAR'}
    draw.text((width//2, y_pos), verdict_texts.get(verdict, 'UNKNOWN'), fill=c['text'], anchor="mt", font=font_medium)
    y_pos += 100
    
    # Score
    draw.text((width//2, y_pos), f"{score}/100", fill=c['text'], anchor="mt", font=font_large)
    y_pos += 180
    
    # Product name (truncate if too long)
    product_display = product_name[:35] + "..." if len(product_name) > 35 else product_name
    draw.text((width//2, y_pos), product_display, fill=c['text'], anchor="mt", font=font_small)
    y_pos += 60
    
    # Brand
    if brand:
        draw.text((width//2, y_pos), f"by {brand}", fill=c['text'], anchor="mt", font=font_tiny)
    y_pos += 100
    
    # Main issue (if any)
    if main_issue and 'no significant' not in main_issue.lower():
        # Wrap text
        issue_short = main_issue[:60] + "..." if len(main_issue) > 60 else main_issue
        draw.text((width//2, y_pos), f"⚠ {issue_short}", fill=c['text'], anchor="mt", font=font_tiny)
    
    # Footer
    draw.text((width//2, height - 60), "Scan products at HonestWorld.app", fill=c['text'], anchor="mb", font=font_tiny)
    draw.text((width//2, height - 30), "#HonestWorld #ConsumerAwareness", fill=c['text'], anchor="mb", font=font_tiny)
    
    return img

def create_story_image(product_name, brand, score, verdict, main_issue=""):
    """Generate Instagram/TikTok story format (9:16)."""
    
    width, height = 1080, 1920
    
    colors = {
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a', 'text': '#ffffff'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706', 'text': '#ffffff'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626', 'text': '#ffffff'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563', 'text': '#ffffff'}
    }
    
    c = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    
    # Gradient effect
    draw.rectangle([0, height//2, width, height], fill=c['bg2'])
    
    try:
        font_huge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 180)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 100)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
    except:
        font_huge = font_large = font_medium = font_small = ImageFont.load_default()
    
    y_pos = 200
    
    # Logo
    draw.text((width//2, y_pos), "🌍 HonestWorld", fill=c['text'], anchor="mt", font=font_medium)
    y_pos += 200
    
    # Verdict icon
    verdict_icons = {'BUY': '✓', 'CAUTION': '⚠', 'AVOID': '✗', 'UNCLEAR': '?'}
    draw.text((width//2, y_pos), verdict_icons.get(verdict, '?'), fill=c['text'], anchor="mt", font=font_huge)
    y_pos += 250
    
    # Verdict text
    verdict_texts = {'BUY': 'GOOD TO BUY', 'CAUTION': 'USE CAUTION', 'AVOID': 'AVOID THIS', 'UNCLEAR': 'UNCLEAR'}
    draw.text((width//2, y_pos), verdict_texts.get(verdict, 'UNKNOWN'), fill=c['text'], anchor="mt", font=font_large)
    y_pos += 180
    
    # Score
    draw.text((width//2, y_pos), f"{score}/100", fill=c['text'], anchor="mt", font=font_huge)
    y_pos += 300
    
    # Product
    product_display = product_name[:30] + "..." if len(product_name) > 30 else product_name
    draw.text((width//2, y_pos), product_display, fill=c['text'], anchor="mt", font=font_medium)
    y_pos += 100
    
    if brand:
        draw.text((width//2, y_pos), f"by {brand}", fill=c['text'], anchor="mt", font=font_small)
    
    # Footer
    draw.text((width//2, height - 150), "Scan YOUR products at", fill=c['text'], anchor="mb", font=font_small)
    draw.text((width//2, height - 80), "HonestWorld.app", fill=c['text'], anchor="mb", font=font_medium)
    
    return img

def image_to_base64(img):
    """Convert PIL image to base64 for display and download."""
    buf = BytesIO()
    img.save(buf, format='PNG', quality=95)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()

def get_image_download_link(img, filename, text):
    """Generate download link for image."""
    b64 = image_to_base64(img)
    return f'<a href="data:image/png;base64,{b64}" download="{filename}" style="display:inline-block;padding:10px 20px;background:#3b82f6;color:white;border-radius:8px;text-decoration:none;font-weight:600;margin:5px;">{text}</a>'

# =============================================================================
# BARCODE SCANNING
# =============================================================================
def try_decode_barcode(image_file):
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        barcodes = pyzbar.decode(img)
        if barcodes:
            return barcodes[0].data.decode('utf-8')
    except:
        pass
    return None

def lookup_barcode(barcode):
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=5)
        if r.ok:
            data = r.json()
            if data.get('status') == 1:
                product = data.get('product', {})
                return {
                    'name': product.get('product_name', ''),
                    'brand': product.get('brands', ''),
                    'ingredients': product.get('ingredients_text', ''),
                    'found': True
                }
    except:
        pass
    return {'found': False}

# =============================================================================
# SUPABASE - LEGACY JWT FORMAT
# =============================================================================
def supa_ok():
    # Must have URL and Key, key should be JWT (eyJ) for legacy format
    return bool(SUPABASE_URL and SUPABASE_KEY and len(SUPABASE_KEY) > 20)

def supa_request(method, table, data=None, params=None):
    if not supa_ok():
        return None
    
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    
    # Always use legacy JWT format headers
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == "POST":
            r = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == "PATCH":
            r = requests.patch(url, headers=headers, json=data, params=params, timeout=10)
        elif method == "DELETE":
            r = requests.delete(url, headers=headers, params=params, timeout=10)
        else:
            return None
        
        if r.status_code in [200, 201, 204]:
            return r.json() if r.text and r.status_code != 204 else True
        return None
    except:
        return None

def cloud_log_scan(result, city, country, user_id):
    if not supa_ok():
        return False
    return supa_request("POST", "scans_log", {
        "product_name": str(result.get('product_name', 'Unknown'))[:200],
        "brand": str(result.get('brand', 'Unknown'))[:100],
        "category": str(result.get('product_type', ''))[:50],
        "score": int(result.get('score', 0)),
        "verdict": str(result.get('verdict', 'CAUTION'))[:20],
        "violations_count": len(result.get('violations', [])),
        "city": str(city)[:100],
        "country": str(country)[:100],
        "user_id": str(user_id)[:50]
    }) is not None

def cloud_save_product(result):
    if not supa_ok():
        return False
    name_lower = result.get('product_name', '').lower().strip()[:200]
    if not name_lower:
        return False
    
    existing = supa_request("GET", "products", params={
        "product_name_lower": f"eq.{name_lower}",
        "select": "id,avg_score,scan_count"
    })
    
    if existing and len(existing) > 0:
        p = existing[0]
        new_count = p['scan_count'] + 1
        new_avg = round(((p['avg_score'] * p['scan_count']) + result.get('score', 0)) / new_count, 1)
        supa_request("PATCH", "products", 
            data={"avg_score": new_avg, "scan_count": new_count},
            params={"id": f"eq.{p['id']}"})
    else:
        supa_request("POST", "products", {
            "product_name": result.get('product_name', 'Unknown')[:200],
            "product_name_lower": name_lower,
            "brand": result.get('brand', '')[:100],
            "category": result.get('product_type', '')[:50],
            "avg_score": result.get('score', 0),
            "scan_count": 1
        })
    return True

def cloud_search(query, limit=15):
    if not supa_ok():
        return []
    result = supa_request("GET", "products", params={
        "product_name_lower": f"ilike.%{query.lower()[:50]}%",
        "select": "product_name,brand,avg_score,scan_count",
        "order": "scan_count.desc",
        "limit": str(limit)
    })
    return result if result else []

def cloud_get_stats():
    if not supa_ok():
        return {"products": 0, "scans": 0}
    products = supa_request("GET", "products", params={"select": "id"})
    scans = supa_request("GET", "scans_log", params={"select": "id"})
    return {
        "products": len(products) if products else 0,
        "scans": len(scans) if scans else 0
    }

def cloud_get_recent_scans(limit=50):
    if not supa_ok():
        return []
    result = supa_request("GET", "scans_log", params={
        "select": "product_name,brand,score,verdict,city,country,user_id,created_at",
        "order": "created_at.desc",
        "limit": str(limit)
    })
    return result if result else []

def cloud_get_top_products(limit=20):
    if not supa_ok():
        return []
    result = supa_request("GET", "products", params={
        "select": "product_name,brand,avg_score,scan_count",
        "order": "scan_count.desc",
        "limit": str(limit)
    })
    return result if result else []

# =============================================================================
# INGREDIENT DATABASE
# =============================================================================
HARMFUL = ["paraben", "methylparaben", "propylparaben", "butylparaben", "bha", "bht",
           "triclosan", "formaldehyde", "phthalate", "oxybenzone", "coal tar",
           "hydroquinone", "lead", "mercury", "toluene", "asbestos"]

CAUTION_ING = ["fragrance", "parfum", "sulfate", "sls", "sles", "sodium lauryl",
               "propylene glycol", "peg-", "dimethicone", "aluminum", "fd&c", "dea", "mea"]

SAFE_ING = ["water", "aqua", "glycerin", "aloe", "shea", "coconut", "jojoba",
            "vitamin", "tocopherol", "citric acid", "hyaluronic", "niacinamide"]

def categorize_ingredient(name):
    n = name.lower()
    for h in HARMFUL:
        if h in n: return "harmful"
    for c in CAUTION_ING:
        if c in n: return "caution"
    for s in SAFE_ING:
        if s in n: return "safe"
    return "unknown"

# =============================================================================
# ALLERGENS & PROFILES
# =============================================================================
ALLERGENS = {
    "gluten": ["wheat", "barley", "rye", "gluten"],
    "dairy": ["milk", "lactose", "casein", "whey", "cream"],
    "nuts": ["peanut", "almond", "cashew", "walnut", "hazelnut"],
    "soy": ["soy", "soya", "soybean", "lecithin"],
    "eggs": ["egg", "albumin"],
    "shellfish": ["shrimp", "crab", "lobster"],
    "fragrance": ["fragrance", "parfum", "perfume"],
    "parabens": ["paraben"],
    "sulfates": ["sulfate", "sls", "sles"],
}

PROFILES = {
    "baby": {"name": "Baby Safe", "icon": "👶", "avoid": ["fragrance", "paraben", "sulfate", "alcohol"]},
    "pregnant": {"name": "Pregnancy", "icon": "🤰", "avoid": ["retinol", "salicylic", "benzoyl", "phthalate"]},
    "sensitive": {"name": "Sensitive", "icon": "🌸", "avoid": ["fragrance", "alcohol", "sulfate"]},
    "vegan": {"name": "Vegan", "icon": "🌱", "avoid": ["carmine", "lanolin", "beeswax", "collagen"]},
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
    "OTHER": ["Local pharmacy", "Supermarket"]
}

def get_location_from_ip():
    services = ['https://ipapi.co/json/', 'https://ip-api.com/json/', 'https://ipwho.is/']
    for url in services:
        try:
            r = requests.get(url, timeout=3)
            if r.ok:
                d = r.json()
                city = d.get('city') or d.get('city', 'Unknown')
                country = d.get('country') or d.get('country_name', 'Unknown')
                code = d.get('country_code') or d.get('countryCode', 'OTHER')
                if city and city != 'Unknown':
                    return {'city': city, 'country': country, 'code': code, 
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
        id INTEGER PRIMARY KEY, scan_id TEXT, user_id TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        product TEXT, brand TEXT, score INTEGER, verdict TEXT, thumb BLOB,
        deleted INTEGER DEFAULT 0
    )''')
    
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE
    )''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (
        id INTEGER PRIMARY KEY DEFAULT 1, user_id TEXT, city TEXT, country TEXT
    )''')
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
    if r and r[0]:
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
    
    c.execute('''INSERT INTO scans (scan_id, user_id, product, brand, score, verdict, thumb) 
        VALUES (?,?,?,?,?,?,?)''',
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

def get_history(user_id, n=20, include_deleted=False):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    if include_deleted:
        c.execute('''SELECT id, scan_id, ts, product, brand, score, verdict, thumb 
            FROM scans WHERE user_id=? ORDER BY ts DESC LIMIT ?''', (user_id, n))
    else:
        c.execute('''SELECT id, scan_id, ts, product, brand, score, verdict, thumb 
            FROM scans WHERE user_id=? AND deleted=0 ORDER BY ts DESC LIMIT ?''', (user_id, n))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 
             'score': r[5], 'verdict': r[6], 'thumb': r[7]} for r in rows]

def delete_scan(db_id, user_id):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE scans SET deleted=1 WHERE id=? AND user_id=?', (db_id, user_id))
    conn.commit()
    conn.close()

def get_all_history_admin(n=100):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''SELECT id, scan_id, ts, product, brand, score, verdict, user_id, deleted 
        FROM scans ORDER BY ts DESC LIMIT ?''', (n,))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 
             'score': r[5], 'verdict': r[6], 'user_id': r[7], 'deleted': r[8]} for r in rows]

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
# AI ANALYSIS
# =============================================================================
PROMPT = """Analyze this product for marketing deception.

CRITICAL RULES:
1. If you cannot clearly read the product name or ingredients - set readable to false
2. NEVER give score 100 unless genuinely perfect
3. If image is blurry/unreadable - score 0, verdict UNCLEAR
4. Be STRICT - most products have issues (typical score 60-85)

THE 20 INTEGRITY LAWS (deduct points for each found):
1. Water-Down (-15): First ingredient is cheap filler but marketed as premium
2. Fairy Dusting (-12): Advertised ingredient below position #5
3. Split Sugar (-20): Sugar split into multiple names
4. Low-Fat Trap (-10): Low-fat but high sugar/sodium
5. Natural Fallacy (-10): "Natural" claim with synthetics
6. Made-With Trick (-8): "Made with X" but X is minimal
7. Serving Trick (-10): Tiny unrealistic serving size
8. Slack Fill (-8): Package mostly empty
9. Spec Inflation (-15): "Up to X" unrealistic
10. Compatibility Lie (-12): "Universal" with exceptions
11. Military Myth (-10): Fake military grade
12. Battery Fiction (-12): Unrealistic battery claims
13. Clinical Ghost (-12): "Clinically proven" no proof
14. Dilution Trick (-10): Actives too diluted
15. Free Trap (-15): "Free" needs credit card
16. Unlimited Lie (-18): "Unlimited" with caps
17. Lifetime Illusion (-10): Warranty excludes everything
18. Photo Fake (-12): Package vs reality mismatch
19. Fake Cert (-15): Unverified certification
20. Name Trick (-10): Name implies absent ingredient

HARMFUL INGREDIENTS: Parabens, BHA, BHT, Triclosan, Formaldehyde, Phthalates, Oxybenzone, Coal tar, Hydroquinone, Lead, Mercury, Toluene

SCORING: 80-100=BUY | 50-79=CAUTION | 0-49=AVOID | Unreadable=UNCLEAR

Location: {location} | Stores: {retailers}
{barcode_info}

OUTPUT ONLY JSON:
{{
    "product_name": "<name or 'Unreadable'>",
    "brand": "<brand or 'Unknown'>",
    "product_type": "<food/cosmetics/electronics/household/service/unknown>",
    "readable": <true/false>,
    "score": <0-100>,
    "verdict": "<BUY/CAUTION/AVOID/UNCLEAR>",
    "violations": [{{"law": <1-20>, "name": "<name>", "points": <negative>, "reason": "<evidence>"}}],
    "ingredients": ["<ingredient1>", "..."],
    "harmful_found": ["<harmful ingredients>"],
    "main_issue": "<biggest problem>",
    "better_option": {{"name": "<alternative>", "store": "<store>", "why": "<reason>"}},
    "tip": "<advice>"
}}"""

def analyze(images, loc, progress, barcode_info=None):
    progress(0.2, "🔍 Reading product...")
    genai.configure(api_key=GEMINI_API_KEY)
    
    model = genai.GenerativeModel(
        "gemini-2.0-flash-exp",
        generation_config={"temperature": 0.1, "max_output_tokens": 4000}
    )
    
    pil = [Image.open(img) for img in images]
    for img in images: img.seek(0)
    
    progress(0.5, "⚖️ Analyzing...")
    
    barcode_text = ""
    if barcode_info and barcode_info.get('found'):
        barcode_text = f"BARCODE: {barcode_info.get('name', '')}, Brand: {barcode_info.get('brand', '')}, Ingredients: {barcode_info.get('ingredients', '')}"
    
    prompt = PROMPT.format(
        location=f"{loc.get('city', 'Unknown')}, {loc.get('country', 'Unknown')}",
        retailers=", ".join(loc.get('retailers', ['Local store'])),
        barcode_info=barcode_text
    )
    
    progress(0.8, "📊 Scoring...")
    resp = model.generate_content([prompt] + pil)
    text = resp.text.strip()
    
    result = None
    for pat in [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```', r'\{[\s\S]*\}']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                json_str = m.group(1) if m.lastindex else m.group(0)
                result = json.loads(json_str)
                break
            except:
                continue
    
    if not result:
        try:
            result = json.loads(text)
        except:
            return {
                "product_name": "Unreadable", "brand": "Unknown", "product_type": "unknown",
                "readable": False, "score": 0, "verdict": "UNCLEAR", "violations": [],
                "ingredients": [], "harmful_found": [],
                "main_issue": "Could not read product - please take clearer photo",
                "better_option": {}, "tip": "Ensure product name and ingredients are visible"
            }
    
    # Validation
    if not result.get('readable', True) or result.get('product_name', '').lower() in ['unreadable', 'unknown', '']:
        result['score'] = 0
        result['verdict'] = 'UNCLEAR'
        result['main_issue'] = "Image unclear - please retake"
    else:
        violations = result.get('violations', [])
        total = sum(abs(v.get('points', 0)) for v in violations)
        correct_score = max(0, min(100, 100 - total))
        
        if correct_score == 100 and len(result.get('ingredients', [])) > 0:
            has_issues = any(categorize_ingredient(i) in ['harmful', 'caution'] for i in result.get('ingredients', []))
            if has_issues:
                correct_score = 85
        
        result['score'] = correct_score
        result['verdict'] = 'BUY' if correct_score >= 80 else ('CAUTION' if correct_score >= 50 else 'AVOID')
    
    progress(1.0, "✅ Done!")
    return result

# =============================================================================
# UI HELPERS
# =============================================================================
def score_color(s):
    if s >= 80: return "#22c55e"
    if s >= 50: return "#f59e0b"
    return "#ef4444"

def thumb_b64(data):
    return base64.b64encode(data).decode() if data else None
# =============================================================================
# CSS
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, sans-serif; }
.stApp { background: #f8fafc !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 500px; }
h1, h2, h3, h4 { color: #1e293b; font-weight: 700; }
p, span, div, label { color: #334155; }

[data-testid="stCameraInput"] { max-width: 280px !important; margin: 0 auto !important; }
[data-testid="stCameraInput"] video { max-height: 200px !important; border-radius: 16px; }

.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280, #4b5563); }
.verdict-card { border-radius: 24px; padding: 1.5rem; text-align: center; color: white; margin: 1rem 0; }
.verdict-icon { font-size: 4rem; line-height: 1; }
.verdict-text { font-size: 1.5rem; font-weight: 900; margin: 0.5rem 0; }
.verdict-score { font-size: 3rem; font-weight: 900; }

.stat-row { display: flex; gap: 0.5rem; margin: 0.75rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.75rem; text-align: center; }
.stat-val { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; }

.alert-danger { background: #fef2f2; border: 2px solid #ef4444; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.alert-warning { background: #fffbeb; border: 2px solid #f59e0b; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.issue-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

.ing-summary { display: flex; gap: 0.5rem; margin: 0.5rem 0; flex-wrap: wrap; }
.ing-badge { padding: 0.4rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
.ing-harmful { background: #fecaca; color: #dc2626; }
.ing-caution { background: #fef3c7; color: #d97706; }
.ing-safe { background: #bbf7d0; color: #16a34a; }

.violation { background: #fef2f2; border-left: 4px solid #ef4444; padding: 0.75rem; margin: 0.3rem 0; border-radius: 0 10px 10px 0; }
.alt-card { background: #f0fdf4; border: 1px solid #86efac; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }

.history-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }
.history-thumb { width: 44px; height: 44px; border-radius: 10px; object-fit: cover; background: #f1f5f9; }
.history-score { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.8rem; }

.share-section { background: #f1f5f9; border-radius: 16px; padding: 1rem; margin: 1rem 0; }
.share-preview { max-width: 200px; border-radius: 12px; margin: 0.5rem auto; display: block; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.share-buttons { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center; margin-top: 1rem; }
.share-btn { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.6rem 1rem; border-radius: 8px; color: white; font-weight: 600; font-size: 0.8rem; text-decoration: none; }
.share-twitter { background: #1DA1F2; }
.share-facebook { background: #4267B2; }
.share-whatsapp { background: #25D366; }
.share-download { background: #6366f1; }
.share-story { background: linear-gradient(45deg, #f09433, #e6683c, #dc2743); }

.progress-box { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; text-align: center; }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 1rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }

.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }

.loc-badge { background: #dbeafe; color: #2563eb; padding: 0.3rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
.admin-card { background: #1e293b; color: white; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.admin-stat { font-size: 2rem; font-weight: 800; color: #60a5fa; }
.tip-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
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
if 'barcode_data' not in st.session_state: st.session_state.barcode_data = None
if 'share_img' not in st.session_state: st.session_state.share_img = None
if 'share_story' not in st.session_state: st.session_state.share_story = None
if 'loc' not in st.session_state:
    saved = get_saved_location()
    st.session_state.loc = saved if saved else get_location_from_ip()

loc = st.session_state.loc
stats = get_stats()
user_id = get_user_id()

# Header
col1, col2 = st.columns([3, 1.5])
with col1:
    st.markdown("# 🌍 HonestWorld")
with col2:
    if stats['streak'] > 0:
        st.markdown(f"<span class='streak-badge'>🔥 {stats['streak']}</span>", unsafe_allow_html=True)
    st.markdown(f"<span class='loc-badge'>📍 {loc.get('city', 'Unknown')}</span>", unsafe_allow_html=True)

# Navigation
if st.session_state.admin:
    tabs = st.tabs(["🔍 Scan", "🔎 Search", "📜 History", "👤 Profile", "📊 Admin"])
else:
    tabs = st.tabs(["🔍 Scan", "🔎 Search", "📜 History", "👤 Profile"])

# =============================================================================
# TAB: SCAN
# =============================================================================
with tabs[0]:
    if st.session_state.result:
        r = st.session_state.result
        score = r.get('score', 0)
        verdict = r.get('verdict', 'CAUTION')
        product_name = r.get('product_name', 'Unknown')
        brand = r.get('brand', '')
        main_issue = r.get('main_issue', '')
        
        if st.button("🔄 Scan Another"):
            st.session_state.result = None
            st.session_state.imgs = []
            st.session_state.barcode_data = None
            st.session_state.share_img = None
            st.session_state.share_story = None
            st.rerun()
        
        if verdict == 'UNCLEAR':
            st.warning("⚠️ Could not read product. Please take a clearer photo.")
        
        # Alerts
        ingredients = r.get('ingredients', [])
        alerts = check_alerts(ingredients, get_allergies(), get_profiles())
        for a in alerts:
            icon = "🚨" if a['type'] == 'allergy' else a.get('icon', '⚠️')
            cls = 'alert-danger' if a['type'] == 'allergy' else 'alert-warning'
            st.markdown(f"<div class='{cls}'>{icon} <strong>{a['name']}</strong>: {a['trigger']}</div>", unsafe_allow_html=True)
        
        # Verdict card
        verdict_class = f"verdict-{verdict.lower()}"
        verdict_icons = {"BUY": "✓", "CAUTION": "⚠", "AVOID": "✗", "UNCLEAR": "?"}
        verdict_texts = {"BUY": "GOOD TO BUY", "CAUTION": "USE CAUTION", "AVOID": "AVOID THIS", "UNCLEAR": "UNCLEAR"}
        
        st.markdown(f'''
        <div class="verdict-card {verdict_class}">
            <div class="verdict-icon">{verdict_icons.get(verdict, "?")}</div>
            <div class="verdict-text">{verdict_texts.get(verdict, "UNKNOWN")}</div>
            <div class="verdict-score">{score}<span style="font-size:1.2rem;">/100</span></div>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f"### {product_name}")
        st.caption(f"{brand} • {r.get('product_type', '')}")
        
        if main_issue and 'no significant' not in main_issue.lower():
            st.markdown(f"<div class='issue-box'>⚠️ {main_issue}</div>", unsafe_allow_html=True)
        
        # Ingredients
        harmful_list = r.get('harmful_found', [])
        if ingredients:
            harmful = len(harmful_list) if harmful_list else sum(1 for i in ingredients if categorize_ingredient(i) == 'harmful')
            caution = sum(1 for i in ingredients if categorize_ingredient(i) == 'caution')
            safe = sum(1 for i in ingredients if categorize_ingredient(i) == 'safe')
            
            st.markdown(f'''
            <div class="ing-summary">
                <span class="ing-badge ing-harmful">🔴 {harmful} Harmful</span>
                <span class="ing-badge ing-caution">🟡 {caution} Caution</span>
                <span class="ing-badge ing-safe">🟢 {safe} Safe</span>
            </div>
            ''', unsafe_allow_html=True)
            
            if harmful_list:
                st.markdown(f"**⚠️ Harmful:** {', '.join(harmful_list)}")
            
            with st.expander("View all ingredients"):
                for ing in ingredients:
                    cat = categorize_ingredient(ing)
                    icon = {"harmful": "🔴", "caution": "🟡", "safe": "🟢"}.get(cat, "⚪")
                    st.markdown(f"{icon} {ing}")
        
        # Violations
        violations = r.get('violations', [])
        if violations:
            with st.expander(f"⚖️ {len(violations)} Violations"):
                for v in violations:
                    st.markdown(f"**Law {v.get('law')}: {v.get('name')}** ({v.get('points')}) - {v.get('reason', '')}")
        
        # Better option
        better = r.get('better_option', {})
        if better and better.get('name') and verdict not in ['BUY', 'UNCLEAR']:
            st.markdown(f"<div class='alt-card'><strong>💡 Try:</strong> {better.get('name')} at {better.get('store', '')}</div>", unsafe_allow_html=True)
        
        if r.get('tip'):
            st.markdown(f"<div class='tip-box'>💡 {r['tip']}</div>", unsafe_allow_html=True)
        
        # =================================================================
        # SHARE SECTION - WITH GENERATED IMAGES
        # =================================================================
        if verdict != 'UNCLEAR':
            st.markdown("---")
            st.markdown("### 📤 Share Your Discovery")
            
            # Generate share images if not already
            if st.session_state.share_img is None:
                st.session_state.share_img = create_share_image(product_name, brand, score, verdict, main_issue)
                st.session_state.share_story = create_story_image(product_name, brand, score, verdict, main_issue)
            
            share_img = st.session_state.share_img
            share_story = st.session_state.share_story
            
            st.markdown("<div class='share-section'>", unsafe_allow_html=True)
            
            # Preview
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📱 Post (1:1)**")
                st.image(share_img, width=150)
                b64_post = image_to_base64(share_img)
                st.markdown(f'''<a href="data:image/png;base64,{b64_post}" download="honestworld_{score}.png" 
                    style="display:inline-block;padding:8px 16px;background:#6366f1;color:white;border-radius:8px;text-decoration:none;font-size:0.8rem;font-weight:600;">
                    ⬇️ Download Post</a>''', unsafe_allow_html=True)
            
            with col2:
                st.markdown("**📱 Story (9:16)**")
                st.image(share_story, width=100)
                b64_story = image_to_base64(share_story)
                st.markdown(f'''<a href="data:image/png;base64,{b64_story}" download="honestworld_story_{score}.png" 
                    style="display:inline-block;padding:8px 16px;background:linear-gradient(45deg,#f09433,#dc2743);color:white;border-radius:8px;text-decoration:none;font-size:0.8rem;font-weight:600;">
                    ⬇️ Download Story</a>''', unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Quick share links
            share_text = f"🌍 I scanned {product_name} - scored {score}/100! Check your products at HonestWorld #HonestWorld"
            encoded = urllib.parse.quote(share_text)
            
            st.markdown("**Quick Share:**")
            st.markdown(f'''
            <div class="share-buttons">
                <a href="https://twitter.com/intent/tweet?text={encoded}" target="_blank" class="share-btn share-twitter">🐦 Tweet</a>
                <a href="https://wa.me/?text={encoded}" target="_blank" class="share-btn share-whatsapp">💬 WhatsApp</a>
                <a href="https://www.facebook.com/sharer/sharer.php?quote={encoded}" target="_blank" class="share-btn share-facebook">📘 Facebook</a>
            </div>
            <p style="font-size:0.75rem;color:#64748b;text-align:center;margin-top:0.5rem;">
                📸 For Instagram/TikTok: Download image above → Open app → Create post → Upload image
            </p>
            ''', unsafe_allow_html=True)
        
        st.caption(f"ID: {st.session_state.sid}")
    
    else:
        # Stats
        st.markdown(f'''
        <div class="stat-row">
            <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">Scans</div></div>
            <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Avoided</div></div>
            <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Streak</div></div>
        </div>
        ''', unsafe_allow_html=True)
        
        mode = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
        
        imgs = []
        barcode_info = None
        
        if mode == "📷 Camera":
            if st.session_state.imgs:
                cols = st.columns(min(4, len(st.session_state.imgs) + 1))
                for i, img in enumerate(st.session_state.imgs):
                    with cols[i]:
                        st.image(img, width=70)
                        if st.button("✕", key=f"rm{i}"):
                            st.session_state.imgs.pop(i)
                            st.rerun()
                if len(st.session_state.imgs) < 3:
                    with cols[len(st.session_state.imgs)]:
                        if st.button("➕", key="add"):
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
            up = st.file_uploader("", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
            if up: imgs = up[:3]
        
        else:
            st.info("📊 Take clear photo of barcode")
            bc = st.camera_input("", label_visibility="collapsed", key="bc")
            if bc:
                imgs = [bc]
                barcode = try_decode_barcode(bc)
                if barcode:
                    st.success(f"✅ Barcode: {barcode}")
                    barcode_info = lookup_barcode(barcode)
                    if barcode_info.get('found'):
                        st.markdown(f"📦 **{barcode_info.get('name')}** by {barcode_info.get('brand')}")
                    st.session_state.barcode_data = barcode_info
        
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
                        pil.thumbnail((100, 100))
                        buf = BytesIO()
                        pil.save(buf, format='JPEG', quality=75)
                        thumb = buf.getvalue()
                    except: pass
                    
                    for i in imgs: i.seek(0)
                    
                    bc_info = st.session_state.get('barcode_data')
                    result = analyze(imgs, loc, update, bc_info)
                    
                    if result.get('verdict') != 'UNCLEAR':
                        sid = save_scan(result, user_id, thumb)
                        cloud_log_scan(result, loc.get('city', ''), loc.get('country', ''), user_id)
                        cloud_save_product(result)
                    else:
                        sid = "UNCLEAR"
                    
                    st.session_state.result = result
                    st.session_state.sid = sid
                    st.session_state.imgs = []
                    st.session_state.barcode_data = None
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
    st.markdown("### 🔎 Search")
    
    if supa_ok():
        cs = cloud_get_stats()
        st.caption(f"{cs.get('products', 0)} products in database")
    else:
        st.warning("⚠️ Database not connected")
    
    q = st.text_input("", placeholder="Search...", label_visibility="collapsed")
    
    if q and len(q) >= 2:
        results = cloud_search(q) if supa_ok() else []
        if results:
            for p in results:
                score = int(p.get('avg_score', 0))
                color = score_color(score)
                st.markdown(f'''
                <div class="history-row">
                    <div style="flex:1;"><strong>{p.get('product_name', '?')}</strong><br/>
                    <span style="font-size:0.75rem;color:#64748b;">{p.get('brand', '')} • {p.get('scan_count', 0)}x</span></div>
                    <div class="history-score" style="background:{color};">{score}</div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info("Not found. Scan it!")

# =============================================================================
# TAB: HISTORY
# =============================================================================
with tabs[2]:
    st.markdown("### 📜 My History")
    
    history = get_history(user_id, 20)
    if not history:
        st.info("No scans yet")
    else:
        for h in history:
            score = h['score']
            color = score_color(score)
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f'''
                <div class="history-row">
                    <div style="flex:1;"><strong>{h['product']}</strong><br/>
                    <span style="font-size:0.75rem;color:#64748b;">{h['brand']}</span></div>
                    <div class="history-score" style="background:{color};">{score}</div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button("🗑️", key=f"del_{h['db_id']}"):
                    delete_scan(h['db_id'], user_id)
                    st.rerun()

# =============================================================================
# TAB: PROFILE
# =============================================================================
with tabs[3]:
    st.markdown("### 👤 Profile")
    
    st.markdown(f'''
    <div class="stat-row">
        <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">Scans</div></div>
        <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Avoided</div></div>
        <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Streak</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**📍 Location**")
    col1, col2 = st.columns(2)
    with col1:
        new_city = st.text_input("City", value=loc.get('city', ''))
    with col2:
        new_country = st.text_input("Country", value=loc.get('country', ''))
    
    if st.button("📍 Update"):
        if new_city:
            save_location(new_city, new_country)
            st.session_state.loc = {'city': new_city, 'country': new_country, 'retailers': RETAILERS.get('AU', RETAILERS['OTHER'])}
            st.success("✅ Saved!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("**🛡️ Allergens**")
    curr_a = get_allergies()
    sel_a = []
    cols = st.columns(3)
    for i, a in enumerate(ALLERGENS.keys()):
        with cols[i % 3]:
            if st.checkbox(a.title(), value=a in curr_a, key=f"a_{a}"):
                sel_a.append(a)
    
    st.markdown("---")
    st.markdown("**👨‍👩‍👧 Profiles**")
    curr_p = get_profiles()
    sel_p = []
    for k, v in PROFILES.items():
        if st.checkbox(f"{v['icon']} {v['name']}", value=k in curr_p, key=f"p_{k}"):
            sel_p.append(k)
    
    if st.button("💾 Save", type="primary"):
        save_allergies(sel_a)
        save_profiles(sel_p)
        st.success("✅ Saved!")
    
    st.markdown("---")
    with st.expander("🔐 Admin"):
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
        st.markdown("### 📊 Admin")
        
        if st.button("Logout"):
            st.session_state.admin = False
            st.rerun()
        
        st.markdown(f"**Supabase:** {'✅ Connected' if supa_ok() else '❌ Not connected'}")
        st.markdown(f"**Key format:** `{SUPABASE_KEY[:20]}...`" if SUPABASE_KEY else "No key")
        
        if supa_ok():
            cs = cloud_get_stats()
            st.markdown(f"**Cloud:** {cs.get('scans', 0)} scans, {cs.get('products', 0)} products")
            
            st.markdown("**Recent:**")
            for s in cloud_get_recent_scans(10):
                st.markdown(f"• {s.get('product_name')} ({s.get('score')}) - {s.get('city')}")

st.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:0.7rem;padding:1rem;'>🌍 v18 • {loc.get('city', '?')}</div>", unsafe_allow_html=True)
