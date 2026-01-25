"""
🌍 HONESTWORLD v32.0 - VALUE GAP DETECTION
Universal Filler Detection • Legal-Safe Vocabulary • Health Grades • Better Share Images

NEW IN v32:
1. Universal "Value Gap" Logic - detects premium marketing + cheap fillers
2. Legal-safe vocabulary (no "scam", "fake", "lie", "avoid")
3. Health Grade (A-E) for food products
4. Value Discrepancy caps score at 60
5. Updated share images (no download messaging)
6. All v31 features preserved
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

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

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

def add_privacy_jitter(lat, lon, meters=75):
    earth_radius = 6371000
    jitter_distance = random.uniform(50, 100)
    angle = random.uniform(0, 2 * math.pi)
    lat_offset = (jitter_distance * math.cos(angle)) / earth_radius * (180 / math.pi)
    lon_offset = (jitter_distance * math.sin(angle)) / (earth_radius * math.cos(math.radians(lat))) * (180 / math.pi)
    return lat + lat_offset, lon + lon_offset

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATEGORIES WITH FUNCTIONAL EXPECTATIONS
# ═══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATEGORIES = {
    "CATEGORY_FOOD": {
        "name": "Food & Beverage", "icon": "🍎",
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "protein_bar", "meal", "spread", "butter", "margarine", "candy", "dessert", "soup", "sauce", "jerky", "juice"],
        "health_profiles": ["diabetes", "heartcondition", "glutenfree", "vegan", "allergyprone", "keto"],
        "water_expected": ["beverage", "soup", "sauce", "drink", "juice", "tea", "coffee"],
        "functional_expectations": {
            "spread": "fat/oil", "butter": "cream/fat", "margarine": "oil/fat",
            "jerky": "meat", "juice": "fruit", "protein_bar": "protein",
            "honey": "honey", "jam": "fruit", "peanut_butter": "peanuts"
        }
    },
    "CATEGORY_SUPPLEMENT": {
        "name": "Supplements", "icon": "💊",
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega", "multivitamin", "pre_workout", "collagen"],
        "health_profiles": ["diabetes", "pregnancy", "vegan", "glutenfree", "allergyprone"],
        "water_expected": [],
        "functional_expectations": {
            "protein": "protein (whey/casein/plant)", "collagen": "collagen",
            "omega": "fish oil/omega-3", "probiotic": "live cultures"
        }
    },
    "CATEGORY_COSMETIC": {
        "name": "Cosmetics & Personal Care", "icon": "🧴",
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "toner", "mask", "deodorant", "micellar", "soap", "bodywash", "oil", "balm"],
        "health_profiles": ["sensitive", "allergyprone", "pregnancy", "baby", "vegan"],
        "water_expected": ["shampoo", "conditioner", "toner", "micellar", "bodywash", "soap", "cleanser", "lotion"],
        "functional_expectations": {
            "serum": "active ingredients", "oil": "oils", "balm": "wax/butter",
            "essence": "concentrated actives", "concentrate": "active ingredients"
        }
    },
    "CATEGORY_ELECTRONICS": {
        "name": "Electronics", "icon": "📱",
        "subtypes": ["phone", "laptop", "tablet", "accessory", "cable", "charger", "audio", "wearable"],
        "health_profiles": [],
        "water_expected": [],
        "functional_expectations": {}
    },
    "CATEGORY_HOUSEHOLD": {
        "name": "Household", "icon": "🧹",
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener", "laundry"],
        "health_profiles": ["sensitive", "allergyprone", "baby", "pregnancy"],
        "water_expected": ["cleaner", "detergent", "disinfectant"],
        "functional_expectations": {}
    },
    "CATEGORY_BOOK": {
        "name": "Books", "icon": "📚",
        "subtypes": ["fiction", "non-fiction", "textbook", "children", "reference"],
        "health_profiles": [],
        "water_expected": [],
        "functional_expectations": {}
    }
}

# Universal cheap fillers that indicate low value when used as primary ingredient
CHEAP_FILLERS = [
    "water", "aqua", "eau",
    "sugar", "glucose", "fructose", "corn syrup", "high fructose corn syrup", "hfcs",
    "maltodextrin", "dextrin", "modified starch", "starch",
    "palm oil", "canola oil", "soybean oil", "sunflower oil", "vegetable oil",
    "cellulose", "microcrystalline cellulose",
    "natural flavor", "artificial flavor", "flavor"
]

# Premium marketing signals
PREMIUM_SIGNALS = [
    "bio", "organic", "natural", "pure", "raw", "clean", "whole",
    "premium", "luxury", "artisan", "craft", "gourmet", "select",
    "pro", "professional", "clinical", "medical-grade", "pharmaceutical",
    "concentrate", "essence", "extract", "potent", "advanced",
    "100%", "real", "authentic", "traditional", "original"
]

# ═══════════════════════════════════════════════════════════════════════════════
# THE 20 INTEGRITY LAWS WITH LOGIC GATES
# ═══════════════════════════════════════════════════════════════════════════════
INTEGRITY_LAWS = {
    1: {
        "name": "Water-Down Deception", 
        "base_points": -15, 
        "description": "Premium-priced product but #1 ingredient is water or cheap filler",
        "tip": "Check if first ingredient matches the premium price",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD"],
        "logic_gate": "APPLY IF product is cream, serum, concentrate, or premium paste. IGNORE IF product is beverage, soup, toner, micellar water, shampoo, or cleanser where water is functionally required.",
        "ignore_subtypes": ["beverage", "soup", "drink", "juice", "shampoo", "conditioner", "toner", "micellar", "bodywash", "cleanser", "tea", "coffee"]
    },
    2: {
        "name": "Fairy Dusting", 
        "base_points": -12, 
        "description": "Hero ingredient advertised on front is below position #5 in actual ingredients list",
        "tip": "Ingredients listed by quantity",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "logic_gate": "ALWAYS APPLY if front claims specific ingredient prominence"
    },
    3: {
        "name": "Split Sugar Trick", 
        "base_points": -18, 
        "description": "Sugar split into 3+ different names to hide total sugar content",
        "tip": "Add up ALL sugar types",
        "applies_to": ["CATEGORY_FOOD"],
        "logic_gate": "APPLY IF product claims 'healthy', 'fitness', 'natural', or 'low sugar'. IGNORE IF product is openly candy, soda, or dessert (consumer expects sugar).",
        "ignore_subtypes": ["candy", "chocolate", "dessert", "soda", "ice cream", "cake", "cookie", "confectionery"]
    },
    4: {
        "name": "Low-Fat Trap", 
        "base_points": -10, 
        "description": "Claims 'low fat' but compensates with high sugar",
        "tip": "Low-fat often means high sugar",
        "applies_to": ["CATEGORY_FOOD"],
        "logic_gate": "APPLY ONLY IF product makes 'low fat' or 'reduced fat' claim"
    },
    5: {
        "name": "Natural Fallacy", 
        "base_points": -12, 
        "description": "Claims 'natural', 'bio', or 'organic' but contains synthetics or claim is unverified",
        "tip": "'Natural' and 'Bio' are often unregulated marketing terms",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_HOUSEHOLD"],
        "logic_gate": "STRICT MODE: If packaging uses green leaves, 'Earth' imagery, or words like 'Pure/Raw/Natural/Bio/Organic' but ingredients contain synthetics OR no certification visible -> DEDUCT",
        "visual_triggers": ["green leaves", "earth", "nature", "wood", "plant", "farm"]
    },
    6: {
        "name": "Made-With Loophole", 
        "base_points": -8, 
        "description": "'Made with real X' but X is minimal amount",
        "tip": "'Made with' requires only tiny amount",
        "applies_to": ["CATEGORY_FOOD"],
        "logic_gate": "APPLY IF front says 'Made with real...' but that ingredient is below position #5"
    },
    7: {
        "name": "Serving Size Trick", 
        "base_points": -10, 
        "description": "Unrealistically small serving size to make nutrition look better",
        "tip": "Check servings per container",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "logic_gate": "APPLY IF serving size is unusually small"
    },
    8: {
        "name": "Slack Fill", 
        "base_points": -8, 
        "description": "Package mostly air/empty space",
        "tip": "Check net weight, not package size",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"],
        "logic_gate": "APPLY IF visible evidence of excessive empty space"
    },
    9: {
        "name": "Spec Inflation", 
        "base_points": -15, 
        "description": "'Up to X speed/capacity' unrealistic",
        "tip": "'Up to' means lab conditions",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS"
    },
    10: {
        "name": "Compatibility Claim", 
        "base_points": -12, 
        "description": "'Universal' with hidden exceptions",
        "tip": "Check compatibility in fine print",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS"
    },
    11: {
        "name": "Military Grade Claim", 
        "base_points": -10, 
        "description": "Claims 'military grade' without MIL-STD cert",
        "tip": "Real military spec cites MIL-STD number",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS"
    },
    12: {
        "name": "Battery Life Claim", 
        "base_points": -12, 
        "description": "Unrealistic battery life claims",
        "tip": "Tested with minimal usage",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS"
    },
    13: {
        "name": "Unverified Clinical Claim", 
        "base_points": -12, 
        "description": "'Clinically proven' or 'scientifically tested' without citing actual study",
        "tip": "Real proof includes study details",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"],
        "logic_gate": "APPLY IF claims 'clinically proven' without visible study citation"
    },
    14: {
        "name": "Concentration Concern", 
        "base_points": -10, 
        "description": "Active ingredient too diluted to be effective",
        "tip": "Effective: Vitamin C 10-20%, Retinol 0.3-1%, Niacinamide 2-5%",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"],
        "logic_gate": "APPLY IF product advertises specific active but concentration not stated or too low"
    },
    15: {
        "name": "Free Trial Concern", 
        "base_points": -15, 
        "description": "'Free' requires credit card/hidden purchase",
        "tip": "Free trial usually auto-charges",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS/SERVICES"
    },
    16: {
        "name": "Unlimited Claim", 
        "base_points": -18, 
        "description": "'Unlimited' with hidden caps",
        "tip": "'Unlimited' rarely means unlimited",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS/SERVICES"
    },
    17: {
        "name": "Lifetime Warranty Claim", 
        "base_points": -10, 
        "description": "'Lifetime warranty' with exclusions",
        "tip": "'Lifetime' has many exclusions",
        "applies_to": ["CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY ONLY TO ELECTRONICS"
    },
    18: {
        "name": "Photo Styling", 
        "base_points": -12, 
        "description": "Package photo much better than actual product likely looks",
        "tip": "Photos are professionally styled",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"],
        "logic_gate": "APPLY IF product photo is clearly stylized beyond reasonable expectation"
    },
    19: {
        "name": "Unverified Certification", 
        "base_points": -15, 
        "description": "Claims certification (organic, bio, cruelty-free) without verifiable certification logo/number",
        "tip": "Real certs show logo and certification ID number",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_ELECTRONICS"],
        "logic_gate": "APPLY IF claims 'certified' but no official logo with ID visible"
    },
    20: {
        "name": "Name Implication", 
        "base_points": -10, 
        "description": "Product name implies ingredient that's barely present",
        "tip": "'Honey Oat' doesn't mean much honey",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"],
        "logic_gate": "APPLY IF product NAME contains ingredient below position #5"
    },
    21: {
        "name": "Value Discrepancy", 
        "base_points": -20, 
        "description": "Premium marketing used to sell product with cheap filler as main ingredient",
        "tip": "Check if #1 ingredient matches the product's implied promise",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"],
        "logic_gate": "APPLY IF premium signals (bio, organic, premium, pro) + cheap filler (#1 ingredient) + functional expectation mismatch. CAPS SCORE AT 60."
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# CITATION DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
CITATIONS = {
    "paraben": {"concern": "Potential endocrine disruption", "severity": "medium", "source": "EU SCCS"},
    "methylparaben": {"concern": "Potential hormone disruption", "severity": "medium", "source": "EU SCCS"},
    "propylparaben": {"concern": "Higher absorption rate", "severity": "medium", "source": "EU SCCS"},
    "butylparaben": {"concern": "Higher potency endocrine activity", "severity": "high", "source": "Danish EPA"},
    "fragrance": {"concern": "Undisclosed chemical mixture, allergen", "severity": "medium", "source": "AAD"},
    "parfum": {"concern": "Undisclosed chemical mixture, allergen", "severity": "medium", "source": "EU Regulation"},
    "sodium lauryl sulfate": {"concern": "Can irritate sensitive skin", "severity": "low", "source": "CIR Panel"},
    "dmdm hydantoin": {"concern": "Formaldehyde-releasing preservative", "severity": "high", "source": "IARC"},
    "triclosan": {"concern": "Endocrine disruption, antibiotic resistance", "severity": "high", "source": "FDA Ban 2016"},
    "oxybenzone": {"concern": "Hormone disruption, coral damage", "severity": "medium", "source": "Hawaii Ban"},
    "trans fat": {"concern": "Heart disease risk", "severity": "high", "source": "FDA Ban"},
    "hydrogenated oil": {"concern": "May contain trans fats", "severity": "high", "source": "FDA/AHA"},
    "high fructose corn syrup": {"concern": "Metabolic concerns when over-consumed", "severity": "medium", "source": "AJCN"},
    "palm oil": {"concern": "Environmental and saturated fat concerns", "severity": "low", "source": "WHO"},
    "red 40": {"concern": "Hyperactivity in sensitive children", "severity": "low", "source": "EFSA"},
    "yellow 5": {"concern": "May cause reactions in sensitive individuals", "severity": "low", "source": "FDA"},
    "aspartame": {"concern": "IARC 'possibly carcinogenic'", "severity": "low", "source": "WHO IARC 2023"},
    "sodium nitrite": {"concern": "Forms nitrosamines when heated", "severity": "medium", "source": "IARC"},
    "titanium dioxide": {"concern": "EU food ban 2022", "severity": "medium", "source": "EFSA"},
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
    "diabetes": {"name": "Diabetes", "icon": "🩺", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin", "sucrose"], "notification": "⚠️ Contains sugar/sweeteners - monitor blood glucose"},
    "heartcondition": {"name": "Heart Health", "icon": "❤️", "applies_to": ["CATEGORY_FOOD"], "ingredient_flags": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat", "palm oil"], "notification": "⚠️ Contains sodium/fats - monitor for heart health"},
    "glutenfree": {"name": "Gluten-Free", "icon": "🌾", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["wheat", "barley", "rye", "gluten", "malt", "spelt", "kamut", "triticale"], "notification": "🚨 Contains or may contain GLUTEN"},
    "vegan": {"name": "Vegan", "icon": "🌱", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"], "ingredient_flags": ["gelatin", "carmine", "honey", "milk", "whey", "casein", "egg", "lanolin", "beeswax", "collagen", "lard", "tallow"], "notification": "⚠️ May contain animal-derived ingredients"},
    "sensitive": {"name": "Sensitive Skin", "icon": "🌸", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"], "ingredient_flags": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate"], "notification": "⚠️ Contains potential irritants - patch test recommended"},
    "pregnancy": {"name": "Pregnancy", "icon": "🤰", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_FOOD"], "ingredient_flags": ["retinol", "retinoid", "salicylic acid", "benzoyl peroxide", "hydroquinone"], "notification": "⚠️ Contains ingredients to discuss with doctor during pregnancy"},
    "allergyprone": {"name": "Allergy Prone", "icon": "🤧", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"], "ingredient_flags": ["peanut", "tree nut", "soy", "milk", "egg", "wheat", "shellfish", "fish", "sesame", "fragrance"], "notification": "⚠️ Contains common allergens - check carefully"},
    "keto": {"name": "Keto Diet", "icon": "🥑", "applies_to": ["CATEGORY_FOOD"], "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "maltodextrin", "wheat", "rice", "potato starch", "starch"], "notification": "⚠️ Contains high-carb ingredients"},
}

ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "malt", "spelt"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "coconut"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu", "lecithin"], "applies_to": ["CATEGORY_FOOD"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise", "meringue"], "applies_to": ["CATEGORY_FOOD"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish"], "applies_to": ["CATEGORY_FOOD"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy", "fish oil"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOCATION-AWARE ALTERNATIVES
# ═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVES_BY_COUNTRY = {
    "AU": {
        "spread": {"name": "Nuttelex Original", "retailer": "Woolworths, Coles", "score": 88, "why": "Australian made, transparent ingredients"},
        "butter": {"name": "Naturli Organic Vegan Block", "retailer": "Woolworths, Coles", "score": 85, "why": "Certified organic, plant-based"},
        "cleanser": {"name": "Cetaphil Gentle Skin Cleanser", "retailer": "Chemist Warehouse, Priceline", "score": 85, "why": "Fragrance-free options"},
        "moisturizer": {"name": "CeraVe Moisturising Cream", "retailer": "Chemist Warehouse, Priceline", "score": 92, "why": "Ceramides, fragrance-free"},
        "serum": {"name": "The Ordinary Niacinamide 10%", "retailer": "Priceline, Mecca", "score": 91, "why": "Transparent formula, effective concentration"},
        "sunscreen": {"name": "Cancer Council SPF 50+", "retailer": "Woolworths, Coles, Chemist Warehouse", "score": 90, "why": "Australian made, high protection"},
        "vitamin": {"name": "Blackmores or Swisse", "retailer": "Chemist Warehouse, Priceline", "score": 88, "why": "Australian TGA approved"},
        "protein": {"name": "Bulk Nutrients WPI", "retailer": "bulknutrients.com.au", "score": 90, "why": "Australian made, high protein %"},
        "default": {"name": "Check Chemist Warehouse or Woolworths", "retailer": "Local stores", "score": None, "why": "Wide range available locally"}
    },
    "US": {
        "spread": {"name": "Earth Balance Organic", "retailer": "Whole Foods, Target", "score": 85, "why": "USDA Organic certified"},
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "CVS, Target, Walmart", "score": 92, "why": "Fragrance-free, ceramides"},
        "moisturizer": {"name": "CeraVe Moisturizing Cream", "retailer": "CVS, Target, Walmart", "score": 94, "why": "Dermatologist recommended"},
        "vitamin": {"name": "Thorne Research", "retailer": "Amazon, Thorne.com", "score": 94, "why": "Third-party tested, NSF certified"},
        "protein": {"name": "Optimum Nutrition Gold Standard", "retailer": "Amazon, GNC", "score": 88, "why": "Third-party tested"},
        "default": {"name": "Check Target or Whole Foods", "retailer": "Target, Whole Foods", "score": None, "why": "Wide selection available"}
    },
    "GB": {
        "spread": {"name": "Flora Plant Butter", "retailer": "Tesco, Sainsbury's", "score": 84, "why": "Plant-based, widely available"},
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "Boots, Superdrug", "score": 92, "why": "Fragrance-free"},
        "vitamin": {"name": "Holland & Barrett", "retailer": "Holland & Barrett, Boots", "score": 85, "why": "Quality tested"},
        "default": {"name": "Check Boots or Tesco", "retailer": "Boots, Tesco", "score": None, "why": "Wide range available"}
    },
    "OTHER": {
        "spread": {"name": "Local organic plant butter", "retailer": "Local health store, iHerb", "score": 80, "why": "Check for certifications"},
        "cleanser": {"name": "CeraVe or Cetaphil", "retailer": "Local pharmacy, iHerb", "score": 92, "why": "Global brands"},
        "vitamin": {"name": "NOW Foods or Nature Made", "retailer": "iHerb, Amazon", "score": 88, "why": "Ships internationally"},
        "default": {"name": "Check iHerb.com", "retailer": "iHerb", "score": None, "why": "International shipping"}
    }
}

def get_alternative(product_name, product_type, product_category, country_code):
    country_alts = ALTERNATIVES_BY_COUNTRY.get(country_code, ALTERNATIVES_BY_COUNTRY['OTHER'])
    search = f"{product_name} {product_type or ''}".lower()
    
    for keyword in ['spread', 'butter', 'cleanser', 'moisturizer', 'serum', 'sunscreen', 'vitamin', 'protein']:
        if keyword in search and keyword in country_alts:
            alt = country_alts[keyword]
            if alt['name'].lower() not in search.lower():
                return alt
    
    if product_category == 'CATEGORY_SUPPLEMENT':
        return country_alts.get('vitamin', country_alts['default'])
    elif product_category == 'CATEGORY_COSMETIC':
        return country_alts.get('moisturizer', country_alts['default'])
    
    return country_alts['default']

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
    """Legal-safe verdicts"""
    if score >= 90: return "EXCEPTIONAL"
    elif score >= 70: return "BUY"
    elif score >= 40: return "CAUTION"
    return "HIGH_CAUTION"

def get_verdict_display(verdict):
    return {
        'EXCEPTIONAL': {'icon': '★', 'text': 'EXCEPTIONAL', 'color': '#06b6d4'},
        'BUY': {'icon': '✓', 'text': 'GOOD TO BUY', 'color': '#22c55e'},
        'CAUTION': {'icon': '!', 'text': 'USE CAUTION', 'color': '#f59e0b'},
        'HIGH_CAUTION': {'icon': '!!', 'text': 'HIGH CAUTION', 'color': '#ef4444'},
        'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}
    }.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH GRADE CALCULATION (Nutri-Score Style)
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_health_grade(nutrition):
    """Calculate health grade A-E based on nutrition data"""
    if not nutrition:
        return None, "Insufficient nutrition data"
    
    negative_points = 0
    positive_points = 0
    
    # Negative points (0-40)
    energy = nutrition.get('energy-kcal_100g', nutrition.get('energy_100g', 0))
    if energy: 
        if energy > 800: negative_points += 10
        elif energy > 600: negative_points += 7
        elif energy > 400: negative_points += 4
    
    sugars = nutrition.get('sugars_100g', 0)
    if sugars:
        if sugars > 45: negative_points += 10
        elif sugars > 31: negative_points += 7
        elif sugars > 18: negative_points += 4
    
    sat_fat = nutrition.get('saturated-fat_100g', 0)
    if sat_fat:
        if sat_fat > 10: negative_points += 10
        elif sat_fat > 6: negative_points += 7
        elif sat_fat > 3: negative_points += 4
    
    sodium = nutrition.get('sodium_100g', 0) * 1000 if nutrition.get('sodium_100g') else nutrition.get('salt_100g', 0) * 400
    if sodium:
        if sodium > 900: negative_points += 10
        elif sodium > 600: negative_points += 7
        elif sodium > 300: negative_points += 4
    
    # Positive points (0-15)
    fiber = nutrition.get('fiber_100g', 0)
    if fiber:
        if fiber > 4.7: positive_points += 5
        elif fiber > 2.8: positive_points += 3
    
    protein = nutrition.get('proteins_100g', 0)
    if protein:
        if protein > 8: positive_points += 5
        elif protein > 4.7: positive_points += 3
    
    # Final score
    final_score = negative_points - positive_points
    
    if final_score <= 0: grade = 'A'
    elif final_score <= 2: grade = 'B'
    elif final_score <= 10: grade = 'C'
    elif final_score <= 18: grade = 'D'
    else: grade = 'E'
    
    details = f"Nutritional density score: {final_score}"
    return grade, details

def get_health_grade_color(grade):
    return {'A': '#22c55e', 'B': '#84cc16', 'C': '#f59e0b', 'D': '#f97316', 'E': '#ef4444'}.get(grade, '#6b7280')

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
    c.execute('''CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT, product_hash TEXT, product_category TEXT, product_type TEXT, score INTEGER, verdict TEXT, ingredients TEXT, violations TEXT, bonuses TEXT, notifications TEXT, thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, lat REAL, lon REAL, geohash TEXT, city TEXT, country TEXT, implied_promise TEXT, value_discrepancy INTEGER DEFAULT 0, health_grade TEXT)''')
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
    
    for col in ['lat', 'lon', 'geohash', 'city', 'country', 'implied_promise', 'value_discrepancy', 'health_grade']:
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

def get_verified_score(product_name, brand=""):
    try:
        product_hash = get_product_hash(product_name, brand)
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT verified_score, scan_count, violations FROM verified_products WHERE product_hash = ?', (product_hash,))
        r = c.fetchone()
        conn.close()
        if r and r[1] >= 2: return {'score': r[0], 'scan_count': r[1], 'violations': json.loads(r[2]) if r[2] else []}
    except: pass
    return None

def save_verified_score(result):
    try:
        product_name, brand = result.get('product_name', ''), result.get('brand', '')
        product_hash = get_product_hash(product_name, brand)
        score = result.get('score', 70)
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT verified_score, scan_count FROM verified_products WHERE product_hash = ?', (product_hash,))
        existing = c.fetchone()
        if existing:
            old_score, count = existing
            weight = 0.9 if count >= 3 else count / (count + 1)
            new_score = int(old_score * weight + score * (1 - weight))
            c.execute('UPDATE verified_products SET verified_score=?, scan_count=?, last_verified=CURRENT_TIMESTAMP, violations=? WHERE product_hash=?', (new_score, count + 1, json.dumps(result.get('violations', [])), product_hash))
        else:
            c.execute('INSERT INTO verified_products (product_hash, product_name, brand, verified_score, product_category, ingredients, violations) VALUES (?,?,?,?,?,?,?)', (product_hash, product_name, brand, score, result.get('product_category', ''), json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', []))))
        conn.commit()
        conn.close()
    except: pass

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
    c.execute('''INSERT INTO scans (scan_id, user_id, product, brand, product_hash, product_category, product_type, score, verdict, ingredients, violations, bonuses, notifications, thumb, lat, lon, geohash, city, country, implied_promise, value_discrepancy, health_grade) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
              (sid, user_id, result.get('product_name', ''), result.get('brand', ''), product_hash, result.get('product_category', ''), result.get('product_type', ''), result.get('score', 0), result.get('verdict', ''), json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), json.dumps(result.get('bonuses', [])), json.dumps(result.get('notifications', [])), thumb, lat, lon, geohash, city, country, result.get('implied_promise', ''), 1 if result.get('value_discrepancy') else 0, result.get('health_grade', '')))
    
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
    save_verified_score(result)
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
    c.execute('SELECT lat, lon, geohash, score, verdict, city, country, product, ts FROM scans WHERE lat IS NOT NULL AND lon IS NOT NULL ORDER BY ts DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{'lat': r[0], 'lon': r[1], 'geohash': r[2], 'score': r[3], 'verdict': r[4], 'city': r[5], 'country': r[6], 'product': r[7], 'ts': r[8]} for r in rows]

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
# SUPABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def supa_ok():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def supa_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}

def supabase_lookup_barcode(barcode):
    if not supa_ok(): return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/products?barcode=eq.{barcode}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.ok:
            data = r.json()
            if data and len(data) > 0:
                p = data[0]
                return {'found': True, 'name': p.get('product_name', ''), 'brand': p.get('brand', ''), 'ingredients': p.get('ingredients', ''), 'product_type': p.get('product_type', ''), 'categories': p.get('categories', ''), 'nutrition': p.get('nutrition', {}), 'image_url': p.get('image_url', ''), 'source': 'HonestWorld Community', 'confidence': 'high', 'crowdsourced': True}
    except: pass
    return None

def supabase_save_product(barcode, product_data, user_id):
    if not supa_ok(): return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/products"
        headers = supa_headers()
        payload = {"barcode": barcode, "product_name": product_data.get('name', ''), "brand": product_data.get('brand', ''), "ingredients": product_data.get('ingredients', ''), "product_type": product_data.get('product_type', ''), "categories": product_data.get('categories', ''), "nutrition": json.dumps(product_data.get('nutrition', {})), "contributed_by": user_id, "created_at": datetime.now().isoformat()}
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.ok
    except: return False

def supabase_get_global_scans(limit=1000):
    if not supa_ok(): return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/scans_log?select=lat,lon,geohash,score,verdict,city,country,product_name,created_at&lat=not.is.null&order=created_at.desc&limit={limit}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(url, headers=headers, timeout=15)
        if r.ok: return r.json()
    except: pass
    return []

def cloud_log_scan(result, location, user_id):
    if supa_ok():
        try:
            url = f"{SUPABASE_URL}/rest/v1/scans_log"
            headers = supa_headers()
            lat, lon = location.get('lat'), location.get('lon')
            if lat and lon:
                lat, lon = add_privacy_jitter(lat, lon)
                geohash = encode_geohash(lat, lon)
            else: geohash = None
            requests.post(url, headers=headers, json={"product_name": result.get('product_name', ''), "brand": result.get('brand', ''), "score": result.get('score', 0), "verdict": result.get('verdict', ''), "city": location.get('city', ''), "country": location.get('country', ''), "user_id": user_id, "lat": lat, "lon": lon, "geohash": geohash}, timeout=5)
        except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# BARCODE FUNCTIONS
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
        c.execute('SELECT product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, description FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]:
            return {'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 'product_type': r[3], 'categories': r[4], 'nutrition': json.loads(r[5]) if r[5] else {}, 'image_url': r[6], 'source': r[7], 'description': r[8] or '', 'cached': True}
    except: pass
    return None

def is_book_isbn(barcode):
    return barcode and len(barcode) >= 10 and barcode[:3] in ['978', '979']

def lookup_open_food_facts(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.3, "🍎 Searching Open Food Facts...")
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
    if progress_callback: progress_callback(0.4, "🧴 Searching Open Beauty Facts...")
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
    if progress_callback: progress_callback(0.5, "📚 Searching Open Library...")
    try:
        r = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{barcode}&format=json&jscmd=data", timeout=12)
        if r.ok:
            d = r.json()
            key = f"ISBN:{barcode}"
            if key in d:
                book = d[key]
                authors = ', '.join([a.get('name', '') for a in book.get('authors', [])]) if book.get('authors') else ''
                return {'found': True, 'name': book.get('title', ''), 'brand': authors, 'ingredients': '', 'categories': 'Books', 'product_type': 'book', 'source': 'Open Library', 'confidence': 'high', 'is_book': True, 'publishers': ', '.join([p.get('name', '') for p in book.get('publishers', [])]) if book.get('publishers') else '', 'publish_date': book.get('publish_date', ''), 'pages': book.get('number_of_pages', '')}
    except: pass
    return None

def lookup_upc_itemdb(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.6, "🔍 Searching UPC Database...")
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
    if not barcode: return {'found': False, 'reason': 'No barcode provided'}
    
    if progress_callback: progress_callback(0.1, "📦 Checking local cache...")
    cached = get_cached_barcode(barcode)
    if cached:
        if progress_callback: progress_callback(1.0, "✓ Found in cache!")
        return cached
    
    if progress_callback: progress_callback(0.2, "🌍 Searching HonestWorld database...")
    supabase_result = supabase_lookup_barcode(barcode)
    if supabase_result:
        if progress_callback: progress_callback(1.0, "✓ Found in HonestWorld!")
        cache_barcode(barcode, supabase_result)
        return supabase_result
    
    if is_book_isbn(barcode):
        result = lookup_open_library(barcode, progress_callback)
        if result:
            if progress_callback: progress_callback(1.0, "✓ Book found!")
            cache_barcode(barcode, result)
            return result
    
    result = lookup_open_food_facts(barcode, progress_callback)
    if result:
        if progress_callback: progress_callback(1.0, "✓ Found!")
        cache_barcode(barcode, result)
        return result
    
    result = lookup_open_beauty_facts(barcode, progress_callback)
    if result:
        if progress_callback: progress_callback(1.0, "✓ Found!")
        cache_barcode(barcode, result)
        return result
    
    result = lookup_upc_itemdb(barcode, progress_callback)
    if result:
        if progress_callback: progress_callback(1.0, "✓ Found!")
        cache_barcode(barcode, result)
        return result
    
    if progress_callback: progress_callback(1.0, "❌ Not found")
    return {'found': False, 'barcode': barcode, 'reason': 'not_in_database'}

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
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L'), img.rotate(90, expand=True), img.rotate(270, expand=True), img.rotate(180)]:
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
        resp = model.generate_content(["Look at this image and find the BARCODE. Read the numeric digits printed BELOW the barcode lines. Return ONLY the digits with NO spaces. If you cannot read it, return: NONE", img])
        text = resp.text.strip().upper()
        if 'NONE' in text or 'CANNOT' in text: return None
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
            if trigger.lower() in ing_text or f"may contain {trigger.lower()}" in full_lower:
                notifications.append({'type': 'allergen', 'key': allergy_key, 'name': allergen['name'], 'icon': allergen['icon'], 'message': f"🚨 Contains or may contain {allergen['name'].upper()}!", 'severity': 'danger'})
                break
    
    return notifications

# ═══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS PROMPT - WITH ALL 21 INTEGRITY LAWS
# ═══════════════════════════════════════════════════════════════════════════════
ANALYSIS_PROMPT = """You are HonestWorld's Marketing Integrity Analyzer.

