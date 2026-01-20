"""
🌍 HONESTWORLD v25.0 - ADVANCED AI LOGIC EDITION
Smart Context • Dynamic Scoring • Claims vs Reality • Scientific Sources
ALL FEATURES PRESERVED + MAJOR UPGRADES
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

VERSION = "25.0"
LOCAL_DB = Path.home() / "honestworld_v25.db"

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# THE 20 INTEGRITY LAWS - With DYNAMIC WEIGHTS by category
INTEGRITY_LAWS = {
    1: {"name": "Water-Down Deception", "base_points": -15, "category": "ingredients",
        "description": "Product claims 'premium/luxury' but #1 ingredient is water/cheap filler",
        "tip": "Check if the first ingredient matches the premium price",
        "dynamic_weights": {"cosmetics_serum": -25, "cosmetics_mist": -5, "food": -15, "supplement": -10}},
    2: {"name": "Fairy Dusting", "base_points": -12, "category": "ingredients",
        "description": "Hero ingredient advertised on front is below position #5",
        "tip": "Ingredients are listed by quantity - first = most",
        "dynamic_weights": {"cosmetics": -15, "food": -12, "supplement": -18}},
    3: {"name": "Split Sugar Trick", "base_points": -18, "category": "ingredients",
        "description": "Sugar split into 3+ names to hide total amount",
        "tip": "Add up ALL sugar types - they're often the real #1 ingredient"},
    4: {"name": "Low-Fat Trap", "base_points": -10, "category": "ingredients",
        "description": "Claims 'low fat' but compensates with high sugar",
        "tip": "Low-fat often means high sugar - check nutrition label"},
    5: {"name": "Natural Fallacy", "base_points": -10, "category": "ingredients",
        "description": "Claims 'natural' but contains synthetic ingredients",
        "tip": "'Natural' is unregulated - look for actual certifications",
        "dynamic_weights": {"cosmetics": -15, "food": -12, "household": -8}},
    6: {"name": "Made-With Loophole", "base_points": -8, "category": "ingredients",
        "description": "'Made with real X' but X is minimal in list",
        "tip": "'Made with' only requires a tiny amount"},
    7: {"name": "Serving Size Trick", "base_points": -10, "category": "packaging",
        "description": "Unrealistically small serving size",
        "tip": "Check servings per container - you probably eat more"},
    8: {"name": "Slack Fill", "base_points": -8, "category": "packaging",
        "description": "Package is mostly air/empty space",
        "tip": "Check net weight, not package size"},
    9: {"name": "Spec Inflation", "base_points": -15, "category": "electronics",
        "description": "'Up to X speed/capacity' unrealistic claims",
        "tip": "'Up to' means maximum under perfect conditions"},
    10: {"name": "Compatibility Lie", "base_points": -12, "category": "electronics",
        "description": "'Universal' with hidden exceptions",
        "tip": "Check compatibility list in fine print"},
    11: {"name": "Military Grade Myth", "base_points": -10, "category": "electronics",
        "description": "Claims 'military grade' without MIL-STD cert",
        "tip": "Real military spec products cite the MIL-STD number"},
    12: {"name": "Battery Fiction", "base_points": -12, "category": "electronics",
        "description": "Unrealistic battery life claims",
        "tip": "Battery life tested with screen dim and minimal use"},
    13: {"name": "Clinical Ghost", "base_points": -12, "category": "beauty",
        "description": "'Clinically proven' without study citation",
        "tip": "Real clinical proof includes study size and methodology"},
    14: {"name": "Concentration Trick", "base_points": -10, "category": "beauty",
        "description": "Active ingredient too diluted to be effective",
        "tip": "Effective concentrations: Vitamin C 10-20%, Retinol 0.3-1%"},
    15: {"name": "Free Trap", "base_points": -15, "category": "services",
        "description": "'Free' requires credit card or hidden purchase",
        "tip": "'Free trial' usually auto-charges - set cancel reminder"},
    16: {"name": "Unlimited Lie", "base_points": -18, "category": "services",
        "description": "'Unlimited' with caps or throttling",
        "tip": "'Unlimited' almost never means truly unlimited"},
    17: {"name": "Lifetime Illusion", "base_points": -10, "category": "services",
        "description": "'Lifetime warranty' with extensive exclusions",
        "tip": "'Lifetime' often means limited with many exclusions"},
    18: {"name": "Photo vs Reality", "base_points": -12, "category": "packaging",
        "description": "Package photo much better than actual product",
        "tip": "Package photos are styled - read actual contents"},
    19: {"name": "Fake Certification", "base_points": -15, "category": "claims",
        "description": "Claims certification without proper logo/number",
        "tip": "Real certifications show certifier's logo and ID number"},
    20: {"name": "Name Trick", "base_points": -10, "category": "claims",
        "description": "Product name implies ingredient not present",
        "tip": "'Honey Oat' doesn't mean it contains much honey or oat"}
}

# SCIENTIFIC SOURCES for ingredient warnings - "Cite Your Sources"
INGREDIENT_SCIENCE = {
    "paraben": {
        "concern": "Potential endocrine disruption",
        "severity": "medium",
        "sources": ["EU Scientific Committee on Consumer Safety (SCCS)", "Danish EPA Study 2018"],
        "context": "cosmetics",
        "note": "Low concentrations generally considered safe by FDA"
    },
    "methylparaben": {
        "concern": "Potential hormone disruption at high doses",
        "severity": "medium",
        "sources": ["EU SCCS Opinion 2013", "Journal of Applied Toxicology"],
        "context": "cosmetics"
    },
    "propylparaben": {
        "concern": "Higher absorption than methylparaben",
        "severity": "medium",
        "sources": ["EU SCCS restricted to 0.14%", "Environmental Working Group"],
        "context": "cosmetics"
    },
    "fragrance": {
        "concern": "Undisclosed mixture of chemicals, potential allergens",
        "severity": "medium",
        "sources": ["American Academy of Dermatology", "Contact Dermatitis Journal"],
        "context": "cosmetics",
        "note": "Companies not required to disclose fragrance components"
    },
    "sodium lauryl sulfate": {
        "concern": "Can irritate sensitive skin and eyes",
        "severity": "low",
        "sources": ["Journal of the American College of Toxicology", "CIR Expert Panel"],
        "context": "cosmetics",
        "note": "Safe in rinse-off products at typical concentrations"
    },
    "sodium laureth sulfate": {
        "concern": "Milder than SLS but potential 1,4-dioxane contamination",
        "severity": "low",
        "sources": ["FDA Guidance on 1,4-dioxane", "EWG Database"],
        "context": "cosmetics"
    },
    "phthalate": {
        "concern": "Potential endocrine disruption, reproductive effects",
        "severity": "high",
        "sources": ["CDC National Report on Human Exposure", "EPA Phthalate Action Plan"],
        "context": "cosmetics"
    },
    "dmdm hydantoin": {
        "concern": "Formaldehyde-releasing preservative",
        "severity": "high",
        "sources": ["International Agency for Research on Cancer", "Contact Dermatitis studies"],
        "context": "cosmetics"
    },
    "high fructose corn syrup": {
        "concern": "Linked to obesity, metabolic syndrome when over-consumed",
        "severity": "medium",
        "sources": ["American Journal of Clinical Nutrition", "Princeton University Study"],
        "context": "food"
    },
    "trans fat": {
        "concern": "Increases LDL cholesterol, heart disease risk",
        "severity": "high",
        "sources": ["FDA Ban 2018", "American Heart Association", "WHO Guidelines"],
        "context": "food"
    },
    "red 40": {
        "concern": "Hyperactivity concerns in sensitive children",
        "severity": "low",
        "sources": ["FDA CFSAN", "Southampton Study (UK)", "EFSA Opinion"],
        "context": "food",
        "note": "Requires warning label in EU, not in US"
    }
}

# POSITIVE BONUSES - Reward good practices
POSITIVE_BONUSES = {
    "certified_organic": {"points": 5, "name": "Certified Organic", "icon": "🌿", "keywords": ["usda organic", "certified organic", "100% organic"]},
    "fragrance_free": {"points": 4, "name": "Fragrance-Free", "icon": "🌸", "keywords": ["fragrance-free", "fragrance free", "unscented", "no fragrance"]},
    "third_party_tested": {"points": 5, "name": "Third-Party Tested", "icon": "✅", "keywords": ["nsf certified", "usp verified", "consumerlab", "third party tested"]},
    "ewg_verified": {"points": 4, "name": "EWG Verified", "icon": "🛡️", "keywords": ["ewg verified"]},
    "transparent_fragrance": {"points": 5, "name": "Fragrance Transparency", "icon": "📋", "keywords": ["fragrance ingredients listed", "fragrance disclosure"]},
    "recyclable_packaging": {"points": 3, "name": "Recyclable Packaging", "icon": "♻️", "keywords": ["recyclable", "post-consumer recycled", "pcr plastic"]},
    "glass_packaging": {"points": 4, "name": "Glass Packaging", "icon": "🫙", "keywords": ["glass bottle", "glass jar", "glass container"]},
    "cruelty_free": {"points": 3, "name": "Cruelty-Free", "icon": "🐰", "keywords": ["cruelty-free", "cruelty free", "not tested on animals", "leaping bunny"]},
    "vegan_certified": {"points": 3, "name": "Vegan Certified", "icon": "🌱", "keywords": ["vegan certified", "certified vegan"]},
    "short_ingredient_list": {"points": 2, "name": "Clean Formula", "icon": "✨", "check": "ingredient_count_under_10"}
}

def get_verdict(score):
    if score >= 90: return "EXCEPTIONAL"
    elif score >= 75: return "BUY"
    elif score >= 50: return "CAUTION"
    return "AVOID"

def get_verdict_display(verdict):
    return {'EXCEPTIONAL': {'icon': '★', 'text': 'EXCEPTIONAL', 'color': '#06b6d4'},
            'BUY': {'icon': '✓', 'text': 'GOOD TO BUY', 'color': '#22c55e'},
            'CAUTION': {'icon': '!', 'text': 'CHECK FIRST', 'color': '#f59e0b'},
            'AVOID': {'icon': '✗', 'text': 'NOT RECOMMENDED', 'color': '#ef4444'},
            'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}}.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})

# PRODUCT CATEGORIES with sub-types for dynamic scoring
PRODUCT_CATEGORIES = {
    "food": {
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "fresh"],
        "keywords": ["nutrition facts", "calories", "serving size", "sugar", "protein", "carbohydrate", "sodium", "vitamin", "ingredients:"],
        "health_concerns": ["diabetes", "heartcondition", "glutenfree", "vegan", "allergyprone"]
    },
    "cosmetics": {
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "face_cream", "mist", "toner", "mask"],
        "keywords": ["skin", "hair", "moisturizer", "cleanser", "shampoo", "spf", "dermatologist", "apply to", "topical"],
        "health_concerns": ["sensitive", "allergyprone", "pregnancy", "baby"]  # Relevant for cosmetics!
    },
    "supplement": {
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega"],
        "keywords": ["supplement facts", "dietary supplement", "daily value", "capsule", "tablet", "b complex", "vitamin"],
        "health_concerns": ["diabetes", "pregnancy", "vegan", "glutenfree", "allergyprone"]
    },
    "electronics": {
        "subtypes": ["phone", "computer", "accessory", "cable", "charger", "audio"],
        "keywords": ["battery", "usb", "wireless", "bluetooth", "mah", "watt", "processor"],
        "health_concerns": []
    },
    "household": {
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener"],
        "keywords": ["cleaner", "detergent", "disinfectant", "household", "laundry"],
        "health_concerns": ["sensitive", "allergyprone", "baby", "pregnancy"]
    }
}

# CONTEXT-AWARE HEALTH PROFILES - Smart alerts based on product category
HEALTH_PROFILES = {
    "diabetes": {
        "name": "Diabetes", "icon": "🩺",
        "food_concerns": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin"],
        "supplement_concerns": ["sugar", "maltodextrin", "dextrose"],
        "cosmetics_concerns": [],  # Not relevant for cosmetics
        "alert_template": {"food": "High sugar content - may affect blood sugar", "supplement": "Contains sweeteners - check carb content"}
    },
    "baby": {
        "name": "Baby Safe", "icon": "👶",
        "food_concerns": ["honey", "salt", "artificial sweetener", "caffeine"],
        "cosmetics_concerns": ["fragrance", "parfum", "alcohol denat", "retinol", "salicylic", "essential oil", "menthol", "camphor"],
        "household_concerns": ["chlorine", "ammonia", "fragrance"],
        "alert_template": {"food": "Not recommended for infants under 1 year", "cosmetics": "May be too harsh for baby's delicate skin", "household": "Keep away from baby items"}
    },
    "pregnancy": {
        "name": "Pregnancy", "icon": "🤰",
        "food_concerns": ["raw", "unpasteurized", "high mercury fish", "caffeine excess"],
        "cosmetics_concerns": ["retinol", "retinoid", "salicylic acid", "benzoyl peroxide", "hydroquinone", "phthalate", "chemical sunscreen"],
        "supplement_concerns": ["vitamin a excess", "retinol"],
        "alert_template": {"cosmetics": "Consult doctor - some ingredients not recommended during pregnancy", "supplement": "Check with healthcare provider before use"}
    },
    "sensitive": {
        "name": "Sensitive Skin", "icon": "🌸",
        "cosmetics_concerns": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate", "sodium lauryl", "witch hazel", "citrus oil"],
        "household_concerns": ["fragrance", "dye", "chlorine"],
        "alert_template": {"cosmetics": "Contains potential irritants for sensitive skin", "household": "May irritate sensitive skin on contact"}
    },
    "vegan": {
        "name": "Vegan", "icon": "🌱",
        "food_concerns": ["gelatin", "carmine", "honey", "milk", "whey", "casein", "egg", "lard", "tallow"],
        "cosmetics_concerns": ["lanolin", "carmine", "beeswax", "collagen", "keratin", "silk", "squalene", "guanine"],
        "supplement_concerns": ["gelatin", "fish oil", "bone meal"],
        "alert_template": {"default": "May contain animal-derived ingredients"}
    },
    "glutenfree": {
        "name": "Gluten-Free", "icon": "🌾",
        "food_concerns": ["wheat", "barley", "rye", "oat", "gluten", "malt", "triticale"],
        "supplement_concerns": ["wheat", "gluten", "barley grass"],
        "cosmetics_concerns": [],  # Gluten in cosmetics rarely an issue unless ingested
        "alert_template": {"food": "Contains gluten - not suitable for celiac disease", "supplement": "May contain gluten"}
    },
    "heartcondition": {
        "name": "Heart Health", "icon": "❤️",
        "food_concerns": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat"],
        "supplement_concerns": [],
        "cosmetics_concerns": [],  # NOT relevant for cosmetics!
        "alert_template": {"food": "High sodium/fat content - consider heart-healthy alternatives"}
    },
    "allergyprone": {
        "name": "Allergy Prone", "icon": "🤧",
        "food_concerns": ["nut", "peanut", "soy", "milk", "egg", "wheat", "shellfish", "fish", "sesame"],
        "cosmetics_concerns": ["fragrance", "nut oil", "almond", "coconut", "shea", "lanolin"],
        "household_concerns": ["fragrance", "dye"],
        "alert_template": {"food": "Contains common allergen", "cosmetics": "Contains potential allergen - patch test recommended"}
    }
}

# ALLERGENS with context
ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "flour", "malt"], "contexts": ["food", "supplement"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"], "contexts": ["food", "supplement"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia"], "contexts": ["food", "cosmetics"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"], "contexts": ["food", "cosmetics"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu", "lecithin"], "contexts": ["food", "supplement"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise", "meringue"], "contexts": ["food"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish", "chitosan"], "contexts": ["food", "supplement"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy", "fish oil"], "contexts": ["food", "supplement"]},
    "fragrance": {"name": "Fragrance", "icon": "🌺", "triggers": ["fragrance", "parfum", "perfume", "aroma"], "contexts": ["cosmetics", "household"]},
    "sulfates": {"name": "Sulfates", "icon": "🧴", "triggers": ["sulfate", "sls", "sles", "sodium lauryl", "sodium laureth"], "contexts": ["cosmetics"]},
    "parabens": {"name": "Parabens", "icon": "⚗️", "triggers": ["paraben", "methylparaben", "propylparaben", "butylparaben"], "contexts": ["cosmetics"]}
}

# ALTERNATIVES DATABASE - Extended with more categories
ALTERNATIVES = {
    "cleanser": {"name": "CeraVe Hydrating Cleanser", "why": "Fragrance-free, ceramides, gentle formula", "score": 92},
    "moisturizer": {"name": "CeraVe Moisturizing Cream", "why": "Ceramides, hyaluronic acid, fragrance-free", "score": 94},
    "sunscreen": {"name": "EltaMD UV Clear SPF 46", "why": "Zinc oxide, niacinamide, fragrance-free", "score": 93},
    "serum": {"name": "The Ordinary Niacinamide 10%", "why": "Transparent ingredients, effective concentration", "score": 91},
    "shampoo": {"name": "Free & Clear Shampoo", "why": "No sulfates, fragrance, parabens", "score": 94},
    "conditioner": {"name": "Free & Clear Conditioner", "why": "Gentle formula for sensitive scalps", "score": 93},
    "body wash": {"name": "Dove Sensitive Skin Body Wash", "why": "Hypoallergenic, fragrance-free option", "score": 87},
    "body lotion": {"name": "Vanicream Moisturizing Cream", "why": "No dyes, fragrance, parabens, lanolin", "score": 95},
    "face cream": {"name": "La Roche-Posay Toleriane", "why": "Minimal ingredients, dermatologist tested", "score": 93},
    "deodorant": {"name": "Native Deodorant (Unscented)", "why": "No aluminum, parabens, sulfates", "score": 86},
    "baby": {"name": "Cetaphil Baby Daily Lotion", "why": "Pediatrician tested, no parabens", "score": 91},
    "cereal": {"name": "Nature's Path Organic Cereals", "why": "USDA organic, no artificial colors", "score": 85},
    "snack": {"name": "RXBAR or Larabar", "why": "Simple ingredients, no added sugar", "score": 82},
    "chips": {"name": "Jackson's Sweet Potato Chips", "why": "Simple ingredients, coconut oil", "score": 80},
    "vitamin": {"name": "Thorne Basic B Complex", "why": "Third-party tested, bioavailable forms", "score": 94},
    "supplement": {"name": "NOW Foods or Thorne brand", "why": "GMP certified, third-party tested", "score": 90},
    "b complex": {"name": "Thorne Basic B Complex", "why": "Active forms, no fillers, third-party tested", "score": 94},
    "multivitamin": {"name": "Thorne Basic Nutrients", "why": "High quality, third-party verified", "score": 92},
    "protein": {"name": "Momentous Whey Protein", "why": "NSF Certified for Sport, clean formula", "score": 91},
    "default": {"name": "Search EWG.org database", "why": "Independent safety ratings for 80,000+ products", "score": None}
}

def get_alternative(product_name, product_type, subtype=None):
    """Get better alternative based on product name, type, and subtype"""
    search_text = f"{product_name} {product_type or ''} {subtype or ''}".lower()
    # Check specific matches first
    for key in ALTERNATIVES:
        if key in search_text and ALTERNATIVES[key]['name'].lower() not in search_text:
            return ALTERNATIVES[key]
    # Check by type/subtype
    if subtype and subtype in ALTERNATIVES:
        return ALTERNATIVES[subtype]
    if product_type == 'supplement':
        return ALTERNATIVES.get('supplement', ALTERNATIVES['default'])
    if product_type == 'cosmetics':
        for term in ['clean', 'wash', 'cream', 'lotion', 'serum', 'shampoo']:
            if term in search_text:
                return ALTERNATIVES.get(term.replace('wash', 'body wash'), ALTERNATIVES['default'])
    return ALTERNATIVES['default']

RETAILERS = {
    "AU": ["Chemist Warehouse", "Priceline Pharmacy", "Woolworths", "Coles"],
    "US": ["CVS", "Walgreens", "Target", "Walmart", "Whole Foods"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's"],
    "NZ": ["Chemist Warehouse", "Countdown", "Unichem"],
    "CA": ["Shoppers Drug Mart", "Walmart", "London Drugs"],
    "OTHER": ["Local pharmacy", "Health food store", "Online retailers"]
}

def get_location():
    """Auto-detect location from IP with multiple fallbacks"""
    services = [
        ('https://ipapi.co/json/', lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))),
        ('https://ip-api.com/json/', lambda d: (d.get('city'), d.get('country'), d.get('countryCode'))),
        ('https://ipinfo.io/json', lambda d: (d.get('city'), d.get('country'), d.get('country'))),
    ]
    for url, extract in services:
        try:
            r = requests.get(url, timeout=5)
            if r.ok:
                d = r.json()
                city, country, code = extract(d)
                if city and city not in ['', 'Unknown', None]:
                    return {'city': city, 'country': country or '', 'code': code or 'OTHER', 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
        except: continue
    return {'city': 'Your City', 'country': 'Your Country', 'code': 'OTHER', 'retailers': RETAILERS['OTHER']}
# DATABASE WITH LEARNING SYSTEM
def normalize_product_name(name):
    return re.sub(r'[^\w\s]', '', name.lower()).strip() if name else ""

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT, product_type TEXT, subtype TEXT, score INTEGER, verdict TEXT, ingredients TEXT, violations TEXT, bonuses TEXT, thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS learned_products (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name_lower TEXT UNIQUE, product_name TEXT, brand TEXT, product_type TEXT, avg_score REAL, scan_count INTEGER DEFAULT 1, ingredients TEXT, violations TEXT, last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (barcode TEXT PRIMARY KEY, product_name TEXT, brand TEXT, ingredients TEXT, product_type TEXT, categories TEXT, nutrition TEXT, image_url TEXT, score INTEGER, source TEXT, confidence TEXT, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP)''')
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
    if r and r[0] and r[0] not in ['Unknown', '', 'Your City']:
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

def cache_barcode(barcode, data):
    """Cache barcode data for faster future lookups"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO barcode_cache 
                     (barcode, product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, confidence, last_updated) 
                     VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''', 
                  (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''), 
                   data.get('product_type', ''), data.get('categories', ''), json.dumps(data.get('nutrition', {})),
                   data.get('image_url', ''), data.get('source', ''), data.get('confidence', 'medium')))
        conn.commit()
        conn.close()
    except: pass

def get_cached_barcode(barcode):
    """Get cached barcode data"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, confidence FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]:
            return {
                'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 
                'product_type': r[3], 'categories': r[4], 'nutrition': json.loads(r[5]) if r[5] else {},
                'image_url': r[6], 'source': r[7], 'confidence': r[8], 'cached': True
            }
    except: pass
    return None

def save_scan(result, user_id, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('INSERT INTO scans (scan_id, user_id, product, brand, product_type, subtype, score, verdict, ingredients, violations, bonuses, thumb) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', 
              (sid, user_id, result.get('product_name',''), result.get('brand',''), result.get('product_type', ''), 
               result.get('subtype', ''), result.get('score',0), result.get('verdict',''), 
               json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), 
               json.dumps(result.get('bonuses', [])), thumb))
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

# CLOUD DATABASE (Supabase)
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
# BARCODE SCANNING - ACCURATE LIKE COMPETITORS (Yuka, Think Dirty, CodeCheck)
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
        # Try multiple preprocessing approaches
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L')]:
            barcodes = pyzbar.decode(proc_img)
            if barcodes:
                return barcodes[0].data.decode('utf-8')
    except: pass
    return None

def ai_read_barcode(image_file):
    """AI reads barcode numbers from image"""
    if not GEMINI_API_KEY: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        resp = model.generate_content([
            "Look at this image and find any barcode. Read the numbers printed below the barcode lines. "
            "Return ONLY the digits with no spaces. If multiple barcodes, return the clearest one. "
            "If no barcode or unreadable, return exactly: NONE", img
        ])
        text = resp.text.strip().upper()
        if 'NONE' in text or 'UNREADABLE' in text: return None
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14: return digits
    except: pass
    return None

def lookup_barcode_accurate(barcode):
    """
    ACCURATE barcode lookup like competitors (Yuka, Think Dirty, CodeCheck)
    Searches multiple databases and returns the BEST match
    """
    results = []
    
    # 1. Open Food Facts (Best for food products globally)
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=8)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or p.get('generic_name') or ''
                if name:
                    results.append({
                        'found': True,
                        'name': name,
                        'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '',
                        'categories': p.get('categories', ''),
                        'nutrition': p.get('nutriments', {}),
                        'image_url': p.get('image_url', ''),
                        'product_type': 'food',
                        'source': 'Open Food Facts',
                        'confidence': 'high'
                    })
    except: pass
    
    # 2. Open Beauty Facts (Best for cosmetics/personal care)
    try:
        r = requests.get(f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json", timeout=8)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or ''
                if name:
                    results.append({
                        'found': True,
                        'name': name,
                        'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '',
                        'categories': p.get('categories', ''),
                        'image_url': p.get('image_url', ''),
                        'product_type': 'cosmetics',
                        'source': 'Open Beauty Facts',
                        'confidence': 'high'
                    })
    except: pass
    
    # 3. Open Products Facts (Household, etc)
    try:
        r = requests.get(f"https://world.openproductsfacts.org/api/v0/product/{barcode}.json", timeout=8)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or ''
                if name:
                    results.append({
                        'found': True,
                        'name': name,
                        'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text', ''),
                        'product_type': 'household',
                        'source': 'Open Products Facts',
                        'confidence': 'high'
                    })
    except: pass
    
    # 4. UPC Item DB (General products, good for supplements/electronics)
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=8)
        if r.ok:
            d = r.json()
            items = d.get('items', [])
            if items:
                item = items[0]
                results.append({
                    'found': True,
                    'name': item.get('title', ''),
                    'brand': item.get('brand', ''),
                    'description': item.get('description', ''),
                    'categories': item.get('category', ''),
                    'image_url': item.get('images', [''])[0] if item.get('images') else '',
                    'source': 'UPC Item DB',
                    'confidence': 'medium'
                })
    except: pass
    
    # Return BEST result (prioritize: has ingredients > high confidence > has name)
    if results:
        # Sort by: has ingredients (most important), confidence, name length
        results.sort(key=lambda x: (
            bool(x.get('ingredients')),  # Has ingredients first
            x.get('confidence') == 'high',  # High confidence
            len(x.get('name', ''))  # Longer name (more specific)
        ), reverse=True)
        return results[0]
    
    return {'found': False}

def smart_barcode_lookup(barcode, progress_callback=None):
    """
    Smart barcode lookup with caching and fallback
    Works like Yuka/Think Dirty - accurate and fast
    """
    if progress_callback: progress_callback(0.1, "Checking cache...")
    
    # 1. Check cache first (instant!)
    cached = get_cached_barcode(barcode)
    if cached:
        if progress_callback: progress_callback(1.0, "✓ Found in cache!")
        return cached
    
    if progress_callback: progress_callback(0.3, "Searching product databases...")
    
    # 2. Search all databases
    result = lookup_barcode_accurate(barcode)
    
    if result.get('found'):
        if progress_callback: progress_callback(0.8, "✓ Product found!")
        # Cache for future
        cache_barcode(barcode, result)
        return result
    
    if progress_callback: progress_callback(1.0, "Not found in databases")
    return {'found': False, 'barcode': barcode}

# SHARE IMAGE GENERATION - FIXED (no emoji issues)
def create_share_image(product_name, brand, score, verdict, violations=None, bonuses=None):
    width, height = 1080, 1080
    colors = {
        'EXCEPTIONAL': {'bg': '#06b6d4', 'bg2': '#0891b2'},
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}
    }
    c = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    
    # Gradient
    for i in range(height//2, height):
        progress = (i - height//2) / (height//2)
        r1, g1, b1 = int(c['bg'][1:3], 16), int(c['bg'][3:5], 16), int(c['bg'][5:7], 16)
        r2, g2, b2 = int(c['bg2'][1:3], 16), int(c['bg2'][3:5], 16), int(c['bg2'][5:7], 16)
        draw.line([(0, i), (width, i)], fill=(int(r1+(r2-r1)*progress), int(g1+(g2-g1)*progress), int(b1+(b2-b1)*progress)))
    
    # Fonts
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_icon = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_verdict = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 140)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except:
        font_title = font_icon = font_verdict = font_score = font_product = font_footer = ImageFont.load_default()
    
    display = get_verdict_display(verdict)
    
    # Title
    draw.text((width//2, 60), "HonestWorld", fill='white', anchor="mt", font=font_title)
    
    # Icon (text symbol, not emoji)
    draw.text((width//2, 180), display['icon'], fill='white', anchor="mt", font=font_icon)
    
    # Verdict text
    draw.text((width//2, 340), display['text'], fill='white', anchor="mt", font=font_verdict)
    
    # Score
    draw.text((width//2, 440), f"{score}/100", fill='white', anchor="mt", font=font_score)
    
    # Product name
    pname = product_name[:38] + "..." if len(product_name) > 38 else product_name
    draw.text((width//2, 650), pname, fill='white', anchor="mt", font=font_product)
    
    # Brand
    if brand:
        bname = f"by {brand[:32]}"
        draw.text((width//2, 710), bname, fill='white', anchor="mt", font=font_product)
    
    # Footer
    draw.text((width//2, height - 55), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    
    return img

def create_story_image(product_name, brand, score, verdict, main_issue=""):
    width, height = 1080, 1920
    colors = {
        'EXCEPTIONAL': {'bg': '#06b6d4', 'bg2': '#0891b2'},
        'BUY': {'bg': '#22c55e', 'bg2': '#16a34a'},
        'CAUTION': {'bg': '#f59e0b', 'bg2': '#d97706'},
        'AVOID': {'bg': '#ef4444', 'bg2': '#dc2626'},
        'UNCLEAR': {'bg': '#6b7280', 'bg2': '#4b5563'}
    }
    c = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c['bg'])
    draw = ImageDraw.Draw(img)
    
    # Gradient
    for i in range(height//2, height):
        progress = (i - height//2) / (height//2)
        r1, g1, b1 = int(c['bg'][1:3], 16), int(c['bg'][3:5], 16), int(c['bg'][5:7], 16)
        r2, g2, b2 = int(c['bg2'][1:3], 16), int(c['bg2'][3:5], 16), int(c['bg2'][5:7], 16)
        draw.line([(0, i), (width, i)], fill=(int(r1+(r2-r1)*progress), int(g1+(g2-g1)*progress), int(b1+(b2-b1)*progress)))
    
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_icon = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
        font_verdict = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 44)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except:
        font_title = font_icon = font_verdict = font_score = font_product = font_footer = ImageFont.load_default()
    
    display = get_verdict_display(verdict)
    
    draw.text((width//2, 250), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width//2, 450), display['icon'], fill='white', anchor="mt", font=font_icon)
    draw.text((width//2, 720), display['text'], fill='white', anchor="mt", font=font_verdict)
    draw.text((width//2, 880), f"{score}/100", fill='white', anchor="mt", font=font_score)
    
    pname = product_name[:34] + "..." if len(product_name) > 34 else product_name
    draw.text((width//2, 1200), pname, fill='white', anchor="mt", font=font_product)
    if brand:
        draw.text((width//2, 1270), f"by {brand[:30]}", fill='white', anchor="mt", font=font_product)
    
    draw.text((width//2, height - 140), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    
    return img

def image_to_bytes(img, format='PNG'):
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()

# CONTEXT-AWARE HEALTH ALERTS - Smart logic
def check_health_alerts(ingredients, user_allergies, user_profiles, product_type, product_subtype=None):
    """
    SMART health alerts - context-aware based on product category
    Example: Heart health warnings ONLY for food, Skin irritation warnings for cosmetics
    """
    alerts = []
    if not ingredients: return alerts
    ing_text = ' '.join(ingredients).lower() if isinstance(ingredients, list) else ingredients.lower()
    
    # Check allergens with context
    for allergy_key in user_allergies:
        if allergy_key in ALLERGENS:
            allergen = ALLERGENS[allergy_key]
            # Check if allergen is relevant for this product type
            if product_type not in allergen.get('contexts', ['food', 'cosmetics', 'supplement']):
                continue
            for trigger in allergen['triggers']:
                if trigger in ing_text:
                    alerts.append({
                        'type': 'allergy',
                        'name': allergen['name'],
                        'icon': allergen['icon'],
                        'trigger': trigger,
                        'severity': 'high',
                        'message': f"Contains {trigger} - potential allergen"
                    })
                    break
    
    # Check health profiles WITH SMART CONTEXT
    for profile_key in user_profiles:
        if profile_key not in HEALTH_PROFILES:
            continue
        profile = HEALTH_PROFILES[profile_key]
        
        # Get concerns for THIS product type
        concerns_key = f"{product_type}_concerns"
        concerns = profile.get(concerns_key, [])
        
        # If no specific concerns for this product type, skip
        if not concerns:
            continue
        
        for concern in concerns:
            if concern in ing_text:
                # Get appropriate message template
                template = profile.get('alert_template', {}).get(product_type, profile.get('alert_template', {}).get('default', f"Contains {concern}"))
                
                alerts.append({
                    'type': 'profile',
                    'name': profile['name'],
                    'icon': profile['icon'],
                    'trigger': concern,
                    'severity': 'medium',
                    'message': template
                })
                break
    
    return alerts

def get_science_citation(ingredient):
    """Get scientific source for ingredient warning"""
    ing_lower = ingredient.lower()
    for key, data in INGREDIENT_SCIENCE.items():
        if key in ing_lower:
            return data
    return None
# ADVANCED AI ANALYSIS - Claims vs Reality, Dynamic Scoring, Scientific Sources
ANALYSIS_PROMPT = """You are HonestWorld's advanced AI analyzer. Analyze this product using our 20 Integrity Laws with SMART context-aware logic.

## STEP 1: CLASSIFY THE PRODUCT
First, determine:
- product_type: food / cosmetics / supplement / electronics / household / services
- subtype: (for cosmetics: cleanser, serum, moisturizer, shampoo, sunscreen, etc.)

## STEP 2: CROSS-REFERENCE FRONT vs BACK (Claims vs Reality)
Analyze BOTH the front marketing claims AND the back ingredient list:
- If front says "NATURAL" but back has synthetics → "Natural Fallacy" violation
- If front highlights ingredient X but X is position 6+ on back → "Fairy Dusting" violation  
- If front says "Clinically Proven" but no study cited → "Clinical Ghost" violation
- If front says "Dermatologist Recommended" but no disclaimer → Flag it

## STEP 3: APPLY DYNAMIC SCORING (based on product category)
Base score: 85
Penalties vary by context:
- Water as #1 in "Premium Serum": -25 pts (Water-Down Deception - HIGH)
- Water as #1 in "Body Mist": -5 pts (Expected for category)
- Fragrance in baby product: -12 pts (Higher penalty)
- Fragrance in adult perfumed lotion: -5 pts (Expected)

## STEP 4: AWARD POSITIVE BONUSES
+5: Certified Organic (USDA, EU organic)
+5: Third-party tested (NSF, USP, ConsumerLab)
+4: Fragrance-free (for cosmetics)
+4: EWG Verified
+3: Recyclable/sustainable packaging
+3: Cruelty-free certified
+2: Short clean ingredient list (<10 ingredients)

## THE 20 INTEGRITY LAWS:
1. Water-Down Deception (-15 base): Premium claim but water/#1 is cheap filler
2. Fairy Dusting (-12): Hero ingredient below position #5
3. Split Sugar Trick (-18): 3+ sugar names hiding total
4. Low-Fat Trap (-10): Low fat but high sugar
5. Natural Fallacy (-10): "Natural" with synthetics
6. Made-With Loophole (-8): "Made with X" but X is minimal
7. Serving Size Trick (-10): Unrealistic tiny servings
8. Slack Fill (-8): Package mostly empty
9. Spec Inflation (-15): "Up to X" unrealistic claims
10. Compatibility Lie (-12): "Universal" with exceptions
11. Military Grade Myth (-10): No real MIL-STD cert
12. Battery Fiction (-12): Unrealistic battery claims
13. Clinical Ghost (-12): "Clinically proven" no citation
14. Concentration Trick (-10): Active too diluted
15. Free Trap (-15): "Free" needs payment
16. Unlimited Lie (-18): "Unlimited" with caps
17. Lifetime Illusion (-10): "Lifetime" with exclusions
18. Photo vs Reality (-12): Photo much better than actual
19. Fake Certification (-15): Claims fake cert
20. Name Trick (-10): Name implies absent ingredient

## COSMETIC INGREDIENT FLAGS (with scientific basis):
- Parabens: -8 pts - "Potential hormone disruptor (EU SCCS)"
- Fragrance/Parfum: -8 pts - "Undisclosed chemicals (AAD)"
- Sulfates (SLS/SLES): -6 pts - "Can irritate sensitive skin"
- Phthalates: -12 pts - "Potential hormone disruptor (CDC)"
- Formaldehyde releasers: -15 pts - "Can release formaldehyde (IARC)"

## CONTEXT:
Location: {location}
{barcode_context}

## OUTPUT FORMAT (Valid JSON):
{{
    "product_name": "Exact name from image",
    "brand": "Brand name",
    "product_type": "food/cosmetics/supplement/electronics/household",
    "subtype": "specific type like cleanser, serum, vitamin, etc",
    "readable": true,
    "score": <0-100>,
    "front_claims": ["list of marketing claims from front"],
    "violations": [
        {{
            "law": <1-20 or null>,
            "name": "Violation name",
            "points": <negative>,
            "evidence": "SPECIFIC evidence - quote exact text/ingredient",
            "science": "Brief scientific basis if applicable"
        }}
    ],
    "bonuses": [
        {{
            "name": "Bonus name",
            "points": <positive>,
            "evidence": "What earned this bonus"
        }}
    ],
    "ingredients": ["full list if visible"],
    "ingredients_to_watch": [
        {{
            "name": "ingredient",
            "reason": "why flagged",
            "severity": "high/medium/low"
        }}
    ],
    "good_ingredients": ["beneficial ingredients"],
    "main_issue": "Primary concern or 'Clean formula'",
    "positive": "Main positive aspect",
    "tip": "Helpful consumer advice",
    "confidence": "high/medium/low"
}}

## CRITICAL RULES:
1. EVERY deduction must have specific evidence
2. Apply DYNAMIC weights based on product category
3. Award bonuses for positive attributes
4. Cross-reference front claims with back ingredients
5. Provide scientific basis for ingredient flags when possible"""

def analyze_product(images, location, progress_callback, barcode_info=None):
    """Advanced AI analysis with Claims vs Reality engine and dynamic scoring"""
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "brand": "", "score": 0, "verdict": "UNCLEAR", 
                "readable": False, "violations": [], "main_issue": "Please add GEMINI_API_KEY"}
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    
    progress_callback(0.3, "Analyzing front & back...")
    
    # Build barcode context
    barcode_context = ""
    if barcode_info and barcode_info.get('found'):
        barcode_context = f"""
BARCODE DATABASE INFO:
- Product: {barcode_info.get('name', '')}
- Brand: {barcode_info.get('brand', '')}
- Category: {barcode_info.get('categories', '')}
- Ingredients from database: {barcode_info.get('ingredients', '')[:800]}
- Source: {barcode_info.get('source', '')}
Use this as reference. If image shows different product, trust the IMAGE."""
    
    progress_callback(0.5, "Cross-referencing claims...")
    
    prompt = ANALYSIS_PROMPT.format(
        location=f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}",
        barcode_context=barcode_context
    )
    
    progress_callback(0.7, "Calculating dynamic score...")
    
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
            return {"product_name": "Parse Error", "brand": "", "score": 0, "verdict": "UNCLEAR",
                    "readable": False, "violations": [], "main_issue": "Could not parse response"}
        
        # Ensure valid score
        score = result.get('score', 75)
        if isinstance(score, str):
            try: score = int(re.sub(r'[^\d]', '', score))
            except: score = 75
        score = max(0, min(100, score))
        
        # Calculate from violations and bonuses if provided
        violations = result.get('violations', [])
        bonuses = result.get('bonuses', [])
        
        # If AI didn't calculate properly, do it ourselves
        if not violations and score < 85:
            # Generate explanation
            missing = 85 - score
            violations = [{"law": None, "name": "Formula concerns", "points": -missing, 
                          "evidence": result.get('main_issue', 'Minor concerns detected')}]
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['violations'] = violations
        result['bonuses'] = bonuses
        
        # Apply learning consistency
        if result.get('product_name'):
            learned = get_learned_product(result['product_name'])
            if learned and learned.get('scan_count', 0) >= 2:
                weight = min(learned['scan_count'] * 0.15, 0.5)
                result['score'] = int(score * (1 - weight) + learned['score'] * weight)
                result['verdict'] = get_verdict(result['score'])
        
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        
        progress_callback(1.0, "Analysis complete!")
        return result
        
    except Exception as e:
        return {"product_name": "Analysis Error", "brand": "", "score": 0, "verdict": "UNCLEAR",
                "readable": False, "violations": [], "main_issue": f"Error: {str(e)[:100]}"}

# CSS STYLES - Enhanced with science citations
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
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

.alert-danger { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 2px solid #ef4444; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.alert-warning { background: linear-gradient(135deg, #fffbeb, #fef3c7); border: 2px solid #f59e0b; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.alert-info { background: linear-gradient(135deg, #eff6ff, #dbeafe); border: 2px solid #3b82f6; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }

.issue-box { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.75rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.positive-box { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.75rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.bonus-box { background: linear-gradient(135deg, #dbeafe, #bfdbfe); border-left: 4px solid #3b82f6; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.3rem 0; }
.tip-box { background: linear-gradient(135deg, #eff6ff, #dbeafe); border: 1px solid #bfdbfe; border-radius: 12px; padding: 0.75rem; margin: 0.5rem 0; }

.violation-box { background: linear-gradient(135deg, #fef2f2, #fecaca); border-left: 4px solid #ef4444; padding: 0.75rem; border-radius: 0 10px 10px 0; margin: 0.4rem 0; }
.violation-title { font-weight: 700; color: #dc2626; }
.violation-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.25rem; }
.violation-science { font-size: 0.75rem; color: #6b7280; font-style: italic; margin-top: 0.2rem; background: #fef2f2; padding: 0.3rem 0.5rem; border-radius: 4px; }

.ing-summary { display: flex; gap: 0.5rem; margin: 0.5rem 0; flex-wrap: wrap; }
.ing-badge { padding: 0.35rem 0.7rem; border-radius: 20px; font-weight: 600; font-size: 0.8rem; }
.ing-watch { background: #fed7aa; color: #c2410c; }
.ing-good { background: #bbf7d0; color: #16a34a; }

.science-btn { background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 4px; padding: 0.15rem 0.4rem; font-size: 0.7rem; color: #64748b; cursor: pointer; margin-left: 0.3rem; }

.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }
.alt-score { display: inline-block; background: #22c55e; color: white; padding: 0.2rem 0.5rem; border-radius: 8px; font-weight: 700; font-size: 0.8rem; }

.history-score { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.85rem; }

.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn { display: flex; flex-direction: column; align-items: center; padding: 0.75rem; border-radius: 12px; color: white; text-decoration: none; font-weight: 600; font-size: 0.75rem; }
.share-btn span { font-size: 1.3rem; margin-bottom: 0.2rem; }

.progress-box { background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.5rem; text-align: center; }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 1rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }

.loc-badge { background: #dbeafe; color: #2563eb; padding: 0.3rem 0.7rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; display: inline-block; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.7rem; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
.category-badge { background: #e0e7ff; color: #4f46e5; padding: 0.2rem 0.5rem; border-radius: 8px; font-size: 0.7rem; font-weight: 600; }

.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }

.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }

.law-card { background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.75rem; margin: 0.3rem 0; }
.law-title { font-weight: 700; color: #1e293b; }
.law-points { color: #ef4444; font-weight: 700; }
.law-desc { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stCameraInput"] video { max-height: 200px !important; border-radius: 16px; }
</style>
"""
# MAIN APPLICATION - All features preserved + Advanced Logic
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    # Session state
    if 'result' not in st.session_state: st.session_state.result = None
    if 'scan_id' not in st.session_state: st.session_state.scan_id = None
    if 'admin' not in st.session_state: st.session_state.admin = False
    if 'barcode_info' not in st.session_state: st.session_state.barcode_info = None
    if 'barcode_num' not in st.session_state: st.session_state.barcode_num = None
    if 'show_result' not in st.session_state: st.session_state.show_result = False
    
    # Location - auto-detect then save
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        if saved and saved.get('city') not in ['Unknown', '', None, 'Your City']:
            st.session_state.loc = saved
        else:
            detected = get_location()
            st.session_state.loc = detected
            if detected.get('city') not in ['Unknown', 'Your City']:
                save_location(detected['city'], detected['country'])
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🌍 HonestWorld")
        loc_city = st.session_state.loc.get('city', '')
        if loc_city and loc_city not in ['Unknown', 'Your City']:
            st.markdown(f"<span class='loc-badge'>📍 {loc_city}</span>", unsafe_allow_html=True)
    with col2:
        stats = get_stats()
        if stats['streak'] > 0:
            st.markdown(f"<span class='streak-badge'>🔥 {stats['streak']}</span>", unsafe_allow_html=True)
    
    # Stats
    st.markdown(f"""<div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>{stats['scans']}</div><div class='stat-lbl'>Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['avoided']}</div><div class='stat-lbl'>Avoided</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['best_streak']}</div><div class='stat-lbl'>Best Streak</div></div>
    </div>""", unsafe_allow_html=True)
    
    # Tabs
    tab_scan, tab_history, tab_profile, tab_laws = st.tabs(["📷 Scan", "📋 History", "👤 Profile", "⚖️ Laws"])
    
    with tab_scan:
        if st.session_state.result and st.session_state.show_result:
            display_result(st.session_state.result, user_id)
        else:
            input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
            images = []
            
            if input_method == "📷 Camera":
                st.caption("📸 Point at product (front AND back for best results)")
                cam_img = st.camera_input("Photo", label_visibility="collapsed")
                if cam_img:
                    images = [cam_img]
                    st.success("✅ Photo captured!")
                    if st.checkbox("+ Add back of package"):
                        cam_img2 = st.camera_input("Back photo", label_visibility="collapsed", key="cam2")
                        if cam_img2: images.append(cam_img2)
            
            elif input_method == "📁 Upload":
                uploaded = st.file_uploader("Upload images", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
                if uploaded:
                    images = uploaded[:3]
                    st.success(f"✅ {len(images)} image(s)")
            
            else:  # Barcode
                st.markdown("**📊 Barcode Scanner**")
                st.caption("Works like Yuka - searches global product databases")
                barcode_img = st.camera_input("Scan barcode", label_visibility="collapsed", key="barcode_cam")
                if barcode_img:
                    with st.spinner("Reading barcode..."):
                        barcode_num = try_decode_barcode_pyzbar(barcode_img)
                        if not barcode_num:
                            barcode_num = ai_read_barcode(barcode_img)
                        
                        if barcode_num:
                            st.info(f"📊 Barcode: **{barcode_num}**")
                            st.session_state.barcode_num = barcode_num
                            
                            progress_placeholder = st.empty()
                            def update_progress(pct, msg):
                                progress_placeholder.markdown(f"<div class='progress-box'><div style='font-weight: 600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div></div>", unsafe_allow_html=True)
                            
                            barcode_info = smart_barcode_lookup(barcode_num, update_progress)
                            progress_placeholder.empty()
                            
                            if barcode_info.get('found'):
                                st.success(f"✅ **{barcode_info.get('name', '')}**")
                                if barcode_info.get('brand'):
                                    st.caption(f"by {barcode_info.get('brand')} • Source: {barcode_info.get('source', '')}")
                                with st.expander("📋 Database info", expanded=False):
                                    if barcode_info.get('ingredients'):
                                        st.markdown(f"**Ingredients:** {barcode_info.get('ingredients', '')[:400]}...")
                                    if barcode_info.get('categories'):
                                        st.markdown(f"**Category:** {barcode_info.get('categories', '')[:100]}")
                                st.session_state.barcode_info = barcode_info
                                images = [barcode_img]
                            else:
                                st.warning("Product not in databases. Try photo scan for analysis.")
                        else:
                            st.error("Could not read barcode. Try clearer image or photo scan.")
            
            # Analyze button
            if images:
                if st.button("🔍 ANALYZE PRODUCT", use_container_width=True, type="primary"):
                    progress_placeholder = st.empty()
                    def update_progress(pct, msg):
                        icons = ['🔍', '🧪', '⚖️', '✨']
                        icon = icons[min(int(pct * 4), 3)]
                        progress_placeholder.markdown(f"<div class='progress-box'><div style='font-size: 2rem;'>{icon}</div><div style='font-weight: 600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div></div>", unsafe_allow_html=True)
                    
                    bi = st.session_state.get('barcode_info')
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
                        
                        st.session_state.result = result
                        st.session_state.scan_id = scan_id
                        st.session_state.show_result = True
                        st.session_state.barcode_info = None
                        st.session_state.barcode_num = None
                        st.rerun()
                    else:
                        st.error("❌ Could not analyze. Try clearer photo showing product name and ingredients.")
    
    with tab_history:
        history = get_history(user_id, 30)
        if not history:
            st.info("📋 No scans yet!")
        else:
            for item in history:
                score = item['score']
                color = '#06b6d4' if score >= 90 else '#22c55e' if score >= 75 else '#f59e0b' if score >= 50 else '#ef4444'
                fav = "⭐ " if item['favorite'] else ""
                col1, col2, col3 = st.columns([0.7, 3.3, 0.5])
                with col1:
                    st.markdown(f"<div class='history-score' style='background: {color};'>{score}</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"**{fav}{item['product'][:30]}**")
                    st.caption(f"{item['brand'][:18] if item['brand'] else ''} • {item['ts'][:10]}")
                with col3:
                    if st.button("⭐" if not item['favorite'] else "★", key=f"fav_{item['db_id']}"):
                        toggle_favorite(item['db_id'], item['favorite'])
                        st.rerun()
    
    with tab_profile:
        st.markdown("### ⚙️ Settings")
        
        st.markdown("**📍 Location**")
        col1, col2 = st.columns(2)
        with col1:
            city = st.text_input("City", value=st.session_state.loc.get('city', ''))
        with col2:
            country = st.text_input("Country", value=st.session_state.loc.get('country', ''))
        if st.button("Update Location"):
            code = save_location(city, country)
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
            st.success("✅ Updated!")
            st.rerun()
        
        st.markdown("---")
        st.markdown("**🏥 Health Profiles**")
        st.caption("Smart alerts based on product type")
        current_profiles = get_profiles()
        new_profiles = st.multiselect("", list(HEALTH_PROFILES.keys()), default=current_profiles, 
                                       format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}", label_visibility="collapsed")
        if new_profiles != current_profiles:
            save_profiles(new_profiles)
            st.success("✅ Updated!")
        
        st.markdown("---")
        st.markdown("**🚨 Allergen Alerts**")
        current_allergies = get_allergies()
        new_allergies = st.multiselect("", list(ALLERGENS.keys()), default=current_allergies,
                                        format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}", 
                                        label_visibility="collapsed", key="allergies")
        if new_allergies != current_allergies:
            save_allergies(new_allergies)
            st.success("✅ Updated!")
        
        st.markdown("---")
        st.markdown("**🔐 Admin**")
        admin_pw = st.text_input("Password", type="password", label_visibility="collapsed")
        if admin_pw and hashlib.sha256(admin_pw.encode()).hexdigest() == ADMIN_HASH:
            st.session_state.admin = True
        if st.session_state.admin:
            conn = sqlite3.connect(LOCAL_DB)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM scans')
            scans = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM learned_products')
            learned = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM barcode_cache')
            barcodes = c.fetchone()[0]
            conn.close()
            st.markdown(f"📊 **{scans}** scans | **{learned}** learned | **{barcodes}** barcodes cached")
            st.markdown(f"☁️ Cloud: {'🟢' if supa_ok() else '🔴'}")
    
    with tab_laws:
        st.markdown("### ⚖️ The 20 Integrity Laws")
        st.caption("Transparent, evidence-based scoring with dynamic weights")
        
        categories = {
            "🧪 Ingredients": [1, 2, 3, 4, 5, 6],
            "📦 Packaging": [7, 8, 18],
            "📱 Electronics": [9, 10, 11, 12],
            "💄 Beauty": [13, 14],
            "📋 Services": [15, 16, 17],
            "🏷️ Claims": [19, 20]
        }
        for cat, nums in categories.items():
            with st.expander(cat):
                for n in nums:
                    if n in INTEGRITY_LAWS:
                        law = INTEGRITY_LAWS[n]
                        st.markdown(f"""<div class='law-card'>
                            <span class='law-title'>Law {n}: {law['name']}</span>
                            <span class='law-points'> ({law['base_points']} pts)</span>
                            <div class='law-desc'>{law['description']}</div>
                            <div style='font-size: 0.8rem; color: #059669; margin-top: 0.3rem;'>💡 {law['tip']}</div>
                        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown(f"<center style='color: #94a3b8; font-size: 0.75rem;'>🌍 HonestWorld v{VERSION} • Advanced AI • Context-Aware</center>", unsafe_allow_html=True)


def display_result(result, user_id):
    """Display result with scientific sources and bonuses"""
    score = result.get('score', 0)
    verdict = result.get('verdict', 'UNCLEAR')
    product_type = result.get('product_type', 'unknown')
    subtype = result.get('subtype', '')
    display = get_verdict_display(verdict)
    
    # Verdict card
    st.markdown(f"""<div class='verdict-card verdict-{verdict.lower()}'>
        <div class='verdict-icon'>{display['icon']}</div>
        <div class='verdict-text'>{display['text']}</div>
        <div class='verdict-score'>{score}<span style='font-size: 1.5rem;'>/100</span></div>
    </div>""", unsafe_allow_html=True)
    
    # Product info
    st.markdown(f"### {result.get('product_name', 'Unknown')}")
    if result.get('brand'):
        st.markdown(f"*by {result.get('brand')}*")
    if product_type != 'unknown':
        type_display = f"{product_type.title()}" + (f" • {subtype}" if subtype else "")
        st.markdown(f"<span class='category-badge'>{type_display}</span>", unsafe_allow_html=True)
    
    # Health alerts - CONTEXT AWARE
    alerts = check_health_alerts(result.get('ingredients', []), get_allergies(), get_profiles(), product_type, subtype)
    for alert in alerts:
        css = 'alert-danger' if alert['severity'] == 'high' else 'alert-warning'
        st.markdown(f"""<div class='{css}'>
            <strong>{alert['icon']} {alert['name']} {'Alert' if alert['severity'] == 'high' else 'Note'}</strong><br>
            <span style='font-size: 0.9rem;'>{alert.get('message', f"Contains: {alert['trigger']}")}</span>
        </div>""", unsafe_allow_html=True)
    
    # Violations with science
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Deductions ({len(violations)})", expanded=True):
            for v in violations:
                law_text = f"Law {v.get('law')}: " if v.get('law') else ""
                science_html = ""
                if v.get('science'):
                    science_html = f"<div class='violation-science'>📚 {v.get('science')}</div>"
                st.markdown(f"""<div class='violation-box'>
                    <div class='violation-title'>{law_text}{v.get('name', 'Deduction')} ({v.get('points', 0)} pts)</div>
                    <div class='violation-evidence'>{v.get('evidence', '')}</div>
                    {science_html}
                </div>""", unsafe_allow_html=True)
    
    # Bonuses
    bonuses = result.get('bonuses', [])
    if bonuses:
        with st.expander(f"✨ Bonuses ({len(bonuses)})", expanded=False):
            for b in bonuses:
                st.markdown(f"""<div class='bonus-box'>
                    <strong>+{b.get('points', 0)} pts: {b.get('name', '')}</strong><br>
                    <span style='font-size: 0.85rem; color: #3b82f6;'>{b.get('evidence', '')}</span>
                </div>""", unsafe_allow_html=True)
    
    # Main issue / positive
    main_issue = result.get('main_issue', '')
    if main_issue and main_issue.lower() not in ['clean formula', 'none']:
        st.markdown(f"<div class='issue-box'>⚠️ <strong>Main Concern:</strong> {main_issue}</div>", unsafe_allow_html=True)
    if result.get('positive'):
        st.markdown(f"<div class='positive-box'>✅ <strong>Positive:</strong> {result.get('positive')}</div>", unsafe_allow_html=True)
    
    # Ingredients
    with st.expander("🧪 Ingredients", expanded=False):
        watch = result.get('ingredients_to_watch', [])
        if watch:
            st.markdown("**⚠️ Watch:**")
            for w in watch[:6]:
                if isinstance(w, dict):
                    science = get_science_citation(w.get('name', ''))
                    science_note = f" • *{science['sources'][0]}*" if science else ""
                    st.markdown(f"<span class='ing-badge ing-watch'>{w.get('name', '')}</span> {w.get('reason', '')}{science_note}", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='ing-badge ing-watch'>{w}</span>", unsafe_allow_html=True)
        good = result.get('good_ingredients', [])
        if good:
            st.markdown("**✅ Good:**")
            badges = " ".join([f"<span class='ing-badge ing-good'>{g}</span>" for g in good[:8]])
            st.markdown(f"<div class='ing-summary'>{badges}</div>", unsafe_allow_html=True)
        if result.get('ingredients'):
            st.markdown("**All:** " + ", ".join(result.get('ingredients', [])[:25]))
    
    # Tip
    if result.get('tip'):
        st.markdown(f"<div class='tip-box'>💡 <strong>Tip:</strong> {result.get('tip')}</div>", unsafe_allow_html=True)
    
    # Alternative
    if verdict in ['CAUTION', 'AVOID']:
        alt = get_alternative(result.get('product_name', ''), product_type, subtype)
        alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
        retailers = ', '.join(st.session_state.loc.get('retailers', ['Local stores'])[:3])
        st.markdown(f"""<div class='alt-card'>
            <strong>💚 Better Alternative:</strong><br>
            <span style='font-size: 1.1rem; font-weight: 600;'>{alt['name']}</span> {alt_score_html}<br>
            <span style='color: #16a34a;'>{alt['why']}</span><br>
            <span style='font-size: 0.85rem; color: #64748b;'>Available at: {retailers}</span>
        </div>""", unsafe_allow_html=True)
    
    # Share
    st.markdown("### 📤 Share")
    share_img = create_share_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict)
    story_img = create_story_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post", data=image_to_bytes(share_img), file_name=f"hw_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story", data=image_to_bytes(story_img), file_name=f"hw_story_{score}.png", mime="image/png", use_container_width=True)
    
    share_text = f"Scanned {result.get('product_name', 'product')} - {score}/100 ({verdict}) #HonestWorld"
    enc = urllib.parse.quote(share_text)
    st.markdown(f"""<div class='share-grid'>
        <a href='https://twitter.com/intent/tweet?text={enc}' target='_blank' class='share-btn' style='background:#1DA1F2;'><span>𝕏</span>Twitter</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={enc}' target='_blank' class='share-btn' style='background:#4267B2;'><span>f</span>Facebook</a>
        <a href='https://wa.me/?text={enc}' target='_blank' class='share-btn' style='background:#25D366;'><span>💬</span>WhatsApp</a>
        <a href='https://t.me/share/url?text={enc}' target='_blank' class='share-btn' style='background:#0088cc;'><span>➤</span>Telegram</a>
        <a href='https://instagram.com' target='_blank' class='share-btn' style='background:linear-gradient(45deg,#f09433,#dc2743);'><span>📷</span>Instagram</a>
        <a href='https://tiktok.com' target='_blank' class='share-btn' style='background:#000;'><span>♪</span>TikTok</a>
    </div>""", unsafe_allow_html=True)
    
    st.markdown("")
    if st.button("🔄 Scan Another Product", use_container_width=True):
        st.session_state.result = None
        st.session_state.scan_id = None
        st.session_state.show_result = False
        st.rerun()


if __name__ == "__main__":
    main()
