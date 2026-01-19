"""
🌍 HONESTWORLD v15.0 - PREMIUM EDITION
Mobile-First, Light Mode, Global Database, Admin Analytics

CHANGES FROM v14:
✅ Light mode (better for in-store use)
✅ Simpler ingredient display (X harmful, Y safe)
✅ Fixed score math bug
✅ Admin dashboard (password protected)
✅ Global Supabase database
✅ Bigger, clearer verdict
✅ Mobile-optimized UI
✅ API key from environment/secrets
"""

import streamlit as st
import google.generativeai as genai
import json
import re
import sqlite3
from PIL import Image
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
    layout="centered",  # Better for mobile
    initial_sidebar_state="collapsed"
)

LOCAL_DB = Path.home() / "honestworld_v15.db"

# API Key - Try secrets first, then environment, then fallback
try:
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "AIzaSyCnUy-L-Bv4wlm9h1lSDY7GQKtD3g5XWtM"))
except:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCnUy-L-Bv4wlm9h1lSDY7GQKtD3g5XWtM")

# Admin password (change this!)
ADMIN_PASSWORD_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# =============================================================================
# SUPABASE - GLOBAL DATABASE
# =============================================================================
# Get from secrets or environment
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))
except:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def supabase_ok():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def supa_post(table, data):
    if not supabase_ok(): return None
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            json=data, timeout=5
        )
        return r.json() if r.ok else None
    except: return None

def supa_get(table, params=None):
    if not supabase_ok(): return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params=params, timeout=5
        )
        return r.json() if r.ok else []
    except: return []

def supa_upsert(table, data, on_conflict="id"):
    if not supabase_ok(): return None
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", 
                     "Prefer": f"return=representation,resolution=merge-duplicates"},
            json=data, timeout=5
        )
        return r.json() if r.ok else None
    except: return None

# =============================================================================
# CLOUD FUNCTIONS
# =============================================================================
def cloud_log_scan(result, loc, user_id):
    """Log every scan to global database for analytics."""
    if not supabase_ok(): return
    supa_post("scans_log", {
        "product_name": result.get('product_name', 'Unknown'),
        "brand": result.get('brand', 'Unknown'),
        "category": result.get('product_type', ''),
        "score": result.get('score', 0),
        "verdict": result.get('verdict', 'CAUTION'),
        "violations_count": len(result.get('violations', [])),
        "city": loc.get('city', ''),
        "country": loc.get('country', ''),
        "user_id": user_id
    })

def cloud_upsert_product(result):
    """Update product in global database."""
    if not supabase_ok(): return
    name_lower = result.get('product_name', '').lower().strip()
    if not name_lower: return
    
    # Check if exists
    existing = supa_get("products", {"product_name_lower": f"eq.{name_lower}", "select": "id,avg_score,scan_count"})
    
    if existing:
        p = existing[0]
        new_count = p['scan_count'] + 1
        new_avg = round(((p['avg_score'] * p['scan_count']) + result.get('score', 0)) / new_count, 1)
        # Update via RPC or direct update
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/products?id=eq.{p['id']}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
            json={"avg_score": new_avg, "scan_count": new_count}, timeout=5
        )
    else:
        supa_post("products", {
            "product_name": result.get('product_name', 'Unknown'),
            "product_name_lower": name_lower,
            "brand": result.get('brand', ''),
            "category": result.get('product_type', ''),
            "avg_score": result.get('score', 0),
            "scan_count": 1,
            "ingredients_json": json.dumps(result.get('ingredients_rated', []))
        })

def cloud_search(query, limit=15):
    if not supabase_ok(): return []
    return supa_get("products", {
        "product_name_lower": f"ilike.%{query.lower()}%",
        "select": "product_name,brand,avg_score,scan_count",
        "order": "scan_count.desc",
        "limit": limit
    })

def cloud_get_stats():
    """Get global stats for admin dashboard."""
    if not supabase_ok(): return {}
    products = supa_get("products", {"select": "id"})
    scans = supa_get("scans_log", {"select": "id"})
    return {
        "total_products": len(products) if products else 0,
        "total_scans": len(scans) if scans else 0
    }

