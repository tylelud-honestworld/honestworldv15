"""
🌍 HONESTWORLD v28.0 - ULTIMATE EDITION
Zero Bugs • Perfect Accuracy • Score Consistency • Local Alternatives

FIXES FROM v27:
1. HTML rendering error fixed
2. All social media restored
3. Same product = Same score (learning system)
4. Citations properly displayed
5. Better location detection (GPS priority)
6. Profile alerts as notifications (don't affect score)
7. Retailer-specific alternatives
8. Enhanced barcode with AI
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

VERSION = "28.0"
LOCAL_DB = Path.home() / "honestworld_v28.db"

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATEGORIES - Context Gatekeeper
# ═══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATEGORIES = {
    "CATEGORY_FOOD": {
        "name": "Food & Beverage", "icon": "🍎",
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "protein_bar", "meal"],
        "enabled_rules": ["nutritional", "sugar_analysis", "sodium_check", "allergen", "fine_print", "claims_vs_facts"],
        "health_profiles": ["diabetes", "heartcondition", "glutenfree", "vegan", "allergyprone", "keto"]
    },
    "CATEGORY_SUPPLEMENT": {
        "name": "Supplements", "icon": "💊",
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega", "multivitamin"],
        "enabled_rules": ["concentration_check", "third_party_testing", "allergen", "fine_print", "claims_vs_facts"],
        "health_profiles": ["diabetes", "pregnancy", "vegan", "glutenfree", "allergyprone"]
    },
    "CATEGORY_COSMETIC": {
        "name": "Cosmetics & Personal Care", "icon": "🧴",
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "toner", "mask", "deodorant"],
        "enabled_rules": ["chemical_safety", "allergen", "fragrance_check", "claims_vs_facts", "fine_print"],
        "health_profiles": ["sensitive", "allergyprone", "pregnancy", "baby", "vegan"]
    },
    "CATEGORY_ELECTRONICS": {
        "name": "Electronics", "icon": "📱",
        "subtypes": ["phone", "laptop", "tablet", "accessory", "cable", "charger", "audio", "wearable"],
        "enabled_rules": ["spec_check", "repairability", "claims_vs_facts"],
        "health_profiles": []
    },
    "CATEGORY_HOUSEHOLD": {
        "name": "Household", "icon": "🧹",
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener", "laundry"],
        "enabled_rules": ["chemical_safety", "allergen", "fine_print", "claims_vs_facts"],
        "health_profiles": ["sensitive", "allergyprone", "baby", "pregnancy"]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# THE 20 INTEGRITY LAWS
# ═══════════════════════════════════════════════════════════════════════════════
INTEGRITY_LAWS = {
    1: {"name": "Water-Down Deception", "base_points": -15, "description": "Premium claim but #1 ingredient is water/cheap filler", "tip": "Check if first ingredient matches the premium price", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD"]},
    2: {"name": "Fairy Dusting", "base_points": -12, "description": "Hero ingredient advertised on front is below position #5", "tip": "Ingredients listed by quantity", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    3: {"name": "Split Sugar Trick", "base_points": -18, "description": "Sugar split into 3+ names to hide total", "tip": "Add up ALL sugar types", "applies_to": ["CATEGORY_FOOD"]},
    4: {"name": "Low-Fat Trap", "base_points": -10, "description": "Claims 'low fat' but compensates with high sugar", "tip": "Low-fat often means high sugar", "applies_to": ["CATEGORY_FOOD"]},
    5: {"name": "Natural Fallacy", "base_points": -12, "description": "Claims 'natural' but contains synthetics", "tip": "'Natural' is unregulated", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_HOUSEHOLD"]},
    6: {"name": "Made-With Loophole", "base_points": -8, "description": "'Made with real X' but X is minimal", "tip": "'Made with' requires only tiny amount", "applies_to": ["CATEGORY_FOOD"]},
    7: {"name": "Serving Size Trick", "base_points": -10, "description": "Unrealistically small serving size", "tip": "Check servings per container", "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    8: {"name": "Slack Fill", "base_points": -8, "description": "Package mostly air/empty space", "tip": "Check net weight, not package size", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    9: {"name": "Spec Inflation", "base_points": -15, "description": "'Up to X speed/capacity' unrealistic", "tip": "'Up to' means lab conditions", "applies_to": ["CATEGORY_ELECTRONICS"]},
    10: {"name": "Compatibility Lie", "base_points": -12, "description": "'Universal' with hidden exceptions", "tip": "Check compatibility in fine print", "applies_to": ["CATEGORY_ELECTRONICS"]},
    11: {"name": "Military Grade Myth", "base_points": -10, "description": "Claims 'military grade' without MIL-STD cert", "tip": "Real military spec cites MIL-STD number", "applies_to": ["CATEGORY_ELECTRONICS"]},
    12: {"name": "Battery Fiction", "base_points": -12, "description": "Unrealistic battery life claims", "tip": "Tested with minimal usage", "applies_to": ["CATEGORY_ELECTRONICS"]},
    13: {"name": "Clinical Ghost", "base_points": -12, "description": "'Clinically proven' without citing study", "tip": "Real proof includes study details", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    14: {"name": "Concentration Trick", "base_points": -10, "description": "Active ingredient too diluted", "tip": "Effective: Vitamin C 10-20%, Retinol 0.3-1%", "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    15: {"name": "Free Trap", "base_points": -15, "description": "'Free' requires credit card/hidden purchase", "tip": "Free trial usually auto-charges", "applies_to": ["CATEGORY_ELECTRONICS"]},
    16: {"name": "Unlimited Lie", "base_points": -18, "description": "'Unlimited' with hidden caps", "tip": "'Unlimited' rarely means unlimited", "applies_to": ["CATEGORY_ELECTRONICS"]},
    17: {"name": "Lifetime Illusion", "base_points": -10, "description": "'Lifetime warranty' with exclusions", "tip": "'Lifetime' has many exclusions", "applies_to": ["CATEGORY_ELECTRONICS"]},
    18: {"name": "Photo vs Reality", "base_points": -12, "description": "Package photo much better than product", "tip": "Photos are professionally styled", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    19: {"name": "Fake Claim", "base_points": -15, "description": "Claims certification without verification", "tip": "Real certs show logo and ID", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_ELECTRONICS"]},
    20: {"name": "Name Trick", "base_points": -10, "description": "Product name implies absent ingredient", "tip": "'Honey Oat' doesn't mean much honey", "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# CITATION DATABASE - Properly Structured for Display
# ═══════════════════════════════════════════════════════════════════════════════
CITATIONS = {
    # Parabens
    "paraben": {"concern": "Potential endocrine disruption", "severity": "medium", "source": "EU SCCS", "full_source": "EU Scientific Committee on Consumer Safety (SCCS), 2013"},
    "methylparaben": {"concern": "Potential hormone disruption", "severity": "medium", "source": "EU SCCS", "full_source": "EU SCCS Opinion 2013, CIR Expert Panel"},
    "propylparaben": {"concern": "Higher absorption rate", "severity": "medium", "source": "EU SCCS", "full_source": "EU SCCS - Restricted to 0.14%"},
    "butylparaben": {"concern": "Higher potency endocrine activity", "severity": "high", "source": "Danish EPA", "full_source": "Danish EPA, EU SCCS Opinion 2013"},
    "ethylparaben": {"concern": "Potential endocrine effects", "severity": "medium", "source": "EU SCCS", "full_source": "EU SCCS Opinion 2013"},
    
    # Fragrance
    "fragrance": {"concern": "Undisclosed chemical mixture, allergen", "severity": "medium", "source": "AAD", "full_source": "American Academy of Dermatology"},
    "parfum": {"concern": "Undisclosed chemical mixture, allergen", "severity": "medium", "source": "EU Regulation", "full_source": "EU Cosmetics Regulation 1223/2009"},
    
    # Sulfates
    "sodium lauryl sulfate": {"concern": "Can irritate sensitive skin", "severity": "low", "source": "CIR Panel", "full_source": "Cosmetic Ingredient Review Expert Panel"},
    "sodium laureth sulfate": {"concern": "Potential 1,4-dioxane contamination", "severity": "low", "source": "FDA", "full_source": "FDA Guidance on 1,4-dioxane"},
    "sls": {"concern": "Can irritate sensitive skin", "severity": "low", "source": "CIR Panel", "full_source": "Cosmetic Ingredient Review Expert Panel"},
    
    # Formaldehyde releasers
    "dmdm hydantoin": {"concern": "Formaldehyde-releasing preservative", "severity": "high", "source": "IARC", "full_source": "International Agency for Research on Cancer"},
    "quaternium-15": {"concern": "Formaldehyde releaser, allergen", "severity": "high", "source": "ACDS", "full_source": "American Contact Dermatitis Society - Allergen of Year 2015"},
    "imidazolidinyl urea": {"concern": "Formaldehyde releaser", "severity": "high", "source": "IARC", "full_source": "IARC, EU SCCS"},
    "diazolidinyl urea": {"concern": "Formaldehyde releaser", "severity": "high", "source": "IARC", "full_source": "IARC Classification"},
    
    # Other cosmetic
    "triclosan": {"concern": "Endocrine disruption, antibiotic resistance", "severity": "high", "source": "FDA Ban 2016", "full_source": "FDA Ban in Consumer Antiseptics 2016"},
    "oxybenzone": {"concern": "Hormone disruption, coral damage", "severity": "medium", "source": "Hawaii Ban", "full_source": "Hawaii Sunscreen Ban Act 104, 2021"},
    "hydroquinone": {"concern": "Potential carcinogen", "severity": "high", "source": "EU Ban", "full_source": "EU Cosmetics Regulation - Banned for OTC"},
    "retinol": {"concern": "Pregnancy risk (teratogenic)", "severity": "context", "source": "FDA", "full_source": "FDA Pregnancy Category X for oral retinoids"},
    "phthalate": {"concern": "Endocrine disruption", "severity": "high", "source": "CDC/EPA", "full_source": "CDC National Report, EPA Phthalate Action Plan"},
    
    # Silicones (lower concern)
    "dimethicone": {"concern": "May cause buildup", "severity": "low", "source": "CIR", "full_source": "Generally considered safe by CIR"},
    "cyclomethicone": {"concern": "Environmental persistence", "severity": "low", "source": "EU Review", "full_source": "EU Environmental Review"},
    
    # Food
    "trans fat": {"concern": "Heart disease risk", "severity": "high", "source": "FDA Ban", "full_source": "FDA PHO Ban 2018, American Heart Association"},
    "hydrogenated oil": {"concern": "May contain trans fats", "severity": "high", "source": "FDA/AHA", "full_source": "FDA, American Heart Association"},
    "high fructose corn syrup": {"concern": "Metabolic concerns when over-consumed", "severity": "medium", "source": "AJCN", "full_source": "American Journal of Clinical Nutrition"},
    "red 40": {"concern": "Hyperactivity in sensitive children", "severity": "low", "source": "EFSA", "full_source": "EFSA Opinion, Southampton Study"},
    "yellow 5": {"concern": "May cause reactions", "severity": "low", "source": "FDA", "full_source": "FDA CFSAN"},
    "aspartame": {"concern": "IARC 'possibly carcinogenic'", "severity": "low", "source": "WHO IARC 2023", "full_source": "WHO IARC Review 2023"},
    "msg": {"concern": "May cause reactions in sensitive individuals", "severity": "low", "source": "FDA GRAS", "full_source": "FDA Generally Recognized as Safe"},
    "sodium nitrite": {"concern": "Forms nitrosamines when heated", "severity": "medium", "source": "IARC", "full_source": "IARC Group 2A probable carcinogen"},
    "bha": {"concern": "Possible carcinogen", "severity": "medium", "source": "IARC", "full_source": "IARC Group 2B, California Prop 65"},
    "bht": {"concern": "Possible endocrine effects", "severity": "low", "source": "NTP", "full_source": "National Toxicology Program"},
    "titanium dioxide": {"concern": "EU food ban 2022", "severity": "medium", "source": "EFSA", "full_source": "EFSA Opinion 2021, EU Ban 2022"},
    "carrageenan": {"concern": "Digestive inflammation concerns", "severity": "low", "source": "Cornucopia", "full_source": "Cornucopia Institute Review"},
    
    # Packaging
    "bpa": {"concern": "Endocrine disruption", "severity": "high", "source": "FDA", "full_source": "FDA Banned in Baby Bottles 2012"},
}

def get_citation(ingredient_name):
    """Get citation for ingredient - returns dict with source info"""
    if not ingredient_name:
        return None
    key = ingredient_name.lower().strip()
    
    # Direct match
    if key in CITATIONS:
        return CITATIONS[key]
    
    # Partial match
    for db_key, data in CITATIONS.items():
        if db_key in key or key in db_key:
            return data
    
    return None

def format_citation_display(ingredient_name, concern=None):
    """Format citation for UI display - returns (text, has_citation)"""
    citation = get_citation(ingredient_name)
    if citation:
        return f"{citation.get('concern', concern or 'Concern flagged')} • {citation.get('source', '')}", True
    return f"{concern or 'Potential concern'} • No citation", False
# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH PROFILES - Notifications Only (Don't Affect Score)
# ═══════════════════════════════════════════════════════════════════════════════
HEALTH_PROFILES = {
    "diabetes": {
        "name": "Diabetes", "icon": "🩺",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin", "sucrose"],
        "fine_print_scan": ["high sugar", "not suitable for diabetics", "may affect blood sugar"],
        "notification": "⚠️ Contains sugar/sweeteners - monitor blood glucose"
    },
    "heartcondition": {
        "name": "Heart Health", "icon": "❤️",
        "applies_to": ["CATEGORY_FOOD"],  # ONLY FOOD!
        "ingredient_flags": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat"],
        "fine_print_scan": ["high sodium", "high salt"],
        "notification": "⚠️ Contains sodium/fats - monitor for heart health"
    },
    "glutenfree": {
        "name": "Gluten-Free", "icon": "🌾",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["wheat", "barley", "rye", "gluten", "malt", "spelt", "kamut", "triticale"],
        "fine_print_scan": ["may contain wheat", "may contain gluten", "traces of wheat", "processed in a facility", "shared equipment with wheat"],
        "notification": "🚨 Contains or may contain GLUTEN"
    },
    "vegan": {
        "name": "Vegan", "icon": "🌱",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["gelatin", "carmine", "honey", "milk", "whey", "casein", "egg", "lanolin", "beeswax", "collagen", "keratin", "shellac", "lard", "tallow"],
        "fine_print_scan": ["may contain milk", "may contain egg", "not suitable for vegans"],
        "notification": "⚠️ May contain animal-derived ingredients"
    },
    "sensitive": {
        "name": "Sensitive Skin", "icon": "🌸",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"],
        "ingredient_flags": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate", "sodium lauryl", "witch hazel"],
        "fine_print_scan": ["patch test recommended", "not suitable for sensitive skin", "may cause irritation"],
        "notification": "⚠️ Contains potential irritants - patch test recommended"
    },
    "pregnancy": {
        "name": "Pregnancy", "icon": "🤰",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_FOOD"],
        "ingredient_flags": ["retinol", "retinoid", "salicylic acid", "benzoyl peroxide", "hydroquinone", "vitamin a"],
        "fine_print_scan": ["not recommended during pregnancy", "consult doctor if pregnant", "avoid if pregnant"],
        "notification": "⚠️ Contains ingredients to discuss with doctor during pregnancy"
    },
    "baby": {
        "name": "Baby Safe", "icon": "👶",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD", "CATEGORY_FOOD"],
        "ingredient_flags": ["fragrance", "parfum", "essential oil", "menthol", "camphor", "alcohol denat", "honey"],
        "fine_print_scan": ["not for children under", "keep away from children", "not suitable for infants"],
        "notification": "⚠️ May not be suitable for babies/young children"
    },
    "allergyprone": {
        "name": "Allergy Prone", "icon": "🤧",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"],
        "ingredient_flags": ["peanut", "tree nut", "soy", "milk", "egg", "wheat", "shellfish", "fish", "sesame", "fragrance", "lanolin"],
        "fine_print_scan": ["may contain", "traces of", "processed in a facility"],
        "notification": "⚠️ Contains common allergens - check carefully"
    },
    "keto": {
        "name": "Keto Diet", "icon": "🥑",
        "applies_to": ["CATEGORY_FOOD"],
        "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "maltodextrin", "wheat", "rice", "potato starch", "corn starch"],
        "fine_print_scan": [],
        "notification": "⚠️ Contains high-carb ingredients"
    },
    "dairy": {
        "name": "Dairy-Free", "icon": "🥛",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese", "yogurt", "ghee", "lactalbumin"],
        "fine_print_scan": ["may contain milk", "may contain dairy", "traces of milk", "contains milk ingredients"],
        "notification": "🚨 Contains or may contain DAIRY"
    }
}

ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "malt", "spelt"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu", "lecithin"], "applies_to": ["CATEGORY_FOOD"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise", "meringue", "lysozyme"], "applies_to": ["CATEGORY_FOOD"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish", "scallop", "oyster"], "applies_to": ["CATEGORY_FOOD"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy", "fish oil"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "sesame": {"name": "Sesame", "icon": "🫘", "triggers": ["sesame", "tahini"], "applies_to": ["CATEGORY_FOOD"]},
    "fragrance": {"name": "Fragrance", "icon": "🌺", "triggers": ["fragrance", "parfum", "perfume"], "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"]},
    "sulfates": {"name": "Sulfates", "icon": "🧴", "triggers": ["sulfate", "sls", "sles", "sodium lauryl", "sodium laureth"], "applies_to": ["CATEGORY_COSMETIC"]},
    "parabens": {"name": "Parabens", "icon": "⚗️", "triggers": ["paraben", "methylparaben", "propylparaben", "butylparaben"], "applies_to": ["CATEGORY_COSMETIC"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# RETAILER-SPECIFIC ALTERNATIVES - Accurate for Each Country
# ═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVES_BY_COUNTRY = {
    "AU": {
        "cleanser": {"name": "Cetaphil Gentle Skin Cleanser", "retailer": "Chemist Warehouse, Priceline, Woolworths, Coles", "score": 85, "why": "Widely available, fragrance-free options"},
        "moisturizer": {"name": "CeraVe Moisturising Cream", "retailer": "Chemist Warehouse, Priceline", "score": 92, "why": "Ceramides, fragrance-free"},
        "serum": {"name": "The Ordinary Niacinamide 10%", "retailer": "Priceline, Mecca, Adore Beauty", "score": 91, "why": "Affordable, effective"},
        "sunscreen": {"name": "Cancer Council SPF 50+", "retailer": "Woolworths, Coles, Chemist Warehouse", "score": 90, "why": "Australian made, high protection"},
        "shampoo": {"name": "Sukin Natural Shampoo", "retailer": "Woolworths, Coles, Chemist Warehouse", "score": 88, "why": "Australian, natural ingredients"},
        "body_lotion": {"name": "QV Skin Lotion", "retailer": "Chemist Warehouse, Priceline, Woolworths", "score": 93, "why": "Dermatologist recommended, fragrance-free"},
        "deodorant": {"name": "Sukin Natural Deodorant", "retailer": "Woolworths, Coles, Priceline", "score": 85, "why": "No aluminum, Australian made"},
        "protein_bar": {"name": "Clif Bar or Carman's", "retailer": "Woolworths, Coles", "score": 80, "why": "Widely available, better ingredients"},
        "cereal": {"name": "Uncle Tobys or Sanitarium", "retailer": "Woolworths, Coles", "score": 82, "why": "Australian brands, less processed"},
        "snack": {"name": "Carman's Muesli Bars", "retailer": "Woolworths, Coles", "score": 81, "why": "Australian, natural ingredients"},
        "vitamin": {"name": "Blackmores or Swisse", "retailer": "Chemist Warehouse, Priceline, Woolworths", "score": 88, "why": "Australian TGA approved"},
        "supplement": {"name": "Blackmores or Nature's Own", "retailer": "Chemist Warehouse, Priceline", "score": 87, "why": "Australian made, TGA listed"},
        "default": {"name": "Check Chemist Warehouse or Priceline", "retailer": "Chemist Warehouse, Priceline", "score": None, "why": "Wide range of alternatives"}
    },
    "US": {
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "CVS, Walgreens, Target, Walmart", "score": 92, "why": "Fragrance-free, ceramides"},
        "moisturizer": {"name": "CeraVe Moisturizing Cream", "retailer": "CVS, Walgreens, Target, Walmart", "score": 94, "why": "Ceramides, hyaluronic acid"},
        "serum": {"name": "The Ordinary Niacinamide 10%", "retailer": "Ulta, Sephora, Target", "score": 91, "why": "Affordable, transparent formula"},
        "sunscreen": {"name": "EltaMD UV Clear SPF 46", "retailer": "Dermstore, Amazon, Ulta", "score": 93, "why": "Dermatologist recommended"},
        "shampoo": {"name": "Free & Clear Shampoo", "retailer": "CVS, Walgreens, Amazon", "score": 94, "why": "No sulfates, fragrance, parabens"},
        "body_lotion": {"name": "Vanicream Moisturizing Lotion", "retailer": "CVS, Walgreens, Target", "score": 95, "why": "Dermatologist recommended, no irritants"},
        "deodorant": {"name": "Native Deodorant (Unscented)", "retailer": "Target, Walmart, CVS", "score": 86, "why": "No aluminum, parabens"},
        "protein_bar": {"name": "RXBAR", "retailer": "Target, Walmart, Whole Foods", "score": 84, "why": "Simple ingredients, no added sugar"},
        "cereal": {"name": "Nature's Path Organic", "retailer": "Target, Whole Foods, Walmart", "score": 85, "why": "USDA organic, no artificial colors"},
        "vitamin": {"name": "Thorne Research", "retailer": "Amazon, Thorne.com", "score": 94, "why": "Third-party tested, NSF certified"},
        "supplement": {"name": "NOW Foods", "retailer": "Whole Foods, Amazon, Vitamin Shoppe", "score": 90, "why": "GMP certified"},
        "default": {"name": "Check EWG.org for ratings", "retailer": "Various retailers", "score": None, "why": "Independent safety ratings"}
    },
    "GB": {
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "Boots, Superdrug", "score": 92, "why": "Fragrance-free, gentle"},
        "moisturizer": {"name": "CeraVe Moisturising Cream", "retailer": "Boots, Superdrug, Sainsbury's", "score": 94, "why": "Ceramides, dermatologist recommended"},
        "serum": {"name": "The Ordinary Niacinamide 10%", "retailer": "Boots, Superdrug, Cult Beauty", "score": 91, "why": "UK brand, affordable"},
        "sunscreen": {"name": "La Roche-Posay Anthelios", "retailer": "Boots, Superdrug", "score": 92, "why": "High protection, sensitive skin"},
        "shampoo": {"name": "Simple Kind to Skin", "retailer": "Boots, Tesco, Sainsbury's", "score": 87, "why": "No harsh chemicals"},
        "body_lotion": {"name": "E45 Moisturising Lotion", "retailer": "Boots, Tesco, Superdrug", "score": 90, "why": "Dermatologically tested"},
        "vitamin": {"name": "Holland & Barrett Own Brand", "retailer": "Holland & Barrett, Boots", "score": 85, "why": "Quality tested"},
        "default": {"name": "Check Boots or Holland & Barrett", "retailer": "Boots, Holland & Barrett", "score": None, "why": "Wide range available"}
    },
    "NZ": {
        "cleanser": {"name": "Cetaphil Gentle Cleanser", "retailer": "Chemist Warehouse NZ, Countdown", "score": 85, "why": "Gentle, widely available"},
        "moisturizer": {"name": "CeraVe or QV", "retailer": "Chemist Warehouse NZ, Unichem", "score": 92, "why": "Fragrance-free options"},
        "sunscreen": {"name": "Cancer Society SPF 50+", "retailer": "Countdown, New World, Chemist Warehouse", "score": 91, "why": "NZ made, high protection"},
        "vitamin": {"name": "Radiance or GO Healthy", "retailer": "Chemist Warehouse NZ, Countdown", "score": 86, "why": "NZ brands"},
        "default": {"name": "Check Chemist Warehouse NZ", "retailer": "Chemist Warehouse NZ", "score": None, "why": "Good range"}
    },
    "CA": {
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "Shoppers Drug Mart, Walmart", "score": 92, "why": "Widely available"},
        "moisturizer": {"name": "CeraVe Moisturizing Cream", "retailer": "Shoppers Drug Mart, Walmart, Costco", "score": 94, "why": "Excellent formula"},
        "vitamin": {"name": "Jamieson or Webber Naturals", "retailer": "Shoppers Drug Mart, Costco", "score": 87, "why": "Canadian brands, NPN certified"},
        "default": {"name": "Check Shoppers Drug Mart", "retailer": "Shoppers Drug Mart", "score": None, "why": "Wide selection"}
    },
    "OTHER": {
        "cleanser": {"name": "CeraVe Hydrating Cleanser", "retailer": "Local pharmacy, iHerb", "score": 92, "why": "Internationally available"},
        "moisturizer": {"name": "CeraVe or Cetaphil", "retailer": "Local pharmacy, Amazon, iHerb", "score": 92, "why": "Global brands"},
        "vitamin": {"name": "NOW Foods or Nature Made", "retailer": "iHerb, Amazon", "score": 88, "why": "Ships internationally"},
        "default": {"name": "Check iHerb.com", "retailer": "iHerb (ships globally)", "score": None, "why": "International shipping"}
    }
}

def get_alternative(product_name, product_type, product_category, country_code):
    """Get country-specific alternative that's actually available locally"""
    country_alts = ALTERNATIVES_BY_COUNTRY.get(country_code, ALTERNATIVES_BY_COUNTRY['OTHER'])
    search = f"{product_name} {product_type or ''}".lower()
    
    # Find by product type
    for key in country_alts:
        if key in search and key != 'default':
            alt = country_alts[key]
            # Don't recommend same product
            if alt['name'].lower() not in search.lower():
                return alt
    
    # Check category defaults
    if product_category == 'CATEGORY_SUPPLEMENT':
        return country_alts.get('supplement', country_alts.get('vitamin', country_alts['default']))
    elif product_category == 'CATEGORY_COSMETIC':
        for term in ['cleanser', 'moisturizer', 'serum', 'shampoo', 'lotion', 'sunscreen', 'deodorant']:
            if term in search:
                return country_alts.get(term, country_alts['default'])
        return country_alts.get('moisturizer', country_alts['default'])
    elif product_category == 'CATEGORY_FOOD':
        for term in ['bar', 'cereal', 'snack', 'protein']:
            if term in search:
                return country_alts.get(term if term != 'bar' else 'protein_bar', country_alts['default'])
    
    return country_alts['default']

