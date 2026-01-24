"""
HONESTWORLD v33.0 - FINAL POLISH EDITION

FIXES:
1. Score displays correctly in share images
2. NO emojis in generated images (text symbols only)
3. World map works properly
4. Clean share images (removed AI-powered text)
5. Dynamic badge system (Health for Food, Safety for Cosmetics, None for Electronics)
6. Split ingredient summation logic
7. Citation credibility hierarchy (WHO/FDA/EFSA priority)
8. Stale data re-check (6 months)
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
import random
import math

st.set_page_config(page_title="HonestWorld", page_icon="🌍", layout="centered", initial_sidebar_state="collapsed")

VERSION = "33.0"
LOCAL_DB = Path.home() / "honestworld_v33.db"
STALE_THRESHOLD_DAYS = 180

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════════
# GEOHASH UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'

def encode_geohash(lat, lon, precision=6):
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    geohash, bits, bit, ch, even = [], [16, 8, 4, 2, 1], 0, 0, True
    while len(geohash) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon > mid: ch |= bits[bit]; lon_range[0] = mid
            else: lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid: ch |= bits[bit]; lat_range[0] = mid
            else: lat_range[1] = mid
        even = not even
        if bit < 4: bit += 1
        else: geohash.append(BASE32[ch]); bit, ch = 0, 0
    return ''.join(geohash)

def add_privacy_jitter(lat, lon):
    earth_radius = 6371000
    jitter_distance = random.uniform(50, 100)
    angle = random.uniform(0, 2 * math.pi)
    lat_offset = (jitter_distance * math.cos(angle)) / earth_radius * (180 / math.pi)
    lon_offset = (jitter_distance * math.sin(angle)) / (earth_radius * math.cos(math.radians(lat))) * (180 / math.pi)
    return lat + lat_offset, lon + lon_offset

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATEGORIES WITH BADGE TYPES
# ═══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATEGORIES = {
    "CATEGORY_FOOD": {
        "name": "Food & Beverage", "icon": "🍎",
        "badge_type": "health",
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "protein_bar", "meal", "spread", "butter", "margarine", "candy", "dessert", "soup", "sauce", "jerky", "juice"],
        "water_expected": ["beverage", "soup", "sauce", "drink", "juice", "tea", "coffee"],
    },
    "CATEGORY_SUPPLEMENT": {
        "name": "Supplements", "icon": "💊",
        "badge_type": "health",
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega", "multivitamin"],
    },
    "CATEGORY_COSMETIC": {
        "name": "Cosmetics & Personal Care", "icon": "🧴",
        "badge_type": "safety",
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "toner", "mask", "deodorant", "soap", "bodywash"],
        "water_expected": ["shampoo", "conditioner", "toner", "bodywash", "soap", "cleanser", "lotion"],
    },
    "CATEGORY_ELECTRONICS": {
        "name": "Electronics", "icon": "📱",
        "badge_type": "none",
        "subtypes": ["phone", "laptop", "tablet", "accessory", "cable", "charger", "audio", "wearable"],
    },
    "CATEGORY_HOUSEHOLD": {
        "name": "Household", "icon": "🧹",
        "badge_type": "safety",
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener", "laundry"],
    },
    "CATEGORY_BOOK": {
        "name": "Books", "icon": "📚",
        "badge_type": "none",
        "subtypes": ["fiction", "non-fiction", "textbook", "children", "reference"],
    }
}

# Sugar variants for summation detection
SUGAR_VARIANTS = ["sugar", "glucose", "fructose", "dextrose", "maltose", "sucrose", "corn syrup", "high fructose corn syrup", "hfcs", "glucose syrup", "invert sugar", "cane sugar", "brown sugar", "honey", "agave", "maple syrup", "molasses", "maltodextrin", "dextrin"]

# Oil variants for summation detection  
OIL_VARIANTS = ["palm oil", "canola oil", "soybean oil", "sunflower oil", "vegetable oil", "rapeseed oil", "corn oil", "cottonseed oil", "palm kernel oil", "hydrogenated oil", "partially hydrogenated"]

# Cheap fillers
CHEAP_FILLERS = ["water", "aqua", "maltodextrin", "dextrin", "modified starch", "starch", "cellulose", "microcrystalline cellulose", "natural flavor", "artificial flavor"]

# ═══════════════════════════════════════════════════════════════════════════════
# THE 21 INTEGRITY LAWS
# ═══════════════════════════════════════════════════════════════════════════════
INTEGRITY_LAWS = {
    1: {"name": "Water-Down Deception", "base_points": -15, "description": "Premium product but #1 ingredient is water/filler", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD"]},
    2: {"name": "Fairy Dusting", "base_points": -12, "description": "Hero ingredient below position #5", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    3: {"name": "Split Ingredient Trick", "base_points": -18, "description": "Same ingredient split into 3+ names to hide total amount", "applies_to": ["CATEGORY_FOOD"]},
    4: {"name": "Low-Fat Trap", "base_points": -10, "description": "Low fat but high sugar compensation", "applies_to": ["CATEGORY_FOOD"]},
    5: {"name": "Natural Fallacy", "base_points": -12, "description": "Claims natural/bio/organic without certification", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_HOUSEHOLD"]},
    6: {"name": "Made-With Loophole", "base_points": -8, "description": "'Made with real X' but X is minimal", "applies_to": ["CATEGORY_FOOD"]},
    7: {"name": "Serving Size Trick", "base_points": -10, "description": "Unrealistically small serving size", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    8: {"name": "Slack Fill", "base_points": -8, "description": "Package mostly empty space", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    9: {"name": "Spec Inflation", "base_points": -15, "description": "'Up to X' unrealistic claims", "applies_to": ["CATEGORY_ELECTRONICS"]},
    10: {"name": "Compatibility Claim", "base_points": -12, "description": "'Universal' with hidden exceptions", "applies_to": ["CATEGORY_ELECTRONICS"]},
    11: {"name": "Military Grade Claim", "base_points": -10, "description": "Claims military grade without MIL-STD", "applies_to": ["CATEGORY_ELECTRONICS"]},
    12: {"name": "Battery Life Claim", "base_points": -12, "description": "Unrealistic battery claims", "applies_to": ["CATEGORY_ELECTRONICS"]},
    13: {"name": "Unverified Clinical Claim", "base_points": -12, "description": "'Clinically proven' without study citation", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    14: {"name": "Concentration Concern", "base_points": -10, "description": "Active ingredient too diluted", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    15: {"name": "Free Trial Concern", "base_points": -15, "description": "'Free' requires hidden purchase", "applies_to": ["CATEGORY_ELECTRONICS"]},
    16: {"name": "Unlimited Claim", "base_points": -18, "description": "'Unlimited' with hidden caps", "applies_to": ["CATEGORY_ELECTRONICS"]},
    17: {"name": "Lifetime Warranty Claim", "base_points": -10, "description": "'Lifetime warranty' with exclusions", "applies_to": ["CATEGORY_ELECTRONICS"]},
    18: {"name": "Photo Styling", "base_points": -12, "description": "Photo much better than reality", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    19: {"name": "Unverified Certification", "base_points": -15, "description": "Claims certification without proof", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    20: {"name": "Name Implication", "base_points": -10, "description": "Name implies ingredient barely present", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    21: {"name": "Value Discrepancy", "base_points": -20, "description": "Premium marketing with cheap filler reality", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# CITATION DATABASE WITH AUTHORITY HIERARCHY
# ═══════════════════════════════════════════════════════════════════════════════
# Priority: WHO > FDA > EFSA > EU SCCS > National agencies > Single studies
CITATIONS = {
    "paraben": {"concern": "Potential endocrine disruption", "severity": "medium", "source": "EU SCCS", "authority": "high"},
    "methylparaben": {"concern": "Potential hormone disruption", "severity": "medium", "source": "EU SCCS", "authority": "high"},
    "fragrance": {"concern": "Undisclosed mixture, potential allergen", "severity": "medium", "source": "AAD", "authority": "medium"},
    "parfum": {"concern": "Undisclosed mixture, potential allergen", "severity": "medium", "source": "EU Regulation", "authority": "high"},
    "sodium lauryl sulfate": {"concern": "May irritate sensitive skin", "severity": "low", "source": "CIR Panel", "authority": "medium"},
    "dmdm hydantoin": {"concern": "Formaldehyde-releasing preservative", "severity": "high", "source": "IARC", "authority": "high"},
    "triclosan": {"concern": "Endocrine disruption concern", "severity": "high", "source": "FDA Ban 2016", "authority": "high"},
    "oxybenzone": {"concern": "Hormone disruption, coral damage", "severity": "medium", "source": "Hawaii Ban", "authority": "medium"},
    "trans fat": {"concern": "Cardiovascular risk", "severity": "high", "source": "WHO/FDA", "authority": "high"},
    "hydrogenated oil": {"concern": "May contain trans fats", "severity": "high", "source": "FDA/AHA", "authority": "high"},
    "high fructose corn syrup": {"concern": "Metabolic concerns when over-consumed", "severity": "medium", "source": "AJCN", "authority": "medium"},
    "palm oil": {"concern": "Environmental and saturated fat concerns", "severity": "low", "source": "WHO", "authority": "high"},
    "red 40": {"concern": "Hyperactivity in sensitive children", "severity": "low", "source": "EFSA", "authority": "high"},
    "aspartame": {"concern": "IARC Group 2B - possibly carcinogenic", "severity": "low", "source": "WHO/IARC 2023", "authority": "high"},
    "sodium nitrite": {"concern": "Forms nitrosamines when heated", "severity": "medium", "source": "IARC", "authority": "high"},
    "titanium dioxide": {"concern": "EU food ban 2022", "severity": "medium", "source": "EFSA", "authority": "high"},
}

def get_citation(ingredient_name):
    if not ingredient_name: return None
    key = ingredient_name.lower().strip()
    if key in CITATIONS: return CITATIONS[key]
    for db_key, data in CITATIONS.items():
        if db_key in key or key in db_key: return data
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH PROFILES & ALLERGENS
# ═══════════════════════════════════════════════════════════════════════════════
HEALTH_PROFILES = {
    "diabetes": {"name": "Diabetes", "icon": "🩺", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin", "sucrose"], "notification": "Contains sugar/sweeteners - monitor blood glucose"},
    "heartcondition": {"name": "Heart Health", "icon": "❤️", "applies_to": ["CATEGORY_FOOD"], "ingredient_flags": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat", "palm oil"], "notification": "Contains sodium/fats - monitor for heart health"},
    "glutenfree": {"name": "Gluten-Free", "icon": "🌾", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["wheat", "barley", "rye", "gluten", "malt", "spelt", "kamut", "triticale"], "notification": "Contains or may contain GLUTEN"},
    "vegan": {"name": "Vegan", "icon": "🌱", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["gelatin", "carmine", "honey", "milk", "whey", "casein", "egg", "lanolin", "beeswax", "collagen", "lard", "tallow"], "notification": "May contain animal-derived ingredients"},
    "sensitive": {"name": "Sensitive Skin", "icon": "🌸", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"], "ingredient_flags": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate"], "notification": "Contains potential irritants"},
    "allergyprone": {"name": "Allergy Prone", "icon": "🤧", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"], "ingredient_flags": ["peanut", "tree nut", "soy", "milk", "egg", "wheat", "shellfish", "fish", "sesame", "fragrance"], "notification": "Contains common allergens"},
}

ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "malt", "spelt"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu", "lecithin"], "applies_to": ["CATEGORY_FOOD"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise"], "applies_to": ["CATEGORY_FOOD"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn"], "applies_to": ["CATEGORY_FOOD"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOCATION-AWARE ALTERNATIVES
# ═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVES_BY_COUNTRY = {
    "AU": {
        "spread": {"name": "Nuttelex Original", "retailer": "Woolworths, Coles", "score": 88, "why": "Australian made, transparent ingredients"},
        "butter": {"name": "Naturli Organic Vegan Block", "retailer": "Woolworths, Coles", "score": 85, "why": "Certified organic"},
        "cleanser": {"name": "Cetaphil Gentle Skin Cleanser", "retailer": "Chemist Warehouse", "score": 85, "why": "Fragrance-free"},
        "moisturizer": {"name": "CeraVe Moisturising Cream", "retailer": "Chemist Warehouse", "score": 92, "why": "Ceramides, fragrance-free"},
        "vitamin": {"name": "Blackmores or Swisse", "retailer": "Chemist Warehouse", "score": 88, "why": "TGA approved"},
        "protein": {"name": "Bulk Nutrients WPI", "retailer": "bulknutrients.com.au", "score": 90, "why": "High protein %"},
        "default": {"name": "Check Chemist Warehouse", "retailer": "Local stores", "score": None, "why": "Wide range available"}
    },
    "US": {
        "spread": {"name": "Earth Balance Organic", "retailer": "Whole Foods, Target", "score": 85, "why": "USDA Organic"},
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "CVS, Target", "score": 92, "why": "Fragrance-free"},
        "vitamin": {"name": "Thorne Research", "retailer": "Amazon", "score": 94, "why": "NSF certified"},
        "default": {"name": "Check Target or Whole Foods", "retailer": "Target, Whole Foods", "score": None, "why": "Wide selection"}
    },
    "GB": {
        "spread": {"name": "Flora Plant Butter", "retailer": "Tesco, Sainsbury's", "score": 84, "why": "Plant-based"},
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "Boots", "score": 92, "why": "Fragrance-free"},
        "default": {"name": "Check Boots or Tesco", "retailer": "Boots, Tesco", "score": None, "why": "Wide range"}
    },
    "OTHER": {
        "default": {"name": "Check iHerb.com", "retailer": "iHerb", "score": None, "why": "International shipping"}
    }
}

def get_alternative(product_name, product_type, product_category, country_code):
    country_alts = ALTERNATIVES_BY_COUNTRY.get(country_code, ALTERNATIVES_BY_COUNTRY['OTHER'])
    search = f"{product_name} {product_type or ''}".lower()
    
    for keyword in ['spread', 'butter', 'cleanser', 'moisturizer', 'vitamin', 'protein']:
        if keyword in search and keyword in country_alts:
            alt = country_alts[keyword]
            if alt['name'].lower() not in search.lower():
                return alt
    
    return country_alts.get('default', ALTERNATIVES_BY_COUNTRY['OTHER']['default'])

# ═══════════════════════════════════════════════════════════════════════════════
# LOCATION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
RETAILERS_DISPLAY = {
    "AU": ["Chemist Warehouse", "Priceline", "Woolworths", "Coles"],
    "US": ["CVS", "Walgreens", "Target", "Walmart"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's"],
    "OTHER": ["Local pharmacy", "iHerb", "Amazon"]
}

def detect_location_enhanced():
    for service in [
        {'url': 'https://ipapi.co/json/', 'extract': lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'), d.get('latitude'), d.get('longitude'), d.get('region'))},
        {'url': 'https://ip-api.com/json/', 'extract': lambda d: (d.get('city'), d.get('country'), d.get('countryCode'), d.get('lat'), d.get('lon'), d.get('regionName'))},
    ]:
        try:
            r = requests.get(service['url'], timeout=5)
            if r.ok:
                d = r.json()
                extracted = service['extract'](d)
                city, country, code = extracted[0], extracted[1], extracted[2]
                lat = extracted[3] if len(extracted) > 3 else None
                lon = extracted[4] if len(extracted) > 4 else None
                region = extracted[5] if len(extracted) > 5 else ''
                
                if city and city not in ['', 'Unknown', None]:
                    code = code.upper() if code and len(code) == 2 else 'OTHER'
                    if lat and lon:
                        lat, lon = add_privacy_jitter(float(lat), float(lon))
                        geohash = encode_geohash(lat, lon)
                    else:
                        lat, lon, geohash = None, None, None
                    
                    return {'city': city, 'region': region or '', 'country': country or '', 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER']), 'lat': lat, 'lon': lon, 'geohash': geohash}
        except: continue
    
    return {'city': 'Unknown', 'region': '', 'country': 'Unknown', 'code': 'OTHER', 'retailers': RETAILERS_DISPLAY['OTHER'], 'lat': None, 'lon': None, 'geohash': None}

def get_verdict(score):
    if score >= 90: return "EXCEPTIONAL"
    elif score >= 70: return "BUY"
    elif score >= 40: return "CAUTION"
    return "HIGH_CAUTION"

def get_verdict_display(verdict):
    return {
        'EXCEPTIONAL': {'icon': '*', 'text': 'EXCEPTIONAL', 'color': '#06b6d4'},
        'BUY': {'icon': '+', 'text': 'GOOD TO BUY', 'color': '#22c55e'},
        'CAUTION': {'icon': '!', 'text': 'USE CAUTION', 'color': '#f59e0b'},
        'HIGH_CAUTION': {'icon': '!!', 'text': 'HIGH CAUTION', 'color': '#ef4444'},
        'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}
    }.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH GRADE (Food Only) & SAFETY GRADE (Cosmetics Only)
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_health_grade(nutrition, category):
    """Calculate health grade A-E - ONLY for Food/Beverage"""
    if category not in ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]:
        return None, None
    
    if not nutrition:
        return None, "No nutrition data"
    
    negative_points = 0
    positive_points = 0
    
    energy = nutrition.get('energy-kcal_100g', nutrition.get('energy_100g', 0)) or 0
    if energy > 800: negative_points += 10
    elif energy > 600: negative_points += 7
    elif energy > 400: negative_points += 4
    
    sugars = nutrition.get('sugars_100g', 0) or 0
    if sugars > 45: negative_points += 10
    elif sugars > 31: negative_points += 7
    elif sugars > 18: negative_points += 4
    
    sat_fat = nutrition.get('saturated-fat_100g', 0) or 0
    if sat_fat > 10: negative_points += 10
    elif sat_fat > 6: negative_points += 7
    elif sat_fat > 3: negative_points += 4
    
    sodium = (nutrition.get('sodium_100g', 0) or 0) * 1000
    if not sodium:
        sodium = (nutrition.get('salt_100g', 0) or 0) * 400
    if sodium > 900: negative_points += 10
    elif sodium > 600: negative_points += 7
    elif sodium > 300: negative_points += 4
    
    fiber = nutrition.get('fiber_100g', 0) or 0
    if fiber > 4.7: positive_points += 5
    elif fiber > 2.8: positive_points += 3
    
    protein = nutrition.get('proteins_100g', 0) or 0
    if protein > 8: positive_points += 5
    elif protein > 4.7: positive_points += 3
    
    final_score = negative_points - positive_points
    
    if final_score <= 0: grade = 'A'
    elif final_score <= 2: grade = 'B'
    elif final_score <= 10: grade = 'C'
    elif final_score <= 18: grade = 'D'
    else: grade = 'E'
    
    return grade, f"Score: {final_score}"

def calculate_safety_grade(ingredients_flagged, category):
    """Calculate safety grade - ONLY for Cosmetics/Household"""
    if category not in ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"]:
        return None, None
    
    if not ingredients_flagged:
        return "LOW", "No concerning ingredients detected"
    
    high_severity = sum(1 for i in ingredients_flagged if i.get('severity') == 'high')
    medium_severity = sum(1 for i in ingredients_flagged if i.get('severity') == 'medium')
    
    if high_severity >= 2: return "HIGH", f"{high_severity} high-concern ingredients"
    elif high_severity == 1 or medium_severity >= 3: return "MED", "Some ingredients of concern"
    else: return "LOW", "Generally considered safe"

def get_health_grade_color(grade):
    return {'A': '#22c55e', 'B': '#84cc16', 'C': '#f59e0b', 'D': '#f97316', 'E': '#ef4444'}.get(grade, '#6b7280')

def get_safety_grade_color(grade):
    return {'LOW': '#22c55e', 'MED': '#f59e0b', 'HIGH': '#ef4444'}.get(grade, '#6b7280')

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def normalize_product_name(name):
    if not name: return ""
    return re.sub(r'[^\w\s]', '', name.lower()).strip()

def get_product_hash(product_name, brand=""):
    normalized = normalize_product_name(f"{brand} {product_name}")
    return hashlib.md5(normalized.encode()).hexdigest()[:16]

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT, product_hash TEXT, product_category TEXT, product_type TEXT, score INTEGER, verdict TEXT, ingredients TEXT, violations TEXT, bonuses TEXT, notifications TEXT, thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, lat REAL, lon REAL, geohash TEXT, city TEXT, country TEXT, implied_promise TEXT, value_discrepancy INTEGER DEFAULT 0, health_grade TEXT, safety_grade TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS verified_products (id INTEGER PRIMARY KEY AUTOINCREMENT, product_hash TEXT UNIQUE, product_name TEXT, brand TEXT, verified_score INTEGER, scan_count INTEGER DEFAULT 1, product_category TEXT, ingredients TEXT, violations TEXT, last_verified DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (barcode TEXT PRIMARY KEY, product_name TEXT, brand TEXT, ingredients TEXT, product_type TEXT, categories TEXT, nutrition TEXT, image_url TEXT, source TEXT, description TEXT, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, flagged INTEGER DEFAULT 0, streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE)''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (id INTEGER PRIMARY KEY DEFAULT 1, user_id TEXT, city TEXT, country TEXT, country_code TEXT, lat REAL, lon REAL)''')
    c.execute('SELECT user_id FROM user_info WHERE id=1')
    if not c.fetchone():
        c.execute('INSERT INTO user_info (id, user_id) VALUES (1, ?)', (str(uuid.uuid4()),))
    
    for col in ['lat', 'lon', 'geohash', 'city', 'country', 'implied_promise', 'value_discrepancy', 'health_grade', 'safety_grade']:
        try: c.execute(f'ALTER TABLE scans ADD COLUMN {col} TEXT')
        except: pass
    
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
    c.execute('SELECT city, country, country_code, lat, lon FROM user_info WHERE id=1')
    r = c.fetchone()
    conn.close()
    if r and r[0] and r[0] not in ['Unknown', '']:
        code = r[2] or 'OTHER'
        return {'city': r[0], 'country': r[1] or '', 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER']), 'lat': r[3], 'lon': r[4]}
    return None

def save_location(city, country, lat=None, lon=None):
    country_map = {'australia': 'AU', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB', 'uk': 'GB', 'new zealand': 'NZ', 'canada': 'CA'}
    code = country_map.get((country or '').lower(), 'OTHER')
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE user_info SET city=?, country=?, country_code=?, lat=?, lon=? WHERE id=1', (city, country, code, lat, lon))
    conn.commit()
    conn.close()
    return code

def save_scan(result, user_id, thumb=None, location=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    product_hash = get_product_hash(result.get('product_name', ''), result.get('brand', ''))
    lat = location.get('lat') if location else None
    lon = location.get('lon') if location else None
    geohash = location.get('geohash') if location else None
    city = location.get('city') if location else None
    country = location.get('country') if location else None
    
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO scans (scan_id, user_id, product, brand, product_hash, product_category, product_type, score, verdict, ingredients, violations, bonuses, notifications, thumb, lat, lon, geohash, city, country, implied_promise, value_discrepancy, health_grade, safety_grade) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
              (sid, user_id, result.get('product_name', ''), result.get('brand', ''), product_hash, result.get('product_category', ''), result.get('product_type', ''), result.get('score', 0), result.get('verdict', ''), json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), json.dumps(result.get('bonuses', [])), json.dumps(result.get('notifications', [])), thumb, lat, lon, geohash, city, country, result.get('implied_promise', ''), 1 if result.get('value_discrepancy') else 0, result.get('health_grade', ''), result.get('safety_grade', '')))
    
    today = datetime.now().date()
    c.execute('SELECT scans, flagged, streak, best_streak, last_scan FROM stats WHERE id=1')
    r = c.fetchone()
    if r:
        scans, flagged, streak, best, last = r
        if last:
            try:
                ld = datetime.strptime(last, '%Y-%m-%d').date()
                streak = streak + 1 if ld == today - timedelta(days=1) else (streak if ld == today else 1)
            except: streak = 1
        else: streak = 1
        best = max(best, streak)
        if result.get('verdict') in ['HIGH_CAUTION', 'CAUTION']: flagged += 1
        c.execute('UPDATE stats SET scans=?, flagged=?, streak=?, best_streak=?, last_scan=? WHERE id=1', (scans + 1, flagged, streak, best, today.isoformat()))
    conn.commit()
    conn.close()
    return sid

def get_history(user_id, n=30):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT id, scan_id, ts, product, brand, score, verdict, thumb, favorite FROM scans WHERE user_id=? AND deleted=0 ORDER BY ts DESC LIMIT ?', (user_id, n))
    rows = c.fetchall()
    conn.close()
    return [{'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4], 'score': r[5], 'verdict': r[6], 'thumb': r[7], 'favorite': r[8]} for r in rows]

def get_map_data(limit=500):
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT lat, lon, score, verdict, city, country, product FROM scans WHERE lat IS NOT NULL AND lon IS NOT NULL AND lat != "" ORDER BY ts DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'lat': float(r[0]) if r[0] else None, 'lon': float(r[1]) if r[1] else None, 'score': r[2], 'verdict': r[3], 'city': r[4], 'country': r[5], 'product': r[6]} for r in rows if r[0] and r[1]]

def get_stats():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT scans, flagged, streak, best_streak FROM stats WHERE id=1')
    r = c.fetchone()
    conn.close()
    return {'scans': r[0], 'flagged': r[1], 'streak': r[2], 'best_streak': r[3]} if r else {'scans': 0, 'flagged': 0, 'streak': 0, 'best_streak': 0}

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

# ═══════════════════════════════════════════════════════════════════════════════
# BARCODE FUNCTIONS WITH STALE DATA CHECK
# ═══════════════════════════════════════════════════════════════════════════════
def cache_barcode(barcode, data):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO barcode_cache (barcode, product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, description, last_updated) VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)', (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''), data.get('product_type', ''), data.get('categories', ''), json.dumps(data.get('nutrition', {})), data.get('image_url', ''), data.get('source', ''), data.get('description', '')))
        conn.commit()
        conn.close()
    except: pass

def get_cached_barcode(barcode):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, description, last_updated FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]:
            last_updated = r[9] if len(r) > 9 else None
            is_stale = False
            if last_updated:
                try:
                    lu_date = datetime.strptime(last_updated[:10], '%Y-%m-%d')
                    if (datetime.now() - lu_date).days > STALE_THRESHOLD_DAYS:
                        is_stale = True
                except: pass
            
            return {'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 'product_type': r[3], 'categories': r[4], 'nutrition': json.loads(r[5]) if r[5] else {}, 'image_url': r[6], 'source': r[7], 'description': r[8] or '', 'cached': True, 'is_stale': is_stale}
    except: pass
    return None

def is_book_isbn(barcode):
    return barcode and len(barcode) >= 10 and barcode[:3] in ['978', '979']

def lookup_open_food_facts(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.3, "Searching Open Food Facts...")
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=12)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or p.get('generic_name') or ''
                if name:
                    return {'found': True, 'name': name, 'brand': p.get('brands', ''), 'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '', 'categories': p.get('categories', ''), 'nutrition': p.get('nutriments', {}), 'image_url': p.get('image_url', ''), 'product_type': 'food', 'source': 'Open Food Facts', 'confidence': 'high' if p.get('ingredients_text') else 'medium'}
    except: pass
    return None

def lookup_open_beauty_facts(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.4, "Searching Open Beauty Facts...")
    try:
        r = requests.get(f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json", timeout=12)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or ''
                if name: return {'found': True, 'name': name, 'brand': p.get('brands', ''), 'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '', 'categories': p.get('categories', ''), 'image_url': p.get('image_url', ''), 'product_type': 'cosmetics', 'source': 'Open Beauty Facts', 'confidence': 'high' if p.get('ingredients_text') else 'medium'}
    except: pass
    return None

def lookup_open_library(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.5, "Searching Open Library...")
    try:
        r = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{barcode}&format=json&jscmd=data", timeout=12)
        if r.ok:
            d = r.json()
            key = f"ISBN:{barcode}"
            if key in d:
                book = d[key]
                authors = ', '.join([a.get('name', '') for a in book.get('authors', [])]) if book.get('authors') else ''
                return {'found': True, 'name': book.get('title', ''), 'brand': authors, 'ingredients': '', 'categories': 'Books', 'product_type': 'book', 'source': 'Open Library', 'confidence': 'high', 'is_book': True}
    except: pass
    return None

def lookup_upc_itemdb(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.6, "Searching UPC Database...")
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=12)
        if r.ok:
            d = r.json()
            items = d.get('items', [])
            if items:
                item = items[0]
                return {'found': True, 'name': item.get('title', ''), 'brand': item.get('brand', ''), 'description': item.get('description', ''), 'categories': item.get('category', ''), 'image_url': item.get('images', [''])[0] if item.get('images') else '', 'source': 'UPC Item DB', 'confidence': 'medium'}
    except: pass
    return None

def waterfall_barcode_search(barcode, progress_callback=None):
    if not barcode: return {'found': False, 'reason': 'No barcode'}
    
    if progress_callback: progress_callback(0.1, "Checking cache...")
    cached = get_cached_barcode(barcode)
    if cached and not cached.get('is_stale'):
        if progress_callback: progress_callback(1.0, "Found in cache!")
        return cached
    
    if progress_callback: progress_callback(0.2, "Searching databases...")
    
    if is_book_isbn(barcode):
        result = lookup_open_library(barcode, progress_callback)
        if result:
            cache_barcode(barcode, result)
            return result
    
    result = lookup_open_food_facts(barcode, progress_callback)
    if result:
        cache_barcode(barcode, result)
        return result
    
    result = lookup_open_beauty_facts(barcode, progress_callback)
    if result:
        cache_barcode(barcode, result)
        return result
    
    result = lookup_upc_itemdb(barcode, progress_callback)
    if result:
        cache_barcode(barcode, result)
        return result
    
    if progress_callback: progress_callback(1.0, "Not found")
    return {'found': False, 'barcode': barcode}

def preprocess_barcode_image(image):
    try:
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        return enhancer.enhance(2.5).filter(ImageFilter.SHARPEN)
    except: return image

def try_decode_barcode_pyzbar(image_file):
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L'), img.rotate(90, expand=True)]:
            try:
                barcodes = pyzbar.decode(proc_img)
                if barcodes: return barcodes[0].data.decode('utf-8')
            except: continue
    except: pass
    return None

def ai_read_barcode(image_file):
    if not GEMINI_API_KEY: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        resp = model.generate_content(["Read the BARCODE digits below the barcode lines. Return ONLY digits, no spaces. If unreadable, return NONE", img])
        text = resp.text.strip().upper()
        if 'NONE' in text: return None
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14: return digits
    except: pass
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
def check_profile_notifications(ingredients, full_text, user_profiles, user_allergies, product_category):
    notifications = []
    if not ingredients and not full_text: return notifications
    ing_text = (' '.join(ingredients) if isinstance(ingredients, list) else ingredients or '').lower()
    full_lower = (full_text or '').lower()
    
    for profile_key in user_profiles:
        if profile_key not in HEALTH_PROFILES: continue
        profile = HEALTH_PROFILES[profile_key]
        if product_category not in profile.get('applies_to', []): continue
        for flag in profile.get('ingredient_flags', []):
            if flag.lower() in ing_text:
                notifications.append({'type': 'profile', 'key': profile_key, 'name': profile['name'], 'icon': profile['icon'], 'message': profile.get('notification'), 'severity': 'warning'})
                break
    
    for allergy_key in user_allergies:
        if allergy_key not in ALLERGENS: continue
        allergen = ALLERGENS[allergy_key]
        if product_category not in allergen.get('applies_to', []): continue
        for trigger in allergen['triggers']:
            if trigger.lower() in ing_text:
                notifications.append({'type': 'allergen', 'key': allergy_key, 'name': allergen['name'], 'icon': allergen['icon'], 'message': f"Contains or may contain {allergen['name'].upper()}!", 'severity': 'danger'})
                break
    
    return notifications

# ═══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS PROMPT WITH SPLIT INGREDIENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
ANALYSIS_PROMPT = """You are HonestWorld's Marketing Integrity Analyzer.

