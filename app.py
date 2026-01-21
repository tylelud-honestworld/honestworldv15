"""
🌍 HONESTWORLD v27.0 - CONTEXT-AWARE INTEGRITY ENGINE
Zero Hallucination • Provable Truth • Perfect Barcode • Smart Categories

Core Principles:
1. ZERO HALLUCINATION - If it can't be proved, don't display it
2. CONTEXT GATEKEEPER - Category determines which rules apply
3. PROVABLE TRUTH - Every red flag needs citation, else yellow
4. PERFECT BARCODE - Fetch from local retailers when label is hard to scan
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

VERSION = "27.0"
LOCAL_DB = Path.home() / "honestworld_v27.db"

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: CONTEXT GATEKEEPER - Product Categories & Rule Sets
# ═══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATEGORIES = {
    "CATEGORY_FOOD": {
        "name": "Food & Beverage",
        "icon": "🍎",
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "fresh", "baked", "candy", "protein_bar", "meal"],
        "keywords": ["nutrition facts", "calories", "serving size", "sugar", "protein", "carbohydrate", "sodium", "ingredients:", "total fat", "dietary fiber"],
        "enabled_rules": ["nutritional", "sugar_analysis", "sodium_check", "allergen", "fine_print", "shrinkflation", "claims_vs_facts"],
        "disabled_rules": ["chemical_safety", "repairability", "spec_check"],
        "health_profiles": ["diabetes", "heartcondition", "glutenfree", "vegan", "allergyprone", "keto"]
    },
    "CATEGORY_SUPPLEMENT": {
        "name": "Supplements & Vitamins",
        "icon": "💊",
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega", "multivitamin", "amino", "pre_workout"],
        "keywords": ["supplement facts", "dietary supplement", "daily value", "amount per serving", "other ingredients"],
        "enabled_rules": ["concentration_check", "third_party_testing", "allergen", "fine_print", "claims_vs_facts"],
        "disabled_rules": ["chemical_safety", "repairability", "shrinkflation"],
        "health_profiles": ["diabetes", "pregnancy", "vegan", "glutenfree", "allergyprone"]
    },
    "CATEGORY_COSMETIC": {
        "name": "Cosmetics & Personal Care",
        "icon": "🧴",
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "face_cream", "toner", "mask", "deodorant", "makeup"],
        "keywords": ["for external use", "apply to", "skin", "hair", "dermatologist", "spf", "moisturize", "directions:"],
        "enabled_rules": ["chemical_safety", "allergen", "fragrance_check", "claims_vs_facts", "concentration_check", "fine_print"],
        "disabled_rules": ["nutritional", "sugar_analysis", "sodium_check", "repairability", "shrinkflation"],
        "health_profiles": ["sensitive", "allergyprone", "pregnancy", "baby", "vegan"]
    },
    "CATEGORY_ELECTRONICS": {
        "name": "Electronics & Tech",
        "icon": "📱",
        "subtypes": ["phone", "laptop", "tablet", "accessory", "cable", "charger", "audio", "wearable", "appliance", "battery"],
        "keywords": ["battery", "usb", "wireless", "bluetooth", "mah", "watt", "volt", "input:", "output:", "fcc", "ce mark"],
        "enabled_rules": ["spec_check", "repairability", "claims_vs_facts", "compatibility_check"],
        "disabled_rules": ["nutritional", "chemical_safety", "allergen", "sugar_analysis"],
        "health_profiles": []
    },
    "CATEGORY_HOUSEHOLD": {
        "name": "Household & Cleaning",
        "icon": "🧹",
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener", "laundry", "dish_soap"],
        "keywords": ["surface", "clean", "disinfect", "laundry", "dish", "warning:", "caution:", "keep out of reach"],
        "enabled_rules": ["chemical_safety", "allergen", "fine_print", "claims_vs_facts"],
        "disabled_rules": ["nutritional", "sugar_analysis", "repairability", "spec_check"],
        "health_profiles": ["sensitive", "allergyprone", "baby", "pregnancy"]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4: PROVABLE TRUTH - Citation Database (Red = has source, Yellow = no source)
# ═══════════════════════════════════════════════════════════════════════════════
CITATION_DATABASE = {
    # COSMETIC INGREDIENTS - With full citations
    "paraben": {
        "concern": "Potential endocrine disruption",
        "severity": "red",  # Has citation = red allowed
        "source": "EU Scientific Committee on Consumer Safety (SCCS)",
        "source_url": "https://ec.europa.eu/health/scientific_committees/consumer_safety",
        "year": "2013, updated 2020",
        "context": ["cosmetics"],
        "note": "Restricted to 0.4% individual, 0.8% total in EU"
    },
    "methylparaben": {
        "concern": "Potential hormone disruption at high doses",
        "severity": "red",
        "source": "EU SCCS Opinion",
        "source_url": "https://ec.europa.eu/health/scientific_committees/consumer_safety",
        "year": "2013",
        "context": ["cosmetics"]
    },
    "propylparaben": {
        "concern": "Higher absorption rate, restricted in EU",
        "severity": "red",
        "source": "EU SCCS - Restricted to 0.14%",
        "year": "2013",
        "context": ["cosmetics"]
    },
    "butylparaben": {
        "concern": "Higher potency endocrine activity",
        "severity": "red",
        "source": "Danish EPA, EU SCCS",
        "year": "2013",
        "context": ["cosmetics"],
        "note": "Banned in Denmark for children under 3"
    },
    "fragrance": {
        "concern": "Undisclosed mixture of 3,000+ potential chemicals",
        "severity": "red",
        "source": "American Academy of Dermatology (AAD)",
        "source_url": "https://www.aad.org",
        "year": "2021",
        "context": ["cosmetics", "household"],
        "note": "Leading cause of cosmetic contact dermatitis"
    },
    "parfum": {
        "concern": "Same as fragrance - undisclosed chemical mixture",
        "severity": "red",
        "source": "EU Cosmetics Regulation 1223/2009",
        "context": ["cosmetics"]
    },
    "sodium lauryl sulfate": {
        "concern": "Can irritate sensitive skin",
        "severity": "yellow",  # Lower concern, still flagged
        "source": "Cosmetic Ingredient Review (CIR)",
        "year": "2005",
        "context": ["cosmetics"],
        "note": "Safe in rinse-off products per CIR panel"
    },
    "sodium laureth sulfate": {
        "concern": "Potential 1,4-dioxane contamination",
        "severity": "yellow",
        "source": "FDA Guidance",
        "context": ["cosmetics"]
    },
    "phthalate": {
        "concern": "Endocrine disruption, reproductive effects",
        "severity": "red",
        "source": "CDC National Report, EPA Phthalate Action Plan",
        "source_url": "https://www.epa.gov/assessing-and-managing-chemicals-under-tsca/phthalates",
        "year": "2012",
        "context": ["cosmetics"]
    },
    "dmdm hydantoin": {
        "concern": "Formaldehyde-releasing preservative",
        "severity": "red",
        "source": "International Agency for Research on Cancer (IARC)",
        "year": "2012",
        "context": ["cosmetics"],
        "note": "IARC classifies formaldehyde as Group 1 carcinogen"
    },
    "quaternium-15": {
        "concern": "Formaldehyde releaser, contact allergen",
        "severity": "red",
        "source": "American Contact Dermatitis Society - Allergen of the Year 2015",
        "year": "2015",
        "context": ["cosmetics"]
    },
    "triclosan": {
        "concern": "Endocrine disruption, antibiotic resistance",
        "severity": "red",
        "source": "FDA - Banned in OTC Antiseptic Wash Products",
        "source_url": "https://www.fda.gov",
        "year": "2016",
        "context": ["cosmetics", "household"]
    },
    "oxybenzone": {
        "concern": "Potential hormone disruption, coral reef damage",
        "severity": "red",
        "source": "Hawaii Sunscreen Ban (Act 104)",
        "year": "2021",
        "context": ["cosmetics"],
        "note": "Banned in Hawaii, Key West, Palau for reef protection"
    },
    "hydroquinone": {
        "concern": "Potential carcinogen, ochronosis risk",
        "severity": "red",
        "source": "EU Cosmetics Regulation - Banned for OTC",
        "context": ["cosmetics"],
        "note": "Banned in EU, Japan, Australia for OTC use"
    },
    "retinol": {
        "concern": "Teratogenic - pregnancy risk",
        "severity": "red",
        "source": "FDA Pregnancy Category X (oral retinoids)",
        "context": ["cosmetics"],
        "note": "Avoid during pregnancy - topical caution advised"
    },
    
    # FOOD INGREDIENTS
    "trans fat": {
        "concern": "Increases LDL, heart disease risk",
        "severity": "red",
        "source": "FDA Final Rule - PHO Ban, American Heart Association",
        "source_url": "https://www.fda.gov",
        "year": "2018",
        "context": ["food"],
        "note": "Banned in US food supply"
    },
    "hydrogenated oil": {
        "concern": "May contain trans fats",
        "severity": "red",
        "source": "FDA, American Heart Association",
        "context": ["food"],
        "note": "Partially hydrogenated = trans fats"
    },
    "high fructose corn syrup": {
        "concern": "Linked to metabolic issues when over-consumed",
        "severity": "yellow",
        "source": "American Journal of Clinical Nutrition",
        "year": "2004",
        "context": ["food"]
    },
    "red 40": {
        "concern": "Hyperactivity in sensitive children",
        "severity": "yellow",
        "source": "EFSA Opinion, Southampton Study",
        "year": "2007",
        "context": ["food"],
        "note": "Requires warning in EU, not US"
    },
    "yellow 5": {
        "concern": "May cause reactions in aspirin-sensitive individuals",
        "severity": "yellow",
        "source": "FDA CFSAN",
        "context": ["food"]
    },
    "aspartame": {
        "concern": "IARC 'possibly carcinogenic' classification",
        "severity": "yellow",
        "source": "WHO IARC Review",
        "year": "2023",
        "context": ["food"],
        "note": "FDA maintains safety at approved levels"
    },
    "bpa": {
        "concern": "Endocrine disruption",
        "severity": "red",
        "source": "FDA - Banned in Baby Bottles, EFSA",
        "year": "2012",
        "context": ["food", "household"]
    },
    "titanium dioxide": {
        "concern": "Potential genotoxicity concerns",
        "severity": "red",
        "source": "EFSA Opinion - EU Food Ban",
        "year": "2022",
        "context": ["food"],
        "note": "Banned in food in EU since 2022, allowed in US"
    },
    
    # ELECTRONICS - Repairability Citations
    "sealed_battery": {
        "concern": "Reduces device lifespan, e-waste",
        "severity": "yellow",
        "source": "iFixit Repairability Standards, EU Right to Repair Directive",
        "year": "2021",
        "context": ["electronics"]
    },
    "proprietary_charger": {
        "concern": "E-waste, consumer lock-in",
        "severity": "yellow",
        "source": "EU Common Charger Directive 2022/2380",
        "year": "2022",
        "context": ["electronics"],
        "note": "USB-C mandate for EU from 2024"
    },
    "non_replaceable_parts": {
        "concern": "Planned obsolescence",
        "severity": "yellow",
        "source": "EU Ecodesign Directive, France Repairability Index",
        "context": ["electronics"]
    }
}

def get_citation(ingredient_name):
    """Get citation for ingredient - returns severity level based on evidence"""
    key = ingredient_name.lower().strip()
    
    # Direct match
    if key in CITATION_DATABASE:
        return CITATION_DATABASE[key]
    
    # Partial match
    for db_key, data in CITATION_DATABASE.items():
        if db_key in key or key in db_key:
            return data
    
    # No citation found - return yellow (unverified concern)
    return None

def get_flag_severity(ingredient_name, product_category):
    """
    PROVABLE TRUTH: Red flag only if we have citation, else yellow
    """
    citation = get_citation(ingredient_name)
    
    if citation:
        # Check if citation applies to this product category
        contexts = citation.get('context', [])
        category_map = {
            'CATEGORY_FOOD': 'food',
            'CATEGORY_SUPPLEMENT': 'food',
            'CATEGORY_COSMETIC': 'cosmetics',
            'CATEGORY_ELECTRONICS': 'electronics',
            'CATEGORY_HOUSEHOLD': 'household'
        }
        relevant_context = category_map.get(product_category, 'food')
        
        if not contexts or relevant_context in contexts:
            return citation.get('severity', 'yellow'), citation
    
    # No citation = yellow warning only
    return 'yellow', None
# ═══════════════════════════════════════════════════════════════════════════════
# THE 20 INTEGRITY LAWS - With Dynamic Category Weights
# ═══════════════════════════════════════════════════════════════════════════════
INTEGRITY_LAWS = {
    1: {"name": "Water-Down Deception", "base_points": -15, "category": "ingredients",
        "description": "Premium claim but #1 ingredient is water/cheap filler",
        "tip": "Check if first ingredient matches the premium price",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD"],
        "dynamic": {"serum": -25, "concentrate": -25, "mist": -3, "toner": -5, "beverage": 0}},
    2: {"name": "Fairy Dusting", "base_points": -12, "category": "ingredients",
        "description": "Hero ingredient advertised on front is below position #5",
        "tip": "Ingredients listed by quantity - first = most",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    3: {"name": "Split Sugar Trick", "base_points": -18, "category": "ingredients",
        "description": "Sugar split into 3+ names to hide total amount",
        "tip": "Add up ALL sugar types - often the real #1",
        "applies_to": ["CATEGORY_FOOD"]},
    4: {"name": "Low-Fat Trap", "base_points": -10, "category": "ingredients",
        "description": "Claims 'low fat' but compensates with high sugar",
        "tip": "Low-fat often means high sugar",
        "applies_to": ["CATEGORY_FOOD"]},
    5: {"name": "Natural Fallacy", "base_points": -12, "category": "claims",
        "description": "Claims 'natural' but contains synthetic ingredients",
        "tip": "'Natural' is unregulated - look for certifications",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_FOOD", "CATEGORY_HOUSEHOLD"],
        "synthetic_flags": ["phenoxyethanol", "dimethicone", "peg-", "propylene glycol", "artificial"]},
    6: {"name": "Made-With Loophole", "base_points": -8, "category": "ingredients",
        "description": "'Made with real X' but X is minimal",
        "tip": "'Made with' legally requires only tiny amount",
        "applies_to": ["CATEGORY_FOOD"]},
    7: {"name": "Serving Size Trick", "base_points": -10, "category": "packaging",
        "description": "Unrealistically small serving size",
        "tip": "Check servings per container",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    8: {"name": "Slack Fill", "base_points": -8, "category": "packaging",
        "description": "Package mostly air/empty space",
        "tip": "Check net weight, not package size",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    9: {"name": "Spec Inflation", "base_points": -15, "category": "electronics",
        "description": "'Up to X speed/capacity' unrealistic claims",
        "tip": "'Up to' means perfect lab conditions",
        "applies_to": ["CATEGORY_ELECTRONICS"]},
    10: {"name": "Compatibility Lie", "base_points": -12, "category": "electronics",
         "description": "'Universal' with hidden exceptions",
         "tip": "Check compatibility list in fine print",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    11: {"name": "Military Grade Myth", "base_points": -10, "category": "electronics",
         "description": "Claims 'military grade' without MIL-STD cert",
         "tip": "Real military spec cites MIL-STD number",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    12: {"name": "Battery Fiction", "base_points": -12, "category": "electronics",
         "description": "Unrealistic battery life claims",
         "tip": "Tested with minimal usage - expect 60-70%",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    13: {"name": "Clinical Ghost", "base_points": -12, "category": "claims",
         "description": "'Clinically proven' without citing study",
         "tip": "Real clinical proof includes study details",
         "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    14: {"name": "Concentration Trick", "base_points": -10, "category": "ingredients",
         "description": "Active ingredient too diluted to be effective",
         "tip": "Effective: Vitamin C 10-20%, Retinol 0.3-1%",
         "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"]},
    15: {"name": "Free Trap", "base_points": -15, "category": "services",
         "description": "'Free' requires credit card or hidden purchase",
         "tip": "Free trial usually auto-charges",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    16: {"name": "Unlimited Lie", "base_points": -18, "category": "services",
         "description": "'Unlimited' with hidden caps or throttling",
         "tip": "'Unlimited' rarely means truly unlimited",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    17: {"name": "Lifetime Illusion", "base_points": -10, "category": "services",
         "description": "'Lifetime warranty' with extensive exclusions",
         "tip": "'Lifetime' often has many exclusions",
         "applies_to": ["CATEGORY_ELECTRONICS"]},
    18: {"name": "Photo vs Reality", "base_points": -12, "category": "packaging",
         "description": "Package photo much better than actual product",
         "tip": "Package photos are professionally styled",
         "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    19: {"name": "Fake Certification", "base_points": -15, "category": "claims",
         "description": "Claims certification without proper verification",
         "tip": "Real certs show logo and verification ID",
         "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_ELECTRONICS"]},
    20: {"name": "Name Trick", "base_points": -10, "category": "claims",
         "description": "Product name implies absent ingredient",
         "tip": "'Honey Oat' doesn't mean much honey/oats",
         "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5: ELECTRONICS REPAIRABILITY & SHRINKFLATION
# ═══════════════════════════════════════════════════════════════════════════════
REPAIRABILITY_FACTORS = {
    "user_replaceable_battery": {"points": 15, "name": "User Replaceable Battery", "icon": "🔋"},
    "standard_screws": {"points": 5, "name": "Standard Screws (No Proprietary)", "icon": "🔩"},
    "usb_c_port": {"points": 5, "name": "Standard USB-C Port", "icon": "🔌"},
    "modular_design": {"points": 10, "name": "Modular/Repairable Design", "icon": "🔧"},
    "available_parts": {"points": 5, "name": "Spare Parts Available", "icon": "📦"},
    "sealed_battery": {"points": -10, "name": "Sealed/Non-Removable Battery", "icon": "⚠️"},
    "proprietary_screws": {"points": -5, "name": "Proprietary Screws", "icon": "❌"},
    "glued_components": {"points": -10, "name": "Glued Components", "icon": "🔒"},
    "no_repair_manual": {"points": -5, "name": "No Repair Documentation", "icon": "📵"}
}

SHRINKFLATION_REFERENCE = {
    # Category averages for comparison (grams or ml per dollar)
    "chips": {"avg_weight_per_dollar": 28, "unit": "g"},
    "cereal": {"avg_weight_per_dollar": 50, "unit": "g"},
    "chocolate": {"avg_weight_per_dollar": 25, "unit": "g"},
    "protein_bar": {"avg_weight_per_dollar": 15, "unit": "g"},
    "beverage": {"avg_volume_per_dollar": 350, "unit": "ml"},
    "ice_cream": {"avg_volume_per_dollar": 200, "unit": "ml"}
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT-AWARE HEALTH PROFILES
# ═══════════════════════════════════════════════════════════════════════════════
HEALTH_PROFILES = {
    "diabetes": {
        "name": "Diabetes", "icon": "🩺",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "dextrose", "maltose", "honey", "agave", "maltodextrin"],
        "fine_print_scan": ["high sugar", "not suitable for diabetics", "may affect blood sugar"],
        "alert_template": "Contains ingredients that may affect blood glucose"
    },
    "heartcondition": {
        "name": "Heart Health", "icon": "❤️",
        "applies_to": ["CATEGORY_FOOD"],  # ONLY FOOD - not cosmetics!
        "ingredient_flags": ["sodium", "salt", "msg", "trans fat", "hydrogenated", "saturated fat"],
        "fine_print_scan": ["high sodium", "high salt", "not suitable for low sodium"],
        "alert_template": "Contains ingredients to monitor for heart health"
    },
    "glutenfree": {
        "name": "Gluten-Free", "icon": "🌾",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["wheat", "barley", "rye", "gluten", "malt", "spelt", "kamut"],
        "fine_print_scan": ["may contain wheat", "may contain gluten", "traces of wheat", "processed in a facility", "shared equipment"],
        "alert_template": "Contains or may contain gluten"
    },
    "vegan": {
        "name": "Vegan", "icon": "🌱",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT"],
        "ingredient_flags": ["gelatin", "carmine", "honey", "milk", "whey", "casein", "egg", "lanolin", "beeswax", "collagen", "keratin"],
        "fine_print_scan": ["may contain milk", "may contain egg", "not suitable for vegans"],
        "alert_template": "May contain animal-derived ingredients"
    },
    "sensitive": {
        "name": "Sensitive Skin", "icon": "🌸",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"],
        "ingredient_flags": ["fragrance", "parfum", "alcohol denat", "essential oil", "menthol", "sulfate", "sodium lauryl"],
        "fine_print_scan": ["patch test recommended", "not suitable for sensitive skin", "may cause irritation", "discontinue if irritation"],
        "alert_template": "Contains potential irritants for sensitive skin"
    },
    "pregnancy": {
        "name": "Pregnancy", "icon": "🤰",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_SUPPLEMENT", "CATEGORY_FOOD"],
        "ingredient_flags": ["retinol", "retinoid", "salicylic acid", "benzoyl peroxide", "hydroquinone", "high dose vitamin a"],
        "fine_print_scan": ["not recommended during pregnancy", "consult doctor if pregnant", "avoid if pregnant"],
        "alert_template": "Contains ingredients to discuss with doctor during pregnancy"
    },
    "baby": {
        "name": "Baby Safe", "icon": "👶",
        "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD", "CATEGORY_FOOD"],
        "ingredient_flags": ["fragrance", "parfum", "essential oil", "menthol", "camphor", "alcohol denat"],
        "fine_print_scan": ["not for children under", "keep away from children", "not suitable for infants", "adult use only"],
        "alert_template": "May not be suitable for babies/young children"
    },
    "allergyprone": {
        "name": "Allergy Prone", "icon": "🤧",
        "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"],
        "ingredient_flags": ["peanut", "tree nut", "soy", "milk", "egg", "wheat", "shellfish", "fish", "sesame", "fragrance"],
        "fine_print_scan": ["may contain", "traces of", "processed in a facility"],
        "alert_template": "Contains common allergens"
    },
    "keto": {
        "name": "Keto Diet", "icon": "🥑",
        "applies_to": ["CATEGORY_FOOD"],
        "ingredient_flags": ["sugar", "glucose", "fructose", "corn syrup", "maltodextrin", "wheat", "rice", "potato starch"],
        "fine_print_scan": [],
        "alert_template": "Contains high-carb ingredients"
    }
}

ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", "triggers": ["wheat", "barley", "rye", "gluten", "malt", "spelt"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "dairy": {"name": "Dairy", "icon": "🥛", "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", "triggers": ["peanut", "groundnut", "arachis"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_COSMETIC"]},
    "soy": {"name": "Soy", "icon": "🫘", "triggers": ["soy", "soya", "soybean", "tofu", "lecithin"], "applies_to": ["CATEGORY_FOOD"]},
    "eggs": {"name": "Eggs", "icon": "🥚", "triggers": ["egg", "albumin", "mayonnaise", "meringue"], "applies_to": ["CATEGORY_FOOD"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish"], "applies_to": ["CATEGORY_FOOD"]},
    "fish": {"name": "Fish", "icon": "🐟", "triggers": ["fish", "salmon", "tuna", "cod", "anchovy", "fish oil"], "applies_to": ["CATEGORY_FOOD", "CATEGORY_SUPPLEMENT"]},
    "sesame": {"name": "Sesame", "icon": "🫘", "triggers": ["sesame", "tahini"], "applies_to": ["CATEGORY_FOOD"]},
    "fragrance": {"name": "Fragrance", "icon": "🌺", "triggers": ["fragrance", "parfum", "perfume"], "applies_to": ["CATEGORY_COSMETIC", "CATEGORY_HOUSEHOLD"]},
    "sulfates": {"name": "Sulfates", "icon": "🧴", "triggers": ["sulfate", "sls", "sles", "sodium lauryl", "sodium laureth"], "applies_to": ["CATEGORY_COSMETIC"]},
    "parabens": {"name": "Parabens", "icon": "⚗️", "triggers": ["paraben", "methylparaben", "propylparaben", "butylparaben"], "applies_to": ["CATEGORY_COSMETIC"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# PERFECT BARCODE SYSTEM - Multi-Source + Retailer Lookup
# ═══════════════════════════════════════════════════════════════════════════════
RETAILER_APIS = {
    "AU": {
        "name": "Australia",
        "retailers": [
            {"name": "Woolworths", "search_url": "https://www.woolworths.com.au/shop/search/products?searchTerm={query}", "type": "grocery"},
            {"name": "Coles", "search_url": "https://www.coles.com.au/search?q={query}", "type": "grocery"},
            {"name": "Chemist Warehouse", "search_url": "https://www.chemistwarehouse.com.au/search?searchtext={query}", "type": "pharmacy"},
            {"name": "Priceline", "search_url": "https://www.priceline.com.au/search/?q={query}", "type": "pharmacy"}
        ]
    },
    "US": {
        "name": "United States",
        "retailers": [
            {"name": "Target", "search_url": "https://www.target.com/s?searchTerm={query}", "type": "general"},
            {"name": "Walmart", "search_url": "https://www.walmart.com/search?q={query}", "type": "general"},
            {"name": "CVS", "search_url": "https://www.cvs.com/search?searchTerm={query}", "type": "pharmacy"},
            {"name": "Walgreens", "search_url": "https://www.walgreens.com/search/results.jsp?Ntt={query}", "type": "pharmacy"}
        ]
    },
    "GB": {
        "name": "United Kingdom",
        "retailers": [
            {"name": "Boots", "search_url": "https://www.boots.com/search?text={query}", "type": "pharmacy"},
            {"name": "Tesco", "search_url": "https://www.tesco.com/groceries/en-GB/search?query={query}", "type": "grocery"},
            {"name": "Superdrug", "search_url": "https://www.superdrug.com/search?text={query}", "type": "pharmacy"}
        ]
    },
    "NZ": {
        "name": "New Zealand",
        "retailers": [
            {"name": "Countdown", "search_url": "https://www.countdown.co.nz/shop/searchproducts?search={query}", "type": "grocery"},
            {"name": "Chemist Warehouse NZ", "search_url": "https://www.chemistwarehouse.co.nz/search?searchtext={query}", "type": "pharmacy"}
        ]
    },
    "OTHER": {
        "name": "International",
        "retailers": [
            {"name": "iHerb", "search_url": "https://www.iherb.com/search?kw={query}", "type": "supplements"},
            {"name": "Amazon", "search_url": "https://www.amazon.com/s?k={query}", "type": "general"}
        ]
    }
}

def get_retailer_search_links(product_name, country_code):
    """Generate search links for local retailers"""
    retailers = RETAILER_APIS.get(country_code, RETAILER_APIS['OTHER'])['retailers']
    encoded_name = urllib.parse.quote(product_name)
    
    links = []
    for r in retailers:
        links.append({
            'name': r['name'],
            'url': r['search_url'].format(query=encoded_name),
            'type': r['type']
        })
    return links

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

RETAILERS_DISPLAY = {
    "AU": ["Chemist Warehouse", "Priceline", "Woolworths", "Coles"],
    "US": ["CVS", "Walgreens", "Target", "Walmart", "Whole Foods"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's"],
    "NZ": ["Chemist Warehouse", "Countdown", "Unichem"],
    "CA": ["Shoppers Drug Mart", "Walmart", "London Drugs"],
    "OTHER": ["Local pharmacy", "Health food store", "iHerb", "Amazon"]
}

def get_location():
    """Auto-detect location from IP"""
    services = [
        ('https://ipapi.co/json/', lambda d: (d.get('city'), d.get('country_name'), d.get('country_code'))),
        ('https://ip-api.com/json/', lambda d: (d.get('city'), d.get('country'), d.get('countryCode'))),
    ]
    for url, extract in services:
        try:
            r = requests.get(url, timeout=5)
            if r.ok:
                d = r.json()
                city, country, code = extract(d)
                if city and city not in ['', 'Unknown', None]:
                    return {'city': city, 'country': country or '', 'code': code or 'OTHER', 
                            'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER'])}
        except: continue
    return {'city': 'Your City', 'country': 'Your Country', 'code': 'OTHER', 'retailers': RETAILERS_DISPLAY['OTHER']}
# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_product_name(name):
    return re.sub(r'[^\w\s]', '', name.lower()).strip() if name else ""

def init_db():
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT UNIQUE, user_id TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP, product TEXT, brand TEXT,
        product_category TEXT, product_type TEXT, score INTEGER, verdict TEXT,
        ingredients TEXT, violations TEXT, bonuses TEXT, fine_print_alerts TEXT,
        thumb BLOB, favorite INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS learned_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_name_lower TEXT UNIQUE,
        product_name TEXT, brand TEXT, product_type TEXT, avg_score REAL,
        scan_count INTEGER DEFAULT 1, ingredients TEXT, violations TEXT,
        last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (
        barcode TEXT PRIMARY KEY, product_name TEXT, brand TEXT, ingredients TEXT,
        product_type TEXT, categories TEXT, nutrition TEXT, image_url TEXT,
        source TEXT, confidence TEXT, last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY DEFAULT 1, scans INTEGER DEFAULT 0, avoided INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0, last_scan DATE
    )''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
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
    code_map = {'australia': 'AU', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB', 'new zealand': 'NZ', 'canada': 'CA'}
    country_lower = (country or '').lower()
    code = 'OTHER'
    for key, val in code_map.items():
        if key in country_lower:
            code = val
            break
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
            c.execute('UPDATE learned_products SET avg_score=?, scan_count=?, last_scanned=CURRENT_TIMESTAMP, ingredients=?, violations=? WHERE product_name_lower=?',
                      (new_avg, new_count, json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])), name_lower))
        else:
            c.execute('INSERT INTO learned_products (product_name_lower, product_name, brand, product_type, avg_score, ingredients, violations) VALUES (?,?,?,?,?,?,?)',
                      (name_lower, name, result.get('brand', ''), result.get('product_type', ''), result.get('score', 70),
                       json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', []))))
        conn.commit()
        conn.close()
    except: pass

def get_learned_product(product_name):
    try:
        name_lower = normalize_product_name(product_name)
        if not name_lower: return None
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, product_type, avg_score, scan_count FROM learned_products WHERE product_name_lower = ?', (name_lower,))
        r = c.fetchone()
        conn.close()
        if r: return {'product_name': r[0], 'brand': r[1], 'product_type': r[2], 'score': int(r[3]), 'scan_count': r[4]}
    except: pass
    return None

def cache_barcode(barcode, data):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO barcode_cache (barcode, product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, confidence, last_updated) 
                     VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''),
                   data.get('product_type', ''), data.get('categories', ''), json.dumps(data.get('nutrition', {})),
                   data.get('image_url', ''), data.get('source', ''), data.get('confidence', 'medium')))
        conn.commit()
        conn.close()
    except: pass

def get_cached_barcode(barcode):
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT product_name, brand, ingredients, product_type, categories, nutrition, image_url, source, confidence FROM barcode_cache WHERE barcode = ?', (barcode,))
        r = c.fetchone()
        conn.close()
        if r and r[0]:
            return {'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2], 'product_type': r[3],
                    'categories': r[4], 'nutrition': json.loads(r[5]) if r[5] else {}, 'image_url': r[6],
                    'source': r[7], 'confidence': r[8], 'cached': True}
    except: pass
    return None

def save_scan(result, user_id, thumb=None):
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO scans (scan_id, user_id, product, brand, product_category, product_type, score, verdict, ingredients, violations, bonuses, fine_print_alerts, thumb) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (sid, user_id, result.get('product_name', ''), result.get('brand', ''), result.get('product_category', ''),
               result.get('product_type', ''), result.get('score', 0), result.get('verdict', ''),
               json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])),
               json.dumps(result.get('bonuses', [])), json.dumps(result.get('fine_print_alerts', [])), thumb))
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

# ═══════════════════════════════════════════════════════════════════════════════
# PERFECT BARCODE SYSTEM - Multiple Sources + AI Enhancement
# ═══════════════════════════════════════════════════════════════════════════════

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
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L'), img.rotate(90), img.rotate(270)]:
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
        resp = model.generate_content([
            "Find and read the barcode in this image. Return ONLY the numeric digits beneath the barcode lines. "
            "If there are multiple barcodes, return the main product barcode (usually UPC/EAN). "
            "Return ONLY digits, no spaces or other characters. If unreadable, return: NONE", img
        ])
        text = resp.text.strip().upper()
        if 'NONE' in text or 'CANNOT' in text or 'UNREADABLE' in text: return None
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14: return digits
    except: pass
    return None

def lookup_barcode_all_sources(barcode):
    """Search ALL available databases for maximum accuracy"""
    results = []
    
    # 1. Open Food Facts (Global food database)
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
    
    # 2. Open Beauty Facts (Cosmetics)
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
    
    # 3. Open Products Facts (Household)
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
    
    # 4. UPC Item DB (General - good for supplements, electronics)
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
    
    # 5. Nutritionix (Food database with detailed nutrition)
    try:
        r = requests.get(f"https://trackapi.nutritionix.com/v2/search/item?upc={barcode}",
                        headers={"x-app-id": "common", "x-app-key": "common"}, timeout=10)
        if r.ok:
            d = r.json()
            if d.get('foods'):
                food = d['foods'][0]
                results.append({
                    'found': True, 'name': food.get('food_name', ''), 'brand': food.get('brand_name', ''),
                    'nutrition': {'calories': food.get('nf_calories'), 'protein': food.get('nf_protein'),
                                 'carbs': food.get('nf_total_carbohydrate'), 'fat': food.get('nf_total_fat'),
                                 'sugar': food.get('nf_sugars'), 'sodium': food.get('nf_sodium')},
                    'product_type': 'food', 'source': 'Nutritionix', 'confidence': 'high'
                })
    except: pass
    
    # Return BEST result (prioritize: has ingredients > high confidence > longer name)
    if results:
        results.sort(key=lambda x: (
            bool(x.get('ingredients')),
            x.get('confidence') == 'high',
            len(x.get('name', ''))
        ), reverse=True)
        return results[0]
    
    return {'found': False}

def smart_barcode_lookup(barcode, progress_callback=None):
    """Perfect barcode lookup with caching"""
    if progress_callback: progress_callback(0.1, "Checking cache...")
    
    cached = get_cached_barcode(barcode)
    if cached:
        if progress_callback: progress_callback(1.0, "✓ Found in cache!")
        return cached
    
    if progress_callback: progress_callback(0.3, "Searching global databases...")
    
    result = lookup_barcode_all_sources(barcode)
    
    if result.get('found'):
        if progress_callback: progress_callback(0.9, "✓ Product found!")
        cache_barcode(barcode, result)
        return result
    
    if progress_callback: progress_callback(1.0, "Not in databases - use photo scan")
    return {'found': False, 'barcode': barcode}
# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2 & 3: CLAIM VS FACT ENGINE + FINE PRINT SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

def check_fine_print_alerts(full_text, user_profiles, user_allergies, product_category):
    """
    MODULE 3: Deep Scan Profile Guard
    Scans entire text for exclusionary phrases beyond just ingredients
    """
    alerts = []
    if not full_text: return alerts
    text_lower = full_text.lower()
    
    # Check profiles
    for profile_key in user_profiles:
        if profile_key not in HEALTH_PROFILES: continue
        profile = HEALTH_PROFILES[profile_key]
        
        # Check if profile applies to this category
        if product_category not in profile.get('applies_to', []): continue
        
        # Scan for fine print phrases
        for phrase in profile.get('fine_print_scan', []):
            if phrase.lower() in text_lower:
                alerts.append({
                    'type': 'fine_print',
                    'profile': profile_key,
                    'profile_name': profile['name'],
                    'icon': profile['icon'],
                    'matched_phrase': phrase,
                    'severity': 'high',
                    'message': f"Fine print warning: \"{phrase}\" detected"
                })
                break
    
    # Check allergens
    for allergy_key in user_allergies:
        if allergy_key not in ALLERGENS: continue
        allergen = ALLERGENS[allergy_key]
        
        if product_category not in allergen.get('applies_to', []): continue
        
        # Fine print patterns for allergens
        fine_print_patterns = [
            f"may contain {allergy_key}", f"traces of {allergy_key}",
            f"processed in a facility that handles {allergy_key}",
            f"manufactured on shared equipment with {allergy_key}"
        ]
        for trigger in allergen['triggers']:
            fine_print_patterns.extend([
                f"may contain {trigger}", f"traces of {trigger}"
            ])
        
        for pattern in fine_print_patterns:
            if pattern in text_lower:
                alerts.append({
                    'type': 'allergen_fine_print',
                    'allergen': allergy_key,
                    'allergen_name': allergen['name'],
                    'icon': allergen['icon'],
                    'matched_phrase': pattern,
                    'severity': 'high',
                    'message': f"Fine print: \"{pattern}\" detected"
                })
                break
    
    return alerts

def check_health_alerts(ingredients, user_allergies, user_profiles, product_category):
    """Context-aware health alerts - only applies relevant rules based on category"""
    alerts = []
    if not ingredients: return alerts
    ing_text = ' '.join(ingredients).lower() if isinstance(ingredients, list) else ingredients.lower()
    
    # Allergens
    for allergy_key in user_allergies:
        if allergy_key not in ALLERGENS: continue
        allergen = ALLERGENS[allergy_key]
        if product_category not in allergen.get('applies_to', []): continue
        
        for trigger in allergen['triggers']:
            if trigger.lower() in ing_text:
                alerts.append({
                    'type': 'allergy', 'name': allergen['name'], 'icon': allergen['icon'],
                    'trigger': trigger, 'severity': 'high',
                    'message': f"Contains {trigger}"
                })
                break
    
    # Health profiles - CONTEXT GATEKEEPER
    for profile_key in user_profiles:
        if profile_key not in HEALTH_PROFILES: continue
        profile = HEALTH_PROFILES[profile_key]
        
        # CRITICAL: Only apply if category matches
        if product_category not in profile.get('applies_to', []): continue
        
        for flag in profile.get('ingredient_flags', []):
            if flag.lower() in ing_text:
                alerts.append({
                    'type': 'profile', 'name': profile['name'], 'icon': profile['icon'],
                    'trigger': flag, 'severity': 'medium',
                    'message': profile.get('alert_template', f"Contains {flag}")
                })
                break
    
    return alerts

# ═══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVES DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVES = {
    "cleanser": {"name": "CeraVe Hydrating Cleanser", "why": "Fragrance-free, ceramides, gentle", "score": 92},
    "moisturizer": {"name": "CeraVe Moisturizing Cream", "why": "Ceramides, hyaluronic acid, fragrance-free", "score": 94},
    "serum": {"name": "The Ordinary Niacinamide 10%", "why": "Transparent formula, effective concentration", "score": 91},
    "sunscreen": {"name": "EltaMD UV Clear SPF 46", "why": "Zinc oxide, fragrance-free", "score": 93},
    "shampoo": {"name": "Free & Clear Shampoo", "why": "No sulfates, fragrance, parabens", "score": 94},
    "body_lotion": {"name": "Vanicream Moisturizing Lotion", "why": "No dyes, fragrance, parabens", "score": 95},
    "deodorant": {"name": "Native Deodorant (Unscented)", "why": "No aluminum, parabens", "score": 86},
    "protein_bar": {"name": "RXBAR", "why": "Simple ingredients, no added sugar", "score": 84},
    "cereal": {"name": "Nature's Path Organic", "why": "USDA organic, no artificial colors", "score": 85},
    "snack": {"name": "Larabar", "why": "Whole food ingredients only", "score": 82},
    "vitamin": {"name": "Thorne Research", "why": "Third-party tested, bioavailable forms", "score": 94},
    "supplement": {"name": "NOW Foods", "why": "GMP certified, third-party tested", "score": 90},
    "protein": {"name": "Momentous Whey", "why": "NSF Certified for Sport", "score": 91},
    "default": {"name": "Check EWG.org", "why": "Independent safety ratings", "score": None}
}

def get_alternative(product_name, product_type, product_category):
    search = f"{product_name} {product_type or ''}".lower()
    for key in ALTERNATIVES:
        if key in search and key != 'default':
            alt = ALTERNATIVES[key]
            if alt['name'].lower() not in search: return alt
    if product_category == 'CATEGORY_SUPPLEMENT': return ALTERNATIVES.get('supplement', ALTERNATIVES['default'])
    if product_category == 'CATEGORY_COSMETIC':
        for term in ['cleanser', 'moisturizer', 'serum', 'shampoo', 'lotion']:
            if term in search: return ALTERNATIVES.get(term, ALTERNATIVES['default'])
    if product_category == 'CATEGORY_FOOD':
        for term in ['bar', 'cereal', 'snack', 'protein']:
            if term in search: return ALTERNATIVES.get(term if term != 'bar' else 'protein_bar', ALTERNATIVES['default'])
    return ALTERNATIVES['default']

# ═══════════════════════════════════════════════════════════════════════════════
# AI ANALYSIS WITH CONTEXT GATEKEEPER
# ═══════════════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are HonestWorld's Context-Aware Integrity Engine.

## CRITICAL: ZERO HALLUCINATION POLICY
- ONLY report what you can PROVE from the image
- If you cannot read something clearly, say "Unable to verify"
- Do NOT make assumptions about ingredients not visible

## STEP 1: CONTEXT GATEKEEPER - Classify First
Determine category BEFORE applying any rules:
- CATEGORY_FOOD: Edible items, drinks (has Nutrition Facts)
- CATEGORY_SUPPLEMENT: Vitamins, supplements (has Supplement Facts)
- CATEGORY_COSMETIC: Skincare, makeup, soap, shampoo (for external use)
- CATEGORY_ELECTRONICS: Gadgets, devices, cables (has specs)
- CATEGORY_HOUSEHOLD: Cleaning supplies, detergents

## STEP 2: CATEGORY-SPECIFIC RULES

IF CATEGORY_FOOD:
✓ ENABLE: Nutritional analysis, sugar check, sodium check, allergens
✗ DISABLE: Chemical safety (cosmetic rules), repairability

IF CATEGORY_COSMETIC:
✓ ENABLE: Chemical safety, fragrance check, allergens
✗ DISABLE: Nutritional analysis, sugar/sodium checks

IF CATEGORY_ELECTRONICS:
✓ ENABLE: Spec check, repairability, battery analysis
✗ DISABLE: ALL ingredient-based rules

## STEP 3: CLAIM VS FACT CROSS-CHECK
Compare FRONT marketing claims with BACK technical data:

| Front Claim | Check Against | Violation if Mismatch |
|-------------|---------------|----------------------|
| "Natural/All Natural" | Synthetics in ingredients (phenoxyethanol, dimethicone, PEG-, artificial) | Law 5: Natural Fallacy (-12) |
| "Unscented/Fragrance-Free" | "Fragrance" or "Parfum" in ingredients | Law 19: Fake Claim (-15) |
| "Premium/Luxury" | Water/cheap filler as #1 ingredient | Law 1: Water-Down (-15 to -25) |
| "With [Hero Ingredient]" | Hero ingredient below position #5 | Law 2: Fairy Dusting (-12) |
| "Clinically Proven" | No study citation visible | Law 13: Clinical Ghost (-12) |
| "High Protein" | Check actual protein per serving | Verify claim |

## STEP 4: FINE PRINT DEEP SCAN
Scan ALL visible text for:
- "May contain traces of..." 
- "Processed in a facility that handles..."
- "Not suitable for..."
- "Patch test recommended"
- "Consult doctor if pregnant"
- "Not for children under..."

## STEP 5: PROVABLE SCORING
Base: 85 points
- ONLY deduct if you have EVIDENCE from the image
- For ingredient flags: specify which ingredient and where it appears
- For claim violations: quote the claim AND the contradicting fact

## ELECTRONICS SPECIFIC (if CATEGORY_ELECTRONICS):
Check for:
- "User replaceable battery" (+15) vs "Sealed battery" (-10)
- "Standard USB-C" (+5) vs "Proprietary connector" (-5)
- Repairability indicators

## CONTEXT:
Location: {location}
User Profiles: {user_profiles}
User Allergies: {user_allergies}
{barcode_context}

## REQUIRED OUTPUT (Valid JSON):
{{
    "product_name": "Exact name from image",
    "brand": "Brand name",
    "product_category": "CATEGORY_FOOD/CATEGORY_COSMETIC/CATEGORY_SUPPLEMENT/CATEGORY_ELECTRONICS/CATEGORY_HOUSEHOLD",
    "product_type": "specific type (cleanser, protein_bar, vitamin, etc)",
    "readable": true,
    "score": <0-100>,
    "front_claims": ["List marketing claims from front"],
    "fine_print_detected": ["List any fine print warnings found"],
    "violations": [
        {{
            "law": <1-20 or null>,
            "name": "Law name",
            "points": <negative>,
            "evidence": "QUOTE exact text from image proving this",
            "source": "Citation if available (e.g., EU SCCS, FDA)"
        }}
    ],
    "bonuses": [
        {{"name": "Bonus", "points": <positive>, "evidence": "What earned it"}}
    ],
    "ingredients": ["list if visible"],
    "ingredients_flagged": [
        {{
            "name": "ingredient",
            "concern": "specific concern",
            "severity": "red/yellow",
            "source": "Scientific source (EU SCCS, FDA, etc.) or null if unverified"
        }}
    ],
    "main_issue": "Primary concern or 'Clean formula'",
    "positive": "Main positive",
    "confidence": "high/medium/low"
}}

## CRITICAL RULES:
1. Category determines which rules apply - do NOT apply food rules to cosmetics
2. Every red flag MUST have a scientific citation, else make it yellow
3. Quote exact evidence from image for violations
4. If label is partially obscured, note what you CAN and CANNOT verify"""