## MISSION
Analyze products for marketing integrity - identifying gaps between PROMISES (marketing) and REALITY (ingredients/specs).
You MUST check ALL 21 Integrity Laws that apply to this product category.

═══════════════════════════════════════════════════════════════════════════════
STEP 1: CATEGORY & CONTEXT IDENTIFICATION
═══════════════════════════════════════════════════════════════════════════════

1. **Category:** Food/Beverage, Cosmetic, Supplement, Electronics, Household, Book
2. **Subtype:** Be specific (spread, serum, protein powder, beverage, cable)
3. **Implied Promise:** What is this product CLAIMING to be?
4. **Functional Expectation:** What SHOULD be the primary ingredient?
   - Butter/Spread → Fat/Cream/Oil
   - Protein Powder → Protein
   - Aloe Gel → Aloe
   - Serum → Active ingredients
   - Beef Jerky → Meat

═══════════════════════════════════════════════════════════════════════════════
STEP 2: UNIVERSAL "VALUE GAP" ANALYSIS
═══════════════════════════════════════════════════════════════════════════════

### Step A: Check for "Premium Marketing Signals"
- "Bio", "Organic", "Natural", "Pure", "Raw", "Clean"
- "Premium", "Luxury", "Artisan", "Gourmet"
- "Pro", "Professional", "Clinical"
- "Concentrate", "Essence", "100%", "Real"
- Green leaves, earth imagery, wooden textures