## MISSION
Analyze products for marketing integrity - gaps between PROMISES and REALITY.

## STEP 1: CATEGORY & CONTEXT
1. Category: Food/Beverage, Cosmetic, Supplement, Electronics, Household, Book
2. Subtype: Be specific (spread, serum, protein powder, cable)
3. Implied Promise: What is this product CLAIMING to be?
4. Functional Expectation: What SHOULD be the primary ingredient?

## STEP 2: SPLIT INGREDIENT DETECTION (Critical!)
Competitors miss this. Manufacturers split ingredients to hide totals.

**SUGAR VARIANTS to SUM:** sugar, glucose, fructose, dextrose, maltose, sucrose, corn syrup, HFCS, glucose syrup, invert sugar, cane sugar, honey, agave, maltodextrin

**OIL VARIANTS to SUM:** palm oil, canola oil, soybean oil, sunflower oil, vegetable oil, rapeseed oil, corn oil, hydrogenated oil

**RULE:** If multiple variants of same base ingredient appear, mentally SUM them. If combined total would be #1 ingredient, trigger Law #3 (Split Ingredient Trick).

Example: Sugar is #4, Glucose Syrup is #5, Dextrose is #6 → Combined they're #1 → FLAG IT

## STEP 3: VALUE GAP ANALYSIS
IF (Marketing uses Bio/Organic/Premium/Pro/Luxury claims)
AND (Main ingredient is cheap filler: water, maltodextrin, cheap oil)
AND (Filler contradicts functional expectation)
THEN → value_discrepancy = TRUE → CAP SCORE AT 60