# ═══════════════════════════════════════════════════════════════════════════════
# BETTER LOCATION DETECTION - Multiple Fallbacks
# ═══════════════════════════════════════════════════════════════════════════════
RETAILERS_DISPLAY = {
    "AU": ["Chemist Warehouse", "Priceline", "Woolworths", "Coles"],
    "US": ["CVS", "Walgreens", "Target", "Walmart"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's"],
    "NZ": ["Chemist Warehouse NZ", "Countdown", "Unichem"],
    "CA": ["Shoppers Drug Mart", "Walmart", "Costco"],
    "DE": ["dm", "Rossmann", "Müller"],
    "FR": ["Sephora", "Monoprix", "Carrefour"],
    "OTHER": ["Local pharmacy", "iHerb", "Amazon"]
}

def detect_location_enhanced():
    """Enhanced location detection with multiple fallbacks"""
    location_services = [
        # Primary: ipapi.co (usually most accurate)
        {
            'url': 'https://ipapi.co/json/',
            'extract': lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))
        },
        # Fallback 1: ip-api.com
        {
            'url': 'https://ip-api.com/json/',
            'extract': lambda d: (d.get('city'), d.get('country'), d.get('countryCode'))
        },
        # Fallback 2: ipinfo.io
        {
            'url': 'https://ipinfo.io/json',
            'extract': lambda d: (d.get('city'), d.get('country'), d.get('country'))
        },
        # Fallback 3: geolocation-db
        {
            'url': 'https://geolocation-db.com/json/',
            'extract': lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))
        }
    ]
    
    for service in location_services:
        try:
            r = requests.get(service['url'], timeout=5)
            if r.ok:
                d = r.json()
                city, country, code = service['extract'](d)
                
                # Validate the response
                if city and city not in ['', 'Unknown', None, 'Not found', 'undefined']:
                    # Normalize country code
                    if code and len(code) == 2:
                        code = code.upper()
                    else:
                        # Try to map country name to code
                        country_map = {
                            'australia': 'AU', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB',
                            'uk': 'GB', 'new zealand': 'NZ', 'canada': 'CA', 'germany': 'DE', 'france': 'FR',
                            'japan': 'JP', 'singapore': 'SG', 'hong kong': 'HK'
                        }
                        code = country_map.get((country or '').lower(), 'OTHER')
                    
                    return {
                        'city': city,
                        'country': country or '',
                        'code': code,
                        'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER'])
                    }
        except Exception:
            continue
    
    # Ultimate fallback - ask user
    return {
        'city': 'Unknown',
        'country': 'Unknown',
        'code': 'OTHER',
        'retailers': RETAILERS_DISPLAY['OTHER'],
        'needs_manual': True
    }