def analyze_product(images, location, progress_callback, barcode_info=None, user_profiles=None, user_allergies=None):
    """Advanced AI analysis with Context Gatekeeper"""
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {"product_name": "API Key Missing", "score": 0, "verdict": "UNCLEAR", "readable": False,
                "violations": [], "main_issue": "Please add GEMINI_API_KEY"}
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    
    progress_callback(0.3, "Classifying product category...")
    
    barcode_context = ""
    if barcode_info and barcode_info.get('found'):
        barcode_context = f"""
BARCODE DATABASE INFO (Use as reference, verify against image):
- Product: {barcode_info.get('name', '')}
- Brand: {barcode_info.get('brand', '')}
- Category: {barcode_info.get('categories', '')}
- Ingredients: {barcode_info.get('ingredients', '')[:1000]}
- Source: {barcode_info.get('source', '')}
If image shows different product, trust IMAGE."""
    
    prompt = ANALYSIS_PROMPT.format(
        location=f"{location.get('city', '')}, {location.get('country', '')}",
        user_profiles=', '.join(user_profiles) if user_profiles else 'None',
        user_allergies=', '.join(user_allergies) if user_allergies else 'None',
        barcode_context=barcode_context
    )
    
    progress_callback(0.5, "Applying context rules...")
    
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
            return {"product_name": "Parse Error", "score": 0, "verdict": "UNCLEAR",
                    "readable": False, "violations": [], "main_issue": "Could not parse response"}
        
        progress_callback(0.8, "Calculating score...")
        
        # Validate and ensure score
        score = result.get('score', 75)
        if isinstance(score, str):
            try: score = int(re.sub(r'[^\d]', '', score))
            except: score = 75
        score = max(0, min(100, score))
        
        violations = result.get('violations', [])
        if not violations and score < 85:
            missing = 85 - score
            violations = [{"law": None, "name": "Minor concerns", "points": -missing,
                          "evidence": result.get('main_issue', 'Some concerns detected')}]
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['violations'] = violations
        
        # Learning consistency
        if result.get('product_name'):
            learned = get_learned_product(result['product_name'])
            if learned and learned.get('scan_count', 0) >= 3:
                weight = min(learned['scan_count'] * 0.1, 0.4)
                result['score'] = int(score * (1 - weight) + learned['score'] * weight)
                result['verdict'] = get_verdict(result['score'])
        
        if not result.get('readable', True):
            result['score'] = 0
            result['verdict'] = 'UNCLEAR'
        
        progress_callback(1.0, "Analysis complete!")
        return result
        
    except Exception as e:
        return {"product_name": "Analysis Error", "score": 0, "verdict": "UNCLEAR",
                "readable": False, "violations": [], "main_issue": f"Error: {str(e)[:100]}"}