### Step B: Check for "Cheap Filler Reality"
Is #1 or #2 ingredient a low-value filler?
- Water/Aqua (when NOT functionally required)
- Sugar, Glucose, Corn Syrup, Maltodextrin
- Cheap oils (Palm, Canola, Soybean) in "premium" products
- Cellulose, Gums, Thickeners as main ingredients

### Step C: The "Premium Paradox" Detection
IF (Marketing uses Premium/Natural/Bio/Pro claims)
AND (Main ingredient contradicts Functional Expectation)
AND (Main ingredient is cheap filler)
THEN → value_discrepancy = TRUE → CAP SCORE AT 60

Context-dependent:
- Water IS expected in: beverages, soups, shampoos, toners, cleansers
- Water is NOT expected in: spreads, serums, concentrates, balms
- Sugar IS expected in: candy, desserts, soda
- Sugar is NOT expected in: "healthy" snacks, protein bars

### Step D: SPLIT INGREDIENT DETECTION (Important!)
Manufacturers split ingredients to hide totals. SUM these:
- SUGARS: sugar, glucose, fructose, dextrose, maltose, corn syrup, HFCS, maltodextrin, honey, agave, invert sugar
- OILS: palm oil, canola oil, soybean oil, sunflower oil, vegetable oil, rapeseed oil