Context exceptions:
- Water IS expected in: beverages, soups, shampoos, toners, cleansers
- Sugar IS expected in: candy, desserts, soda

## STEP 4: CITATION CREDIBILITY
When citing ingredient concerns, use this hierarchy:
1. WHO/FDA/EFSA/EU SCCS (High authority) → Use confidently
2. IARC, National agencies (Medium) → Use with context
3. Single studies (Low) → Mark as "Controversial" not "Dangerous"

If evidence is weak/debated → verdict = CAUTION (Yellow), not HIGH_CAUTION (Red)

## SCORING (Base: 100)
Deduct for violations. Apply caps:
- value_discrepancy = TRUE → Cap at 60
- Split ingredient detected → -18 points

Verdicts:
- 90-100: EXCEPTIONAL
- 70-89: BUY  
- 40-69: CAUTION
- 0-39: HIGH_CAUTION

Context: {location}
{barcode_context}

## OUTPUT (Valid JSON)
{{
    "product_name": "Name",
    "brand": "Brand",
    "product_category": "CATEGORY_X",
    "product_type": "subtype",
    "implied_promise": "What marketing claims",
    "functional_expectation": "Expected #1 ingredient",
    "actual_reality": "Actual #1 ingredient",
    "value_discrepancy": true/false,
    "value_discrepancy_reason": "Why if true",
    "split_ingredients_detected": true/false,
    "split_ingredients_detail": "Which ingredients were split",
    "readable": true,
    "score": 0-100,
    "violations": [{{"law": 1, "name": "Name", "points": -X, "evidence": "Why"}}],
    "bonuses": [{{"name": "Bonus", "points": X, "evidence": "Why"}}],
    "ingredients": ["list"],
    "ingredients_flagged": [{{"name": "X", "concern": "Y", "source": "WHO/FDA/etc", "severity": "high/medium/low"}}],
    "good_ingredients": ["beneficial"],
    "main_issue": "Primary concern",
    "positive": "Main positive",
    "front_claims": ["claims"],
    "confidence": "high/medium/low"
}}"""

def analyze_product(images, location, progress_callback, barcode_info=None, user_profiles=None, user_allergies=None):
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": "Add GEMINI_API_KEY"}
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    
    progress_callback(0.3, "Analyzing...")
    
    barcode_context = ""
    if barcode_info and barcode_info.get('found'):
        barcode_context = f"""