def cloud_get_recent_scans(limit=50):
    """Get recent scans for admin."""
    if not supabase_ok(): return []
    return supa_get("scans_log", {
        "select": "product_name,brand,score,verdict,city,country,created_at",
        "order": "created_at.desc",
        "limit": limit
    })

def cloud_get_top_products(limit=20):
    """Get most scanned products."""
    if not supabase_ok(): return []
    return supa_get("products", {
        "select": "product_name,brand,avg_score,scan_count",
        "order": "scan_count.desc",
        "limit": limit
    })

# =============================================================================
# INGREDIENT SAFETY - SIMPLIFIED
# =============================================================================
HARMFUL_KEYWORDS = [
    "paraben", "methylparaben", "propylparaben", "butylparaben", "ethylparaben",
    "bha", "bht", "triclosan", "formaldehyde", "phthalate", "oxybenzone",
    "coal tar", "hydroquinone", "lead", "mercury", "toluene"
]

CAUTION_KEYWORDS = [
    "fragrance", "parfum", "sulfate", "sls", "sles", "sodium lauryl",
    "propylene glycol", "peg-", "dimethicone", "aluminum", "fd&c", "dea", "mea"
]

SAFE_KEYWORDS = [
    "water", "aqua", "glycerin", "aloe", "shea", "coconut", "jojoba",
    "vitamin", "tocopherol", "citric acid", "hyaluronic", "niacinamide"
]

def categorize_ingredient(name):
    """Simple categorization: harmful, caution, or safe."""
    name_lower = name.lower()
    for kw in HARMFUL_KEYWORDS:
        if kw in name_lower:
            return "harmful"
    for kw in CAUTION_KEYWORDS:
        if kw in name_lower:
            return "caution"
    for kw in SAFE_KEYWORDS:
        if kw in name_lower:
            return "safe"
    return "unknown"

# =============================================================================
# 20 INTEGRITY LAWS
# =============================================================================
LAWS = {
    1: {"name": "Water-Down", "points": -15, "cat": "Ingredients"},
    2: {"name": "Fairy Dusting", "points": -12, "cat": "Ingredients"},
    3: {"name": "Split Sugar", "points": -20, "cat": "Ingredients"},
    4: {"name": "Low-Fat Trap", "points": -10, "cat": "Nutrition"},
    5: {"name": "Natural Fallacy", "points": -10, "cat": "Claims"},
    6: {"name": "Made-With Trick", "points": -8, "cat": "Claims"},
    7: {"name": "Serving Trick", "points": -10, "cat": "Packaging"},
    8: {"name": "Slack Fill", "points": -8, "cat": "Packaging"},
    9: {"name": "Spec Inflation", "points": -15, "cat": "Electronics"},
    10: {"name": "Compatibility Lie", "points": -12, "cat": "Electronics"},
    11: {"name": "Military Myth", "points": -10, "cat": "Electronics"},
    12: {"name": "Battery Fiction", "points": -12, "cat": "Electronics"},
    13: {"name": "Clinical Ghost", "points": -12, "cat": "Health"},
    14: {"name": "Dilution Trick", "points": -10, "cat": "Health"},
    15: {"name": "Free Trap", "points": -15, "cat": "Services"},
    16: {"name": "Unlimited Lie", "points": -18, "cat": "Services"},
    17: {"name": "Lifetime Illusion", "points": -10, "cat": "Warranty"},
    18: {"name": "Photo Fake", "points": -12, "cat": "Packaging"},
    19: {"name": "Fake Cert", "points": -15, "cat": "Claims"},
    20: {"name": "Name Trick", "points": -10, "cat": "Naming"},
}

# =============================================================================
# ALLERGENS & PROFILES
# =============================================================================
ALLERGENS = {
    "gluten": ["wheat", "barley", "rye", "gluten"],
    "dairy": ["milk", "lactose", "casein", "whey", "cream"],
    "nuts": ["peanut", "almond", "cashew", "walnut", "hazelnut"],
    "soy": ["soy", "soya", "soybean", "lecithin"],
    "eggs": ["egg", "albumin"],
    "shellfish": ["shrimp", "crab", "lobster", "prawn"],
    "fragrance": ["fragrance", "parfum", "perfume"],
    "parabens": ["paraben"],
    "sulfates": ["sulfate", "sls", "sles"],
}