If COMBINED they would be #1 ingredient → Trigger Law #3

═══════════════════════════════════════════════════════════════════════════════
STEP 3: CHECK ALL 21 INTEGRITY LAWS (Apply ALL that are relevant!)
═══════════════════════════════════════════════════════════════════════════════

### FOOD & COSMETIC LAWS (1-8):

**LAW 1: Water-Down Deception (-15 pts)**
- APPLY IF: Product is cream, serum, concentrate, spread, paste, balm where water is NOT the expected main ingredient
- IGNORE IF: beverage, soup, toner, shampoo, cleanser (water expected)
- CHECK: Is water/aqua the #1 ingredient when it shouldn't be?

**LAW 2: Fairy Dusting (-12 pts)**
- APPLY IF: Hero ingredient advertised on front is below position #5 in actual ingredient list
- CHECK: Does packaging prominently feature an ingredient that's barely present?

**LAW 3: Split Ingredient Trick (-18 pts)**
- APPLY IF: Same base ingredient (sugar/oil) appears 3+ times under different names
- CHECK: Sugar + Glucose Syrup + Dextrose = combined #1? Flag it!

**LAW 4: Low-Fat Trap (-10 pts)**
- APPLY IF: Product claims "low fat" or "reduced fat" but compensates with high sugar
- CHECK: Low fat + High sugar = deceptive

**LAW 5: Natural Fallacy (-12 pts)**
- APPLY IF: Claims "natural", "bio", "organic" without certification OR contains synthetic ingredients
- CHECK: Natural imagery but synthetic preservatives or colors?

**LAW 6: Made-With Loophole (-8 pts)**
- APPLY IF: "Made with real X" but X is below position #5
- CHECK: "Made with real fruit" but fruit is 2%?

**LAW 7: Serving Size Trick (-10 pts)**
- APPLY IF: Serving size is unrealistically small to make nutrition look better
- CHECK: Is a "serving" smaller than anyone would actually consume?

**LAW 8: Slack Fill (-8 pts)**
- APPLY IF: Package appears much larger than contents
- CHECK: Is there excessive empty space in packaging?

### ELECTRONICS LAWS (9-12, 15-17):

**LAW 9: Spec Inflation (-15 pts)** [ELECTRONICS ONLY]
- APPLY IF: "Up to X speed/capacity" claims are unrealistic in normal use
- CHECK: "Up to 1000Mbps" but realistically 100?

**LAW 10: Compatibility Claim (-12 pts)** [ELECTRONICS ONLY]
- APPLY IF: "Universal" or "works with all" but has hidden exceptions
- CHECK: Fine print excludes major brands?

**LAW 11: Military Grade Claim (-10 pts)** [ELECTRONICS ONLY]
- APPLY IF: Claims "military grade" without actual MIL-STD certification
- CHECK: Just marketing term without real certification?

**LAW 12: Battery Life Claim (-12 pts)** [ELECTRONICS ONLY]
- APPLY IF: Battery life claims based on minimal usage scenarios
- CHECK: "12 hour battery" but only with screen off?

**LAW 15: Free Trial Concern (-15 pts)** [ELECTRONICS ONLY]
- APPLY IF: "Free" trial requires credit card or has hidden auto-charge
- CHECK: Free = actually free?

**LAW 16: Unlimited Claim (-18 pts)** [ELECTRONICS ONLY]
- APPLY IF: "Unlimited" data/usage but has hidden caps or throttling
- CHECK: Unlimited with asterisks?

**LAW 17: Lifetime Warranty Claim (-10 pts)** [ELECTRONICS ONLY]
- APPLY IF: "Lifetime warranty" but has significant exclusions
- CHECK: Lifetime but excludes normal wear?

### HEALTH & BEAUTY LAWS (13-14):

**LAW 13: Unverified Clinical Claim (-12 pts)**
- APPLY IF: "Clinically proven" or "dermatologist tested" without citing study
- CHECK: Where's the actual clinical study?

**LAW 14: Concentration Concern (-10 pts)**
- APPLY IF: Active ingredient advertised but concentration too low to be effective
- CHECK: "With Vitamin C" but only 0.1%?

### MARKETING & CLAIMS LAWS (18-20):

**LAW 18: Photo Styling (-12 pts)**
- APPLY IF: Package photo significantly better than actual product
- CHECK: Food photo heavily styled vs reality?

**LAW 19: Unverified Certification (-15 pts)**
- APPLY IF: Claims certification (organic, bio, cruelty-free) without verifiable logo/number
- CHECK: "Certified organic" but no cert logo?

**LAW 20: Name Implication (-10 pts)**
- APPLY IF: Product name implies ingredient that's barely present
- CHECK: "Honey Oat Bar" but honey is #8 ingredient?

### VALUE LAW (21):

**LAW 21: Value Discrepancy (-20 pts)** [CAPS SCORE AT 60]
- APPLY IF: Premium marketing (bio/organic/premium) BUT main ingredient is cheap filler
- This is the "Premium Paradox" - triggers automatic score cap at 60
- CHECK: "Bio Premium Spread" but water is #1?