BARCODE DATA:
- Product: {barcode_info.get('name', '')}
- Brand: {barcode_info.get('brand', '')}
- Ingredients: {barcode_info.get('ingredients', '')[:1000]}
- Source: {barcode_info.get('source', '')}"""
    
    prompt = ANALYSIS_PROMPT.format(
        location=f"{location.get('city', '')}, {location.get('country', '')}",
        barcode_context=barcode_context
    )
    
    progress_callback(0.5, "Applying integrity laws...")
    
    try:
        response = model.generate_content([prompt] + pil_images)
        text = response.text.strip()
        
        result = None
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try: result = json.loads(json_match.group(0))
            except: pass
        
        if not result:
            return {"product_name": "Parse Error", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": []}
        
        progress_callback(0.7, "Validating...")
        
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        if result.get('value_discrepancy'):
            score = min(score, 60)
        
        violations = result.get('violations', [])
        total_deduction = sum(abs(v.get('points', 0)) for v in violations)
        expected_score = 100 - total_deduction
        if score > expected_score + 5:
            score = max(0, expected_score)
        
        if result.get('value_discrepancy'):
            score = min(score, 60)
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        
        # Calculate appropriate badge based on category
        cat_info = PRODUCT_CATEGORIES.get(product_category, {})
        badge_type = cat_info.get('badge_type', 'none')
        
        if badge_type == 'health':
            nutrition = barcode_info.get('nutrition', {}) if barcode_info else {}
            health_grade, health_details = calculate_health_grade(nutrition, product_category)
            result['health_grade'] = health_grade
            result['health_grade_details'] = health_details
            result['safety_grade'] = None
        elif badge_type == 'safety':
            ingredients_flagged = result.get('ingredients_flagged', [])
            safety_grade, safety_details = calculate_safety_grade(ingredients_flagged, product_category)
            result['safety_grade'] = safety_grade
            result['safety_grade_details'] = safety_details
            result['health_grade'] = None
        else:
            result['health_grade'] = None
            result['safety_grade'] = None
        
        ingredients = result.get('ingredients', [])
        full_text = ' '.join(result.get('front_claims', []))
        notifications = check_profile_notifications(ingredients, full_text, user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except Exception as e:
        return {"product_name": "Error", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": str(e)[:100]}

def analyze_from_barcode_data(barcode_info, location, progress_callback, user_profiles=None, user_allergies=None):
    if not GEMINI_API_KEY:
        return {"product_name": barcode_info.get('name', 'Unknown'), "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": []}
    
    progress_callback(0.2, "Preparing...")
    
    product_name = barcode_info.get('name', 'Unknown')
    brand = barcode_info.get('brand', '')
    ingredients_text = barcode_info.get('ingredients', '')
    nutrition = barcode_info.get('nutrition', {})
    
    if barcode_info.get('is_book'):
        return {"product_name": product_name, "brand": brand, "product_category": "CATEGORY_BOOK", "readable": True, "score": 85, "verdict": "BUY", "violations": [], "bonuses": [], "ingredients": [], "main_issue": "N/A - Book", "notifications": [], "is_book": True, "health_grade": None, "safety_grade": None}
    
    progress_callback(0.4, "Analyzing...")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    prompt = f"""Analyze this product for HonestWorld:

Product: {product_name}
Brand: {brand}
Ingredients: {ingredients_text if ingredients_text else 'Not available'}

Apply Split Ingredient Detection - sum sugar/oil variants.
Apply Value Gap Detection - premium claims vs cheap fillers.
Use Citation Hierarchy - WHO/FDA/EFSA first.

Location: {location.get('city', '')}, {location.get('country', '')}

Return valid JSON with all fields."""
    
    progress_callback(0.6, "Processing...")
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = {}
        
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        if result.get('value_discrepancy'):
            score = min(score, 60)
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['product_name'] = product_name
        result['brand'] = brand
        result['readable'] = True
        
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        cat_info = PRODUCT_CATEGORIES.get(product_category, {})
        badge_type = cat_info.get('badge_type', 'none')
        
        if badge_type == 'health':
            health_grade, _ = calculate_health_grade(nutrition, product_category)
            result['health_grade'] = health_grade
            result['safety_grade'] = None
        elif badge_type == 'safety':
            safety_grade, _ = calculate_safety_grade(result.get('ingredients_flagged', []), product_category)
            result['safety_grade'] = safety_grade
            result['health_grade'] = None
        else:
            result['health_grade'] = None
            result['safety_grade'] = None
        
        ingredients = result.get('ingredients', [])
        notifications = check_profile_notifications(ingredients, '', user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except:
        return {"product_name": product_name, "brand": brand, "score": 65, "verdict": "CAUTION", "readable": True, "violations": [], "notifications": [], "health_grade": None, "safety_grade": None}

# ═══════════════════════════════════════════════════════════════════════════════
# SHARE IMAGES - NO EMOJIS, SCORE VISIBLE
# ═══════════════════════════════════════════════════════════════════════════════
def create_share_image(product_name, brand, score, verdict, implied_promise="", value_discrepancy=False, health_grade=None, safety_grade=None):
    """Create share image - NO EMOJIS, score visible"""
    width, height = 1080, 1080
    colors = {
        'EXCEPTIONAL': ('#06b6d4', '#0891b2'),
        'BUY': ('#22c55e', '#16a34a'),
        'CAUTION': ('#f59e0b', '#d97706'),
        'HIGH_CAUTION': ('#ef4444', '#dc2626'),
        'UNCLEAR': ('#6b7280', '#4b5563')
    }
    c1, c2 = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    # Gradient
    for i in range(height):
        progress = i / height
        r = int(int(c1[1:3], 16) * (1 - progress) + int(c2[1:3], 16) * progress)
        g = int(int(c1[3:5], 16) * (1 - progress) + int(c2[3:5], 16) * progress)
        b = int(int(c1[5:7], 16) * (1 - progress) + int(c2[5:7], 16) * progress)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_tagline = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 180)
        font_100 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        font_verdict = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        font_title = font_tagline = font_score = font_100 = font_verdict = font_product = font_brand = font_footer = font_badge = ImageFont.load_default()
    
    display = get_verdict_display(verdict)
    
    # Title (no emoji)
    draw.text((width // 2, 50), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 110), "See Through Marketing Claims", fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
    
    # Score circle
    circle_y = 340
    circle_radius = 150
    draw.ellipse([width//2 - circle_radius, circle_y - circle_radius, width//2 + circle_radius, circle_y + circle_radius], fill=(255, 255, 255))
    
    # Score number (dark color for contrast)
    score_color = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    draw.text((width // 2, circle_y - 20), str(score), fill=score_color, anchor="mm", font=font_score)
    draw.text((width // 2, circle_y + 80), "/100", fill=(100, 100, 100), anchor="mm", font=font_100)
    
    # Health or Safety badge (if applicable)
    if health_grade:
        badge_color = get_health_grade_color(health_grade)
        badge_x = width // 2 + 120
        badge_y = circle_y - 120
        draw.ellipse([badge_x - 30, badge_y - 30, badge_x + 30, badge_y + 30], fill=badge_color)
        draw.text((badge_x, badge_y), health_grade, fill='white', anchor="mm", font=font_badge)
    elif safety_grade:
        badge_color = get_safety_grade_color(safety_grade)
        badge_x = width // 2 + 120
        badge_y = circle_y - 120
        draw.ellipse([badge_x - 30, badge_y - 30, badge_x + 30, badge_y + 30], fill=badge_color)
        label = safety_grade[0] if safety_grade else "?"
        draw.text((badge_x, badge_y), label, fill='white', anchor="mm", font=font_badge)
    
    # Verdict
    draw.text((width // 2, 540), display['text'], fill='white', anchor="mt", font=font_verdict)
    
    # Value discrepancy warning
    if value_discrepancy:
        draw.rectangle([(100, 600), (width - 100, 660)], fill=(0, 0, 0, 80))
        draw.text((width // 2, 630), "VALUE DISCREPANCY DETECTED", fill='white', anchor="mm", font=font_tagline)
        y_offset = 80
    else:
        y_offset = 0
    
    # Product name
    pname = product_name[:35] + "..." if len(product_name) > 35 else product_name
    draw.text((width // 2, 620 + y_offset), pname, fill='white', anchor="mt", font=font_product)
    
    # Brand
    if brand:
        draw.text((width // 2, 665 + y_offset), f"by {brand[:30]}", fill=(255, 255, 255, 180), anchor="mt", font=font_brand)
    
    # Implied promise
    if implied_promise:
        draw.text((width // 2, 720 + y_offset), f'Claims: "{implied_promise[:40]}"', fill=(255, 255, 255, 150), anchor="mt", font=font_tagline)
    
    # Divider
    draw.line([(100, 800 + y_offset), (width - 100, 800 + y_offset)], fill=(255, 255, 255, 100), width=2)
    
    # What is HonestWorld - CLEAN VERSION (no AI-powered text)
    draw.text((width // 2, 840 + y_offset), "What is HonestWorld?", fill='white', anchor="mt", font=font_verdict)
    
    info_y = 900 + y_offset
    info_lines = [
        "* Scan products with your camera",
        "* 21 Integrity Laws check claims vs reality",
        "* Get instant honest scores"
    ]
    for line in info_lines:
        draw.text((width // 2, info_y), line, fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
        info_y += 35
    
    # Footer
    draw.text((width // 2, 1030), "HonestWorld.app  |  #HonestWorld #SeeTheTruth", fill=(255, 255, 255, 150), anchor="mt", font=font_footer)
    
    return img

def create_story_image(product_name, brand, score, verdict, implied_promise="", value_discrepancy=False, health_grade=None, safety_grade=None):
    """Create story image - NO EMOJIS, score visible"""
    width, height = 1080, 1920
    colors = {
        'EXCEPTIONAL': ('#06b6d4', '#0891b2'),
        'BUY': ('#22c55e', '#16a34a'),
        'CAUTION': ('#f59e0b', '#d97706'),
        'HIGH_CAUTION': ('#ef4444', '#dc2626'),
        'UNCLEAR': ('#6b7280', '#4b5563')
    }
    c1, c2 = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    # Gradient
    for i in range(height):
        progress = i / height
        r = int(int(c1[1:3], 16) * (1 - progress * 0.7) + int(c2[1:3], 16) * progress * 0.7)
        g = int(int(c1[3:5], 16) * (1 - progress * 0.7) + int(c2[3:5], 16) * progress * 0.7)
        b = int(int(c1[5:7], 16) * (1 - progress * 0.7) + int(c2[5:7], 16) * progress * 0.7)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_tagline = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 240)
        font_100 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        font_verdict = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        font_product = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        font_brand = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
        font_footer = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
    except:
        font_title = font_tagline = font_score = font_100 = font_verdict = font_product = font_brand = font_cta = font_footer = font_badge = ImageFont.load_default()
    
    display = get_verdict_display(verdict)
    
    # Title
    draw.text((width // 2, 120), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 190), "See Through Marketing Claims", fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
    
    # Score circle
    circle_y = 500
    circle_radius = 200
    draw.ellipse([width//2 - circle_radius, circle_y - circle_radius, width//2 + circle_radius, circle_y + circle_radius], fill=(255, 255, 255))
    
    # Score
    score_color = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    draw.text((width // 2, circle_y - 30), str(score), fill=score_color, anchor="mm", font=font_score)
    draw.text((width // 2, circle_y + 100), "/100", fill=(100, 100, 100), anchor="mm", font=font_100)
    
    # Badge
    if health_grade:
        badge_color = get_health_grade_color(health_grade)
        badge_x = width // 2 + 160
        badge_y = circle_y - 160
        draw.ellipse([badge_x - 40, badge_y - 40, badge_x + 40, badge_y + 40], fill=badge_color)
        draw.text((badge_x, badge_y), health_grade, fill='white', anchor="mm", font=font_badge)
    elif safety_grade:
        badge_color = get_safety_grade_color(safety_grade)
        badge_x = width // 2 + 160
        badge_y = circle_y - 160
        draw.ellipse([badge_x - 40, badge_y - 40, badge_x + 40, badge_y + 40], fill=badge_color)
        draw.text((badge_x, badge_y), safety_grade[0], fill='white', anchor="mm", font=font_badge)
    
    # Verdict
    draw.text((width // 2, 780), display['text'], fill='white', anchor="mt", font=font_verdict)
    
    # Value discrepancy
    if value_discrepancy:
        draw.rectangle([(100, 860), (width - 100, 920)], fill=(0, 0, 0, 80))
        draw.text((width // 2, 890), "VALUE DISCREPANCY DETECTED", fill='white', anchor="mm", font=font_tagline)
        y_offset = 80
    else:
        y_offset = 0
    
    # Product
    pname = product_name[:32] + "..." if len(product_name) > 32 else product_name
    draw.text((width // 2, 880 + y_offset), pname, fill='white', anchor="mt", font=font_product)
    if brand:
        draw.text((width // 2, 935 + y_offset), f"by {brand[:28]}", fill=(255, 255, 255, 180), anchor="mt", font=font_brand)
    
    if implied_promise:
        draw.text((width // 2, 1000 + y_offset), f'Claims: "{implied_promise[:35]}"', fill=(255, 255, 255, 150), anchor="mt", font=font_tagline)
    
    # Divider
    draw.line([(100, 1100 + y_offset), (width - 100, 1100 + y_offset)], fill=(255, 255, 255, 80), width=2)
    
    # What is HonestWorld
    draw.text((width // 2, 1160 + y_offset), "What is HonestWorld?", fill='white', anchor="mt", font=font_cta)
    
    info_lines = [
        "* Scan any product with your camera",
        "* AI analyzes marketing vs reality",
        "* 21 Integrity Laws expose inconsistencies",
        "* Get instant honest scores"
    ]
    
    y_pos = 1230 + y_offset
    for line in info_lines:
        draw.text((width // 2, y_pos), line, fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
        y_pos += 50
    
    # CTA
    draw.text((width // 2, 1500 + y_offset), "Know before you buy!", fill='white', anchor="mt", font=font_cta)
    draw.text((width // 2, 1560 + y_offset), "Follow for more product exposes", fill=(255, 255, 255, 180), anchor="mt", font=font_tagline)
    
    # Footer
    draw.text((width // 2, 1750), "HonestWorld.app", fill=(255, 255, 255, 150), anchor="mt", font=font_footer)
    draw.text((width // 2, 1800), "#HonestWorld #SeeTheTruth #MarketingExposed", fill=(255, 255, 255, 120), anchor="mt", font=font_footer)
    
    return img

def image_to_bytes(img, fmt='PNG'):
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()

# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.stApp { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 520px; }

.verdict-exceptional { background: linear-gradient(135deg, #06b6d4, #0891b2); }
.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-high_caution { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280, #4b5563); }

.verdict-card { border-radius: 24px; padding: 2rem; text-align: center; color: white; margin: 1rem 0; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.verdict-score { font-size: 4rem; font-weight: 900; }
.verdict-text { font-size: 1.3rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; margin-top: 0.5rem; }

.stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; }

.value-alert { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 3px solid #ef4444; border-radius: 16px; padding: 1.2rem; margin: 1rem 0; }
.value-alert-title { font-size: 1.1rem; font-weight: 800; color: #dc2626; }
.value-alert-text { font-size: 0.9rem; color: #7f1d1d; margin-top: 0.3rem; }

.badge-row { display: flex; gap: 1rem; justify-content: center; margin: 0.5rem 0; }
.badge-item { text-align: center; }
.badge-circle { width: 50px; height: 50px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.5rem; color: white; margin: 0 auto; }
.badge-label { font-size: 0.7rem; color: #64748b; margin-top: 0.25rem; }

.notif-danger { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-left: 5px solid #ef4444; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.notif-warning { background: linear-gradient(135deg, #fffbeb, #fef3c7); border-left: 5px solid #f59e0b; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }

.alert-issue { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.alert-positive { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

.law-box { background: white; border-left: 4px solid #ef4444; border-radius: 0 12px 12px 0; padding: 0.8rem; margin: 0.4rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.law-title { font-weight: 700; color: #dc2626; font-size: 0.95rem; }
.law-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }

.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }

.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn { display: flex; flex-direction: column; align-items: center; padding: 0.6rem; border-radius: 10px; color: white; text-decoration: none; font-weight: 600; font-size: 0.7rem; }

.progress-box { background: white; border-radius: 16px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 0.75rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }

.loc-badge { background: #dbeafe; color: #1d4ed8; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.7rem; font-weight: 600; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.75rem; font-weight: 700; }

#MainMenu, footer, header { visibility: hidden; }
.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    for key in ['result', 'scan_id', 'barcode_info', 'show_result', 'contribute_mode', 'contribute_barcode']:
        if key not in st.session_state:
            st.session_state[key] = None if key not in ['show_result', 'contribute_mode'] else False
    
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        if saved and saved.get('city') not in ['Unknown', '', None]:
            st.session_state.loc = saved
        else:
            detected = detect_location_enhanced()
            st.session_state.loc = detected
            if detected.get('city') not in ['Unknown', '']:
                save_location(detected['city'], detected['country'], detected.get('lat'), detected.get('lon'))
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🌍 HonestWorld")
        loc = st.session_state.loc
        if loc.get('city') and loc.get('city') != 'Unknown':
            st.markdown(f"<span class='loc-badge'>📍 {loc.get('city')}, {loc.get('country', '')}</span>", unsafe_allow_html=True)
    with col2:
        stats = get_stats()
        if stats['streak'] > 0:
            st.markdown(f"<span class='streak-badge'>🔥 {stats['streak']}</span>", unsafe_allow_html=True)
    
    st.markdown(f"""<div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>{stats['scans']}</div><div class='stat-lbl'>Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['flagged']}</div><div class='stat-lbl'>Flagged</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['best_streak']}</div><div class='stat-lbl'>Best Streak</div></div>
    </div>""", unsafe_allow_html=True)
    
    tab_scan, tab_history, tab_map, tab_profile, tab_laws = st.tabs(["📷 Scan", "📋 History", "🗺️ Map", "👤 Profile", "⚖️ Laws"])
    
    with tab_scan:
        if st.session_state.contribute_mode:
            render_contribute_interface(user_id)
        elif st.session_state.result and st.session_state.show_result:
            display_result(st.session_state.result, user_id)
        else:
            render_scan_interface(user_id)
    
    with tab_history:
        render_history(user_id)
    
    with tab_map:
        render_world_map()
    
    with tab_profile:
        render_profile()
    
    with tab_laws:
        render_laws()
    
    st.markdown(f"<center style='color:#94a3b8;font-size:0.7rem;margin-top:1rem;'>HonestWorld v{VERSION}</center>", unsafe_allow_html=True)

def render_scan_interface(user_id):
    input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
    images = []
    
    if input_method == "📷 Camera":
        st.caption("Point at product label")
        cam_img = st.camera_input("", label_visibility="collapsed")
        if cam_img:
            images = [cam_img]
            st.success("✅ Photo ready")
    
    elif input_method == "📁 Upload":
        uploaded = st.file_uploader("", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded:
            images = uploaded[:3]
            st.success(f"✅ {len(images)} image(s)")
    
    else:
        st.markdown("### 📊 Barcode Scanner")
        barcode_img = st.camera_input("", label_visibility="collapsed", key="barcode_cam")
        
        if barcode_img:
            with st.spinner("Reading barcode..."):
                barcode_num = try_decode_barcode_pyzbar(barcode_img)
                if not barcode_num:
                    barcode_num = ai_read_barcode(barcode_img)
            
            if barcode_num:
                st.info(f"Barcode: **{barcode_num}**")
                progress_container = st.empty()
                def update_progress(pct, msg):
                    progress_container.markdown(f"<div class='progress-box'><div>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
                
                barcode_info = waterfall_barcode_search(barcode_num, update_progress)
                progress_container.empty()
                
                if barcode_info.get('found'):
                    st.success(f"✅ **{barcode_info.get('name', '')}**")
                    st.session_state.barcode_info = barcode_info
                    st.session_state.barcode_only = True
                    images = [barcode_img]
                else:
                    st.warning("Product not in database. Contribute it!")
                    if st.button("📸 Contribute Product", use_container_width=True):
                        st.session_state.contribute_mode = True
                        st.session_state.contribute_barcode = barcode_num
                        st.rerun()
            else:
                st.error("Could not read barcode")
    
    if images or st.session_state.get('barcode_info'):
        if st.button("🔍 ANALYZE", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                progress_ph.markdown(f"<div class='progress-box'><div>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
            user_profiles, user_allergies = get_profiles(), get_allergies()
            bi = st.session_state.get('barcode_info')
            
            if st.session_state.get('barcode_only') and bi and bi.get('found'):
                result = analyze_from_barcode_data(bi, st.session_state.loc, update_prog, user_profiles, user_allergies)
                st.session_state.barcode_only = False
            else:
                result = analyze_product(images, st.session_state.loc, update_prog, bi, user_profiles, user_allergies)
            
            progress_ph.empty()
            
            if result.get('readable', True) and result.get('score', 0) > 0:
                thumb = None
                try:
                    if images:
                        images[0].seek(0)
                        img = Image.open(images[0])
                        img.thumbnail((100, 100))
                        buf = BytesIO()
                        img.save(buf, format='JPEG', quality=60)
                        thumb = buf.getvalue()
                except: pass
                
                scan_id = save_scan(result, user_id, thumb, st.session_state.loc)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.barcode_info = None
                st.rerun()
            else:
                st.error("Could not analyze. Try clearer photo.")

def render_contribute_interface(user_id):
    st.markdown("### 🆕 Contribute Product")
    barcode = st.session_state.get('contribute_barcode', '')
    st.info(f"Barcode: **{barcode}**")
    
    front_img = st.camera_input("Front label", key="contrib_front")
    back_img = st.camera_input("Back/Ingredients", key="contrib_back")
    
    product_name = st.text_input("Product Name")
    brand = st.text_input("Brand")
    
    images = [i for i in [front_img, back_img] if i]
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.contribute_mode = False
            st.rerun()
    with col2:
        if images and st.button("Submit", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                progress_ph.markdown(f"<div class='progress-box'><div>{msg}</div></div>", unsafe_allow_html=True)
            
            result = analyze_product(images, st.session_state.loc, update_prog, None, get_profiles(), get_allergies())
            if product_name: result['product_name'] = product_name
            if brand: result['brand'] = brand
            progress_ph.empty()
            
            if result.get('readable', True):
                cache_barcode(barcode, {'name': result.get('product_name', ''), 'brand': result.get('brand', ''), 'ingredients': ', '.join(result.get('ingredients', []))})
                scan_id = save_scan(result, user_id, None, st.session_state.loc)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.contribute_mode = False
                st.success("Product added!")
                st.rerun()

def display_result(result, user_id):
    score = result.get('score', 0)
    verdict = result.get('verdict', 'UNCLEAR')
    value_discrepancy = result.get('value_discrepancy', False)
    health_grade = result.get('health_grade')
    safety_grade = result.get('safety_grade')
    implied_promise = result.get('implied_promise', '')
    product_category = result.get('product_category', 'CATEGORY_FOOD')
    
    # Value Discrepancy Alert (TOP)
    if value_discrepancy:
        reason = result.get('value_discrepancy_reason', 'Premium marketing with cheap filler')
        st.markdown(f"""<div class='value-alert'>
            <div class='value-alert-title'>⚠️ VALUE DISCREPANCY DETECTED</div>
            <div class='value-alert-text'>{reason}</div>
            <div class='value-alert-text'><strong>Score capped at 60/100</strong></div>
        </div>""", unsafe_allow_html=True)
    
    # Main verdict card
    st.markdown(f"""<div class='verdict-card verdict-{verdict.lower()}'>
        <div class='verdict-score'>{score}<span style='font-size:1.5rem;'>/100</span></div>
        <div class='verdict-text'>{get_verdict_display(verdict)['text']}</div>
    </div>""", unsafe_allow_html=True)
    
    # Badges (Health for Food, Safety for Cosmetics, None for Electronics)
    badges_html = "<div class='badge-row'>"
    badges_html += f"<div class='badge-item'><div class='badge-circle' style='background:#3b82f6;'>{score}</div><div class='badge-label'>Integrity</div></div>"
    
    if health_grade:
        badges_html += f"<div class='badge-item'><div class='badge-circle' style='background:{get_health_grade_color(health_grade)};'>{health_grade}</div><div class='badge-label'>Health</div></div>"
    elif safety_grade:
        badges_html += f"<div class='badge-item'><div class='badge-circle' style='background:{get_safety_grade_color(safety_grade)};'>{safety_grade[0]}</div><div class='badge-label'>Safety</div></div>"
    
    badges_html += "</div>"
    st.markdown(badges_html, unsafe_allow_html=True)
    
    # Product info
    st.markdown(f"### {result.get('product_name', 'Unknown')}")
    if result.get('brand'):
        st.markdown(f"*by {result.get('brand')}*")
    
    cat_info = PRODUCT_CATEGORIES.get(product_category, {})
    st.caption(f"{cat_info.get('icon', '📦')} {cat_info.get('name', 'Product')}")
    
    if implied_promise:
        st.info(f"🎭 **Marketing claim:** \"{implied_promise}\"")
    
    # Notifications
    for notif in result.get('notifications', []):
        css_class = 'notif-danger' if notif.get('severity') == 'danger' else 'notif-warning'
        st.markdown(f"<div class='{css_class}'><strong>{notif.get('icon', '⚠️')} {notif.get('name')}</strong><br>{notif.get('message')}</div>", unsafe_allow_html=True)
    
    # Main issue/positive
    if result.get('main_issue') and result.get('main_issue').lower() not in ['none', 'n/a', '']:
        st.markdown(f"<div class='alert-issue'>⚠️ {result.get('main_issue')}</div>", unsafe_allow_html=True)
    if result.get('positive'):
        st.markdown(f"<div class='alert-positive'>✅ {result.get('positive')}</div>", unsafe_allow_html=True)
    
    # Split ingredients warning
    if result.get('split_ingredients_detected'):
        st.warning(f"🔍 **Split Ingredient Detected:** {result.get('split_ingredients_detail', 'Multiple forms of same ingredient found')}")
    
    # Alternative
    if not result.get('is_book'):
        country_code = st.session_state.loc.get('code', 'OTHER')
        alt = get_alternative(result.get('product_name', ''), result.get('product_type', ''), product_category, country_code)
        if alt.get('name'):
            score_html = f" ({alt['score']}/100)" if alt.get('score') else ''
            st.markdown(f"<div class='alt-card'><strong>💚 Better Alternative:</strong><br>{alt['name']}{score_html}<br><small>{alt.get('why', '')} • {alt.get('retailer', '')}</small></div>", unsafe_allow_html=True)
    
    # Violations
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Issues Found ({len(violations)})", expanded=True):
            for v in violations:
                st.markdown(f"<div class='law-box'><div class='law-title'>Law {v.get('law', '?')}: {v.get('name', '')} ({v.get('points', 0)} pts)</div><div class='law-evidence'>{v.get('evidence', '')}</div></div>", unsafe_allow_html=True)
    
    # Ingredients
    if result.get('ingredients_flagged') or result.get('ingredients'):
        with st.expander("🧪 Ingredients", expanded=False):
            for ing in result.get('ingredients_flagged', []):
                severity = ing.get('severity', 'medium')
                color = '#ef4444' if severity == 'high' else '#f59e0b' if severity == 'medium' else '#6b7280'
                st.markdown(f"<span style='color:{color};font-weight:600;'>• {ing.get('name', '')}</span> - {ing.get('concern', '')} <small>({ing.get('source', '')})</small>", unsafe_allow_html=True)
            
            if result.get('good_ingredients'):
                st.markdown("**Good:** " + ", ".join(result.get('good_ingredients', [])[:10]))
    
    # Share
    st.markdown("### 📤 Share")
    share_img = create_share_image(result.get('product_name', ''), result.get('brand', ''), score, verdict, implied_promise, value_discrepancy, health_grade, safety_grade)
    story_img = create_story_image(result.get('product_name', ''), result.get('brand', ''), score, verdict, implied_promise, value_discrepancy, health_grade, safety_grade)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post Image", data=image_to_bytes(share_img), file_name=f"honestworld_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story Image", data=image_to_bytes(story_img), file_name=f"honestworld_story_{score}.png", mime="image/png", use_container_width=True)
    
    share_text = urllib.parse.quote(f"Scanned {result.get('product_name', '')} with HonestWorld - {score}/100 ({verdict})! #HonestWorld #SeeTheTruth")
    st.markdown(f"""<div class='share-grid'>
        <a href='https://twitter.com/intent/tweet?text={share_text}' target='_blank' class='share-btn' style='background:#1DA1F2;'>Twitter</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={share_text}' target='_blank' class='share-btn' style='background:#4267B2;'>Facebook</a>
        <a href='https://wa.me/?text={share_text}' target='_blank' class='share-btn' style='background:#25D366;'>WhatsApp</a>
    </div>""", unsafe_allow_html=True)
    
    if st.button("🔄 Scan Another", use_container_width=True):
        st.session_state.result = None
        st.session_state.show_result = False
        st.rerun()

def render_history(user_id):
    history = get_history(user_id, 30)
    if not history:
        st.info("No scans yet! Start scanning products.")
    else:
        for item in history:
            score = item['score'] or 0
            color = '#06b6d4' if score >= 90 else '#22c55e' if score >= 70 else '#f59e0b' if score >= 40 else '#ef4444'
            fav = "⭐ " if item['favorite'] else ""
            col1, col2, col3 = st.columns([0.6, 3.4, 0.5])
            with col1:
                st.markdown(f"<div style='width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;color:white;background:{color};'>{score}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{fav}{(item['product'] or '')[:28]}**")
                st.caption(f"{(item['brand'] or '')[:16]} • {(item['ts'] or '')[:10]}")
            with col3:
                if st.button("⭐" if not item['favorite'] else "★", key=f"fav_{item['db_id']}"):
                    toggle_favorite(item['db_id'], item['favorite'])
                    st.rerun()

def render_world_map():
    st.markdown("### 🗺️ Global Scans Map")
    
    loc = st.session_state.loc
    center_lat = loc.get('lat') or -27.5
    center_lon = loc.get('lon') or 153.0
    
    local_data = get_map_data(200)
    
    if not local_data:
        st.info("No scan data with location yet. Scans will appear here!")
        # Show empty map centered on user
        map_html = f"""
        <div id="map" style="height:400px;width:100%;border-radius:16px;"></div>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map').setView([{center_lat}, {center_lon}], 4);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
            L.marker([{center_lat}, {center_lon}]).addTo(map).bindPopup('Your location');
        </script>
        """
        st.components.v1.html(map_html, height=420)
        return
    
    # Build markers
    markers_js = ""
    for p in local_data[:100]:
        if p.get('lat') and p.get('lon'):
            color = '#ef4444' if p.get('verdict') == 'HIGH_CAUTION' else '#f59e0b' if p.get('verdict') == 'CAUTION' else '#22c55e'
            product_safe = (p.get('product', 'Product') or 'Product')[:25].replace("'", "").replace('"', '')
            p_score = p.get('score', '?')
            markers_js += f"L.circleMarker([{p['lat']}, {p['lon']}], {{radius:8,fillColor:'{color}',color:'#fff',weight:2,fillOpacity:0.8}}).addTo(map).bindPopup('{product_safe}: {p_score}/100');\n"
    
    map_html = f"""
    <div id="map" style="height:400px;width:100%;border-radius:16px;"></div>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], 4);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
        L.marker([{center_lat}, {center_lon}]).addTo(map).bindPopup('Your location');
        {markers_js}
    </script>
    """
    st.components.v1.html(map_html, height=420)
    
    st.markdown(f"**{len(local_data)}** scans on map")

def render_profile():
    st.markdown("### ⚙️ Settings")
    
    loc = st.session_state.loc
    st.markdown("**📍 Location**")
    if loc.get('city') and loc.get('city') != 'Unknown':
        st.success(f"Detected: {loc.get('city')}, {loc.get('country', '')}")
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value=loc.get('city', '') if loc.get('city') != 'Unknown' else '')
    with col2:
        country = st.text_input("Country", value=loc.get('country', '') if loc.get('country') != 'Unknown' else '')
    
    if st.button("Update Location"):
        if city and country:
            code = save_location(city, country)
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER']), 'lat': loc.get('lat'), 'lon': loc.get('lon')}
            st.success("Location updated!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("**🏥 Health Profiles**")
    current_profiles = get_profiles()
    new_profiles = st.multiselect("Select", options=list(HEALTH_PROFILES.keys()), default=current_profiles, format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}")
    if st.button("Save Profiles"):
        save_profiles(new_profiles)
        st.success("Saved!")
    
    st.markdown("---")
    st.markdown("**🚨 Allergens**")
    current_allergies = get_allergies()
    new_allergies = st.multiselect("Select allergens", options=list(ALLERGENS.keys()), default=current_allergies, format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}")
    if st.button("Save Allergens"):
        save_allergies(new_allergies)
        st.success("Saved!")

def render_laws():
    st.markdown("### ⚖️ The 21 Integrity Laws")
    
    for num, law in INTEGRITY_LAWS.items():
        with st.expander(f"Law {num}: {law['name']} ({law['base_points']} pts)"):
            st.write(law['description'])

if __name__ == "__main__":
    main()