# ═══════════════════════════════════════════════════════════════════════════════
# SHARE IMAGES - Clean, Professional
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

def image_to_bytes(img, format='PNG'):
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()
# ═══════════════════════════════════════════════════════════════════════════════
# CLEAN UI STYLES - Results First, Details Collapsible
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.stApp { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 520px; }

/* Verdict Cards - PROMINENT */
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

/* Stats - Compact */
.stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
.stat-box { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-val { font-size: 1.3rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; }

/* Alerts - High Visibility */
.alert-high { background: linear-gradient(135deg, #fef2f2, #fee2e2); border-left: 4px solid #ef4444; border-radius: 12px; padding: 0.9rem; margin: 0.4rem 0; }
.alert-medium { background: linear-gradient(135deg, #fffbeb, #fef3c7); border-left: 4px solid #f59e0b; border-radius: 12px; padding: 0.9rem; margin: 0.4rem 0; }
.alert-fine-print { background: linear-gradient(135deg, #fdf4ff, #f3e8ff); border-left: 4px solid #a855f7; border-radius: 12px; padding: 0.9rem; margin: 0.4rem 0; }
.alert-info { background: linear-gradient(135deg, #eff6ff, #dbeafe); border-left: 4px solid #3b82f6; border-radius: 12px; padding: 0.9rem; margin: 0.4rem 0; }

/* Laws - Clean */
.law-box { background: white; border-left: 4px solid #ef4444; border-radius: 0 12px 12px 0; padding: 0.8rem; margin: 0.3rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.law-title { font-weight: 700; color: #dc2626; font-size: 0.95rem; }
.law-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.25rem; }
.law-source { font-size: 0.75rem; color: #6b7280; background: #f1f5f9; padding: 0.2rem 0.5rem; border-radius: 4px; display: inline-block; margin-top: 0.25rem; }

/* Bonuses */
.bonus-box { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border-left: 4px solid #22c55e; padding: 0.6rem; border-radius: 0 10px 10px 0; margin: 0.25rem 0; }

/* Issue/Positive - Prominent */
.issue-box { background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }
.positive-box { background: linear-gradient(135deg, #dcfce7, #bbf7d0); border-left: 4px solid #22c55e; padding: 0.9rem; border-radius: 0 12px 12px 0; margin: 0.5rem 0; }

/* Ingredients - Compact Badges */
.ing-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0; }
.ing-badge { padding: 0.3rem 0.6rem; border-radius: 16px; font-weight: 600; font-size: 0.75rem; }
.ing-red { background: #fee2e2; color: #dc2626; }
.ing-yellow { background: #fef3c7; color: #b45309; }
.ing-green { background: #dcfce7; color: #16a34a; }

/* Alternative - Always Visible */
.alt-card { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 2px solid #86efac; border-radius: 16px; padding: 1rem; margin: 0.75rem 0; }
.alt-score { background: #22c55e; color: white; padding: 0.2rem 0.5rem; border-radius: 6px; font-weight: 700; font-size: 0.8rem; }

/* Share - Compact */
.share-row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin: 0.5rem 0; }
.share-btn { padding: 0.5rem 0.75rem; border-radius: 8px; color: white; text-decoration: none; font-weight: 600; font-size: 0.75rem; flex: 1; text-align: center; min-width: 70px; }

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

/* Expanders - For Optional Details */
[data-testid="stExpander"] { background: white; border: 1px solid #e2e8f0; border-radius: 12px; margin: 0.3rem 0; }
[data-testid="stExpander"] summary { font-weight: 600; }

/* Laws Cards */
.law-card { background: white; border: 1px solid #e2e8f0; border-radius: 10px; padding: 0.7rem; margin: 0.3rem 0; }
.law-card-title { font-weight: 700; color: #1e293b; font-size: 0.9rem; }
.law-card-pts { color: #ef4444; font-weight: 700; }
.law-card-desc { font-size: 0.8rem; color: #64748b; margin-top: 0.2rem; }

/* Retailer Links */
.retailer-row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin: 0.4rem 0; }
.retailer-link { background: #f1f5f9; color: #475569; padding: 0.3rem 0.6rem; border-radius: 6px; font-size: 0.75rem; text-decoration: none; }
.retailer-link:hover { background: #e2e8f0; }

#MainMenu, footer, header { visibility: hidden; }
[data-testid="stCameraInput"] video { max-height: 180px !important; border-radius: 12px; }
</style>
"""
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION - Clean UI, Results First, Details Collapsible
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    # Session state
    if 'result' not in st.session_state: st.session_state.result = None
    if 'scan_id' not in st.session_state: st.session_state.scan_id = None
    if 'admin' not in st.session_state: st.session_state.admin = False
    if 'barcode_info' not in st.session_state: st.session_state.barcode_info = None
    if 'show_result' not in st.session_state: st.session_state.show_result = False
    
    # Location
    if 'loc' not in st.session_state:
        saved = get_saved_location()
        if saved and saved.get('city') not in ['Unknown', '', 'Your City']:
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
        if st.session_state.loc.get('city') not in ['Unknown', 'Your City', '']:
            st.markdown(f"<span class='loc-badge'>📍 {st.session_state.loc.get('city', '')}</span>", unsafe_allow_html=True)
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
    st.markdown(f"<center style='color: #94a3b8; font-size: 0.7rem; margin-top: 1rem;'>🌍 HonestWorld v{VERSION} • Context-Aware Integrity Engine</center>", unsafe_allow_html=True)


def render_scan_interface():
    """Clean scan interface"""
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
    
    else:  # Barcode
        st.markdown("**📊 Perfect Barcode Scanner**")
        st.caption("Can't photograph folded label? Scan barcode and we'll fetch the data!")
        barcode_img = st.camera_input("", label_visibility="collapsed", key="barcode_cam")
        
        if barcode_img:
            with st.spinner("Reading barcode..."):
                barcode_num = try_decode_barcode_pyzbar(barcode_img)
                if not barcode_num:
                    barcode_num = ai_read_barcode(barcode_img)
                
                if barcode_num:
                    st.info(f"📊 Barcode: **{barcode_num}**")
                    
                    progress_ph = st.empty()
                    def update_prog(pct, msg):
                        progress_ph.markdown(f"<div class='progress-box'><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
                    
                    barcode_info = smart_barcode_lookup(barcode_num, update_prog)
                    progress_ph.empty()
                    
                    if barcode_info.get('found'):
                        st.success(f"✅ **{barcode_info.get('name', '')}**")
                        if barcode_info.get('brand'):
                            st.caption(f"by {barcode_info.get('brand')} • {barcode_info.get('source', '')}")
                        
                        # Show retailer links if ingredients not found
                        if not barcode_info.get('ingredients'):
                            st.markdown("**🔗 Find full details:**")
                            links = get_retailer_search_links(barcode_info.get('name', ''), st.session_state.loc.get('code', 'OTHER'))
                            link_html = " ".join([f"<a href='{l['url']}' target='_blank' class='retailer-link'>{l['name']}</a>" for l in links[:4]])
                            st.markdown(f"<div class='retailer-row'>{link_html}</div>", unsafe_allow_html=True)
                        
                        st.session_state.barcode_info = barcode_info
                        images = [barcode_img]
                    else:
                        st.warning("Not found in databases. Try photo scan or search retailers:")
                        links = get_retailer_search_links(barcode_num, st.session_state.loc.get('code', 'OTHER'))
                        link_html = " ".join([f"<a href='{l['url']}' target='_blank' class='retailer-link'>{l['name']}</a>" for l in links[:4]])
                        st.markdown(f"<div class='retailer-row'>{link_html}</div>", unsafe_allow_html=True)
                else:
                    st.error("Could not read barcode. Try clearer image.")
    
    # Analyze button
    if images:
        if st.button("🔍 ANALYZE", use_container_width=True, type="primary"):
            progress_ph = st.empty()
            def update_prog(pct, msg):
                icons = ['🔍', '📋', '⚖️', '✨']
                icon = icons[min(int(pct * 4), 3)]
                progress_ph.markdown(f"<div class='progress-box'><div style='font-size:2rem;'>{icon}</div><div style='font-weight:600;'>{msg}</div><div class='progress-bar'><div class='progress-fill' style='width:{pct*100}%'></div></div></div>", unsafe_allow_html=True)
            
            user_profiles = get_profiles()
            user_allergies = get_allergies()
            bi = st.session_state.get('barcode_info')
            
            result = analyze_product(images, st.session_state.loc, update_prog, bi, user_profiles, user_allergies)
            progress_ph.empty()
            
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
                
                scan_id = save_scan(result, get_user_id(), thumb)
                cloud_log_scan(result, st.session_state.loc.get('city', ''), st.session_state.loc.get('country', ''), get_user_id())
                
                st.session_state.result = result
                st.session_state.scan_id = scan_id
                st.session_state.show_result = True
                st.session_state.barcode_info = None
                st.rerun()
            else:
                st.error("❌ Could not analyze. Try clearer photo showing product name and ingredients.")


def display_result(result, user_id):
    """CLEAN RESULT DISPLAY - Score first, details collapsible"""
    score = result.get('score', 0)
    verdict = result.get('verdict', 'UNCLEAR')
    product_category = result.get('product_category', 'CATEGORY_FOOD')
    product_type = result.get('product_type', '')
    display = get_verdict_display(verdict)
    
    # VERDICT CARD - Most prominent
    st.markdown(f"""<div class='verdict-card verdict-{verdict.lower()}'>
        <div class='verdict-icon'>{display['icon']}</div>
        <div class='verdict-text'>{display['text']}</div>
        <div class='verdict-score'>{score}<span style='font-size:1.5rem;'>/100</span></div>
    </div>""", unsafe_allow_html=True)
    
    # Product info
    st.markdown(f"### {result.get('product_name', 'Unknown')}")
    if result.get('brand'):
        st.markdown(f"*by {result.get('brand')}*")
    
    # Category badge
    cat_icon = PRODUCT_CATEGORIES.get(product_category, {}).get('icon', '📦')
    cat_name = PRODUCT_CATEGORIES.get(product_category, {}).get('name', 'Product')
    st.markdown(f"<span class='cat-badge'>{cat_icon} {cat_name}</span>", unsafe_allow_html=True)
    
    # MAIN ISSUE - Prominent if exists
    main_issue = result.get('main_issue', '')
    if main_issue and main_issue.lower() not in ['clean formula', 'none', '']:
        st.markdown(f"<div class='issue-box'>⚠️ <strong>{main_issue}</strong></div>", unsafe_allow_html=True)
    
    # POSITIVE - Prominent
    if result.get('positive'):
        st.markdown(f"<div class='positive-box'>✅ <strong>{result.get('positive')}</strong></div>", unsafe_allow_html=True)
    
    # HEALTH ALERTS - High visibility
    user_profiles = get_profiles()
    user_allergies = get_allergies()
    
    # Context-aware alerts
    alerts = check_health_alerts(result.get('ingredients', []), user_allergies, user_profiles, product_category)
    for alert in alerts:
        css = 'alert-high' if alert['severity'] == 'high' else 'alert-medium'
        st.markdown(f"<div class='{css}'><strong>{alert['icon']} {alert['name']}</strong><br>{alert['message']}</div>", unsafe_allow_html=True)
    
    # Fine print alerts
    fine_print = result.get('fine_print_detected', [])
    for fp in fine_print:
        st.markdown(f"<div class='alert-fine-print'><strong>📜 Fine Print Found</strong><br>\"{fp}\"</div>", unsafe_allow_html=True)
    
    # ALTERNATIVE - Always visible
    alt = get_alternative(result.get('product_name', ''), product_type, product_category)
    alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
    retailers = ', '.join(st.session_state.loc.get('retailers', ['Local stores'])[:3])
    st.markdown(f"""<div class='alt-card'>
        <strong>💚 {'Better Alternative' if verdict in ['CAUTION', 'AVOID'] else 'Similar Quality'}:</strong><br>
        <span style='font-size:1.05rem;font-weight:600;'>{alt['name']}</span> {alt_score_html}<br>
        <span style='color:#16a34a;'>{alt['why']}</span><br>
        <span style='font-size:0.8rem;color:#64748b;'>At: {retailers}</span>
    </div>""", unsafe_allow_html=True)
    
    # ═══ COLLAPSIBLE DETAILS ═══
    
    # Laws/Violations - Collapsible
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Laws Violated ({len(violations)})", expanded=False):
            for v in violations:
                law_text = f"Law {v.get('law')}: " if v.get('law') else ""
                source_html = f"<div class='law-source'>📚 {v.get('source')}</div>" if v.get('source') else ""
                st.markdown(f"""<div class='law-box'>
                    <div class='law-title'>{law_text}{v.get('name', '')} ({v.get('points', 0)} pts)</div>
                    <div class='law-evidence'>{v.get('evidence', '')}</div>
                    {source_html}
                </div>""", unsafe_allow_html=True)
    
    # Bonuses - Collapsible
    bonuses = result.get('bonuses', [])
    if bonuses:
        with st.expander(f"✨ Bonuses ({len(bonuses)})", expanded=False):
            for b in bonuses:
                st.markdown(f"<div class='bonus-box'><strong>+{b.get('points', 0)}: {b.get('name', '')}</strong><br><span style='font-size:0.85rem;'>{b.get('evidence', '')}</span></div>", unsafe_allow_html=True)
    
    # Ingredients - Collapsible
    ingredients_flagged = result.get('ingredients_flagged', [])
    if ingredients_flagged or result.get('ingredients'):
        with st.expander("🧪 Ingredients Analysis", expanded=False):
            if ingredients_flagged:
                st.markdown("**Flagged:**")
                for ing in ingredients_flagged:
                    severity = ing.get('severity', 'yellow')
                    css = 'ing-red' if severity == 'red' else 'ing-yellow'
                    source_text = f" • {ing.get('source')}" if ing.get('source') else " • *No citation - unverified*"
                    st.markdown(f"<span class='ing-badge {css}'>{ing.get('name', '')}</span> {ing.get('concern', '')}{source_text}", unsafe_allow_html=True)
            
            good = result.get('good_ingredients', [])
            if good:
                st.markdown("**Good:**")
                badges = " ".join([f"<span class='ing-badge ing-green'>{g}</span>" for g in good[:10]])
                st.markdown(f"<div class='ing-row'>{badges}</div>", unsafe_allow_html=True)
            
            if result.get('ingredients'):
                st.markdown(f"**All:** {', '.join(result.get('ingredients', [])[:30])}")
    
    # Front Claims - Collapsible
    front_claims = result.get('front_claims', [])
    if front_claims:
        with st.expander("🏷️ Marketing Claims Detected", expanded=False):
            for claim in front_claims:
                st.markdown(f"• {claim}")
    
    # SHARE - Compact
    st.markdown("### 📤 Share")
    share_img = create_share_image(result.get('product_name', ''), result.get('brand', ''), score, verdict)
    story_img = create_story_image(result.get('product_name', ''), result.get('brand', ''), score, verdict)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post", data=image_to_bytes(share_img), file_name=f"hw_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story", data=image_to_bytes(story_img), file_name=f"hw_story_{score}.png", mime="image/png", use_container_width=True)
    
    share_text = urllib.parse.quote(f"Scanned {result.get('product_name', '')} - {score}/100 ({verdict}) #HonestWorld")
    st.markdown(f"""<div class='share-row'>
        <a href='https://twitter.com/intent/tweet?text={share_text}' target='_blank' class='share-btn' style='background:#1DA1F2;'>𝕏</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={share_text}' target='_blank' class='share-btn' style='background:#4267B2;'>f</a>
        <a href='https://wa.me/?text={share_text}' target='_blank' class='share-btn' style='background:#25D366;'>💬</a>
        <a href='https://t.me/share/url?text={share_text}' target='_blank' class='share-btn' style='background:#0088cc;'>➤</a>
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
    
    # Location
    st.markdown("**📍 Location**")
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City", value=st.session_state.loc.get('city', ''), key="city_in")
    with col2:
        country = st.text_input("Country", value=st.session_state.loc.get('country', ''), key="country_in")
    if st.button("Update Location"):
        code = save_location(city, country)
        st.session_state.loc = {'city': city, 'country': country, 'code': code, 'retailers': RETAILERS_DISPLAY.get(code, RETAILERS_DISPLAY['OTHER'])}
        st.success("✅ Updated!")
        st.rerun()
    
    st.markdown("---")
    
    # Health Profiles
    st.markdown("**🏥 Health Profiles**")
    st.caption("Context-aware: Only relevant rules apply per category")
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
        scans = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM learned_products')
        learned = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM barcode_cache')
        barcodes = c.fetchone()[0]
        conn.close()
        st.markdown(f"📊 **{scans}** scans • **{learned}** learned • **{barcodes}** barcodes")
        st.markdown(f"☁️ Cloud: {'🟢' if supa_ok() else '🔴'}")


def render_laws():
    st.markdown("### ⚖️ The 20 Integrity Laws")
    st.caption("Context-aware: Laws only apply to relevant product categories")
    
    categories = {
        "🧪 Ingredients": [1, 2, 3, 4, 5, 6],
        "📦 Packaging": [7, 8, 18],
        "📱 Electronics": [9, 10, 11, 12],
        "💄 Beauty": [13, 14],
        "📋 Services": [15, 16, 17],
        "🏷️ Claims": [19, 20]
    }
    
    for cat_name, nums in categories.items():
        with st.expander(cat_name, expanded=False):
            for n in nums:
                if n in INTEGRITY_LAWS:
                    law = INTEGRITY_LAWS[n]
                    applies = ', '.join([PRODUCT_CATEGORIES.get(c, {}).get('name', c)[:12] for c in law.get('applies_to', [])])
                    st.markdown(f"""<div class='law-card'>
                        <span class='law-card-title'>Law {n}: {law['name']}</span>
                        <span class='law-card-pts'> ({law['base_points']} pts)</span>
                        <div class='law-card-desc'>{law['description']}</div>
                        <div style='font-size:0.75rem;color:#059669;margin-top:0.2rem;'>💡 {law['tip']}</div>
                        <div style='font-size:0.7rem;color:#64748b;margin-top:0.2rem;'>Applies to: {applies}</div>
                    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