═══════════════════════════════════════════════════════════════════════════════
STEP 4: CITATION HIERARCHY (For flagging ingredients)
═══════════════════════════════════════════════════════════════════════════════

When citing ingredient concerns, prioritize:
1. WHO/FDA/EFSA/EU SCCS (High authority) - Use confidently
2. IARC, National agencies (Medium) - Use with context
3. Single studies (Low) - Mark as "Controversial" not "Dangerous"

If evidence is weak/debated → verdict = CAUTION (Yellow), not HIGH_CAUTION (Red)

═══════════════════════════════════════════════════════════════════════════════
VOCABULARY (Legal-Safe - MANDATORY)
═══════════════════════════════════════════════════════════════════════════════

NEVER use → Use instead:
- "Scam" → "Value Discrepancy"
- "Trash" → "Low Nutritional Density"
- "Lie" → "Inconsistency"
- "Fake" → "Unverified Claim"
- "Avoid" → "High Caution"
- "Dangerous" → "Flagged Ingredient"
- "Bad" → "Below Expectations"

═══════════════════════════════════════════════════════════════════════════════
SCORING (Base: 100)
═══════════════════════════════════════════════════════════════════════════════

Start at 100, deduct for each violation found.
Apply ALL relevant laws - don't stop at just one violation!

Then apply caps:
- If value_discrepancy = TRUE → Cap at 60
- If unverified_certification = TRUE → Cap at 70

Verdicts:
- 90-100: EXCEPTIONAL
- 70-89: BUY
- 40-69: CAUTION
- 0-39: HIGH_CAUTION

Context: Location: {location}
{barcode_context}

═══════════════════════════════════════════════════════════════════════════════
OUTPUT (Valid JSON)
═══════════════════════════════════════════════════════════════════════════════

{{
    "product_name": "Exact name",
    "brand": "Brand",
    "product_category": "CATEGORY_X",
    "product_type": "specific subtype",
    
    "implied_promise": "What marketing claims",
    "functional_expectation": "What #1 ingredient SHOULD be",
    "actual_reality": "What #1 ingredient actually IS",
    
    "value_discrepancy": true/false,
    "value_discrepancy_reason": "Explanation if true",
    "split_ingredients_detected": true/false,
    "split_ingredients_detail": "Which ingredients were split",
    
    "readable": true,
    "score": <0-100>,
    "score_capped": true/false,
    "score_cap_reason": "Why capped",
    
    "violations": [
        {{"law": 1, "name": "Water-Down Deception", "points": -15, "evidence": "Water is #1 in premium spread", "logic_gate": "Applied: spread category expects fat/oil as #1"}}
    ],
    
    "bonuses": [{{"name": "Bonus", "points": <positive>, "evidence": "What earned it"}}],
    
    "ingredients": ["list in order from label"],
    "ingredients_flagged": [{{"name": "ingredient", "concern": "concern", "source": "WHO/FDA/etc", "severity": "high/medium/low"}}],
    "good_ingredients": ["beneficial ones"],
    
    "main_issue": "Primary concern (legal-safe language)",
    "positive": "Main positive",
    
    "front_claims": ["marketing claims from front"],
    "fine_print": ["warnings/disclaimers found"],
    
    "confidence": "high/medium/low",
    "price_value": "poor/fair/good"
}}"""

def analyze_product(images, location, progress_callback, barcode_info=None, user_profiles=None, user_allergies=None):
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": "Add GEMINI_API_KEY to secrets"}
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    
    progress_callback(0.3, "Analyzing with Value Gap detection...")
    
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
            except:
                clean_text = text.replace('```json', '').replace('```', '').strip()
                try: result = json.loads(clean_text)
                except: pass
        
        if not result:
            return {"product_name": "Parse Error", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": "Could not parse AI response"}
        
        progress_callback(0.7, "Validating score...")
        
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        # Apply Value Discrepancy cap
        if result.get('value_discrepancy'):
            score = min(score, 60)
            result['score_capped'] = True
            result['score_cap_reason'] = "Value Discrepancy: Premium marketing with cheap filler"
        
        violations = result.get('violations', [])
        total_deduction = sum(abs(v.get('points', 0)) for v in violations)
        expected_score = 100 - total_deduction
        
        if score > expected_score + 5:
            score = max(0, expected_score)
        
        # Apply cap again after deductions
        if result.get('value_discrepancy'):
            score = min(score, 60)
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        ingredients = result.get('ingredients', [])
        full_text = ' '.join(result.get('fine_print', []) + result.get('front_claims', []))
        
        notifications = check_profile_notifications(ingredients, full_text, user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except Exception as e:
        return {"product_name": "Error", "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": f"Error: {str(e)[:100]}"}

def analyze_from_barcode_data(barcode_info, location, progress_callback, user_profiles=None, user_allergies=None):
    """Analyze product using barcode database information"""
    if not GEMINI_API_KEY:
        return {"product_name": barcode_info.get('name', 'Unknown'), "score": 0, "verdict": "UNCLEAR", "readable": False, "violations": [], "main_issue": "Add GEMINI_API_KEY to secrets"}
    
    progress_callback(0.2, "Preparing analysis...")
    
    product_name = barcode_info.get('name', 'Unknown Product')
    brand = barcode_info.get('brand', '')
    ingredients_text = barcode_info.get('ingredients', '')
    categories = barcode_info.get('categories', '')
    nutrition = barcode_info.get('nutrition', {})
    
    if barcode_info.get('is_book'):
        return {"product_name": product_name, "brand": brand, "product_category": "CATEGORY_BOOK", "product_type": "book", "readable": True, "score": 85, "verdict": "BUY", "violations": [], "bonuses": [], "ingredients": [], "main_issue": "N/A - This is a book", "positive": f"Published: {barcode_info.get('publish_date', 'Unknown')}", "notifications": [], "is_book": True}
    
    progress_callback(0.4, "Analyzing with Value Gap detection...")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    prompt = f"""Analyze this product using HonestWorld's Value Gap Detection:

**Product:** {product_name}
**Brand:** {brand}
**Ingredients:** {ingredients_text if ingredients_text else 'Not available'}
**Categories:** {categories}