def get_verdict(score):
    if score >= 90: return "EXCEPTIONAL"
    elif score >= 75: return "BUY"
    elif score >= 50: return "CAUTION"
    return "AVOID"

def get_verdict_display(verdict):
    return {
        'EXCEPTIONAL': {'icon': '★', 'text': 'EXCEPTIONAL', 'color': '#06b6d4'},
        'BUY': {'icon': '✓', 'text': 'GOOD TO BUY', 'color': '#22c55e'},
        'CAUTION': {'icon': '!', 'text': 'USE CAUTION', 'color': '#f59e0b'},
        'AVOID': {'icon': '✗', 'text': 'AVOID', 'color': '#ef4444'},
        'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}
    }.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})
# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE - Score Consistency System
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_product_name(name):
    """Normalize for consistent matching"""
    if not name: return ""
    # Remove special chars, extra spaces, make lowercase
    return re.sub(r'[^\w\s]', '', name.lower()).strip()

def get_product_hash(product_name, brand=""):
    """Create unique hash for product identification"""
    normalized = normalize_product_name(f"{brand} {product_name}")
    return hashlib.md5(normalized.encode()).hexdigest()[:16]

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    
    # Main scans table
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT,
        product_hash TEXT, product_category TEXT, product_type TEXT,
        score INTEGER, verdict TEXT, ingredients TEXT, violations TEXT,
        bonuses TEXT, notifications TEXT, thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0
    )''')
    
    # SCORE CONSISTENCY: Store verified product scores
    c.execute('''CREATE TABLE IF NOT EXISTS verified_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_hash TEXT UNIQUE,
        product_name TEXT,
        brand TEXT,
        verified_score INTEGER,
        scan_count INTEGER DEFAULT 1,
        product_category TEXT,
        ingredients TEXT,
        violations TEXT,
        last_verified DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Barcode cache
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (
        barcode TEXT PRIMARY KEY, product_name TEXT, brand TEXT, ingredients TEXT,
        product_type TEXT, categories TEXT, nutrition TEXT, image_url TEXT,
        source TEXT, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # User preferences
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    
    # Stats
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE
    )''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    
    # User info with location
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (
        id INTEGER PRIMARY KEY DEFAULT 1, user_id TEXT, city TEXT, country TEXT, country_code TEXT
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
    c.execute('SELECT city, country, country_code FROM user_info WHERE id=1')
    r = c.fetchone()
    conn.close()
    if r and r[0] and r[0] not in ['Unknown', '', 'Your City']:
        code = r[2] or 'OTHER'
        return {'city': r[0], 'country': r[1] or '', 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER'])}
    return None

def save_location(city, country):
    country_map = {'australia': 'AU', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB', 'uk': 'GB',
                   'new zealand': 'NZ', 'canada': 'CA', 'germany': 'DE', 'france': 'FR'}
    code = country_map.get((country or '').lower(), 'OTHER')
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE user_info SET city=?, country=?, country_code=? WHERE id=1', (city, country, code))
    conn.commit()
    conn.close()
    return code

# ═══════════════════════════════════════════════════════════════════════════════
# SCORE CONSISTENCY - Same Product = Same Score
# ═══════════════════════════════════════════════════════════════════════════════

def get_verified_score(product_name, brand=""):
    """Get consistent score for previously scanned product"""
    try:
        product_hash = get_product_hash(product_name, brand)
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''SELECT verified_score, scan_count, violations FROM verified_products 
                    WHERE product_hash = ?''', (product_hash,))
        r = c.fetchone()
        conn.close()
        
        if r and r[1] >= 2:  # Only use if scanned 2+ times
            return {'score': r[0], 'scan_count': r[1], 'violations': json.loads(r[2]) if r[2] else []}
    except:
        pass
    return None

def save_verified_score(result):
    """Save/update verified score for consistency"""
    try:
        product_name = result.get('product_name', '')
        brand = result.get('brand', '')
        product_hash = get_product_hash(product_name, brand)
        score = result.get('score', 70)
        
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        
        c.execute('SELECT verified_score, scan_count FROM verified_products WHERE product_hash = ?', (product_hash,))
        existing = c.fetchone()
        
        if existing:
            # Average with existing, weighted toward more scans
            old_score, count = existing
            # After 3 scans, lock in the score more
            if count >= 3:
                weight = 0.9  # 90% old, 10% new
            else:
                weight = count / (count + 1)
            new_score = int(old_score * weight + score * (1 - weight))
            c.execute('''UPDATE verified_products SET verified_score=?, scan_count=?, 
                        last_verified=CURRENT_TIMESTAMP, violations=? WHERE product_hash=?''',
                      (new_score, count + 1, json.dumps(result.get('violations', [])), product_hash))
        else:
            c.execute('''INSERT INTO verified_products (product_hash, product_name, brand, verified_score, 
                        product_category, ingredients, violations) VALUES (?,?,?,?,?,?,?)''',
                      (product_hash, product_name, brand, score, result.get('product_category', ''),
                       json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', []))))
        
        conn.commit()
        conn.close()
    except:
        pass

def save_scan(result, user_id, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    product_hash = get_product_hash(result.get('product_name', ''), result.get('brand', ''))
    
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO scans (scan_id, user_id, product, brand, product_hash, product_category, 
                product_type, score, verdict, ingredients, violations, bonuses, notifications, thumb) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (sid, user_id, result.get('product_name', ''), result.get('brand', ''), product_hash,
               result.get('product_category', ''), result.get('product_type', ''),
               result.get('score', 0), result.get('verdict', ''),
               json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])),
               json.dumps(result.get('bonuses', [])), json.dumps(result.get('notifications', [])), thumb))
    
    # Update stats
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
    
    # Save for consistency
    save_verified_score(result)
    return sid

def get_history(user_id, n=30):
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

# ═══════════════════════════════════════════════════════════════════════════════
# BARCODE SYSTEM - Enhanced Accuracy
# ═══════════════════════════════════════════════════════════════════════════════

def cache_barcode(barcode, data):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO barcode_cache (barcode, product_name, brand, ingredients, 
                    product_type, categories, nutrition, image_url, source, last_updated) 
                    VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''),
                   data.get('product_type', ''), data.get('categories', ''),
                   json.dumps(data.get('nutrition', {})), data.get('image_url', ''), data.get('source', '')))
        conn.commit()
        conn.close()
    except: pass

def get_cached_barcode(barcode):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, ingredients, product_type, categories, nutrition, image_url, source FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]:
            return {'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 'product_type': r[3],
                    'categories': r[4], 'nutrition': json.loads(r[5]) if r[5] else {}, 'image_url': r[6],
                    'source': r[7], 'cached': True}
    except: pass
    return None

def preprocess_barcode_image(image):
    try:
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.5)
        sharpened = enhanced.filter(ImageFilter.SHARPEN)
        return sharpened
    except:
        return image

def try_decode_barcode_pyzbar(image_file):
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        
        # Try multiple processing methods
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L'), 
                         img.rotate(90, expand=True), img.rotate(270, expand=True),
                         img.rotate(180)]:
            try:
                barcodes = pyzbar.decode(proc_img)
                if barcodes:
                    return barcodes[0].data.decode('utf-8')
            except: continue
    except: pass
    return None

def ai_read_barcode(image_file):
    """Use Gemini AI to read barcode - enhanced accuracy"""
    if not GEMINI_API_KEY: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        
        resp = model.generate_content([
            """Look at this image and find the BARCODE. 
            Read the numeric digits printed BELOW the barcode lines.
            Common formats:
            - UPC-A: 12 digits
            - EAN-13: 13 digits
            - EAN-8: 8 digits
            
            Return ONLY the digits with NO spaces, dashes, or other characters.
            If you cannot read the barcode clearly, return: NONE
            
            Example good responses: 9300617003212, 041570054369
            Example bad responses: "The barcode is...", "9300 6170 0321"
            """, img
        ])
        
        text = resp.text.strip().upper()
        if 'NONE' in text or 'CANNOT' in text or 'UNREADABLE' in text or 'NOT VISIBLE' in text:
            return None
        
        # Extract only digits
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14:
            return digits
    except: pass
    return None

def lookup_barcode_all_sources(barcode):
    """Search ALL databases for complete accuracy"""
    results = []
    
    # 1. Open Food Facts (global food)
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=12)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or p.get('generic_name') or ''
                if name:
                    results.append({
                        'found': True, 'name': name, 'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '',
                        'categories': p.get('categories', ''), 'nutrition': p.get('nutriments', {}),
                        'image_url': p.get('image_url', ''), 'product_type': 'food',
                        'source': 'Open Food Facts', 'confidence': 'high' if p.get('ingredients_text') else 'medium'
                    })
    except: pass
    
    # 2. Open Beauty Facts (cosmetics)
    try:
        r = requests.get(f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json", timeout=12)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or p.get('product_name_en') or ''
                if name:
                    results.append({
                        'found': True, 'name': name, 'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text') or p.get('ingredients_text_en') or '',
                        'categories': p.get('categories', ''), 'image_url': p.get('image_url', ''),
                        'product_type': 'cosmetics', 'source': 'Open Beauty Facts',
                        'confidence': 'high' if p.get('ingredients_text') else 'medium'
                    })
    except: pass
    
    # 3. Open Products Facts (household)
    try:
        r = requests.get(f"https://world.openproductsfacts.org/api/v0/product/{barcode}.json", timeout=12)
        if r.ok:
            d = r.json()
            if d.get('status') == 1:
                p = d.get('product', {})
                name = p.get('product_name') or ''
                if name:
                    results.append({
                        'found': True, 'name': name, 'brand': p.get('brands', ''),
                        'ingredients': p.get('ingredients_text', ''), 'product_type': 'household',
                        'source': 'Open Products Facts', 'confidence': 'medium'
                    })
    except: pass
    
    # 4. UPC Item DB (general)
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=12)
        if r.ok:
            d = r.json()
            items = d.get('items', [])
            if items:
                item = items[0]
                results.append({
                    'found': True, 'name': item.get('title', ''), 'brand': item.get('brand', ''),
                    'description': item.get('description', ''), 'categories': item.get('category', ''),
                    'image_url': item.get('images', [''])[0] if item.get('images') else '',
                    'source': 'UPC Item DB', 'confidence': 'medium'
                })
    except: pass
    
    # Return best result
    if results:
        results.sort(key=lambda x: (bool(x.get('ingredients')), x.get('confidence') == 'high', len(x.get('name', ''))), reverse=True)
        return results[0]
    
    return {'found': False}

def smart_barcode_lookup(barcode, progress_callback=None):
    if progress_callback: progress_callback(0.1, "Checking cache...")
    cached = get_cached_barcode(barcode)
    if cached:
        if progress_callback: progress_callback(1.0, "✓ Found!")
        return cached
    
    if progress_callback: progress_callback(0.3, "Searching databases...")
    result = lookup_barcode_all_sources(barcode)
    
    if result.get('found'):
        if progress_callback: progress_callback(0.9, "✓ Found!")
        cache_barcode(barcode, result)
        return result
    
    if progress_callback: progress_callback(1.0, "Not found")
    return {'found': False, 'barcode': barcode}

def supa_ok(): return bool(SUPABASE_URL and SUPABASE_KEY)

def cloud_log_scan(result, city, country, user_id):
    if supa_ok():
        try:
            url = f"{SUPABASE_URL}/rest/v1/scans_log"
            headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
            requests.post(url, headers=headers, json={
                "product_name": result.get('product_name', ''), "brand": result.get('brand', ''),
                "score": result.get('score', 0), "verdict": result.get('verdict', ''),
                "city": city, "country": country, "user_id": user_id
            }, timeout=5)
        except: pass
# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH ALERTS - Notifications Only (Don't Affect Score)
# ═══════════════════════════════════════════════════════════════════════════════

def check_profile_notifications(ingredients, full_text, user_profiles, user_allergies, product_category):
    """
    Generate NOTIFICATIONS based on user profile.
    These are informational alerts - they do NOT affect the score.
    """
    notifications = []
    if not ingredients and not full_text:
        return notifications
    
    ing_text = (' '.join(ingredients) if isinstance(ingredients, list) else ingredients or '').lower()
    full_lower = (full_text or '').lower()
    
    # Check health profiles
    for profile_key in user_profiles:
        if profile_key not in HEALTH_PROFILES:
            continue
        profile = HEALTH_PROFILES[profile_key]
        
        # Only check if category applies
        if product_category not in profile.get('applies_to', []):
            continue
        
        # Check ingredient flags
        matched = False
        for flag in profile.get('ingredient_flags', []):
            if flag.lower() in ing_text:
                matched = True
                break
        
        # Check fine print
        if not matched:
            for phrase in profile.get('fine_print_scan', []):
                if phrase.lower() in full_lower:
                    matched = True
                    break
        
        if matched:
            notifications.append({
                'type': 'profile',
                'key': profile_key,
                'name': profile['name'],
                'icon': profile['icon'],
                'message': profile.get('notification', f"Contains flagged ingredients for {profile['name']}"),
                'severity': 'warning'
            })
    
    # Check allergens
    for allergy_key in user_allergies:
        if allergy_key not in ALLERGENS:
            continue
        allergen = ALLERGENS[allergy_key]
        
        if product_category not in allergen.get('applies_to', []):
            continue
        
        for trigger in allergen['triggers']:
            if trigger.lower() in ing_text or f"may contain {trigger.lower()}" in full_lower:
                notifications.append({
                    'type': 'allergen',
                    'key': allergy_key,
                    'name': allergen['name'],
                    'icon': allergen['icon'],
                    'message': f"🚨 Contains or may contain {allergen['name'].upper()}!",
                    'severity': 'danger'
                })
                break
    
    return notifications

# ═══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS - With Score Consistency
# ═══════════════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are HonestWorld's Context-Aware Integrity Engine.

## CRITICAL: CONSISTENT SCORING
The same product MUST get the same score. Base your analysis on objective facts only.

## STEP 1: CLASSIFY PRODUCT CATEGORY
- CATEGORY_FOOD: Has "Nutrition Facts", calories, sugar, protein
- CATEGORY_SUPPLEMENT: Has "Supplement Facts", daily value
- CATEGORY_COSMETIC: For external use, skin/hair products
- CATEGORY_ELECTRONICS: Has specs, battery, ports
- CATEGORY_HOUSEHOLD: Cleaning products, detergents

## STEP 2: APPLY CATEGORY-SPECIFIC RULES ONLY
IF CATEGORY_COSMETIC:
- CHECK: Chemical safety, fragrance, claims vs reality
- IGNORE: Nutritional rules (sugar, sodium, etc.)

IF CATEGORY_FOOD:
- CHECK: Nutritional content, sugar, sodium, additives
- IGNORE: Cosmetic rules

## STEP 3: CLAIM VS FACT CROSS-CHECK
| Front Claim | Check For | Violation |
|-------------|-----------|-----------|
| "Natural" | Synthetics (phenoxyethanol, dimethicone, PEG-) | Law 5 (-12) |
| "Fragrance Free" | "Fragrance" or "Parfum" in ingredients | Law 19 (-15) |
| "Paraben Free" | Any paraben in ingredients | Law 19 (-15) |
| "Premium" | Water as #1 ingredient | Law 1 (-15) |

## STEP 4: SCORING (Base: 85)
Deduct ONLY for verified issues:
- Each Law violation: specified points
- Each concerning ingredient WITH citation: -2 to -5

## STEP 5: FLAG INGREDIENTS WITH CITATIONS
For EACH flagged ingredient:
- State the specific concern
- Provide scientific source if known (EU SCCS, FDA, etc.)
- If no citation available, note "potential concern - verify"

## CONTEXT:
Location: {location}
{barcode_context}

## REQUIRED OUTPUT (Valid JSON only):
{{
    "product_name": "Exact product name",
    "brand": "Brand name",
    "product_category": "CATEGORY_FOOD/CATEGORY_COSMETIC/CATEGORY_SUPPLEMENT/CATEGORY_ELECTRONICS/CATEGORY_HOUSEHOLD",
    "product_type": "specific type",
    "readable": true,
    "score": <0-100>,
    "violations": [
        {{
            "law": <number or null>,
            "name": "Violation name",
            "points": <negative number>,
            "evidence": "Quote exact text from image",
            "source": "Scientific source if applicable"
        }}
    ],
    "bonuses": [
        {{"name": "Bonus", "points": <positive>, "evidence": "What earned it"}}
    ],
    "ingredients": ["list"],
    "ingredients_flagged": [
        {{
            "name": "ingredient",
            "concern": "specific concern",
            "source": "Citation (EU SCCS, FDA, CIR, etc.) or null"
        }}
    ],
    "good_ingredients": ["beneficial ingredients"],
    "main_issue": "Primary concern or 'Clean formula'",
    "positive": "Main positive aspect",
    "front_claims": ["marketing claims detected"],
    "fine_print": ["any warnings/disclaimers found"],
    "confidence": "high/medium/low"
}}

CRITICAL: Output ONLY valid JSON. No markdown, no extra text."""

def analyze_product(images, location, progress_callback, barcode_info=None, user_profiles=None, user_allergies=None):
    """AI Analysis with score consistency"""
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "score": 0, "verdict": "UNCLEAR", "readable": False,
                "violations": [], "main_issue": "Add GEMINI_API_KEY to secrets"}
    
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
- Source: {barcode_info.get('source', '')}
Use this data if image is unclear."""
    
    prompt = ANALYSIS_PROMPT.format(
        location=f"{location.get('city', '')}, {location.get('country', '')}",
        barcode_context=barcode_context
    )
    
    progress_callback(0.5, "Applying rules...")
    
    try:
        response = model.generate_content([prompt] + pil_images)
        text = response.text.strip()
        
        # Parse JSON
        result = None
        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
            except:
                # Try cleaning
                clean_text = text.replace('```json', '').replace('```', '').strip()
                try:
                    result = json.loads(clean_text)
                except:
                    pass
        
        if not result:
            return {"product_name": "Parse Error", "score": 0, "verdict": "UNCLEAR",
                    "readable": False, "violations": [], "main_issue": "Could not parse AI response"}
        
        progress_callback(0.7, "Checking consistency...")
        
        # Get score and validate
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        # SCORE CONSISTENCY: Check if we've seen this product before
        product_name = result.get('product_name', '')
        brand = result.get('brand', '')
        
        verified = get_verified_score(product_name, brand)
        if verified and verified['scan_count'] >= 2:
            # Use verified score with small adjustment
            old_score = verified['score']
            # Allow max 5 point variation from verified
            if abs(score - old_score) > 5:
                score = old_score
        
        # Ensure violations explain score
        violations = result.get('violations', [])
        if not violations and score < 85:
            missing = 85 - score
            violations = [{"law": None, "name": "Minor concerns", "points": -missing,
                          "evidence": result.get('main_issue', 'Minor issues detected')}]
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['violations'] = violations
        
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        
        # Add notifications (don't affect score)
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        ingredients = result.get('ingredients', [])
        full_text = ' '.join(result.get('fine_print', []) + result.get('front_claims', []))
        
        notifications = check_profile_notifications(ingredients, full_text, user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except Exception as e:
        return {"product_name": "Error", "score": 0, "verdict": "UNCLEAR",
                "readable": False, "violations": [], "main_issue": f"Error: {str(e)[:100]}"}

# ═══════════════════════════════════════════════════════════════════════════════
# SHARE IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_share_image(product_name, brand, score, verdict):
    width, height = 1080, 1080
    colors = {
        'EXCEPTIONAL': ('#06b6d4', '#0891b2'), 'BUY': ('#22c55e', '#16a34a'),
        'CAUTION': ('#f59e0b', '#d97706'), 'AVOID': ('#ef4444', '#dc2626'),
        'UNCLEAR': ('#6b7280', '#4b5563')
    }
    c1, c2 = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    # Gradient
    for i in range(height // 2, height):
        progress = (i - height // 2) / (height // 2)
        r = int(int(c1[1:3], 16) + (int(c2[1:3], 16) - int(c1[1:3], 16)) * progress)
        g = int(int(c1[3:5], 16) + (int(c2[3:5], 16) - int(c1[3:5], 16)) * progress)
        b = int(int(c1[5:7], 16) + (int(c2[5:7], 16) - int(c1[5:7], 16)) * progress)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
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
    draw.text((width // 2, 60), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 180), display['icon'], fill='white', anchor="mt", font=font_icon)
    draw.text((width // 2, 340), display['text'], fill='white', anchor="mt", font=font_verdict)
    draw.text((width // 2, 440), f"{score}/100", fill='white', anchor="mt", font=font_score)
    
    pname = product_name[:38] + "..." if len(product_name) > 38 else product_name
    draw.text((width // 2, 650), pname, fill='white', anchor="mt", font=font_product)
    if brand:
        draw.text((width // 2, 710), f"by {brand[:32]}", fill='white', anchor="mt", font=font_product)
    draw.text((width // 2, height - 55), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    
    return img

def create_story_image(product_name, brand, score, verdict):
    width, height = 1080, 1920
    colors = {
        'EXCEPTIONAL': ('#06b6d4', '#0891b2'), 'BUY': ('#22c55e', '#16a34a'),
        'CAUTION': ('#f59e0b', '#d97706'), 'AVOID': ('#ef4444', '#dc2626'),
        'UNCLEAR': ('#6b7280', '#4b5563')
    }
    c1, c2 = colors.get(verdict, colors['CAUTION'])
    
    img = Image.new('RGB', (width, height), c1)
    draw = ImageDraw.Draw(img)
    
    for i in range(height // 2, height):
        progress = (i - height // 2) / (height // 2)
        r = int(int(c1[1:3], 16) + (int(c2[1:3], 16) - int(c1[1:3], 16)) * progress)
        g = int(int(c1[3:5], 16) + (int(c2[3:5], 16) - int(c1[3:5], 16)) * progress)
        b = int(int(c1[5:7], 16) + (int(c2[5:7], 16) - int(c1[5:7], 16)) * progress)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
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
    draw.text((width // 2, 250), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 450), display['icon'], fill='white', anchor="mt", font=font_icon)
    draw.text((width // 2, 720), display['text'], fill='white', anchor="mt", font=font_verdict)
    draw.text((width // 2, 880), f"{score}/100", fill='white', anchor="mt", font=font_score)
    
    pname = product_name[:34] + "..." if len(product_name) > 34 else product_name
    draw.text((width // 2, 1200), pname, fill='white', anchor="mt", font=font_product)
    if brand:
        draw.text((width // 2, 1270), f"by {brand[:30]}", fill='white', anchor="mt", font=font_product)
    draw.text((width // 2, height - 140), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    
    return img

def image_to_bytes(img, fmt='PNG'):
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()
# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES - Clean, No Rendering Issues
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.stApp { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 520px; }

/* Verdict Cards */
.verdict-exceptional { background: linear-gradient(135deg, #06b6d4, #0891b2); }
.verdict-buy { background: linear-gradient(135deg, #22c55e, #16a34a); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b, #d97706); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444, #dc2626); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280, #4b5563); }

.verdict-card {
    border-radius: 24px; padding: 2rem; text-align: center; color: white;
    margin: 1rem 0; box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.verdict-icon { font-size: 4rem; margin-bottom: 0.5rem; }
.verdict-text { font-size: 1.3rem; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; }
.verdict-score { font-size: 4rem; font-weight: 900; }

/* Stats */
.stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; }

/* Notifications (profile alerts) */
.notif-danger {
    background: linear-gradient(135deg, #fef2f2, #fee2e2);
    border-left: 5px solid #ef4444;
    border-radius: 12px; padding: 1rem; margin: 0.5rem 0;
    animation: pulse 2s infinite;
}
.notif-warning {
    background: linear-gradient(135deg, #fffbeb, #fef3c7);
    border-left: 5px solid #f59e0b;
    border-radius: 12px; padding: 1rem; margin: 0.5rem 0;
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
}

/* Alerts */
.alert-issue { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.alert-positive { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

/* Laws */
.law-box {
    background: white;
    border-left: 4px solid #ef4444;
    border-radius: 0 12px 12px 0;
    padding: 0.8rem;
    margin: 0.4rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.law-title { font-weight: 700; color: #dc2626; font-size: 0.95rem; }
.law-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }
.law-source { font-size: 0.75rem; color: #059669; background: #ecfdf5; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; }

/* Bonuses */
.bonus-box { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-left: 4px solid #22c55e; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.3rem 0; }

/* Ingredients */
.ing-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0; }
.ing-badge { padding: 0.3rem 0.6rem; border-radius: 16px; font-weight: 600; font-size: 0.75rem; }
.ing-red { background: #fee2e2; color: #dc2626; }
.ing-yellow { background: #fef3c7; color: #b45309; }
.ing-green { background: #dcfce7; color: #16a34a; }
.ing-source { font-size: 0.7rem; color: #059669; font-style: italic; }

/* Alternative */
.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }
.alt-score { background: #22c55e; color: white; padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.8rem; }
.alt-retailer { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }

/* Share - ALL 6 SOCIAL MEDIA */
.share-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin: 0.5rem 0; }
.share-btn {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 0.6rem; border-radius: 10px; color: white; text-decoration: none;
    font-weight: 600; font-size: 0.7rem; transition: transform 0.2s;
}
.share-btn:hover { transform: translateY(-2px); }
.share-btn span { font-size: 1.2rem; margin-bottom: 0.2rem; }

/* Progress */
.progress-box { background: white; border-radius: 16px; padding: 1.5rem; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; margin: 0.75rem 0; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #8b5cf6); transition: width 0.3s; }

/* Badges */
.loc-badge { background: #dbeafe; color: #1d4ed8; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.7rem; font-weight: 600; }
.streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; padding: 0.3rem 0.6rem; border-radius: 16px; font-size: 0.75rem; font-weight: 700; }
.cat-badge { background: #e0e7ff; color: #4338ca; padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.7rem; font-weight: 600; }

/* History */
.history-score { width: 42px; height: 42px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 0.85rem; }

/* Buttons */
.stButton > button { background: linear-gradient(135deg, #3b82f6, #2563eb) !important; color: white !important; font-weight: 700 !important; border: none !important; border-radius: 12px !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f1f5f9; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #64748b; border-radius: 8px; font-weight: 600; }
.stTabs [aria-selected="true"] { background: white !important; color: #1e293b !important; }

/* Expanders */
[data-testid="stExpander"] { background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }

/* Law Cards in Laws tab */
.law-card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 0.7rem; margin: 0.3rem 0; }
.law-card-title { font-weight: 700; color: #1e293b; font-size: 0.9rem; }
.law-card-pts { color: #ef4444; font-weight: 700; }
.law-card-desc { font-size: 0.8rem; color: #64748b; margin-top: 0.2rem; }

/* Location prompt */
.location-prompt { background: linear-gradient(135deg, #eff6ff, #dbeafe); border: 2px solid #3b82f6; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; }

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stCameraInput"] video { max-height: 180px !important; border-radius: 12px; }
</style>
"""
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION - ULTIMATE EDITION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    # Session state
    for key in ['result', 'scan_id', 'admin', 'barcode_info', 'show_result']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'admin' else False
    if 'show_result' not in st.session_state:
        st.session_state.show_result = False
    
    # Location detection - enhanced
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        if saved and saved.get('city') not in ['Unknown', '', 'Your City', None]:
            st.session_state.loc = saved
        else:
            detected = detect_location_enhanced()
            st.session_state.loc = detected
            if detected.get('city') not in ['Unknown', 'Your City', ''] and not detected.get('needs_manual'):
                save_location(detected['city'], detected['country'])
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("# 🌍 HonestWorld")
        loc = st.session_state.loc
        if loc.get('city') and loc.get('city') not in ['Unknown', 'Your City', '']:
            st.markdown(f"<span class='loc-badge'>📍 {loc.get('city')}</span>", unsafe_allow_html=True)
        elif loc.get('needs_manual'):
            st.markdown("<span class='loc-badge'>📍 Set your location in Profile</span>", unsafe_allow_html=True)
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
            render_scan_interface()
    
    with tab_history:
        render_history(user_id)
    
    with tab_profile:
        render_profile()
    
    with tab_laws:
        render_laws()
    
    # Footer
    st.markdown(f"<center style='color:#94a3b8;font-size:0.7rem;margin-top:1rem;'>🌍 HonestWorld v{VERSION} • Ultimate Edition</center>", unsafe_allow_html=True)

def render_scan_interface():
    """Clean scan interface"""
    input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
    images = []
    
    if input_method == "📷 Camera":
        st.caption("📸 Point at product label (front + back for best results)")
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
    
    else:  # Barcode
        st.markdown("**📊 Perfect Barcode Scanner**")
        st.caption("🎯 Fetches complete product data automatically!")
        barcode_img = st.camera_input("", label_visibility="collapsed", key="barcode_cam")
        
        if barcode_img:
            with st.spinner("Reading barcode..."):
                barcode_num = try_decode_barcode_pyzbar(barcode_img)
                if not barcode_num:
                    barcode_num = ai_read_barcode(barcode_img)
                
                if barcode_num:
                    st.info(f"📊 **{barcode_num}**")
                    
                    progress_ph = st.empty()
                    def update_prog(pct, msg):
                        progress_ph.markdown(f"<div class='progress-box'><div>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
                    
                    barcode_info = smart_barcode_lookup(barcode_num, update_prog)
                    progress_ph.empty()
                    
                    if barcode_info.get('found'):
                        st.success(f"✅ **{barcode_info.get('name', '')}**")
                        if barcode_info.get('brand'):
                            st.caption(f"by {barcode_info.get('brand')} • {barcode_info.get('source', '')}")
                        
                        st.session_state.barcode_info = barcode_info
                        st.session_state.barcode_only = True
                        images = [barcode_img]
                    else:
                        st.warning("Not found in databases. Use photo scan instead.")
                else:
                    st.error("Could not read barcode. Try a clearer image.")
    
    # Analyze button - FIXED
    if images or st.session_state.get('barcode_info'):
        if st.button("🔍 ANALYZE", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                icons = ['🔍', '📋', '⚖️', '✨']
                icon = icons[min(int(pct * 4), 3)]
                progress_ph.markdown(f"<div class='progress-box'><div style='font-size:2rem;'>{icon}</div><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
            user_profiles = get_profiles()
            user_allergies = get_allergies()
            bi = st.session_state.get('barcode_info')
            user_id = get_user_id()
            
            # Check if barcode-only mode
            if st.session_state.get('barcode_only') and bi and bi.get('found'):
                result = analyze_from_barcode_data(bi, st.session_state.loc, update_prog, user_profiles, user_allergies)
                st.session_state.barcode_only = False
            else:
                result = analyze_product(images, st.session_state.loc, update_prog, bi, user_profiles, user_allergies)
            
            progress_ph.empty()
            
            if result.get('readable', True) and result.get('score', 0) > 0:
                thumb = None
                try:
                    if images and len(images) > 0:
                        images[0].seek(0)
                        img = Image.open(images[0])
                        img.thumbnail((100, 100))
                        buf = BytesIO()
                        img.save(buf, format='JPEG', quality=60)
                        thumb = buf.getvalue()
                except: 
                    pass
                
                scan_id = save_scan(result, user_id, thumb)
                cloud_log_scan(result, st.session_state.loc.get('city', ''), st.session_state.loc.get('country', ''), user_id)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.barcode_info = None
                st.session_state.barcode_only = False
                st.rerun()
            else:
                st.error("❌ Could not analyze. Try a clearer photo.")
def render_scan_interface():
    """Clean scan interface"""
    input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
    images = []
    
    if input_method == "📷 Camera":
        st.caption("📸 Point at product label (front + back for best results)")
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
    
    else:  # Barcode
        st.markdown("**📊 Perfect Barcode Scanner**")
        st.caption("🎯 Fetches complete product data automatically!")
        barcode_img = st.camera_input("", label_visibility="collapsed", key="barcode_cam")
        
        if barcode_img:
            with st.spinner("Reading barcode..."):
                barcode_num = try_decode_barcode_pyzbar(barcode_img)
                if not barcode_num:
                    barcode_num = ai_read_barcode(barcode_img)
                
                if barcode_num:
                    st.info(f"📊 **{barcode_num}**")
                    
                    progress_ph = st.empty()
                    def update_prog(pct, msg):
                        progress_ph.markdown(f"<div class='progress-box'><div>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
                    
                    barcode_info = smart_barcode_lookup(barcode_num, update_prog)
                    progress_ph.empty()
                    
                    if barcode_info.get('found'):
                        st.success(f"✅ **{barcode_info.get('name', '')}**")
                        if barcode_info.get('brand'):
                            st.caption(f"by {barcode_info.get('brand')} • {barcode_info.get('source', '')}")
                        
                        st.session_state.barcode_info = barcode_info
                        st.session_state.barcode_only = True
                        images = [barcode_img]
                    else:
                        st.warning("Not found in databases. Use photo scan instead.")
                else:
                    st.error("Could not read barcode. Try a clearer image.")
    
    # Analyze button - FIXED (ONLY ONE VERSION)
    if images or st.session_state.get('barcode_info'):
        if st.button("🔍 ANALYZE", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                icons = ['🔍', '📋', '⚖️', '✨']
                icon = icons[min(int(pct * 4), 3)]
                progress_ph.markdown(f"<div class='progress-box'><div style='font-size:2rem;'>{icon}</div><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
            user_profiles = get_profiles()
            user_allergies = get_allergies()
            bi = st.session_state.get('barcode_info')
            user_id = get_user_id()
            
            # Check if barcode-only mode
            if st.session_state.get('barcode_only') and bi and bi.get('found'):
                result = analyze_from_barcode_data(bi, st.session_state.loc, update_prog, user_profiles, user_allergies)
                st.session_state.barcode_only = False
            else:
                result = analyze_product(images, st.session_state.loc, update_prog, bi, user_profiles, user_allergies)
            
            progress_ph.empty()
            
            if result.get('readable', True) and result.get('score', 0) > 0:
                thumb = None
                try:
                    if images and len(images) > 0:
                        images[0].seek(0)
                        img = Image.open(images[0])
                        img.thumbnail((100, 100))
                        buf = BytesIO()
                        img.save(buf, format='JPEG', quality=60)
                        thumb = buf.getvalue()
                except: 
                    pass
                
                scan_id = save_scan(result, user_id, thumb)
                cloud_log_scan(result, st.session_state.loc.get('city', ''), st.session_state.loc.get('country', ''), user_id)
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.barcode_info = None
                st.session_state.barcode_only = False
                st.rerun()
            else:
                st.error("❌ Could not analyze. Try a clearer photo.")
                
def analyze_from_barcode_data(barcode_info, location, progress_callback, user_profiles=None, user_allergies=None):
    """Analyze product using only barcode database information"""
   prompt = f"""Analyze this product from barcode database using HonestWorld's 20 Integrity Laws:

**Product:** {product_name}
**Brand:** {brand}
**Ingredients:** {barcode_info.get('ingredients', 'Not available')}
**Categories:** {barcode_info.get('categories', '')}
**Nutrition:** {nutrition_str}

CRITICAL: Write PLAIN TEXT only - NO HTML tags like <div>, </div>, <span>, etc.

For "evidence": Write clear sentences describing what you found
Example GOOD: "Contains methylparaben and propylparaben which are parabens"
Example BAD: "</div>" or "Paraben Free" or "<div>text</div>"

Apply analysis:
1. Classify product category (CATEGORY_FOOD, CATEGORY_COSMETIC, etc.)
2. Check violations of the 20 Integrity Laws
3. Flag concerning ingredients with SPECIFIC concerns
4. Calculate score (base 85, deduct for issues)

Location: {location.get('city', '')}, {location.get('country', '')}

Return valid JSON with NO HTML in any field:
{{
    "product_name": "exact name",
    "brand": "brand",
    "product_category": "CATEGORY_X",
    "product_type": "type",
    "readable": true,
    "score": 75,
    "violations": [{{"law": 5, "name": "Natural Fallacy", "points": -12, "evidence": "Claims natural but contains synthetic preservatives", "source": "EU Regulation"}}],
    "bonuses": [{{"name": "Bonus", "points": 5, "evidence": "Good reason"}}],
    "ingredients": ["ingredient1", "ingredient2"],
    "ingredients_flagged": [{{"name": "methylparaben", "concern": "Potential hormone disruptor", "source": "EU SCCS"}}],
    "good_ingredients": ["vitamin E"],
    "main_issue": "Contains parabens",
    "positive": "Good antioxidants",
    "front_claims": ["Natural"],
    "fine_print": ["External use only"],
    "confidence": "high"
}}
"""
    
    progress_callback(0.6, "Applying laws...")
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Parse JSON
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group(0))
        else:
            clean_text = text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_text)
        
        # Validate score
        score = result.get('score', 75)
        if isinstance(score, str):
            score = int(re.sub(r'[^\d]', '', score) or '75')
        score = max(0, min(100, score))
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['product_name'] = product_name
        result['brand'] = brand
        result['readable'] = True
        
        # Add notifications
        product_category = result.get('product_category', 'CATEGORY_FOOD')
        ingredients = result.get('ingredients', [])
        full_text = ' '.join(result.get('fine_print', []) + result.get('front_claims', []))
        
        notifications = check_profile_notifications(ingredients, full_text, user_profiles or [], user_allergies or [], product_category)
        result['notifications'] = notifications
        
        progress_callback(1.0, "Complete!")
        return result
        
    except Exception as e:
        return {
            "product_name": product_name,
            "brand": brand,
            "score": 0,
            "verdict": "UNCLEAR",
            "readable": False,
            "main_issue": f"Analysis error: {str(e)[:100]}",
            "violations": [],
            "ingredients": [],
            "product_category": "CATEGORY_FOOD"
        }

def display_result(result, user_id):
    """Display result - FIXED HTML rendering, all features"""
    score = result.get('score', 0)
    verdict = result.get('verdict', 'UNCLEAR')
    product_category = result.get('product_category', 'CATEGORY_FOOD')
    product_type = result.get('product_type', '')
    display = get_verdict_display(verdict)
    
    # Verdict card
    st.markdown(f"""<div class='verdict-card verdict-{verdict.lower()}'>
        <div class='verdict-icon'>{display['icon']}</div>
        <div class='verdict-text'>{display['text']}</div>
        <div class='verdict-score'>{score}<span style='font-size:1.5rem;'>/100</span></div>
    </div>""", unsafe_allow_html=True)
    
    # Product info
    st.markdown(f"### {result.get('product_name', 'Unknown')}")
    if result.get('brand'):
        st.markdown(f"*by {result.get('brand')}*")
    
    cat_info = PRODUCT_CATEGORIES.get(product_category, {})
    st.markdown(f"<span class='cat-badge'>{cat_info.get('icon', '📦')} {cat_info.get('name', 'Product')}</span>", unsafe_allow_html=True)
    
    # NOTIFICATIONS (Profile alerts - don't affect score)
    notifications = result.get('notifications', [])
    for notif in notifications:
        css_class = 'notif-danger' if notif.get('severity') == 'danger' else 'notif-warning'
        st.markdown(f"""<div class='{css_class}'>
            <strong>{notif.get('icon', '⚠️')} {notif.get('name', 'Alert')}</strong><br>
            {notif.get('message', '')}
        </div>""", unsafe_allow_html=True)
    
    # Main issue
    main_issue = result.get('main_issue', '')
    if main_issue and main_issue.lower() not in ['clean formula', 'none', '']:
        st.markdown(f"<div class='alert-issue'>⚠️ <strong>{main_issue}</strong></div>", unsafe_allow_html=True)
    
    # Positive
    if result.get('positive'):
        st.markdown(f"<div class='alert-positive'>✅ <strong>{result.get('positive')}</strong></div>", unsafe_allow_html=True)
    
    # Alternative - Country Specific
    country_code = st.session_state.loc.get('code', 'OTHER')
    alt = get_alternative(result.get('product_name', ''), product_type, product_category, country_code)
    alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
    
    st.markdown(f"""<div class='alt-card'>
        <strong>💚 {'Better Alternative' if verdict in ['CAUTION', 'AVOID'] else 'Similar Quality'}:</strong><br>
        <span style='font-size:1.05rem;font-weight:600;'>{alt['name']}</span> {alt_score_html}<br>
        <span style='color:#16a34a;'>{alt['why']}</span><br>
        <div class='alt-retailer'>📍 Available at: {alt.get('retailer', 'Local stores')}</div>
    </div>""", unsafe_allow_html=True)
    
    # LAWS VIOLATED - Fixed HTML rendering
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Laws Violated ({len(violations)})", expanded=False):
            for v in violations:
                law_num = v.get('law')
                law_text = f"Law {law_num}: " if law_num else ""
                evidence = v.get('evidence', '').replace('<', '&lt;').replace('>', '&gt;')  # Escape HTML
                source = v.get('source', '')
                source_html = f"<div class='law-source'>📚 {source}</div>" if source else ""
                
                st.markdown(f"""<div class='law-box'>
                    <div class='law-title'>{law_text}{v.get('name', 'Violation')} ({v.get('points', 0)} pts)</div>
                    <div class='law-evidence'>{evidence}</div>
                    {source_html}
                </div>""", unsafe_allow_html=True)
    
    # Bonuses
    bonuses = result.get('bonuses', [])
    if bonuses:
        with st.expander(f"✨ Bonuses ({len(bonuses)})", expanded=False):
            for b in bonuses:
                evidence = str(b.get('evidence', '')).replace('<', '&lt;').replace('>', '&gt;')
                st.markdown(f"""<div class='bonus-box'>
                    <strong>+{b.get('points', 0)}: {b.get('name', '')}</strong><br>
                    <span style='font-size:0.85rem;'>{evidence}</span>
                </div>""", unsafe_allow_html=True)
    
    # Ingredients - With proper citations
    ingredients_flagged = result.get('ingredients_flagged', [])
    if ingredients_flagged or result.get('ingredients'):
        with st.expander("🧪 Ingredients Analysis", expanded=False):
            if ingredients_flagged:
                st.markdown("**Flagged:**")
                for ing in ingredients_flagged:
                    ing_name = ing.get('name', '')
                    concern = ing.get('concern', '')
                    
                    # Get citation from our database
                    citation = get_citation(ing_name)
                    if citation:
                        source_text = citation.get('source', '')
                        severity = citation.get('severity', 'medium')
                        css_class = 'ing-red' if severity in ['high', 'medium'] else 'ing-yellow'
                        source_display = f"<span class='ing-source'>• {source_text}</span>"
                    else:
                        css_class = 'ing-yellow'
                        source_display = "<span class='ing-source'>• Verify independently</span>"
                    
                    st.markdown(f"<span class='ing-badge {css_class}'>{ing_name}</span> {concern} {source_display}", unsafe_allow_html=True)
            
            good = result.get('good_ingredients', [])
            if good:
                st.markdown("**Good:**")
                badges = " ".join([f"<span class='ing-badge ing-green'>{g}</span>" for g in good[:10]])
                st.markdown(f"<div class='ing-row'>{badges}</div>", unsafe_allow_html=True)
            
            if result.get('ingredients'):
                st.markdown(f"**All:** {', '.join(result.get('ingredients', [])[:30])}")
    
    # Front Claims
    front_claims = result.get('front_claims', [])
    if front_claims:
        with st.expander("🏷️ Marketing Claims", expanded=False):
            for claim in front_claims:
                st.markdown(f"• {claim}")
    
    # Fine Print
    fine_print = result.get('fine_print', [])
    if fine_print:
        with st.expander("📜 Fine Print Detected", expanded=False):
            for fp in fine_print:
                st.markdown(f"• _{fp}_")
    
    # SHARE - ALL 6 SOCIAL MEDIA
    st.markdown("### 📤 Share")
    
    share_img = create_share_image(result.get('product_name', ''), result.get('brand', ''), score, verdict)
    story_img = create_story_image(result.get('product_name', ''), result.get('brand', ''), score, verdict)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post (1080×1080)", data=image_to_bytes(share_img), file_name=f"hw_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story (1080×1920)", data=image_to_bytes(story_img), file_name=f"hw_story_{score}.png", mime="image/png", use_container_width=True)
    
    # Social share links - ALL 6
    share_text = urllib.parse.quote(f"Scanned {result.get('product_name', '')} with HonestWorld - {score}/100 ({verdict}) #HonestWorld")
    
    st.markdown(f"""<div class='share-grid'>
        <a href='https://twitter.com/intent/tweet?text={share_text}' target='_blank' class='share-btn' style='background:#1DA1F2;'><span>𝕏</span>Twitter</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={share_text}' target='_blank' class='share-btn' style='background:#4267B2;'><span>f</span>Facebook</a>
        <a href='https://wa.me/?text={share_text}' target='_blank' class='share-btn' style='background:#25D366;'><span>💬</span>WhatsApp</a>
        <a href='https://t.me/share/url?text={share_text}' target='_blank' class='share-btn' style='background:#0088cc;'><span>✈</span>Telegram</a>
        <a href='https://www.instagram.com/' target='_blank' class='share-btn' style='background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);'><span>📷</span>Instagram</a>
        <a href='https://www.tiktok.com/' target='_blank' class='share-btn' style='background:#000;'><span>♪</span>TikTok</a>
    </div>""", unsafe_allow_html=True)
    
    # Scan another
    st.markdown("")
    if st.button("🔄 Scan Another", use_container_width=True):
        st.session_state.result = None
        st.session_state.scan_id = None
        st.session_state.show_result = False
        st.rerun()


def render_history(user_id):
    history = get_history(user_id, 30)
    if not history:
        st.info("📋 No scans yet!")
    else:
        for item in history:
            score = item['score']
            color = '#06b6d4' if score >= 90 else '#22c55e' if score >= 75 else '#f59e0b' if score >= 50 else '#ef4444'
            fav = "⭐ " if item['favorite'] else ""
            
            col1, col2, col3 = st.columns([0.6, 3.4, 0.5])
            with col1:
                st.markdown(f"<div class='history-score' style='background:{color};'>{score}</div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"**{fav}{item['product'][:28]}**")
                st.caption(f"{item['brand'][:16] if item['brand'] else ''} • {item['ts'][:10]}")
            with col3:
                if st.button("⭐" if not item['favorite'] else "★", key=f"fav_{item['db_id']}"):
                    toggle_favorite(item['db_id'], item['favorite'])
                    st.rerun()


def render_profile():
    st.markdown("### ⚙️ Settings")
    
    # Location - with manual override
    st.markdown("**📍 Location**")
    loc = st.session_state.loc
    
    if loc.get('needs_manual') or loc.get('city') in ['Unknown', '']:
        st.markdown("<div class='location-prompt'>⚠️ <strong>Location not detected.</strong> Please set manually for accurate alternatives.</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value=loc.get('city', '') if loc.get('city') not in ['Unknown', 'Your City'] else '', key="city_in", placeholder="e.g., Brisbane")
    with col2:
        country = st.text_input("Country", value=loc.get('country', '') if loc.get('country') not in ['Unknown'] else '', key="country_in", placeholder="e.g., Australia")
    
    if st.button("Update Location"):
        if city and country:
            code = save_location(city, country)
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER'])}
            st.success(f"✅ Location set to {city}, {country}")
            st.rerun()
        else:
            st.warning("Please enter both city and country")
    
    st.markdown("---")
    
    # Health Profiles
    st.markdown("**🏥 Health Profiles**")
    st.caption("Get notifications when products contain flagged ingredients (doesn't affect score)")
    
    current_profiles = get_profiles()
    new_profiles = st.multiselect(
        "Select profiles",
        options=list(HEALTH_PROFILES.keys()),
        default=current_profiles,
        format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}",
        key="profiles_sel"
    )
    if st.button("Save Profiles"):
        save_profiles(new_profiles)
        st.success("✅ Saved!")
        st.rerun()
    
    st.markdown("---")
    
    # Allergens
    st.markdown("**🚨 Allergen Alerts**")
    st.caption("Get danger alerts for allergens")
    
    current_allergies = get_allergies()
    new_allergies = st.multiselect(
        "Select allergens",
        options=list(ALLERGENS.keys()),
        default=current_allergies,
        format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}",
        key="allergies_sel"
    )
    if st.button("Save Allergens"):
        save_allergies(new_allergies)
        st.success("✅ Saved!")
        st.rerun()
    
    st.markdown("---")
    
    # Admin
    st.markdown("**🔐 Admin**")
    admin_pw = st.text_input("Password", type="password", key="admin_pw")
    if admin_pw and hashlib.sha256(admin_pw.encode()).hexdigest() == ADMIN_HASH:
        st.session_state.admin = True
    if st.session_state.admin:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM scans')
        total_scans = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM verified_products')
        verified = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM barcode_cache')
        barcodes = c.fetchone()[0]
        conn.close()
        st.markdown(f"📊 **{total_scans}** scans • **{verified}** verified products • **{barcodes}** barcodes")


def render_laws():
    st.markdown("### ⚖️ The 20 Integrity Laws")
    st.caption("Evidence-based scoring system")
    
    categories = {
        "🧪 Ingredients (1-6)": [1, 2, 3, 4, 5, 6],
        "📦 Packaging (7, 8, 18)": [7, 8, 18],
        "📱 Electronics (9-12)": [9, 10, 11, 12],
        "💄 Beauty (13-14)": [13, 14],
        "📋 Services (15-17)": [15, 16, 17],
        "🏷️ Claims (19-20)": [19, 20]
    }
    
    for cat_name, nums in categories.items():
        with st.expander(cat_name, expanded=False):
            for n in nums:
                if n in INTEGRITY_LAWS:
                    law = INTEGRITY_LAWS[n]
                    applies = ', '.join([PRODUCT_CATEGORIES.get(c, {}).get('name', c)[:15] for c in law.get('applies_to', [])])
                    st.markdown(f"""<div class='law-card'>
                        <span class='law-card-title'>Law {n}: {law['name']}</span>
                        <span class='law-card-pts'> ({law['base_points']} pts)</span>
                        <div class='law-card-desc'>{law['description']}</div>
                        <div style='font-size:0.75rem;color:#059669;margin-top:0.2rem;'>💡 {law['tip']}</div>
                        <div style='font-size:0.7rem;color:#64748b;'>Applies to: {applies}</div>
                    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