PROFILES = {
    "baby": {"name": "Baby Safe", "icon": "👶", "avoid": ["fragrance", "paraben", "sulfate", "alcohol", "retinol"]},
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

def get_location():
    try:
        r = requests.get('https://ipwho.is/', timeout=3)
        if r.ok:
            d = r.json()
            cc = d.get('country_code', 'OTHER')
            return {'city': d.get('city', 'Unknown'), 'country': d.get('country', 'Unknown'),
                    'code': cc, 'retailers': RETAILERS.get(cc, RETAILERS['OTHER'])}
    except: pass
    return {'city': 'Unknown', 'country': 'Unknown', 'code': 'OTHER', 'retailers': RETAILERS['OTHER']}

# =============================================================================
# LOCAL DATABASE
# =============================================================================
def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY, scan_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        product TEXT, brand TEXT, score INTEGER, verdict TEXT, thumb BLOB
    )''')
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE
    )''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (
        id INTEGER PRIMARY KEY DEFAULT 1, user_id TEXT
    )''')
    # Generate unique user ID for analytics
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

def save_scan(result, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('INSERT INTO scans (scan_id, product, brand, score, verdict, thumb) VALUES (?,?,?,?,?,?)',
        (sid, result.get('product_name',''), result.get('brand',''), result.get('score',0), result.get('verdict',''), thumb))
    
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

def get_history(n=20):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT scan_id, ts, product, brand, score, verdict, thumb FROM scans ORDER BY ts DESC LIMIT ?', (n,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'ts': r[1], 'product': r[2], 'brand': r[3], 'score': r[4], 'verdict': r[5], 'thumb': r[6]} for r in rows]

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

Location: {location} | Stores: {retailers}

THE 20 INTEGRITY LAWS (deduct points for each violation found):
1. Water-Down (-15): Cheap filler #1 but marketed as premium
2. Fairy Dusting (-12): Advertised ingredient below position #5
3. Split Sugar (-20): Sugar split into multiple names to hide total
4. Low-Fat Trap (-10): Low-fat but added sugar/sodium
5. Natural Fallacy (-10): "Natural" label but contains synthetics
6. Made-With Trick (-8): "Made with X" but X is minimal
7. Serving Trick (-10): Unrealistic tiny serving size
8. Slack Fill (-8): Package mostly empty/air
9. Spec Inflation (-15): "Up to X" only in perfect conditions
10. Compatibility Lie (-12): "Universal" with many exceptions
11. Military Myth (-10): Fake military grade claim
12. Battery Fiction (-12): Unrealistic battery life claims
13. Clinical Ghost (-12): "Clinically proven" without study details
14. Dilution Trick (-10): Active ingredients too diluted
15. Free Trap (-15): "Free" but requires credit card
16. Unlimited Lie (-18): "Unlimited" with hidden caps
17. Lifetime Illusion (-10): Lifetime warranty excludes everything
18. Photo Fake (-12): Package photo vs reality mismatch
19. Fake Cert (-15): Claims certification without proof
20. Name Trick (-10): Product name implies ingredients not present

SCORING: Start at 100. Deduct points for each violation. 
- 80-100 = BUY (green)
- 50-79 = CAUTION (orange)  
- 0-49 = AVOID (red)

Return ONLY valid JSON:
{{
    "product_name": "<exact product name>",
    "brand": "<brand name>",
    "product_type": "<food/cosmetics/electronics/household/service>",
    "score": <calculated score>,
    "verdict": "<BUY/CAUTION/AVOID>",
    "violations": [
        {{"law": <number>, "name": "<law name>", "points": <negative number>, "reason": "<specific evidence>"}}
    ],
    "ingredients": ["<ingredient 1>", "<ingredient 2>", ...],
    "main_issue": "<one sentence - biggest problem, or 'No major issues found'>",
    "better_option": {{"name": "<alternative product>", "store": "<from store list>", "why": "<brief reason>"}},
    "tip": "<one actionable shopping tip>"
}}"""

def analyze(images, loc, progress):
    progress(0.2, "Reading product...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 4000})
    
    pil = [Image.open(img) for img in images]
    for img in images: img.seek(0)
    
    progress(0.5, "Checking 20 integrity laws...")
    prompt = PROMPT.format(location=f"{loc['city']}, {loc['country']}", retailers=", ".join(loc['retailers']))
    
    progress(0.8, "Generating verdict...")
    resp = model.generate_content([prompt] + pil)
    
    text = resp.text.strip()
    # Extract JSON
    for pat in [r'```json\s*(.*?)\s*```', r'\{.*\}']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                result = json.loads(m.group(1) if '```' in pat else m.group(0))
                # Verify score matches violations
                violations = result.get('violations', [])
                calc_score = 100 + sum(v.get('points', 0) for v in violations)
                result['score'] = max(0, min(100, calc_score))
                # Set verdict based on score
                if result['score'] >= 80:
                    result['verdict'] = 'BUY'
                elif result['score'] >= 50:
                    result['verdict'] = 'CAUTION'
                else:
                    result['verdict'] = 'AVOID'
                progress(1.0, "Done!")
                return result
            except: continue
    return json.loads(text)

# =============================================================================
# UI HELPERS
# =============================================================================
def score_color(s):
    if s >= 80: return "#22c55e"  # Green
    if s >= 50: return "#f59e0b"  # Orange
    return "#ef4444"  # Red

def thumb_b64(data):
    return base64.b64encode(data).decode() if data else None
# =============================================================================
# CSS - LIGHT MODE (Better for shopping in bright stores)
# =============================================================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

* { font-family: 'Inter', -apple-system, sans-serif; }

/* Light mode base */
.stApp { background: #f8fafc !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 480px; }

h1, h2, h3, h4 { color: #1e293b; font-weight: 700; }
p, span, div, label { color: #334155; }

/* Camera */
[data-testid="stCameraInput"] { max-width: 280px !important; margin: 0 auto !important; }
[data-testid="stCameraInput"] video { max-height: 200px !important; border-radius: 16px; }

/* Cards */
.card { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1rem; margin: 0.5rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }

/* Big verdict cards */
.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-card { border-radius: 24px; padding: 1.5rem; text-align: center; color: white; margin: 1rem 0; }
.verdict-icon { font-size: 4rem; line-height: 1; }
.verdict-text { font-size: 1.5rem; font-weight: 900; margin: 0.5rem 0; }
.verdict-score { font-size: 3rem; font-weight: 900; }

/* Stats */
.stat-row { display: flex; gap: 0.5rem; margin: 0.75rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.75rem; text-align: center; }
.stat-val { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }

/* Alert boxes */
.alert-danger { background: #fef2f2; border: 2px solid #ef4444; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.alert-warning { background: #fffbeb; border: 2px solid #f59e0b; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.alert-success { background: #f0fdf4; border: 2px solid #22c55e; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }

/* Main issue box */
.issue-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 0.75rem 1rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

/* Ingredient summary */
.ing-summary { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.ing-badge { padding: 0.4rem 0.8rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
.ing-harmful { background: #fecaca; color: #dc2626; }
.ing-caution { background: #fef3c7; color: #d97706; }
.ing-safe { background: #bbf7d0; color: #16a34a; }

/* Violations */
.violation { background: #fef2f2; border-left: 4px solid #ef4444; padding: 0.75rem; margin: 0.3rem 0; border-radius: 0 10px 10px 0; }
.violation-title { color: #dc2626; font-weight: 700; font-size: 0.9rem; }
.violation-reason { color: #64748b; font-size: 0.8rem; margin-top: 0.25rem; }

/* Alternative */
.alt-card { background: #f0fdf4; border: 1px solid #86efac; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.alt-name { color: #16a34a; font-weight: 700; }

/* History */
.history-row { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }
.history-thumb { width: 44px; height: 44px; border-radius: 10px; object-fit: cover; background: #f1f5f9; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; }
.history-score { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.8rem; }

/* Share buttons */
.share-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0; }
.share-btn { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.5rem 0.8rem; border-radius: 8px; color: white; font-weight: 600; font-size: 0.75rem; text-decoration: none; }
.share-twitter { background: #1DA1F2; }
.share-facebook { background: #4267B2; }
.share-whatsapp { background: #25D366; }
.share-telegram { background: #0088cc; }

/* Progress */
.progress-box { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; text-align: center; }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 1rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); border-radius: 3px; transition: width 0.3s; }

/* Buttons */
.stButton > button { 
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important; 
    color: white !important; 
    font-weight: 700 !important; 
    border: none !important; 
    border-radius: 12px !important;
    padding: 0.75rem 1.5rem !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

/* Location badge */
.loc-badge { background: #dbeafe; color: #2563eb; padding: 0.3rem 0.75rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

/* Streak badge */
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.75rem; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }

/* Admin dashboard */
.admin-card { background: #1e293b; color: white; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.admin-stat { font-size: 2rem; font-weight: 800; color: #60a5fa; }

/* Quick tip */
.tip-box { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }
.tip-box::before { content: "💡 "; }

/* Hide streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
</style>
"""

# =============================================================================
# MAIN APP
# =============================================================================
st.markdown(CSS, unsafe_allow_html=True)

# Session state
if 'result' not in st.session_state: st.session_state.result = None
if 'sid' not in st.session_state: st.session_state.sid = None
if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'loc' not in st.session_state: st.session_state.loc = get_location()
if 'admin' not in st.session_state: st.session_state.admin = False

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
    st.markdown(f"<span class='loc-badge'>📍 {loc['city']}</span>", unsafe_allow_html=True)

# Navigation - Add Admin tab if logged in
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
        
        if st.button("🔄 Scan Another Product"):
            st.session_state.result = None
            st.session_state.imgs = []
            st.rerun()
        
        # Personal alerts FIRST
        ingredients = r.get('ingredients', [])
        alerts = check_alerts(ingredients, get_allergies(), get_profiles())
        for a in alerts:
            icon = "🚨" if a['type'] == 'allergy' else a.get('icon', '⚠️')
            cls = 'alert-danger' if a['type'] == 'allergy' else 'alert-warning'
            st.markdown(f"<div class='{cls}'>{icon} <strong>{a['name']}</strong> detected: contains {a['trigger']}</div>", unsafe_allow_html=True)
        
        # BIG VERDICT CARD
        verdict_class = f"verdict-{verdict.lower()}"
        verdict_icon = {"BUY": "✓", "CAUTION": "⚠", "AVOID": "✗"}[verdict]
        verdict_text = {"BUY": "GOOD TO BUY", "CAUTION": "USE CAUTION", "AVOID": "AVOID THIS"}[verdict]
        
        st.markdown(f'''
        <div class="verdict-card {verdict_class}">
            <div class="verdict-icon">{verdict_icon}</div>
            <div class="verdict-text">{verdict_text}</div>
            <div class="verdict-score">{score}<span style="font-size:1.2rem;">/100</span></div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Product name
        st.markdown(f"### {r.get('product_name', 'Unknown Product')}")
        st.caption(f"{r.get('brand', '')} • {r.get('product_type', '')}")
        
        # Main issue (simple, clear)
        main_issue = r.get('main_issue', '')
        if main_issue and 'no major' not in main_issue.lower():
            st.markdown(f"<div class='issue-box'>⚠️ <strong>Main Issue:</strong> {main_issue}</div>", unsafe_allow_html=True)
        
        # SIMPLE INGREDIENT SUMMARY
        if ingredients:
            harmful = sum(1 for i in ingredients if categorize_ingredient(i) == 'harmful')
            caution = sum(1 for i in ingredients if categorize_ingredient(i) == 'caution')
            safe = sum(1 for i in ingredients if categorize_ingredient(i) == 'safe')
            
            st.markdown(f'''
            <div class="ing-summary">
                <span class="ing-badge ing-harmful">🔴 {harmful} Harmful</span>
                <span class="ing-badge ing-caution">🟡 {caution} Caution</span>
                <span class="ing-badge ing-safe">🟢 {safe} Safe</span>
            </div>
            ''', unsafe_allow_html=True)
            
            # Expandable details
            with st.expander("View all ingredients"):
                for ing in ingredients:
                    cat = categorize_ingredient(ing)
                    icon = {"harmful": "🔴", "caution": "🟡", "safe": "🟢"}.get(cat, "⚪")
                    st.markdown(f"{icon} {ing}")
        
        # Violations
        violations = r.get('violations', [])
        if violations:
            with st.expander(f"⚖️ {len(violations)} Law Violations"):
                # Show correct math
                points = sum(v.get('points', 0) for v in violations)
                math_str = "100 " + " ".join([f"- {abs(v.get('points', 0))}" for v in violations]) + f" = {score}"
                st.code(math_str)
                
                for v in violations:
                    st.markdown(f'''
                    <div class="violation">
                        <div class="violation-title">Law {v.get('law', '?')}: {v.get('name', '?')} ({v.get('points', 0)})</div>
                        <div class="violation-reason">{v.get('reason', '')}</div>
                    </div>
                    ''', unsafe_allow_html=True)
        
        # Better option
        better = r.get('better_option', {})
        if better and verdict != 'BUY':
            st.markdown(f'''
            <div class="alt-card">
                <div class="alt-name">💡 Try Instead: {better.get('name', '')}</div>
                <div style="color:#64748b;font-size:0.85rem;">{better.get('why', '')}</div>
                <div style="margin-top:0.5rem;"><span class="loc-badge">📍 {better.get('store', '')}</span></div>
            </div>
            ''', unsafe_allow_html=True)
        
        # Tip
        tip = r.get('tip', '')
        if tip:
            st.markdown(f"<div class='tip-box'>{tip}</div>", unsafe_allow_html=True)
        
        # Actions
        st.markdown("---")
        
        # Share buttons
        st.markdown("**Share your discovery:**")
        share_text = f"🌍 Scanned {r.get('product_name', 'product')} - {score}/100 ({verdict})! #HonestWorld"
        encoded = urllib.parse.quote(share_text)
        
        st.markdown(f'''
        <div class="share-row">
            <a href="https://twitter.com/intent/tweet?text={encoded}" target="_blank" class="share-btn share-twitter">🐦 Twitter</a>
            <a href="https://www.facebook.com/sharer/sharer.php?quote={encoded}" target="_blank" class="share-btn share-facebook">📘 Facebook</a>
            <a href="https://wa.me/?text={encoded}" target="_blank" class="share-btn share-whatsapp">💬 WhatsApp</a>
            <a href="https://t.me/share/url?text={encoded}" target="_blank" class="share-btn share-telegram">✈️ Telegram</a>
        </div>
        ''', unsafe_allow_html=True)
        
        st.caption(f"Scan ID: {st.session_state.sid}")
    
    else:
        # Stats row
        st.markdown(f'''
        <div class="stat-row">
            <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">My Scans</div></div>
            <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Avoided</div></div>
            <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Day Streak</div></div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Scan mode
        mode = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
        
        imgs = []
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
                cam = st.camera_input("Take photo of product", label_visibility="collapsed", key=f"cam{len(st.session_state.imgs)}")
                if cam:
                    st.session_state.imgs.append(cam)
                    st.session_state.adding = False
                    st.rerun()
            imgs = st.session_state.imgs
        
        elif mode == "📁 Upload":
            up = st.file_uploader("Upload product images", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
            if up:
                imgs = up[:3]
        
        else:  # Barcode
            st.info("📊 Point camera at product barcode")
            bc = st.camera_input("", label_visibility="collapsed", key="bc")
            if bc:
                imgs = [bc]
        
        if imgs:
            if st.button("🔍 ANALYZE PRODUCT", type="primary", use_container_width=True):
                prog = st.empty()
                def update(p, t):
                    prog.markdown(f"<div class='progress-box'><div style='color:#64748b;'>{t}</div><div class='progress-bar'><div class='progress-fill' style='width:{p*100}%;'></div></div></div>", unsafe_allow_html=True)
                
                try:
                    # Thumbnail
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
                    result = analyze(imgs, loc, update)
                    
                    # Save locally
                    sid = save_scan(result, thumb)
                    
                    # Save to cloud (global database)
                    cloud_log_scan(result, loc, user_id)
                    cloud_upsert_product(result)
                    
                    st.session_state.result = result
                    st.session_state.sid = sid
                    st.session_state.imgs = []
                    prog.empty()
                    st.rerun()
                except Exception as e:
                    prog.empty()
                    st.error(f"Analysis failed: {e}")

# =============================================================================
# TAB: SEARCH
# =============================================================================
with tabs[1]:
    st.markdown("### 🔎 Search Products")
    
    if supabase_ok():
        cloud_stats = cloud_get_stats()
        st.markdown(f"<div style='text-align:center;color:#64748b;margin-bottom:1rem;'>{cloud_stats.get('total_products', 0)} products in global database</div>", unsafe_allow_html=True)
    
    q = st.text_input("", placeholder="Search product name...", label_visibility="collapsed")
    
    if q and len(q) >= 2:
        results = cloud_search(q) if supabase_ok() else []
        if results:
            for p in results:
                score = int(p.get('avg_score', 0))
                color = score_color(score)
                st.markdown(f'''
                <div class="history-row">
                    <div class="history-thumb">📦</div>
                    <div style="flex:1;">
                        <div style="font-weight:600;">{p.get('product_name', '?')}</div>
                        <div style="font-size:0.75rem;color:#64748b;">{p.get('brand', '')} • {p.get('scan_count', 0)}x scanned</div>
                    </div>
                    <div class="history-score" style="background:{color};">{score}</div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info("No products found. Scan it to add to database!")
    else:
        st.caption("Search the global product database")

# =============================================================================
# TAB: HISTORY
# =============================================================================
with tabs[2]:
    st.markdown("### 📜 My Scan History")
    
    history = get_history(20)
    if not history:
        st.info("No scans yet. Start scanning products!")
    else:
        for h in history:
            score = h['score']
            color = score_color(score)
            verdict_icon = {"BUY": "✓", "CAUTION": "⚠", "AVOID": "✗"}.get(h['verdict'], "?")
            
            thumb_html = ""
            if h.get('thumb'):
                b64 = thumb_b64(h['thumb'])
                thumb_html = f"<img src='data:image/jpeg;base64,{b64}' class='history-thumb'/>"
            else:
                thumb_html = "<div class='history-thumb'>📦</div>"
            
            st.markdown(f'''
            <div class="history-row">
                {thumb_html}
                <div style="flex:1;">
                    <div style="font-weight:600;">{h['product']}</div>
                    <div style="font-size:0.75rem;color:#64748b;">{h['brand']}</div>
                </div>
                <span style="color:{color};font-weight:700;margin-right:0.5rem;">{verdict_icon}</span>
                <div class="history-score" style="background:{color};">{score}</div>
            </div>
            ''', unsafe_allow_html=True)

# =============================================================================
# TAB: PROFILE
# =============================================================================
with tabs[3]:
    st.markdown("### 👤 My Profile")
    
    # Stats
    st.markdown(f'''
    <div class="stat-row">
        <div class="stat-box"><div class="stat-val">{stats['scans']}</div><div class="stat-lbl">Total Scans</div></div>
        <div class="stat-box"><div class="stat-val">{stats['avoided']}</div><div class="stat-lbl">Products Avoided</div></div>
        <div class="stat-box"><div class="stat-val">🔥 {stats['streak']}</div><div class="stat-lbl">Day Streak</div></div>
    </div>
    ''', unsafe_allow_html=True)
    
    if stats['best'] > 0:
        st.caption(f"🏆 Best streak: {stats['best']} days")
    
    st.markdown("---")
    
    # Allergens
    st.markdown("**🛡️ My Allergens**")
    st.caption("We'll alert you if products contain these")
    curr_a = get_allergies()
    sel_a = []
    cols = st.columns(3)
    for i, a in enumerate(ALLERGENS.keys()):
        with cols[i % 3]:
            if st.checkbox(a.title(), value=a in curr_a, key=f"a_{a}"):
                sel_a.append(a)
    
    st.markdown("---")
    
    # Profiles
    st.markdown("**👨‍👩‍👧 Safety Profiles**")
    st.caption("Extra checks for special needs")
    curr_p = get_profiles()
    sel_p = []
    for k, v in PROFILES.items():
        if st.checkbox(f"{v['icon']} {v['name']}", value=k in curr_p, key=f"p_{k}"):
            sel_p.append(k)
    
    if st.button("💾 Save My Settings", type="primary"):
        save_allergies(sel_a)
        save_profiles(sel_p)
        st.success("✅ Settings saved!")
    
    st.markdown("---")
    
    # Admin login (hidden at bottom)
    with st.expander("🔐 Admin Access"):
        pwd = st.text_input("Password", type="password", key="admin_pwd")
        if st.button("Login"):
            if hashlib.sha256(pwd.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
                st.session_state.admin = True
                st.success("✅ Admin access granted!")
                st.rerun()
            else:
                st.error("Wrong password")

# =============================================================================
# TAB: ADMIN (only if logged in)
# =============================================================================
if st.session_state.admin and len(tabs) > 4:
    with tabs[4]:
        st.markdown("### 📊 Admin Dashboard")
        
        if st.button("🚪 Logout"):
            st.session_state.admin = False
            st.rerun()
        
        if supabase_ok():
            cloud_stats = cloud_get_stats()
            
            st.markdown(f'''
            <div class="stat-row">
                <div class="admin-card"><div class="admin-stat">{cloud_stats.get('total_scans', 0)}</div><div style="color:#94a3b8;">Total Scans</div></div>
                <div class="admin-card"><div class="admin-stat">{cloud_stats.get('total_products', 0)}</div><div style="color:#94a3b8;">Products</div></div>
            </div>
            ''', unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("**📈 Recent Scans**")
            recent = cloud_get_recent_scans(30)
            if recent:
                for s in recent:
                    color = score_color(s.get('score', 0))
                    st.markdown(f'''
                    <div class="history-row">
                        <div style="flex:1;">
                            <div style="font-weight:600;">{s.get('product_name', '?')}</div>
                            <div style="font-size:0.7rem;color:#64748b;">{s.get('brand', '')} • {s.get('city', '')}, {s.get('country', '')}</div>
                        </div>
                        <div class="history-score" style="background:{color};">{s.get('score', 0)}</div>
                    </div>
                    ''', unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("**🏆 Top Products**")
            top = cloud_get_top_products(20)
            if top:
                for p in top:
                    st.markdown(f"• **{p.get('product_name', '?')}** ({p.get('brand', '')}) - {p.get('scan_count', 0)} scans, avg {int(p.get('avg_score', 0))}/100")
        else:
            st.warning("⚠️ Supabase not configured. Add SUPABASE_URL and SUPABASE_KEY to secrets.")
            st.markdown("""
            **Setup Instructions:**
            1. Create free account at [supabase.com](https://supabase.com)
            2. Create tables with this SQL:
            ```sql
            CREATE TABLE products (
                id SERIAL PRIMARY KEY,
                product_name TEXT,
                product_name_lower TEXT UNIQUE,
                brand TEXT,
                category TEXT,
                avg_score DECIMAL DEFAULT 0,
                scan_count INTEGER DEFAULT 1,
                ingredients_json TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE TABLE scans_log (
                id SERIAL PRIMARY KEY,
                product_name TEXT,
                brand TEXT,
                category TEXT,
                score INTEGER,
                verdict TEXT,
                violations_count INTEGER,
                city TEXT,
                country TEXT,
                user_id TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            -- Enable public access
            ALTER TABLE products ENABLE ROW LEVEL SECURITY;
            ALTER TABLE scans_log ENABLE ROW LEVEL SECURITY;
            CREATE POLICY "public" ON products FOR ALL USING (true);
            CREATE POLICY "public" ON scans_log FOR ALL USING (true);
            ```
            3. Add to Streamlit secrets:
            ```toml
            SUPABASE_URL = "https://xxx.supabase.co"
            SUPABASE_KEY = "your-anon-key"
            GEMINI_API_KEY = "your-gemini-key"
            ```
            """)

# Footer
st.markdown(f"<div style='text-align:center;color:#94a3b8;font-size:0.7rem;padding:1rem;'>🌍 HonestWorld v15 • 📍 {loc['city']}, {loc['country']}</div>", unsafe_allow_html=True)