APPLY VALUE GAP DETECTION:
1. What is the Implied Promise? (What is this claiming to be?)
2. What is the Functional Expectation? (What SHOULD #1 ingredient be?)
3. What is the Actual Reality? (What IS the #1 ingredient?)
4. Is there a Value Discrepancy? (Premium claims + cheap filler?)

If value_discrepancy = TRUE → Cap score at 60

Use LEGAL-SAFE vocabulary only (no "scam", "fake", "lie", "avoid").
Location: {location.get('city', '')}, {location.get('country', '')}

Return valid JSON."""
    
    progress_callback(0.6, "Applying integrity laws...")
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            result = json.loads(text.replace('```json', '').replace('```', '').strip())
        
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        # Apply Value Discrepancy cap
        if result.get('value_discrepancy'):
            score = min(score, 60)
            result['score_capped'] = True
        
        violations = result.get('violations', [])
        total_deduction = sum(abs(v.get('points', 0)) for v in violations)
        expected_score = 100 - total_deduction
        if score > expected_score + 5:
            score = max(0, expected_score)
        
        if result.get('value_discrepancy'):
            score = min(score, 60)
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['product_name'] = product_name
        result['brand'] = brand
        result['readable'] = True
        
        # Calculate health grade for food
        if nutrition:
            health_grade, health_details = calculate_health_grade(nutrition)
            result['health_grade'] = health_grade
            result['health_grade_details'] = health_details
        
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        ingredients = result.get('ingredients', [])
        full_text = ' '.join(result.get('fine_print', []) + result.get('front_claims', []))
        
        notifications = check_profile_notifications(ingredients, full_text, user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except Exception as e:
        return {"product_name": product_name, "brand": brand, "score": 65, "verdict": "CAUTION", "readable": True, "main_issue": "Limited data - verify claims", "violations": [], "bonuses": [], "ingredients": [], "notifications": [], "confidence": "low"}

# ═══════════════════════════════════════════════════════════════════════════════
# IMPROVED SHARE IMAGES - NO DOWNLOAD MESSAGING
# ═══════════════════════════════════════════════════════════════════════════════
def create_share_image(product_name, brand, score, verdict, implied_promise="", health_grade=None):
    """Create share image - NO EMOJIS, score visible, no AI text"""
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
    
    # Gradient background
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
        font_cta = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        font_title = font_tagline = font_score = font_100 = font_verdict = font_product = font_brand = font_footer = font_cta = font_badge = ImageFont.load_default()
    
    display = get_verdict_display(verdict)
    
    # Title - NO EMOJI
    draw.text((width // 2, 50), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 110), "See Through Marketing Claims", fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
    
    # Score circle - WHITE BACKGROUND for visibility
    circle_y = 340
    circle_radius = 150
    draw.ellipse([width//2 - circle_radius, circle_y - circle_radius, width//2 + circle_radius, circle_y + circle_radius], fill=(255, 255, 255))
    
    # Score number - DARK COLOR for contrast on white circle
    score_color = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    draw.text((width // 2, circle_y - 20), str(score), fill=score_color, anchor="mm", font=font_score)
    draw.text((width // 2, circle_y + 80), "/100", fill=(100, 100, 100), anchor="mm", font=font_100)
    
    # Health grade badge if available
    if health_grade:
        grade_color = get_health_grade_color(health_grade)
        badge_x, badge_y = width // 2 + 120, circle_y - 120
        draw.ellipse([badge_x - 30, badge_y - 30, badge_x + 30, badge_y + 30], fill=grade_color)
        draw.text((badge_x, badge_y), health_grade, fill='white', anchor="mm", font=font_badge)
    
    # Verdict
    draw.text((width // 2, 540), display['text'], fill='white', anchor="mt", font=font_verdict)
    
    # Product name
    pname = product_name[:35] + "..." if len(product_name) > 35 else product_name
    draw.text((width // 2, 620), pname, fill='white', anchor="mt", font=font_product)
    
    # Brand
    if brand:
        draw.text((width // 2, 665), f"by {brand[:30]}", fill=(255, 255, 255, 180), anchor="mt", font=font_brand)
    
    # Implied promise
    if implied_promise:
        draw.text((width // 2, 720), f'Claims: "{implied_promise[:40]}"', fill=(255, 255, 255, 150), anchor="mt", font=font_tagline)
    
    # Divider
    draw.line([(100, 790), (width - 100, 790)], fill=(255, 255, 255, 100), width=2)
    
    # What is HonestWorld - NO EMOJI, NO "AI" TEXT
    draw.text((width // 2, 830), "What is HonestWorld?", fill='white', anchor="mt", font=font_cta)
    
    info_lines = [
        "* Scan any product with your camera",
        "* 21 Integrity Laws check marketing claims",
        "* Get instant honest scores"
    ]
    info_y = 880
    for line in info_lines:
        draw.text((width // 2, info_y), line, fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
        info_y += 35
    
    # Footer
    draw.text((width // 2, 1020), "HonestWorld.app  |  #HonestWorld #SeeTheTruth", fill=(255, 255, 255, 150), anchor="mt", font=font_footer)
    
    return img

def create_story_image(product_name, brand, score, verdict, implied_promise="", value_discrepancy=False, health_grade=None):
    """Create vertical story image - NO EMOJIS, score visible"""
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
    
    # Gradient background
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
    
    # Title - NO EMOJI
    draw.text((width // 2, 120), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 190), "See Through Marketing Claims", fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
    
    # Score circle - WHITE for visibility
    circle_y = 500
    circle_radius = 200
    draw.ellipse([width//2 - circle_radius, circle_y - circle_radius, width//2 + circle_radius, circle_y + circle_radius], fill=(255, 255, 255))
    
    # Score - DARK COLOR for contrast
    score_color = (int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16))
    draw.text((width // 2, circle_y - 30), str(score), fill=score_color, anchor="mm", font=font_score)
    draw.text((width // 2, circle_y + 100), "/100", fill=(100, 100, 100), anchor="mm", font=font_100)
    
    # Health grade badge
    if health_grade:
        grade_color = get_health_grade_color(health_grade)
        badge_x, badge_y = width // 2 + 160, circle_y - 160
        draw.ellipse([badge_x - 40, badge_y - 40, badge_x + 40, badge_y + 40], fill=grade_color)
        draw.text((badge_x, badge_y), health_grade, fill='white', anchor="mm", font=font_badge)
    
    # Verdict
    draw.text((width // 2, 780), display['text'], fill='white', anchor="mt", font=font_verdict)
    
    # Value Discrepancy warning - NO EMOJI
    if value_discrepancy:
        draw.rectangle([(100, 860), (width - 100, 920)], fill=(0, 0, 0, 80))
        draw.text((width // 2, 890), "VALUE DISCREPANCY DETECTED", fill='white', anchor="mm", font=font_tagline)
    
    # Product info
    pname = product_name[:32] + "..." if len(product_name) > 32 else product_name
    draw.text((width // 2, 960), pname, fill='white', anchor="mt", font=font_product)
    if brand:
        draw.text((width // 2, 1015), f"by {brand[:28]}", fill=(255, 255, 255, 180), anchor="mt", font=font_brand)
    
    # Implied promise
    if implied_promise:
        draw.text((width // 2, 1090), f'Claims: "{implied_promise[:35]}"', fill=(255, 255, 255, 150), anchor="mt", font=font_tagline)
    
    # Divider
    draw.line([(100, 1160), (width - 100, 1160)], fill=(255, 255, 255, 80), width=2)
    
    # What is HonestWorld section - NO EMOJIS, NO "AI" TEXT
    draw.text((width // 2, 1220), "What is HonestWorld?", fill='white', anchor="mt", font=font_cta)
    
    info_lines = [
        "* Scan any product with your camera",
        "* 21 Integrity Laws check marketing",
        "* Exposes gaps between claims & reality",
        "* Get instant honest scores"
    ]
    
    y_pos = 1290
    for line in info_lines:
        draw.text((width // 2, y_pos), line, fill=(255, 255, 255, 200), anchor="mt", font=font_tagline)
        y_pos += 50
    
    # CTA - NO EMOJI
    draw.text((width // 2, 1540), "Know before you buy!", fill='white', anchor="mt", font=font_cta)
    draw.text((width // 2, 1600), "Follow for more product exposes", fill=(255, 255, 255, 180), anchor="mt", font=font_tagline)
    
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
.verdict-icon { font-size: 4rem; margin-bottom: 0.5rem; }
.verdict-text { font-size: 1.3rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; }
.verdict-score { font-size: 4rem; font-weight: 900; }

.stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; }

.value-alert { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 3px solid #ef4444; border-radius: 16px; padding: 1.2rem; margin: 1rem 0; animation: pulse 2s infinite; }
.value-alert-title { font-size: 1.1rem; font-weight: 800; color: #dc2626; margin-bottom: 0.5rem; }
.value-alert-text { font-size: 0.9rem; color: #7f1d1d; }
@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); } 50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } }

.health-badge { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 50%; font-weight: 900; font-size: 1.5rem; color: white; }

.notif-danger { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-left: 5px solid #ef4444; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }
.notif-warning { background: linear-gradient(135deg, #fffbeb, #fef3c7); border-left: 5px solid #f59e0b; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }

.alert-issue { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.alert-positive { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

.implied-promise { background: linear-gradient(135deg, #e0e7ff, #c7d2fe); border-left: 4px solid #6366f1; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

.law-box { background: white; border-left: 4px solid #ef4444; border-radius: 0 12px 12px 0; padding: 0.8rem; margin: 0.4rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.law-title { font-weight: 700; color: #dc2626; font-size: 0.95rem; }
.law-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }
.law-gate { font-size: 0.75rem; color: #6366f1; font-style: italic; margin-top: 0.2rem; }

.bonus-box { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-left: 4px solid #22c55e; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.3rem 0; }

.ing-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0; }
.ing-badge { padding: 0.3rem 0.6rem; border-radius: 16px; font-weight: 600; font-size: 0.75rem; }
.ing-red { background: #fee2e2; color: #dc2626; }
.ing-yellow { background: #fef3c7; color: #b45309; }
.ing-green { background: #dcfce7; color: #16a34a; }

.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }
.alt-score { background: #22c55e; color: white; padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.8rem; }

.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0.6rem; border-radius: 10px; color: white; text-decoration: none; font-weight: 600; font-size: 0.7rem; transition: transform 0.2s; }
.share-btn:hover { transform: translateY(-2px); }
.share-btn span { font-size: 1.2rem; margin-bottom: 0.2rem; }

.progress-box { background: white; border-radius: 16px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 0.75rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }

.loc-badge { background: #dbeafe; color: #1d4ed8; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.7rem; font-weight: 600; display: inline-block; margin-top: 0.25rem; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.75rem; font-weight: 700; }
.cat-badge { background: #e0e7ff; color: #4338ca; padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.7rem; font-weight: 600; }

.contribute-box { background: linear-gradient(135deg, #fef3c7, #fde68a); border: 2px dashed #f59e0b; border-radius: 16px; padding: 1.5rem; text-align: center; margin: 1rem 0; }
.contribute-title { font-size: 1.2rem; font-weight: 700; color: #92400e; margin-bottom: 0.5rem; }

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stCameraInput"] video { max-height: 180px !important; border-radius: 12px; }
.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; font-size: 0.85rem; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }
[data-testid="stExpander"] { background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    for key in ['result', 'scan_id', 'admin', 'barcode_info', 'show_result', 'contribute_mode', 'contribute_barcode']:
        if key not in st.session_state:
            st.session_state[key] = None if key not in ['admin', 'show_result', 'contribute_mode'] else False
    
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        if saved and saved.get('city') not in ['Unknown', '', None]:
            st.session_state.loc = saved
        else:
            detected = detect_location_enhanced()
            st.session_state.loc = detected
            if detected.get('city') not in ['Unknown', ''] and not detected.get('needs_manual'):
                save_location(detected['city'], detected['country'], detected.get('lat'), detected.get('lon'))
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🌍 HonestWorld")
        loc = st.session_state.loc
        if loc.get('city') and loc.get('city') not in ['Unknown', '']:
            location_text = f"📍 {loc.get('city')}"
            if loc.get('region'): location_text += f", {loc.get('region')}"
            if loc.get('country'): location_text += f", {loc.get('country')}"
            st.markdown(f"<span class='loc-badge'>{location_text}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='loc-badge'>📍 Set location in Profile</span>", unsafe_allow_html=True)
    with col2:
        stats = get_stats()
        if stats['streak'] > 0:
            st.markdown(f"<span class='streak-badge'>🔥 {stats['streak']}</span>", unsafe_allow_html=True)
    
    st.markdown(f"""<div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>{stats['scans']}</div><div class='stat-lbl'>Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['flagged']}</div><div class='stat-lbl'>Flagged</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['best_streak']}</div><div class='stat-lbl'>Best Streak</div></div>
    </div>""", unsafe_allow_html=True)
    
    tab_scan, tab_history, tab_map, tab_profile, tab_laws = st.tabs(["📷 Scan", "📋 History", "🗺️ World Map", "👤 Profile", "⚖️ Laws"])
    
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
    
    st.markdown(f"<center style='color:#94a3b8;font-size:0.7rem;margin-top:1rem;'>🌍 HonestWorld v{VERSION}</center>", unsafe_allow_html=True)

def render_scan_interface(user_id):
    input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
    images = []
    
    if input_method == "📷 Camera":
        st.caption("📸 Point at product label")
        cam_img = st.camera_input("", label_visibility="collapsed")
        if cam_img:
            images = [cam_img]
            st.success("✅ Photo ready")
            if st.checkbox("+ Add back label"):
                cam2 = st.camera_input("Back", label_visibility="collapsed", key="cam2")
                if cam2: images.append(cam2)
    
    elif input_method == "📁 Upload":
        uploaded = st.file_uploader("", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded:
            images = uploaded[:3]
            st.success(f"✅ {len(images)} image(s)")
    
    else:
        st.markdown("### 📊 Barcode Scanner")
        barcode_img = st.camera_input("", label_visibility="collapsed", key="barcode_cam")
        
        if barcode_img:
            with st.spinner("📖 Reading barcode..."):
                barcode_num = try_decode_barcode_pyzbar(barcode_img)
                if not barcode_num:
                    barcode_num = ai_read_barcode(barcode_img)
            
            if barcode_num:
                st.info(f"📊 Barcode: **{barcode_num}**")
                progress_container = st.empty()
                def update_progress(pct, msg):
                    progress_container.markdown(f"<div class='progress-box'><div style='font-size:1.1rem;font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
                
                barcode_info = waterfall_barcode_search(barcode_num, update_progress)
                progress_container.empty()
                
                if barcode_info.get('found'):
                    st.success(f"✅ **{barcode_info.get('name', '')}**")
                    if barcode_info.get('brand'):
                        st.caption(f"by {barcode_info.get('brand')} • Source: {barcode_info.get('source', '')}")
                    
                    if barcode_info.get('ingredients'):
                        with st.expander("📋 Ingredients"):
                            st.write(barcode_info.get('ingredients', '')[:500])
                    
                    st.session_state.barcode_info = barcode_info
                    st.session_state.barcode_only = True
                    images = [barcode_img]
                else:
                    st.markdown("""<div class='contribute-box'><div class='contribute-title'>🆕 Product Not Found!</div><p>Help the community by adding it.</p></div>""", unsafe_allow_html=True)
                    if st.button("📸 Contribute This Product", use_container_width=True, type="primary"):
                        st.session_state.contribute_mode = True
                        st.session_state.contribute_barcode = barcode_num
                        st.rerun()
            else:
                st.error("❌ Could not read barcode. Try better lighting.")
    
    if images or st.session_state.get('barcode_info'):
        if st.button("🔍 ANALYZE", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                icons = ['🔍', '📋', '⚖️', '✨']
                icon = icons[min(int(pct * 4), 3)]
                progress_ph.markdown(f"<div class='progress-box'><div style='font-size:2rem;'>{icon}</div><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
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
                cloud_log_scan(result, st.session_state.loc, user_id)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.barcode_info = None
                st.session_state.barcode_only = False
                st.rerun()
            else:
                st.error("❌ Could not analyze. Try a clearer photo.")

def render_contribute_interface(user_id):
    st.markdown("### 🆕 Contribute New Product")
    barcode = st.session_state.get('contribute_barcode', '')
    st.info(f"📊 Barcode: **{barcode}**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Front Label:**")
        front_img = st.camera_input("Front", label_visibility="collapsed", key="contrib_front")
    with col2:
        st.markdown("**Back/Ingredients:**")
        back_img = st.camera_input("Back", label_visibility="collapsed", key="contrib_back")
    
    product_name = st.text_input("Product Name", placeholder="e.g., Chocolate Chip Cookies")
    brand = st.text_input("Brand", placeholder="e.g., Nabisco")
    
    images = []
    if front_img: images.append(front_img)
    if back_img: images.append(back_img)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.contribute_mode = False
            st.session_state.contribute_barcode = None
            st.rerun()
    
    with col2:
        if images and st.button("✅ Submit & Analyze", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                progress_ph.markdown(f"<div class='progress-box'><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
            result = analyze_product(images, st.session_state.loc, update_prog, None, get_profiles(), get_allergies())
            if product_name: result['product_name'] = product_name
            if brand: result['brand'] = brand
            progress_ph.empty()
            
            if result.get('readable', True) and result.get('score', 0) > 0:
                product_data = {'name': result.get('product_name', ''), 'brand': result.get('brand', ''), 'ingredients': ', '.join(result.get('ingredients', [])), 'product_type': result.get('product_type', ''), 'categories': result.get('product_category', '')}
                supabase_save_product(barcode, product_data, user_id)
                cache_barcode(barcode, product_data)
                
                thumb = None
                try:
                    images[0].seek(0)
                    img = Image.open(images[0])
                    img.thumbnail((100, 100))
                    buf = BytesIO()
                    img.save(buf, format='JPEG', quality=60)
                    thumb = buf.getvalue()
                except: pass
                
                scan_id = save_scan(result, user_id, thumb, st.session_state.loc)
                cloud_log_scan(result, st.session_state.loc, user_id)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.contribute_mode = False
                st.session_state.contribute_barcode = None
                st.success("🎉 Product added to HonestWorld database!")
                st.rerun()
            else:
                st.error("❌ Could not analyze. Try clearer photos.")

def display_result(result, user_id):
    score = result.get('score', 0)
    verdict = result.get('verdict', 'UNCLEAR')
    product_category = result.get('product_category', 'CATEGORY_FOOD')
    product_type = result.get('product_type', '')
    implied_promise = result.get('implied_promise', '')
    value_discrepancy = result.get('value_discrepancy', False)
    health_grade = result.get('health_grade')
    display = get_verdict_display(verdict)
    
    # VALUE DISCREPANCY ALERT - TOP OF SCREEN (Primary Alert)
    if value_discrepancy:
        reason = result.get('value_discrepancy_reason', 'Premium marketing used with cheap filler ingredients')
        st.markdown(f"""<div class='value-alert'>
            <div class='value-alert-title'>⚠️ VALUE DISCREPANCY DETECTED</div>
            <div class='value-alert-text'>{reason}</div>
            <div class='value-alert-text' style='margin-top:0.5rem;font-weight:600;'>Score capped at 60/100</div>
        </div>""", unsafe_allow_html=True)
    
    # Main verdict card
    st.markdown(f"""<div class='verdict-card verdict-{verdict.lower()}'>
        <div class='verdict-icon'>{display['icon']}</div>
        <div class='verdict-text'>{display['text']}</div>
        <div class='verdict-score'>{score}<span style='font-size:1.5rem;'>/100</span></div>
    </div>""", unsafe_allow_html=True)
    
    # Product info and health grade
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### {result.get('product_name', 'Unknown')}")
        if result.get('brand'):
            st.markdown(f"*by {result.get('brand')}*")
    with col2:
        if health_grade:
            grade_color = get_health_grade_color(health_grade)
            st.markdown(f"<div class='health-badge' style='background:{grade_color};'>{health_grade}</div><div style='font-size:0.7rem;color:#64748b;text-align:center;'>Health</div>", unsafe_allow_html=True)
    
    cat_info = PRODUCT_CATEGORIES.get(product_category, {})
    st.markdown(f"<span class='cat-badge'>{cat_info.get('icon', '📦')} {cat_info.get('name', 'Product')}</span>", unsafe_allow_html=True)
    
    # Implied Promise
    if implied_promise:
        st.markdown(f"<div class='implied-promise'>🎭 <strong>Marketing Promise:</strong> \"{implied_promise}\"</div>", unsafe_allow_html=True)
    
    # Functional expectation vs reality
    if result.get('functional_expectation') and result.get('actual_reality'):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Expected:** {result.get('functional_expectation')}")
        with col2:
            st.markdown(f"**Reality:** {result.get('actual_reality')}")
    
    # Notifications
    for notif in result.get('notifications', []):
        css_class = 'notif-danger' if notif.get('severity') == 'danger' else 'notif-warning'
        st.markdown(f"""<div class='{css_class}'><strong>{notif.get('icon', '⚠️')} {notif.get('name', 'Alert')}</strong><br>{notif.get('message', '')}</div>""", unsafe_allow_html=True)
    
    main_issue = result.get('main_issue', '')
    if main_issue and main_issue.lower() not in ['clean formula', 'none', '', 'n/a', 'no major issues']:
        st.markdown(f"<div class='alert-issue'>⚠️ <strong>{main_issue}</strong></div>", unsafe_allow_html=True)
    
    if result.get('positive'):
        st.markdown(f"<div class='alert-positive'>✅ <strong>{result.get('positive')}</strong></div>", unsafe_allow_html=True)
    
    # Price/Value
    if result.get('price_value'):
        pv = result.get('price_value', '').lower()
        pv_color = '#22c55e' if pv == 'good' else '#f59e0b' if pv == 'fair' else '#ef4444'
        st.markdown(f"<div style='padding:0.5rem;background:#f1f5f9;border-radius:8px;margin:0.5rem 0;'><strong>💰 Value:</strong> <span style='color:{pv_color};font-weight:700;'>{pv.upper()}</span></div>", unsafe_allow_html=True)
    
    # Alternative
    if not result.get('is_book'):
        country_code = st.session_state.loc.get('code', 'OTHER')
        alt = get_alternative(result.get('product_name', ''), product_type, product_category, country_code)
        alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
        st.markdown(f"""<div class='alt-card'><strong>💚 {'Better Alternative' if verdict in ['CAUTION', 'HIGH_CAUTION'] else 'Similar Quality'}:</strong><br><span style='font-size:1.05rem;font-weight:600;'>{alt['name']}</span> {alt_score_html}<br><span style='color:#16a34a;'>{alt['why']}</span><br><div style='font-size:0.85rem;color:#64748b;margin-top:0.3rem;'>📍 {alt.get('retailer', 'Local stores')}</div></div>""", unsafe_allow_html=True)
    
    # Violations
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Integrity Issues ({len(violations)})", expanded=True):
            for v in violations:
                law_num = v.get('law')
                law_text = f"Law {law_num}: " if law_num else ""
                evidence = str(v.get('evidence', '')).replace('<', '&lt;').replace('>', '&gt;')
                logic_gate = v.get('logic_gate', '')
                gate_html = f"<div class='law-gate'>🔀 {logic_gate}</div>" if logic_gate else ""
                st.markdown(f"""<div class='law-box'><div class='law-title'>{law_text}{v.get('name', 'Issue')} ({v.get('points', 0)} pts)</div><div class='law-evidence'>{evidence}</div>{gate_html}</div>""", unsafe_allow_html=True)
    
    # Bonuses
    bonuses = result.get('bonuses', [])
    if bonuses:
        with st.expander(f"✨ Positive Points ({len(bonuses)})", expanded=False):
            for b in bonuses:
                st.markdown(f"""<div class='bonus-box'><strong>+{b.get('points', 0)}: {b.get('name', '')}</strong><br><span style='font-size:0.85rem;'>{b.get('evidence', '')}</span></div>""", unsafe_allow_html=True)
    
    # Ingredients
    ingredients_flagged = result.get('ingredients_flagged', [])
    if ingredients_flagged or result.get('ingredients'):
        with st.expander("🧪 Ingredients Analysis", expanded=False):
            if ingredients_flagged:
                st.markdown("**Flagged:**")
                for ing in ingredients_flagged:
                    ing_name = ing.get('name', '')
                    concern = ing.get('concern', '')
                    citation = get_citation(ing_name)
                    css_class = 'ing-red' if citation and citation.get('severity') in ['high', 'medium'] else 'ing-yellow'
                    source_text = citation.get('source', 'Verify') if citation else 'Verify'
                    st.markdown(f"<span class='ing-badge {css_class}'>{ing_name}</span> {concern} <span style='font-size:0.7rem;color:#059669;'>• {source_text}</span>", unsafe_allow_html=True)
            
            good = result.get('good_ingredients', [])
            if good:
                st.markdown("**Good:**")
                badges = " ".join([f"<span class='ing-badge ing-green'>{g}</span>" for g in good[:10]])
                st.markdown(f"<div class='ing-row'>{badges}</div>", unsafe_allow_html=True)
            
            if result.get('ingredients'):
                st.markdown(f"**All:** {', '.join(result.get('ingredients', [])[:30])}")
    
    # Share
    st.markdown("### 📤 Share")
    share_img = create_share_image(result.get('product_name', ''), result.get('brand', ''), score, verdict, implied_promise, health_grade)
    story_img = create_story_image(result.get('product_name', ''), result.get('brand', ''), score, verdict, implied_promise, value_discrepancy, health_grade)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post (1080×1080)", data=image_to_bytes(share_img), file_name=f"hw_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story (1080×1920)", data=image_to_bytes(story_img), file_name=f"hw_story_{score}.png", mime="image/png", use_container_width=True)
    
    share_text = urllib.parse.quote(f"🔍 Scanned {result.get('product_name', '')} with HonestWorld - {score}/100 ({verdict})! See through marketing claims. #HonestWorld #SeeTheTruth")
    
    st.markdown(f"""<div class='share-grid'>
        <a href='https://twitter.com/intent/tweet?text={share_text}' target='_blank' class='share-btn' style='background:#1DA1F2;'><span>𝕏</span>Twitter</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={share_text}' target='_blank' class='share-btn' style='background:#4267B2;'><span>f</span>Facebook</a>
        <a href='https://wa.me/?text={share_text}' target='_blank' class='share-btn' style='background:#25D366;'><span>💬</span>WhatsApp</a>
        <a href='https://t.me/share/url?text={share_text}' target='_blank' class='share-btn' style='background:#0088cc;'><span>✈️</span>Telegram</a>
        <a href='https://www.instagram.com/' target='_blank' class='share-btn' style='background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);'><span>📷</span>Instagram</a>
        <a href='https://www.tiktok.com/' target='_blank' class='share-btn' style='background:#000;'><span>♪</span>TikTok</a>
    </div>""", unsafe_allow_html=True)
    
    if st.button("🔄 Scan Another", use_container_width=True):
        st.session_state.result = None
        st.session_state.scan_id = None
        st.session_state.show_result = False
        st.rerun()

def render_history(user_id):
    history = get_history(user_id, 30)
    if not history:
        st.info("📋 No scans yet! Start scanning products.")
    else:
        for item in history:
            score = item['score']
            color = '#06b6d4' if score >= 90 else '#22c55e' if score >= 70 else '#f59e0b' if score >= 40 else '#ef4444'
            fav = "⭐ " if item['favorite'] else ""
            col1, col2, col3 = st.columns([0.6, 3.4, 0.5])
            with col1:
                st.markdown(f"<div style='width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;color:white;font-size:0.85rem;background:{color};'>{score}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{fav}{item['product'][:28]}**")
                st.caption(f"{item['brand'][:16] if item['brand'] else ''} • {item['ts'][:10]}")
            with col3:
                if st.button("⭐" if not item['favorite'] else "★", key=f"fav_{item['db_id']}"):
                    toggle_favorite(item['db_id'], item['favorite'])
                    st.rerun()

def render_world_map():
    st.markdown("### 🗺️ Global Live Map")
    st.caption("See where products are being scanned around the world")
    
    loc = st.session_state.loc
    center_lat = loc.get('lat', -27.5)
    center_lon = loc.get('lon', 153.0)
    
    local_data = get_map_data(500)
    global_data = supabase_get_global_scans(1000)
    
    all_points = []
    for d in local_data:
        if d.get('lat') and d.get('lon'):
            all_points.append({'lat': d['lat'], 'lon': d['lon'], 'score': d.get('score', 70), 'verdict': d.get('verdict', 'CAUTION'), 'product': d.get('product', ''), 'city': d.get('city', '')})
    for d in global_data:
        if d.get('lat') and d.get('lon'):
            all_points.append({'lat': d['lat'], 'lon': d['lon'], 'score': d.get('score', 70), 'verdict': d.get('verdict', 'CAUTION'), 'product': d.get('product_name', ''), 'city': d.get('city', '')})
    
    map_html = f"""
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <div id="map" style="height: 400px; width: 100%; border-radius: 16px;"></div>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], 10);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{attribution: '© OpenStreetMap'}}).addTo(map);
        var userMarker = L.marker([{center_lat}, {center_lon}]).addTo(map).bindPopup("<b>📍 You are here</b><br>{loc.get('city', 'Unknown')}");
        var heatData = ["""
    
    heat_points = [f"[{p['lat']}, {p['lon']}, {0.8 if p.get('verdict') == 'HIGH_CAUTION' else 0.5}]" for p in all_points[:500] if p.get('lat') and p.get('lon')]
    map_html += ','.join(heat_points)
    
    map_html += """];
        if (heatData.length > 0) { L.heatLayer(heatData, {radius: 25, blur: 15, gradient: {0.4: 'blue', 0.6: 'lime', 0.8: 'yellow', 1: 'red'}}).addTo(map); }
    """
    
    for p in all_points[:50]:
        if p.get('lat') and p.get('lon'):
            color = '#ef4444' if p.get('verdict') == 'HIGH_CAUTION' else '#f59e0b' if p.get('verdict') == 'CAUTION' else '#22c55e'
            product_safe = (p.get('product', 'Product')[:30] or 'Product').replace("'", "\\'").replace('"', '\\"')
            p_score = p.get('score', '?')
            map_html += f"L.circleMarker([{p['lat']}, {p['lon']}], {{radius: 6, fillColor: '{color}', color: '#fff', weight: 2, fillOpacity: 0.8}}).addTo(map).bindPopup('<b>{product_safe}</b><br>Score: {p_score}/100');"
    
    map_html += "</script>"
    st.components.v1.html(map_html, height=450)
    
    st.markdown(f"""<div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>{len(local_data)}</div><div class='stat-lbl'>Local Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{len(global_data)}</div><div class='stat-lbl'>Global Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{len(set(p.get('city', '') for p in all_points if p.get('city')))}</div><div class='stat-lbl'>Cities</div></div>
    </div>""", unsafe_allow_html=True)

def render_profile():
    st.markdown("### ⚙️ Settings")
    st.markdown("**📍 Location**")
    loc = st.session_state.loc
    if loc.get('city') and loc.get('city') not in ['Unknown', '']:
        st.success(f"✅ Detected: {loc.get('city')}, {loc.get('region', '')} {loc.get('country', '')}")
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value=loc.get('city', '') if loc.get('city') not in ['Unknown'] else '', placeholder="e.g., Redland Bay")
    with col2:
        country = st.text_input("Country", value=loc.get('country', '') if loc.get('country') not in ['Unknown'] else '', placeholder="e.g., Australia")
    
    if st.button("Update Location"):
        if city and country:
            code = save_location(city, country, loc.get('lat'), loc.get('lon'))
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER']), 'lat': loc.get('lat'), 'lon': loc.get('lon')}
            st.success(f"✅ Location set to {city}, {country}")
            st.rerun()
    
    if st.button("🔄 Auto-detect"):
        detected = detect_location_enhanced()
        if detected.get('city') not in ['Unknown', '']:
            st.session_state.loc = detected
            save_location(detected['city'], detected['country'], detected.get('lat'), detected.get('lon'))
            st.success(f"✅ Detected: {detected['city']}, {detected['country']}")
            st.rerun()
    
    st.markdown("---")
    st.markdown("**🏥 Health Profiles**")
    current_profiles = get_profiles()
    new_profiles = st.multiselect("Select profiles", options=list(HEALTH_PROFILES.keys()), default=current_profiles, format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}")
    if st.button("Save Profiles"):
        save_profiles(new_profiles)
        st.success("✅ Saved!")
    
    st.markdown("---")
    st.markdown("**🚨 Allergen Alerts**")
    current_allergies = get_allergies()
    new_allergies = st.multiselect("Select allergens", options=list(ALLERGENS.keys()), default=current_allergies, format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}")
    if st.button("Save Allergens"):
        save_allergies(new_allergies)
        st.success("✅ Saved!")

def render_laws():
    st.markdown("### ⚖️ The 21 Integrity Laws")
    st.caption("With Logic Gates and Value Gap Detection")
    
    categories = {
        "🧪 Ingredients (1-6)": [1, 2, 3, 4, 5, 6],
        "📦 Packaging (7, 8, 18)": [7, 8, 18],
        "📱 Electronics (9-12, 15-17)": [9, 10, 11, 12, 15, 16, 17],
        "💄 Beauty/Health (13-14)": [13, 14],
        "🏷️ Claims (19-20)": [19, 20],
        "💰 Value (21)": [21]
    }
    
    for cat_name, nums in categories.items():
        with st.expander(cat_name, expanded=cat_name == "💰 Value (21)"):
            for n in nums:
                if n in INTEGRITY_LAWS:
                    law = INTEGRITY_LAWS[n]
                    st.markdown(f"**Law {n}: {law['name']}** ({law['base_points']} pts)")
                    st.write(law['description'])
                    st.caption(f"💡 {law['tip']}")
                    if law.get('logic_gate'):
                        st.markdown(f"🔀 *Logic Gate: {law['logic_gate']}*")
                    st.markdown("---")

if __name__ == "__main__":
    main()
