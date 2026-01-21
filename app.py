"""
🌍 HONESTWORLD v26.0 - PREMIUM EDITION
The World's Most Advanced Product Scanner
Fine Print Engine • Claims Verification • Scientific Citations • Dynamic Scoring
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

VERSION = "26.0"
LOCAL_DB = Path.home() / "honestworld_v26.db"

def get_secret(key, default=""):
    try: return st.secrets.get(key, os.environ.get(key, default))
    except: return os.environ.get(key, default)

GEMINI_API_KEY = get_secret("GEMINI_API_KEY", "")
SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_KEY = get_secret("SUPABASE_KEY", "")
ADMIN_HASH = hashlib.sha256("honestworld2024".encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════════
# THE 20 INTEGRITY LAWS - Dynamic Weights by Product Category
# ═══════════════════════════════════════════════════════════════════════════════
INTEGRITY_LAWS = {
    1: {
        "name": "Water-Down Deception",
        "base_points": -15,
        "category": "ingredients",
        "description": "Product claims 'premium/luxury' but #1 ingredient is water or cheap filler",
        "tip": "Check if the first ingredient matches the premium price claim",
        "dynamic_weights": {
            "cosmetics_serum": -25, "cosmetics_concentrate": -25,
            "cosmetics_mist": -3, "cosmetics_toner": -3,
            "beverage": 0, "food": -10, "supplement": -12
        }
    },
    2: {
        "name": "Fairy Dusting",
        "base_points": -12,
        "category": "ingredients",
        "description": "Hero ingredient advertised prominently on front is below position #5 in actual list",
        "tip": "Ingredients are listed by quantity - first = most, last = least",
        "dynamic_weights": {"cosmetics": -15, "food": -12, "supplement": -18}
    },
    3: {
        "name": "Split Sugar Trick",
        "base_points": -18,
        "category": "ingredients",
        "description": "Sugar split into 3+ different names to hide total amount (glucose, fructose, corn syrup, etc.)",
        "tip": "Add up ALL sugar types - they're often the real #1 ingredient combined"
    },
    4: {
        "name": "Low-Fat Trap",
        "base_points": -10,
        "category": "ingredients",
        "description": "Claims 'low fat' or 'fat free' but compensates with high sugar content",
        "tip": "Low-fat often means high sugar - always check the nutrition label"
    },
    5: {
        "name": "Natural Fallacy",
        "base_points": -12,
        "category": "ingredients",
        "description": "Claims '100% Natural' or 'All Natural' but contains synthetic ingredients",
        "tip": "'Natural' is unregulated - look for certified organic or specific certifications",
        "synthetic_triggers": ["phenoxyethanol", "dimethicone", "cyclopentasiloxane", "peg-", "edta", "bht", "bha", "methylisothiazolinone"]
    },
    6: {
        "name": "Made-With Loophole",
        "base_points": -8,
        "category": "ingredients",
        "description": "'Made with real X' but X is minimal in actual ingredient list",
        "tip": "'Made with' legally only requires a tiny amount of the ingredient"
    },
    7: {
        "name": "Serving Size Trick",
        "base_points": -10,
        "category": "packaging",
        "description": "Unrealistically small serving size makes nutrition look better",
        "tip": "Check servings per container - you probably consume more than one serving"
    },
    8: {
        "name": "Slack Fill",
        "base_points": -8,
        "category": "packaging",
        "description": "Package is mostly air/empty space, misleading about actual quantity",
        "tip": "Always check net weight/volume, not package size"
    },
    9: {
        "name": "Spec Inflation",
        "base_points": -15,
        "category": "electronics",
        "description": "'Up to X speed/capacity' claims that are unrealistic in real use",
        "tip": "'Up to' means maximum under perfect lab conditions - expect 50-70% in reality"
    },
    10: {
        "name": "Compatibility Lie",
        "base_points": -12,
        "category": "electronics",
        "description": "'Universal' or 'Works with all' but has hidden exceptions",
        "tip": "Always check the compatibility list in fine print before purchase"
    },
    11: {
        "name": "Military Grade Myth",
        "base_points": -10,
        "category": "electronics",
        "description": "Claims 'military grade' durability without actual MIL-STD certification",
        "tip": "Real military spec products cite the specific MIL-STD number (e.g., MIL-STD-810G)"
    },
    12: {
        "name": "Battery Fiction",
        "base_points": -12,
        "category": "electronics",
        "description": "Unrealistic battery life claims based on minimal usage scenarios",
        "tip": "Battery life is tested with screen dim and minimal use - expect 60-70% in real use"
    },
    13: {
        "name": "Clinical Ghost",
        "base_points": -12,
        "category": "beauty",
        "description": "'Clinically proven' or 'Dermatologist tested' without study citation or details",
        "tip": "Real clinical proof includes study size, methodology, and publication reference"
    },
    14: {
        "name": "Concentration Trick",
        "base_points": -10,
        "category": "beauty",
        "description": "Active ingredient present but too diluted to be effective",
        "tip": "Effective concentrations: Vitamin C 10-20%, Retinol 0.3-1%, Niacinamide 2-5%"
    },
    15: {
        "name": "Free Trap",
        "base_points": -15,
        "category": "services",
        "description": "'Free' offer requires credit card or hidden purchase commitment",
        "tip": "'Free trial' usually auto-charges - always set a calendar reminder to cancel"
    },
    16: {
        "name": "Unlimited Lie",
        "base_points": -18,
        "category": "services",
        "description": "'Unlimited' service has hidden caps, throttling, or fair use limits",
        "tip": "'Unlimited' almost never means truly unlimited - read the fair use policy"
    },
    17: {
        "name": "Lifetime Illusion",
        "base_points": -10,
        "category": "services",
        "description": "'Lifetime warranty' or 'Lifetime guarantee' with extensive exclusions",
        "tip": "'Lifetime' often means 'limited lifetime' with many exclusions in fine print"
    },
    18: {
        "name": "Photo vs Reality",
        "base_points": -12,
        "category": "packaging",
        "description": "Package photo/rendering significantly better than actual product",
        "tip": "Package photos are professionally styled - read actual contents list"
    },
    19: {
        "name": "Fake Certification",
        "base_points": -15,
        "category": "claims",
        "description": "Claims certification or approval without proper logo, number, or verification",
        "tip": "Real certifications show certifier's official logo and verification ID number"
    },
    20: {
        "name": "Name Trick",
        "base_points": -10,
        "category": "claims",
        "description": "Product name implies key ingredient that is absent or minimal",
        "tip": "'Honey Oat Cereal' doesn't guarantee significant honey or whole oat content"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# SCIENTIFIC SOURCES DATABASE - Cite Your Sources
# ═══════════════════════════════════════════════════════════════════════════════
INGREDIENT_SCIENCE = {
    "paraben": {
        "concern": "Potential endocrine disruption",
        "severity": "medium",
        "sources": ["EU Scientific Committee on Consumer Safety (SCCS)", "Danish EPA Study 2018", "Journal of Applied Toxicology"],
        "context": "cosmetics",
        "note": "Low concentrations (<0.4%) generally considered safe by FDA",
        "regulations": "EU restricted to max 0.4% single / 0.8% mixed"
    },
    "methylparaben": {
        "concern": "Potential hormone disruption at high doses",
        "severity": "medium",
        "sources": ["EU SCCS Opinion 2013", "Journal of Applied Toxicology", "Endocrine Reviews"],
        "context": "cosmetics"
    },
    "propylparaben": {
        "concern": "Higher skin absorption than methylparaben",
        "severity": "medium",
        "sources": ["EU SCCS restricted to 0.14%", "Environmental Working Group", "Toxicology Letters"],
        "context": "cosmetics"
    },
    "butylparaben": {
        "concern": "Highest concern among parabens for endocrine effects",
        "severity": "high",
        "sources": ["EU SCCS Opinion", "Danish EPA", "Reproductive Toxicology Journal"],
        "context": "cosmetics"
    },
    "fragrance": {
        "concern": "Undisclosed mixture of potentially 3,000+ chemicals, common allergen",
        "severity": "medium",
        "sources": ["American Academy of Dermatology", "Contact Dermatitis Journal", "IFRA Standards"],
        "context": "cosmetics",
        "note": "Companies not legally required to disclose fragrance components"
    },
    "parfum": {
        "concern": "Same as fragrance - undisclosed chemical mixture",
        "severity": "medium",
        "sources": ["EU Cosmetics Regulation", "RIFM Database"],
        "context": "cosmetics"
    },
    "sodium lauryl sulfate": {
        "concern": "Can irritate sensitive skin and eyes, strips natural oils",
        "severity": "low",
        "sources": ["Journal of the American College of Toxicology", "CIR Expert Panel 1983, updated 2005"],
        "context": "cosmetics",
        "note": "Safe in rinse-off products at typical concentrations per CIR"
    },
    "sodium laureth sulfate": {
        "concern": "Milder than SLS but potential 1,4-dioxane contamination from ethoxylation",
        "severity": "low",
        "sources": ["FDA Guidance on 1,4-dioxane", "EWG Database", "Int J Toxicology"],
        "context": "cosmetics"
    },
    "phthalate": {
        "concern": "Potential endocrine disruption, reproductive and developmental effects",
        "severity": "high",
        "sources": ["CDC National Report on Human Exposure to Environmental Chemicals", "EPA Phthalate Action Plan", "NIH NTP Studies"],
        "context": "cosmetics"
    },
    "dmdm hydantoin": {
        "concern": "Formaldehyde-releasing preservative, sensitizer",
        "severity": "high",
        "sources": ["International Agency for Research on Cancer (IARC)", "Contact Dermatitis Studies", "American Contact Dermatitis Society"],
        "context": "cosmetics"
    },
    "quaternium-15": {
        "concern": "Formaldehyde releaser, common contact allergen",
        "severity": "high",
        "sources": ["IARC", "North American Contact Dermatitis Group"],
        "context": "cosmetics"
    },
    "triclosan": {
        "concern": "Endocrine disruption, antibiotic resistance concerns",
        "severity": "high",
        "sources": ["FDA Ban in Consumer Antiseptics 2016", "Environmental Science & Technology"],
        "context": "cosmetics",
        "note": "Banned in hand soaps by FDA, still allowed in some products"
    },
    "oxybenzone": {
        "concern": "Potential hormone disruption, coral reef damage",
        "severity": "medium",
        "sources": ["Archives of Environmental Contamination and Toxicology", "Hawaii Reef-Safe Sunscreen Law"],
        "context": "cosmetics"
    },
    "high fructose corn syrup": {
        "concern": "Linked to obesity, metabolic syndrome when over-consumed",
        "severity": "medium",
        "sources": ["American Journal of Clinical Nutrition", "Princeton University Neuroscience Study", "Obesity Research Journal"],
        "context": "food"
    },
    "trans fat": {
        "concern": "Increases LDL cholesterol, significantly raises heart disease risk",
        "severity": "high",
        "sources": ["FDA Ban 2018", "American Heart Association", "WHO Guidelines", "New England Journal of Medicine"],
        "context": "food"
    },
    "hydrogenated oil": {
        "concern": "May contain trans fats, cardiovascular risk",
        "severity": "medium",
        "sources": ["FDA", "American Heart Association"],
        "context": "food"
    },
    "red 40": {
        "concern": "Hyperactivity concerns in sensitive children, potential carcinogen debate",
        "severity": "low",
        "sources": ["FDA CFSAN", "Southampton Study (UK)", "EFSA Opinion", "CSPI Reports"],
        "context": "food",
        "note": "Requires warning label in EU, not required in US"
    },
    "yellow 5": {
        "concern": "May cause allergic reactions, hyperactivity in children",
        "severity": "low",
        "sources": ["FDA", "EFSA", "Lancet Study 2007"],
        "context": "food"
    },
    "aspartame": {
        "concern": "Controversial - some studies suggest concerns, regulatory bodies deem safe at typical levels",
        "severity": "low",
        "sources": ["FDA GRAS Status", "EFSA Scientific Opinion 2013", "WHO IARC 2023 Review"],
        "context": "food",
        "note": "IARC classified as 'possibly carcinogenic' in 2023, FDA maintains safety at approved levels"
    },
    "msg": {
        "concern": "May cause reactions in sensitive individuals (Chinese Restaurant Syndrome)",
        "severity": "low",
        "sources": ["FDA GRAS", "Journal of Nutrition", "FASEB Report"],
        "context": "food",
        "note": "Generally recognized as safe by FDA, individual sensitivity varies"
    },
    "bpa": {
        "concern": "Endocrine disruption, developmental effects",
        "severity": "high",
        "sources": ["FDA BPA Program", "Endocrine Society Statement", "NIH NTP"],
        "context": "packaging"
    },
    "titanium dioxide": {
        "concern": "Inhalation concerns for nano-particles, EU food ban 2022",
        "severity": "medium",
        "sources": ["EFSA Opinion 2021", "EU Regulation 2022/63", "IARC Group 2B"],
        "context": "food",
        "note": "Banned in food in EU since 2022, still allowed in US and in cosmetics"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# POSITIVE BONUSES - Reward Good Practices
# ═══════════════════════════════════════════════════════════════════════════════
POSITIVE_BONUSES = {
    "certified_organic": {"points": 5, "name": "Certified Organic", "icon": "🌿", 
                          "keywords": ["usda organic", "certified organic", "100% organic", "ecocert organic", "soil association organic"]},
    "fragrance_free": {"points": 4, "name": "Fragrance-Free", "icon": "🌸", 
                       "keywords": ["fragrance-free", "fragrance free", "unscented", "no fragrance", "without fragrance", "sans parfum"]},
    "third_party_tested": {"points": 5, "name": "Third-Party Tested", "icon": "✅", 
                           "keywords": ["nsf certified", "usp verified", "consumerlab approved", "third party tested", "independently tested"]},
    "ewg_verified": {"points": 4, "name": "EWG Verified", "icon": "🛡️", 
                     "keywords": ["ewg verified", "ewg approved"]},
    "transparent_fragrance": {"points": 5, "name": "Fragrance Transparency", "icon": "📋", 
                              "keywords": ["fragrance ingredients listed", "fragrance disclosure", "full ingredient disclosure"]},
    "recyclable_packaging": {"points": 3, "name": "Recyclable Packaging", "icon": "♻️", 
                             "keywords": ["recyclable", "100% recyclable", "post-consumer recycled", "pcr plastic", "made from recycled"]},
    "glass_packaging": {"points": 3, "name": "Glass Packaging", "icon": "🫙", 
                        "keywords": ["glass bottle", "glass jar", "glass container"]},
    "cruelty_free": {"points": 3, "name": "Cruelty-Free", "icon": "🐰", 
                     "keywords": ["cruelty-free", "cruelty free", "not tested on animals", "leaping bunny", "peta certified"]},
    "vegan_certified": {"points": 3, "name": "Vegan Certified", "icon": "🌱", 
                        "keywords": ["vegan certified", "certified vegan", "100% vegan"]},
    "clean_formula": {"points": 2, "name": "Clean Formula", "icon": "✨", 
                      "keywords": ["clean beauty", "clean formula", "non-toxic"]},
    "dermatologist_developed": {"points": 2, "name": "Dermatologist Developed", "icon": "👨‍⚕️", 
                                 "keywords": ["dermatologist developed", "developed with dermatologists", "created by dermatologists"]},
    "hypoallergenic": {"points": 2, "name": "Hypoallergenic", "icon": "🩹", 
                       "keywords": ["hypoallergenic", "allergy tested", "suitable for sensitive skin"]},
    "non_comedogenic": {"points": 2, "name": "Non-Comedogenic", "icon": "💧", 
                        "keywords": ["non-comedogenic", "won't clog pores", "non comedogenic"]},
    "reef_safe": {"points": 3, "name": "Reef Safe", "icon": "🐠", 
                  "keywords": ["reef safe", "reef friendly", "ocean safe", "coral safe"]},
    "b_corp": {"points": 4, "name": "B Corp Certified", "icon": "🅱️", 
               "keywords": ["b corp", "b corporation", "certified b corp"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# FINE PRINT ENGINE - Disclaimer Patterns by Profile
# ═══════════════════════════════════════════════════════════════════════════════
FINE_PRINT_PATTERNS = {
    "glutenfree": {
        "warning_patterns": [
            "may contain wheat", "may contain gluten", "traces of wheat", "traces of gluten",
            "produced in a facility.*wheat", "manufactured.*gluten", "shared equipment.*wheat",
            "cross-contact.*gluten", "not suitable for celiac", "not gluten-free"
        ],
        "alert_message": "⚠️ Fine Print Warning: This product may contain traces of gluten despite not listing it as an ingredient."
    },
    "dairy": {
        "warning_patterns": [
            "may contain milk", "may contain dairy", "traces of milk", "contains milk ingredients",
            "produced in a facility.*milk", "shared equipment.*dairy", "not suitable for lactose"
        ],
        "alert_message": "⚠️ Fine Print Warning: This product may contain traces of dairy."
    },
    "nuts": {
        "warning_patterns": [
            "may contain nuts", "may contain tree nuts", "traces of nuts", "produced.*nut facility",
            "shared equipment.*nuts", "manufactured.*contains nuts"
        ],
        "alert_message": "⚠️ Fine Print Warning: This product may contain traces of tree nuts."
    },
    "peanuts": {
        "warning_patterns": [
            "may contain peanuts", "traces of peanuts", "peanut facility", "shared.*peanut"
        ],
        "alert_message": "⚠️ Fine Print Warning: This product may contain traces of peanuts."
    },
    "sensitive": {
        "warning_patterns": [
            "not suitable for sensitive skin", "patch test recommended", "test on small area first",
            "discontinue if irritation", "may cause irritation", "for external use only",
            "avoid contact with eyes", "not for use on broken skin"
        ],
        "alert_message": "⚠️ Fine Print Warning: Manufacturer recommends caution for sensitive skin."
    },
    "pregnancy": {
        "warning_patterns": [
            "consult doctor if pregnant", "not recommended during pregnancy", "avoid if pregnant",
            "pregnant women should", "nursing mothers should", "not for use during pregnancy",
            "consult physician if pregnant", "if pregnant or breastfeeding"
        ],
        "alert_message": "⚠️ Fine Print Warning: Product has pregnancy-related warnings."
    },
    "baby": {
        "warning_patterns": [
            "not for children under", "keep out of reach of children", "not suitable for infants",
            "adult use only", "not for babies", "children under.*should not"
        ],
        "alert_message": "⚠️ Fine Print Warning: This product may not be suitable for babies/children."
    },
    "vegan": {
        "warning_patterns": [
            "may contain traces of milk", "may contain egg", "not suitable for vegans",
            "contains animal", "animal derived"
        ],
        "alert_message": "⚠️ Fine Print Warning: Product may contain animal-derived ingredients."
    },
    "diabetes": {
        "warning_patterns": [
            "contains sugar", "high glycemic", "not suitable for diabetics",
            "monitor blood sugar", "consult doctor if diabetic"
        ],
        "alert_message": "⚠️ Fine Print Warning: Product has diabetes-related considerations."
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# FRONT-TO-BACK VERIFICATION - Marketing Claims vs Reality
# ═══════════════════════════════════════════════════════════════════════════════
CLAIM_VERIFICATION = {
    "natural": {
        "claim_patterns": ["100% natural", "all natural", "pure natural", "naturally derived"],
        "synthetic_flags": ["phenoxyethanol", "dimethicone", "cyclopentasiloxane", "cyclohexasiloxane",
                           "peg-", "ppg-", "edta", "bht", "bha", "methylisothiazolinone", 
                           "methylchloroisothiazolinone", "dmdm hydantoin", "iodopropynyl"],
        "violation": {"law": 5, "name": "Natural Fallacy", "points": -12}
    },
    "fragrance_free": {
        "claim_patterns": ["fragrance free", "fragrance-free", "unscented", "no fragrance"],
        "reality_flags": ["fragrance", "parfum", "perfume", "aroma", "masking fragrance"],
        "violation": {"law": 19, "name": "False Fragrance-Free Claim", "points": -15}
    },
    "organic": {
        "claim_patterns": ["organic", "certified organic", "100% organic"],
        "without_cert": True,  # Flag if claim made without certification logo
        "violation": {"law": 19, "name": "Unverified Organic Claim", "points": -10}
    },
    "clinical": {
        "claim_patterns": ["clinically proven", "clinically tested", "dermatologist tested", "doctor recommended"],
        "requires_citation": True,
        "violation": {"law": 13, "name": "Clinical Ghost", "points": -12}
    },
    "hypoallergenic": {
        "claim_patterns": ["hypoallergenic", "allergy tested", "gentle formula"],
        "allergen_flags": ["fragrance", "parfum", "methylisothiazolinone", "formaldehyde", "lanolin"],
        "violation": {"law": 19, "name": "False Hypoallergenic Claim", "points": -12}
    }
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
        'CAUTION': {'icon': '!', 'text': 'CHECK FIRST', 'color': '#f59e0b'},
        'AVOID': {'icon': '✗', 'text': 'NOT RECOMMENDED', 'color': '#ef4444'},
        'UNCLEAR': {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'}
    }.get(verdict, {'icon': '?', 'text': 'UNCLEAR', 'color': '#6b7280'})
# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CATEGORIES - For Dynamic Scoring
# ═══════════════════════════════════════════════════════════════════════════════
PRODUCT_CATEGORIES = {
    "food": {
        "subtypes": ["snack", "beverage", "dairy", "cereal", "condiment", "frozen", "canned", "fresh", "baked", "candy", "supplement_food"],
        "keywords": ["nutrition facts", "calories", "serving size", "sugar", "protein", "carbohydrate", "sodium per", "vitamin", "ingredients:", "total fat"],
        "health_profiles": ["diabetes", "heartcondition", "glutenfree", "vegan", "allergyprone", "pregnancy"]
    },
    "cosmetics": {
        "subtypes": ["cleanser", "moisturizer", "serum", "sunscreen", "shampoo", "conditioner", "body_lotion", "face_cream", 
                     "mist", "toner", "mask", "exfoliant", "eye_cream", "lip_balm", "body_wash", "hand_cream", "deodorant"],
        "keywords": ["skin", "hair", "moisturize", "cleanser", "shampoo", "spf", "dermatologist", "apply to", "topical", "for external use"],
        "health_profiles": ["sensitive", "allergyprone", "pregnancy", "baby", "vegan"]
    },
    "supplement": {
        "subtypes": ["vitamin", "mineral", "herbal", "protein", "probiotic", "omega", "multivitamin", "amino", "enzyme"],
        "keywords": ["supplement facts", "dietary supplement", "daily value", "capsule", "tablet", "softgel", "serving size", "amount per serving"],
        "health_profiles": ["diabetes", "pregnancy", "vegan", "glutenfree", "allergyprone"]
    },
    "electronics": {
        "subtypes": ["phone", "computer", "accessory", "cable", "charger", "audio", "wearable", "appliance"],
        "keywords": ["battery", "usb", "wireless", "bluetooth", "mah", "watt", "volt", "processor", "input:", "output:"],
        "health_profiles": []
    },
    "household": {
        "subtypes": ["cleaner", "detergent", "disinfectant", "air_freshener", "laundry", "dish"],
        "keywords": ["cleaner", "detergent", "disinfect", "household", "laundry", "dish", "surface"],
        "health_profiles": ["sensitive", "allergyprone", "baby", "pregnancy"]
    },
    "baby": {
        "subtypes": ["diaper", "formula", "baby_food", "baby_care", "baby_lotion"],
        "keywords": ["baby", "infant", "pediatrician", "gentle", "tear-free", "newborn"],
        "health_profiles": ["baby", "sensitive", "allergyprone"]
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT-AWARE HEALTH PROFILES
# ═══════════════════════════════════════════════════════════════════════════════
HEALTH_PROFILES = {
    "diabetes": {
        "name": "Diabetes", 
        "icon": "🩺",
        "food_concerns": ["sugar", "glucose", "fructose", "corn syrup", "high fructose", "dextrose", "maltose", 
                         "honey", "agave", "maple syrup", "cane sugar", "brown sugar", "maltodextrin", "sucrose"],
        "supplement_concerns": ["sugar", "maltodextrin", "dextrose", "fructose", "glucose syrup"],
        "cosmetics_concerns": [],  # Not relevant
        "alert_template": {
            "food": "Contains sugar/sweeteners that may affect blood glucose levels",
            "supplement": "Contains sweeteners - check total carbohydrate content"
        }
    },
    "baby": {
        "name": "Baby Safe", 
        "icon": "👶",
        "food_concerns": ["honey", "excess salt", "artificial sweetener", "caffeine", "raw", "unpasteurized"],
        "cosmetics_concerns": ["fragrance", "parfum", "alcohol denat", "retinol", "salicylic acid", "essential oil", 
                              "menthol", "camphor", "eucalyptus", "peppermint oil", "tea tree"],
        "household_concerns": ["chlorine bleach", "ammonia", "fragrance", "optical brightener"],
        "alert_template": {
            "food": "May not be suitable for infants - consult pediatrician",
            "cosmetics": "Contains ingredients that may be too harsh for baby's delicate skin",
            "household": "Keep away from baby items and surfaces baby may contact"
        }
    },
    "pregnancy": {
        "name": "Pregnancy", 
        "icon": "🤰",
        "food_concerns": ["raw fish", "unpasteurized", "high mercury", "excess caffeine", "deli meat", "soft cheese"],
        "cosmetics_concerns": ["retinol", "retinoid", "retinoic acid", "salicylic acid", "benzoyl peroxide", 
                              "hydroquinone", "phthalate", "oxybenzone", "avobenzone", "formaldehyde"],
        "supplement_concerns": ["vitamin a excess", "retinol", "high dose", "herbal"],
        "alert_template": {
            "cosmetics": "Contains ingredients to discuss with your doctor during pregnancy",
            "supplement": "Consult healthcare provider before use during pregnancy",
            "food": "Review with healthcare provider during pregnancy"
        }
    },
    "sensitive": {
        "name": "Sensitive Skin", 
        "icon": "🌸",
        "cosmetics_concerns": ["fragrance", "parfum", "alcohol denat", "denatured alcohol", "essential oil", 
                              "menthol", "sulfate", "sodium lauryl", "witch hazel", "citrus oil", "lemon oil",
                              "lime oil", "bergamot", "eucalyptus", "peppermint", "cinnamon"],
        "household_concerns": ["fragrance", "dye", "chlorine", "optical brightener", "enzyme"],
        "alert_template": {
            "cosmetics": "Contains potential irritants - patch test recommended for sensitive skin",
            "household": "May cause irritation on contact - consider fragrance-free alternatives"
        }
    },
    "vegan": {
        "name": "Vegan", 
        "icon": "🌱",
        "food_concerns": ["gelatin", "carmine", "cochineal", "honey", "milk", "whey", "casein", "egg", 
                         "lard", "tallow", "shellac", "isinglass", "bone char", "l-cysteine"],
        "cosmetics_concerns": ["lanolin", "carmine", "beeswax", "collagen", "keratin", "silk", "squalene", 
                              "guanine", "tallow", "stearic acid", "glycerin", "shellac"],
        "supplement_concerns": ["gelatin", "fish oil", "bone meal", "collagen", "glucosamine", "chondroitin"],
        "alert_template": {
            "default": "May contain animal-derived ingredients"
        }
    },
    "glutenfree": {
        "name": "Gluten-Free", 
        "icon": "🌾",
        "food_concerns": ["wheat", "barley", "rye", "oat", "gluten", "malt", "triticale", "spelt", "kamut", 
                         "semolina", "durum", "farina", "bulgur", "couscous", "seitan"],
        "supplement_concerns": ["wheat", "gluten", "barley grass", "wheat grass", "malt"],
        "cosmetics_concerns": [],  # Gluten in cosmetics rarely an issue unless ingested
        "alert_template": {
            "food": "Contains gluten - not suitable for celiac disease or gluten sensitivity",
            "supplement": "May contain gluten - check certification"
        }
    },
    "heartcondition": {
        "name": "Heart Health", 
        "icon": "❤️",
        "food_concerns": ["sodium", "salt", "msg", "monosodium glutamate", "trans fat", "hydrogenated", 
                         "partially hydrogenated", "saturated fat", "palm oil"],
        "supplement_concerns": [],
        "cosmetics_concerns": [],  # NOT relevant for topical products!
        "alert_template": {
            "food": "High in sodium or unhealthy fats - consider heart-healthy alternatives"
        }
    },
    "allergyprone": {
        "name": "Allergy Prone", 
        "icon": "🤧",
        "food_concerns": ["peanut", "tree nut", "almond", "walnut", "cashew", "soy", "milk", "egg", 
                         "wheat", "shellfish", "fish", "sesame", "mustard", "celery", "lupin"],
        "cosmetics_concerns": ["fragrance", "parfum", "nut oil", "almond oil", "peanut oil", "coconut", 
                              "shea", "lanolin", "propolis", "beeswax", "latex"],
        "household_concerns": ["fragrance", "dye", "enzyme"],
        "alert_template": {
            "food": "Contains common allergen - check all ingredients carefully",
            "cosmetics": "Contains potential allergens - patch test recommended"
        }
    },
    "keto": {
        "name": "Keto Diet", 
        "icon": "🥑",
        "food_concerns": ["sugar", "glucose", "fructose", "corn syrup", "maltodextrin", "dextrose", 
                         "wheat", "rice", "potato", "corn", "high carb"],
        "supplement_concerns": ["maltodextrin", "sugar", "dextrose"],
        "cosmetics_concerns": [],
        "alert_template": {
            "food": "May contain high-carb ingredients not suitable for keto diet"
        }
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# ALLERGENS DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
ALLERGENS = {
    "gluten": {"name": "Gluten", "icon": "🌾", 
               "triggers": ["wheat", "barley", "rye", "gluten", "flour", "malt", "spelt", "kamut", "triticale"], 
               "contexts": ["food", "supplement"]},
    "dairy": {"name": "Dairy", "icon": "🥛", 
              "triggers": ["milk", "lactose", "whey", "casein", "cream", "butter", "cheese", "yogurt", "ghee"], 
              "contexts": ["food", "supplement"]},
    "nuts": {"name": "Tree Nuts", "icon": "🥜", 
             "triggers": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut", "pine nut"], 
             "contexts": ["food", "cosmetics"]},
    "peanuts": {"name": "Peanuts", "icon": "🥜", 
                "triggers": ["peanut", "groundnut", "arachis", "monkey nut"], 
                "contexts": ["food", "cosmetics"]},
    "soy": {"name": "Soy", "icon": "🫘", 
            "triggers": ["soy", "soya", "soybean", "tofu", "tempeh", "edamame", "soy lecithin"], 
            "contexts": ["food", "supplement"]},
    "eggs": {"name": "Eggs", "icon": "🥚", 
             "triggers": ["egg", "albumin", "mayonnaise", "meringue", "lysozyme", "lecithin", "ovalbumin"], 
             "contexts": ["food"]},
    "shellfish": {"name": "Shellfish", "icon": "🦐", 
                  "triggers": ["shrimp", "crab", "lobster", "prawn", "shellfish", "crayfish", "scallop", "mussel", "oyster"], 
                  "contexts": ["food", "supplement"]},
    "fish": {"name": "Fish", "icon": "🐟", 
             "triggers": ["fish", "salmon", "tuna", "cod", "anchovy", "sardine", "fish oil", "omega-3 fish"], 
             "contexts": ["food", "supplement"]},
    "sesame": {"name": "Sesame", "icon": "🫘", 
               "triggers": ["sesame", "tahini", "sesame oil", "hummus"], 
               "contexts": ["food", "cosmetics"]},
    "fragrance": {"name": "Fragrance", "icon": "🌺", 
                  "triggers": ["fragrance", "parfum", "perfume", "aroma", "essential oil blend"], 
                  "contexts": ["cosmetics", "household"]},
    "sulfates": {"name": "Sulfates", "icon": "🧴", 
                 "triggers": ["sulfate", "sls", "sles", "sodium lauryl", "sodium laureth", "ammonium lauryl"], 
                 "contexts": ["cosmetics"]},
    "parabens": {"name": "Parabens", "icon": "⚗️", 
                 "triggers": ["paraben", "methylparaben", "propylparaben", "butylparaben", "ethylparaben"], 
                 "contexts": ["cosmetics"]}
}

# ═══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVES DATABASE - Comprehensive
# ═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVES = {
    # Skincare
    "cleanser": {"name": "CeraVe Hydrating Cleanser", "why": "Fragrance-free, ceramides, gentle for all skin types", "score": 92, "category": "cosmetics"},
    "moisturizer": {"name": "CeraVe Moisturizing Cream", "why": "Ceramides, hyaluronic acid, fragrance-free, non-comedogenic", "score": 94, "category": "cosmetics"},
    "serum": {"name": "The Ordinary Niacinamide 10% + Zinc 1%", "why": "Transparent formula, effective concentration, affordable", "score": 91, "category": "cosmetics"},
    "sunscreen": {"name": "EltaMD UV Clear SPF 46", "why": "Zinc oxide, niacinamide, fragrance-free, won't clog pores", "score": 93, "category": "cosmetics"},
    "toner": {"name": "Paula's Choice Skin Perfecting 2% BHA", "why": "Fragrance-free, effective salicylic acid concentration", "score": 90, "category": "cosmetics"},
    "eye_cream": {"name": "CeraVe Eye Repair Cream", "why": "Ceramides, hyaluronic acid, fragrance-free", "score": 89, "category": "cosmetics"},
    "face_cream": {"name": "La Roche-Posay Toleriane Double Repair", "why": "Minimal ingredients, ceramides, prebiotic", "score": 93, "category": "cosmetics"},
    "exfoliant": {"name": "Paula's Choice 8% AHA Gel", "why": "Effective glycolic acid, no fragrance or irritants", "score": 88, "category": "cosmetics"},
    
    # Hair Care  
    "shampoo": {"name": "Free & Clear Shampoo", "why": "No sulfates, fragrance, parabens, dyes, or protein", "score": 94, "category": "cosmetics"},
    "conditioner": {"name": "Free & Clear Conditioner", "why": "Gentle formula for sensitive scalps, no common irritants", "score": 93, "category": "cosmetics"},
    
    # Body Care
    "body_wash": {"name": "Dove Sensitive Skin Body Wash", "why": "Hypoallergenic, fragrance-free option available", "score": 87, "category": "cosmetics"},
    "body_lotion": {"name": "Vanicream Moisturizing Lotion", "why": "No dyes, fragrance, parabens, lanolin, or formaldehyde", "score": 95, "category": "cosmetics"},
    "body cream": {"name": "Vanicream Moisturizing Cream", "why": "Dermatologist recommended, free from common irritants", "score": 95, "category": "cosmetics"},
    "hand_cream": {"name": "Neutrogena Norwegian Formula", "why": "Concentrated, fragrance-free option, glycerin-based", "score": 86, "category": "cosmetics"},
    "deodorant": {"name": "Native Deodorant (Unscented)", "why": "No aluminum, parabens, sulfates, or phthalates", "score": 86, "category": "cosmetics"},
    "lip_balm": {"name": "Aquaphor Lip Repair", "why": "Minimal ingredients, effective barrier", "score": 88, "category": "cosmetics"},
    
    # Baby Products
    "baby": {"name": "Cetaphil Baby Daily Lotion", "why": "Pediatrician tested, paraben-free, hypoallergenic", "score": 91, "category": "baby"},
    "baby_wash": {"name": "Cetaphil Baby Wash & Shampoo", "why": "Tear-free, dermatologist tested", "score": 90, "category": "baby"},
    "diaper_cream": {"name": "Boudreaux's Butt Paste", "why": "Zinc oxide, effective barrier, pediatrician recommended", "score": 89, "category": "baby"},
    
    # Food Products
    "cereal": {"name": "Nature's Path Organic Cereals", "why": "USDA organic, no artificial colors or preservatives", "score": 85, "category": "food"},
    "snack": {"name": "RXBAR or Larabar", "why": "Simple ingredients, no added sugar, whole foods", "score": 82, "category": "food"},
    "chips": {"name": "Jackson's Sweet Potato Chips", "why": "Simple ingredients, cooked in coconut oil", "score": 80, "category": "food"},
    "bread": {"name": "Dave's Killer Bread (Organic)", "why": "USDA organic, whole grains, no artificial preservatives", "score": 83, "category": "food"},
    "yogurt": {"name": "Siggi's Icelandic Yogurt", "why": "Low sugar, high protein, simple ingredients", "score": 86, "category": "food"},
    
    # Supplements
    "vitamin": {"name": "Thorne Research", "why": "Third-party tested, bioavailable forms, no unnecessary fillers", "score": 94, "category": "supplement"},
    "supplement": {"name": "NOW Foods or Thorne", "why": "GMP certified, third-party tested, transparent labels", "score": 90, "category": "supplement"},
    "b complex": {"name": "Thorne Basic B Complex", "why": "Active methylated forms, no fillers, NSF certified", "score": 94, "category": "supplement"},
    "multivitamin": {"name": "Thorne Basic Nutrients 2/Day", "why": "High quality, third-party verified, bioavailable", "score": 92, "category": "supplement"},
    "protein": {"name": "Momentous Whey Protein", "why": "NSF Certified for Sport, grass-fed, no artificial ingredients", "score": 91, "category": "supplement"},
    "omega": {"name": "Nordic Naturals Ultimate Omega", "why": "Third-party tested for purity, sustainable sourcing", "score": 92, "category": "supplement"},
    "probiotic": {"name": "Seed DS-01 Daily Synbiotic", "why": "Scientifically formulated, third-party tested", "score": 90, "category": "supplement"},
    
    # Household
    "laundry": {"name": "Seventh Generation Free & Clear", "why": "No dyes, fragrances, EPA Safer Choice certified", "score": 88, "category": "household"},
    "dish_soap": {"name": "Seventh Generation Dish Liquid", "why": "Plant-based, no synthetic fragrances", "score": 86, "category": "household"},
    "cleaner": {"name": "Branch Basics Concentrate", "why": "Non-toxic, fragrance-free, one product multiple uses", "score": 89, "category": "household"},
    
    # Default fallback
    "default": {"name": "Search EWG.org or Think Dirty App", "why": "Independent safety ratings for 80,000+ products", "score": None, "category": "general"}
}

def get_alternative(product_name, product_type, subtype=None):
    """Get better alternative based on product context"""
    search_text = f"{product_name} {product_type or ''} {subtype or ''}".lower()
    
    # Check specific subtype first
    if subtype and subtype.replace('_', ' ') in ALTERNATIVES:
        return ALTERNATIVES[subtype.replace('_', ' ')]
    if subtype and subtype in ALTERNATIVES:
        return ALTERNATIVES[subtype]
    
    # Check product name keywords
    for key in ALTERNATIVES:
        if key in search_text and key != 'default':
            alt = ALTERNATIVES[key]
            if alt['name'].lower() not in search_text:  # Don't recommend same product
                return alt
    
    # Check by product type
    if product_type == 'supplement':
        return ALTERNATIVES.get('supplement', ALTERNATIVES['default'])
    elif product_type == 'cosmetics':
        for term in ['cleanser', 'moisturizer', 'serum', 'cream', 'lotion', 'shampoo', 'wash']:
            if term in search_text:
                return ALTERNATIVES.get(term, ALTERNATIVES.get('moisturizer', ALTERNATIVES['default']))
    elif product_type == 'food':
        for term in ['cereal', 'snack', 'chips', 'bread', 'yogurt']:
            if term in search_text:
                return ALTERNATIVES.get(term, ALTERNATIVES['default'])
    
    return ALTERNATIVES['default']

# ═══════════════════════════════════════════════════════════════════════════════
# RETAILERS BY COUNTRY
# ═══════════════════════════════════════════════════════════════════════════════
RETAILERS = {
    "AU": ["Chemist Warehouse", "Priceline Pharmacy", "Woolworths", "Coles", "iHerb"],
    "US": ["CVS", "Walgreens", "Target", "Walmart", "Whole Foods", "Amazon", "iHerb"],
    "GB": ["Boots", "Superdrug", "Tesco", "Sainsbury's", "Holland & Barrett"],
    "NZ": ["Chemist Warehouse", "Countdown", "Unichem", "Life Pharmacy"],
    "CA": ["Shoppers Drug Mart", "Walmart", "London Drugs", "Well.ca"],
    "DE": ["dm", "Rossmann", "Müller", "Douglas"],
    "FR": ["Sephora", "Monoprix", "Carrefour", "Pharmacie"],
    "OTHER": ["Local pharmacy", "Health food store", "Amazon", "iHerb"]
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
                    return {'city': city, 'country': country or '', 'code': code or 'OTHER', 
                            'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
        except: 
            continue
    return {'city': 'Your City', 'country': 'Your Country', 'code': 'OTHER', 'retailers': RETAILERS['OTHER']}
# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE FUNCTIONS - Learning System & Persistence
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_product_name(name):
    """Normalize product name for consistent matching"""
    return re.sub(r'[^\w\s]', '', name.lower()).strip() if name else ""

def init_db():
    """Initialize all database tables"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    
    # Scans history
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT UNIQUE,
        user_id TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        product TEXT,
        brand TEXT,
        product_type TEXT,
        subtype TEXT,
        score INTEGER,
        verdict TEXT,
        ingredients TEXT,
        violations TEXT,
        bonuses TEXT,
        fine_print_alerts TEXT,
        thumb BLOB,
        favorite INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0
    )''')
    
    # Learned products for consistency
    c.execute('''CREATE TABLE IF NOT EXISTS learned_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name_lower TEXT UNIQUE,
        product_name TEXT,
        brand TEXT,
        product_type TEXT,
        avg_score REAL,
        scan_count INTEGER DEFAULT 1,
        ingredients TEXT,
        violations TEXT,
        last_scanned DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Barcode cache for instant lookups
    c.execute('''CREATE TABLE IF NOT EXISTS barcode_cache (
        barcode TEXT PRIMARY KEY,
        product_name TEXT,
        brand TEXT,
        ingredients TEXT,
        product_type TEXT,
        categories TEXT,
        nutrition TEXT,
        image_url TEXT,
        source TEXT,
        confidence TEXT,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # User preferences
    c.execute('CREATE TABLE IF NOT EXISTS allergies (a TEXT PRIMARY KEY)')
    c.execute('CREATE TABLE IF NOT EXISTS profiles (p TEXT PRIMARY KEY)')
    
    # Stats tracking
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        id INTEGER PRIMARY KEY DEFAULT 1,
        scans INTEGER DEFAULT 0,
        avoided INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        last_scan DATE
    )''')
    c.execute('INSERT OR IGNORE INTO stats (id) VALUES (1)')
    
    # User info
    c.execute('''CREATE TABLE IF NOT EXISTS user_info (
        id INTEGER PRIMARY KEY DEFAULT 1,
        user_id TEXT,
        city TEXT,
        country TEXT,
        country_code TEXT
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
        return {'city': r[0], 'country': r[1] or '', 'code': code, 'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
    return None

def save_location(city, country):
    code_map = {
        'australia': 'AU', 'united states': 'US', 'usa': 'US', 'united kingdom': 'GB', 'uk': 'GB',
        'new zealand': 'NZ', 'canada': 'CA', 'germany': 'DE', 'france': 'FR'
    }
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
    """Learn from scan for consistency"""
    try:
        name = result.get('product_name', '')
        name_lower = normalize_product_name(name)
        if not name_lower or len(name_lower) < 3:
            return
        
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT avg_score, scan_count FROM learned_products WHERE product_name_lower = ?', (name_lower,))
        existing = c.fetchone()
        
        if existing:
            old_avg, count = existing
            new_count = count + 1
            new_avg = ((old_avg * count) + result.get('score', 70)) / new_count
            c.execute('''UPDATE learned_products SET avg_score=?, scan_count=?, last_scanned=CURRENT_TIMESTAMP, 
                        ingredients=?, violations=? WHERE product_name_lower=?''',
                      (new_avg, new_count, json.dumps(result.get('ingredients', [])), 
                       json.dumps(result.get('violations', [])), name_lower))
        else:
            c.execute('''INSERT INTO learned_products 
                        (product_name_lower, product_name, brand, product_type, avg_score, ingredients, violations) 
                        VALUES (?,?,?,?,?,?,?)''',
                      (name_lower, name, result.get('brand', ''), result.get('product_type', ''),
                       result.get('score', 70), json.dumps(result.get('ingredients', [])),
                       json.dumps(result.get('violations', []))))
        
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def get_learned_product(product_name):
    """Get previously learned product data"""
    try:
        name_lower = normalize_product_name(product_name)
        if not name_lower:
            return None
        
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''SELECT product_name, brand, product_type, avg_score, scan_count, ingredients, violations 
                    FROM learned_products WHERE product_name_lower = ?''', (name_lower,))
        r = c.fetchone()
        conn.close()
        
        if r:
            return {
                'product_name': r[0], 'brand': r[1], 'product_type': r[2],
                'score': int(r[3]), 'scan_count': r[4],
                'ingredients': json.loads(r[5]) if r[5] else [],
                'violations': json.loads(r[6]) if r[6] else []
            }
    except:
        pass
    return None

def cache_barcode(barcode, data):
    """Cache barcode data for faster future lookups"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO barcode_cache 
                    (barcode, product_name, brand, ingredients, product_type, categories, nutrition, 
                     image_url, source, confidence, last_updated) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                  (barcode, data.get('name', ''), data.get('brand', ''), data.get('ingredients', ''),
                   data.get('product_type', ''), data.get('categories', ''), 
                   json.dumps(data.get('nutrition', {})), data.get('image_url', ''),
                   data.get('source', ''), data.get('confidence', 'medium')))
        conn.commit()
        conn.close()
    except:
        pass

def get_cached_barcode(barcode):
    """Get cached barcode data"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''SELECT product_name, brand, ingredients, product_type, categories, nutrition, 
                    image_url, source, confidence FROM barcode_cache WHERE barcode = ?''', (barcode,))
        r = c.fetchone()
        conn.close()
        
        if r and r[0]:
            return {
                'found': True, 'name': r[0], 'brand': r[1], 'ingredients': r[2],
                'product_type': r[3], 'categories': r[4],
                'nutrition': json.loads(r[5]) if r[5] else {},
                'image_url': r[6], 'source': r[7], 'confidence': r[8], 'cached': True
            }
    except:
        pass
    return None

def save_scan(result, user_id, thumb=None):
    """Save scan to history"""
    sid = f"HW-{uuid.uuid4().hex[:8].upper()}"
    
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    
    c.execute('''INSERT INTO scans 
                (scan_id, user_id, product, brand, product_type, subtype, score, verdict, 
                 ingredients, violations, bonuses, fine_print_alerts, thumb) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (sid, user_id, result.get('product_name', ''), result.get('brand', ''),
               result.get('product_type', ''), result.get('subtype', ''),
               result.get('score', 0), result.get('verdict', ''),
               json.dumps(result.get('ingredients', [])), json.dumps(result.get('violations', [])),
               json.dumps(result.get('bonuses', [])), json.dumps(result.get('fine_print_alerts', [])),
               thumb))
    
    # Update stats
    today = datetime.now().date()
    c.execute('SELECT scans, avoided, streak, best_streak, last_scan FROM stats WHERE id=1')
    r = c.fetchone()
    
    if r:
        scans, avoided, streak, best, last = r
        if last:
            try:
                ld = datetime.strptime(last, '%Y-%m-%d').date()
                if ld == today - timedelta(days=1):
                    streak += 1
                elif ld != today:
                    streak = 1
            except:
                streak = 1
        else:
            streak = 1
        
        best = max(best, streak)
        if result.get('verdict') == 'AVOID':
            avoided += 1
        
        c.execute('UPDATE stats SET scans=?, avoided=?, streak=?, best_streak=?, last_scan=? WHERE id=1',
                  (scans + 1, avoided, streak, best, today.isoformat()))
    
    conn.commit()
    conn.close()
    
    # Learn for consistency
    learn_product(result)
    
    return sid

def get_history(user_id, n=30):
    """Get scan history"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''SELECT id, scan_id, ts, product, brand, score, verdict, thumb, favorite 
                FROM scans WHERE user_id=? AND deleted=0 ORDER BY ts DESC LIMIT ?''', (user_id, n))
    rows = c.fetchall()
    conn.close()
    
    return [{
        'db_id': r[0], 'id': r[1], 'ts': r[2], 'product': r[3], 'brand': r[4],
        'score': r[5], 'verdict': r[6], 'thumb': r[7], 'favorite': r[8]
    } for r in rows]

def get_stats():
    """Get user stats"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT scans, avoided, streak, best_streak FROM stats WHERE id=1')
    r = c.fetchone()
    conn.close()
    
    if r:
        return {'scans': r[0], 'avoided': r[1], 'streak': r[2], 'best_streak': r[3]}
    return {'scans': 0, 'avoided': 0, 'streak': 0, 'best_streak': 0}

def get_allergies():
    """Get user allergen settings"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT a FROM allergies')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_allergies(allergies):
    """Save user allergen settings"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM allergies')
    for a in allergies:
        c.execute('INSERT OR IGNORE INTO allergies (a) VALUES (?)', (a,))
    conn.commit()
    conn.close()

def get_profiles():
    """Get user health profiles"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('SELECT p FROM profiles')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_profiles(profiles):
    """Save user health profiles"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('DELETE FROM profiles')
    for p in profiles:
        c.execute('INSERT OR IGNORE INTO profiles (p) VALUES (?)', (p,))
    conn.commit()
    conn.close()

def toggle_favorite(db_id, current):
    """Toggle favorite status"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('UPDATE scans SET favorite = ? WHERE id = ?', (0 if current else 1, db_id))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CLOUD DATABASE (Supabase)
# ═══════════════════════════════════════════════════════════════════════════════

def supa_ok():
    return bool(SUPABASE_URL and SUPABASE_KEY)

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
        else:
            return None
        
        return r.json() if r.ok and r.text else (True if r.ok else None)
    except:
        pass
    return None

def cloud_log_scan(result, city, country, user_id):
    if supa_ok():
        try:
            supa_request("POST", "scans_log", {
                "product_name": result.get('product_name', ''),
                "brand": result.get('brand', ''),
                "score": result.get('score', 0),
                "verdict": result.get('verdict', ''),
                "product_type": result.get('product_type', ''),
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
        
        existing = supa_request("GET", "products", 
                               params={"product_name_lower": f"eq.{name_lower}", "select": "id,avg_score,scan_count"})
        
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
# ═══════════════════════════════════════════════════════════════════════════════
# BARCODE SCANNING - Accurate Like Competitors (Yuka, Think Dirty, CodeCheck)
# ═══════════════════════════════════════════════════════════════════════════════

def preprocess_barcode_image(image):
    """Enhance barcode image for better reading"""
    try:
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        return enhanced.filter(ImageFilter.SHARPEN)
    except:
        return image

def try_decode_barcode_pyzbar(image_file):
    """Try to decode barcode using pyzbar library"""
    try:
        from pyzbar import pyzbar
        image_file.seek(0)
        img = Image.open(image_file)
        
        # Try multiple preprocessing approaches
        for proc_img in [img, preprocess_barcode_image(img), img.convert('L')]:
            barcodes = pyzbar.decode(proc_img)
            if barcodes:
                return barcodes[0].data.decode('utf-8')
    except:
        pass
    return None

def ai_read_barcode(image_file):
    """Use AI to read barcode numbers from image"""
    if not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        image_file.seek(0)
        img = Image.open(image_file)
        
        resp = model.generate_content([
            "Look at this image and find any barcode (UPC, EAN, etc.). "
            "Read the numbers printed below the barcode lines. "
            "Return ONLY the digits with no spaces or other text. "
            "If multiple barcodes exist, return the clearest one. "
            "If no barcode is visible or unreadable, return exactly: NONE",
            img
        ])
        
        text = resp.text.strip().upper()
        if 'NONE' in text or 'UNREADABLE' in text or 'CANNOT' in text:
            return None
        
        digits = re.sub(r'\D', '', text)
        if 8 <= len(digits) <= 14:
            return digits
    except:
        pass
    return None

def lookup_barcode_databases(barcode):
    """
    Search multiple product databases for barcode - like Yuka/Think Dirty
    Returns best match with product info
    """
    results = []
    
    # 1. Open Food Facts (Best for food globally)
    try:
        r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json", timeout=10)
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
                        'confidence': 'high' if p.get('ingredients_text') else 'medium'
                    })
    except:
        pass
    
    # 2. Open Beauty Facts (Best for cosmetics/personal care)
    try:
        r = requests.get(f"https://world.openbeautyfacts.org/api/v0/product/{barcode}.json", timeout=10)
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
                        'confidence': 'high' if p.get('ingredients_text') else 'medium'
                    })
    except:
        pass
    
    # 3. Open Products Facts (Household, etc)
    try:
        r = requests.get(f"https://world.openproductsfacts.org/api/v0/product/{barcode}.json", timeout=10)
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
                        'confidence': 'high' if p.get('ingredients_text') else 'medium'
                    })
    except:
        pass
    
    # 4. UPC Item DB (General products, supplements, electronics)
    try:
        r = requests.get(f"https://api.upcitemdb.com/prod/trial/lookup?upc={barcode}", timeout=10)
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
                    'ingredients': '',  # UPC Item DB doesn't provide ingredients
                    'source': 'UPC Item DB',
                    'confidence': 'medium'
                })
    except:
        pass
    
    # Return BEST result (prioritize: has ingredients > high confidence > has name)
    if results:
        results.sort(key=lambda x: (
            bool(x.get('ingredients')),  # Has ingredients (most valuable)
            x.get('confidence') == 'high',  # High confidence
            len(x.get('name', ''))  # Longer/more specific name
        ), reverse=True)
        return results[0]
    
    return {'found': False}

def smart_barcode_lookup(barcode, progress_callback=None):
    """Smart barcode lookup with caching - works like competitor apps"""
    if progress_callback:
        progress_callback(0.1, "Checking local cache...")
    
    # 1. Check cache first (instant!)
    cached = get_cached_barcode(barcode)
    if cached:
        if progress_callback:
            progress_callback(1.0, "✓ Found in cache!")
        return cached
    
    if progress_callback:
        progress_callback(0.3, "Searching global databases...")
    
    # 2. Search all databases
    result = lookup_barcode_databases(barcode)
    
    if result.get('found'):
        if progress_callback:
            progress_callback(0.9, "✓ Product found!")
        # Cache for future
        cache_barcode(barcode, result)
        return result
    
    if progress_callback:
        progress_callback(1.0, "Not found in databases")
    return {'found': False, 'barcode': barcode}

# ═══════════════════════════════════════════════════════════════════════════════
# SHARE IMAGE GENERATION - Fixed, No Broken Emojis
# ═══════════════════════════════════════════════════════════════════════════════

def create_share_image(product_name, brand, score, verdict, violations=None, bonuses=None):
    """Create shareable post image (1080x1080)"""
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
    
    # Gradient effect
    for i in range(height // 2, height):
        progress = (i - height // 2) / (height // 2)
        r1, g1, b1 = int(c['bg'][1:3], 16), int(c['bg'][3:5], 16), int(c['bg'][5:7], 16)
        r2, g2, b2 = int(c['bg2'][1:3], 16), int(c['bg2'][3:5], 16), int(c['bg2'][5:7], 16)
        r = int(r1 + (r2 - r1) * progress)
        g = int(g1 + (g2 - g1) * progress)
        b = int(b1 + (b2 - b1) * progress)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    
    # Load fonts
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
    
    # Draw content - text symbols only (no emojis that break)
    draw.text((width // 2, 60), "HonestWorld", fill='white', anchor="mt", font=font_title)
    draw.text((width // 2, 180), display['icon'], fill='white', anchor="mt", font=font_icon)
    draw.text((width // 2, 340), display['text'], fill='white', anchor="mt", font=font_verdict)
    draw.text((width // 2, 440), f"{score}/100", fill='white', anchor="mt", font=font_score)
    
    # Product name (truncate if needed)
    pname = product_name[:38] + "..." if len(product_name) > 38 else product_name
    draw.text((width // 2, 650), pname, fill='white', anchor="mt", font=font_product)
    
    # Brand
    if brand:
        bname = f"by {brand[:32]}"
        draw.text((width // 2, 710), bname, fill='white', anchor="mt", font=font_product)
    
    # Footer
    draw.text((width // 2, height - 55), "Scan at HonestWorld.app", fill='white', anchor="mm", font=font_footer)
    
    return img

def create_story_image(product_name, brand, score, verdict, main_issue=""):
    """Create shareable story image (1080x1920)"""
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
    for i in range(height // 2, height):
        progress = (i - height // 2) / (height // 2)
        r1, g1, b1 = int(c['bg'][1:3], 16), int(c['bg'][3:5], 16), int(c['bg'][5:7], 16)
        r2, g2, b2 = int(c['bg2'][1:3], 16), int(c['bg2'][3:5], 16), int(c['bg2'][5:7], 16)
        r = int(r1 + (r2 - r1) * progress)
        g = int(g1 + (g2 - g1) * progress)
        b = int(b1 + (b2 - b1) * progress)
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
    """Convert PIL image to bytes"""
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()

# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT-AWARE HEALTH ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

def check_health_alerts(ingredients, user_allergies, user_profiles, product_type, product_subtype=None):
    """
    Smart health alerts - context-aware based on product category
    Only shows relevant warnings (e.g., no heart health warning for body cream)
    """
    alerts = []
    if not ingredients:
        return alerts
    
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
        
        # Get concerns for THIS product type specifically
        concerns_key = f"{product_type}_concerns"
        concerns = profile.get(concerns_key, [])
        
        # If no specific concerns for this product type, skip entirely
        if not concerns:
            continue
        
        for concern in concerns:
            if concern in ing_text:
                # Get appropriate message template
                templates = profile.get('alert_template', {})
                message = templates.get(product_type, templates.get('default', f"Contains {concern}"))
                
                alerts.append({
                    'type': 'profile',
                    'name': profile['name'],
                    'icon': profile['icon'],
                    'trigger': concern,
                    'severity': 'medium',
                    'message': message
                })
                break
    
    return alerts

def check_fine_print_alerts(full_text, user_profiles, user_allergies):
    """
    FINE PRINT ENGINE - Scan for disclaimers based on user profile
    Catches "may contain traces of..." and similar warnings
    """
    alerts = []
    if not full_text:
        return alerts
    
    text_lower = full_text.lower()
    
    # Check profile-specific fine print patterns
    all_profiles = list(user_profiles) + list(user_allergies)
    
    for profile_key in all_profiles:
        if profile_key in FINE_PRINT_PATTERNS:
            pattern_data = FINE_PRINT_PATTERNS[profile_key]
            
            for pattern in pattern_data['warning_patterns']:
                if re.search(pattern, text_lower):
                    alerts.append({
                        'type': 'fine_print',
                        'profile': profile_key,
                        'severity': 'warning',
                        'message': pattern_data['alert_message'],
                        'matched_pattern': pattern
                    })
                    break  # One alert per profile
    
    return alerts

def get_science_citation(ingredient):
    """Get scientific source for ingredient warning"""
    ing_lower = ingredient.lower()
    for key, data in INGREDIENT_SCIENCE.items():
        if key in ing_lower:
            return data
    return None
# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED AI ANALYSIS - Fine Print Engine, Claims vs Reality, Dynamic Scoring
# ═══════════════════════════════════════════════════════════════════════════════

ANALYSIS_PROMPT = """You are HonestWorld's Premium AI Analyzer - the world's most advanced product scanner.
Analyze this product using our 20 Integrity Laws with SMART context-aware logic.

## YOUR ANALYSIS STEPS:

### STEP 1: PRODUCT CLASSIFICATION
Identify:
- product_type: food / cosmetics / supplement / electronics / household / baby
- subtype: specific type (e.g., serum, cleanser, vitamin, snack)

### STEP 2: FINE PRINT ENGINE 🔍
CRITICAL: Scan ALL text for disclaimers and warnings:
- "May contain traces of..." (allergens)
- "Not suitable for..." (restrictions)  
- "Patch test recommended" (skin sensitivity)
- "Consult doctor if pregnant/nursing"
- "Not for children under..."
- "Indoor use only" / "Not water resistant"
- Any asterisks (*) with fine print explanations

Report ALL fine print findings in `fine_print_alerts` array.

### STEP 3: FRONT-TO-BACK CROSS-VERIFICATION (Anti-Deception)
Compare FRONT marketing claims with BACK ingredient reality:

| Front Claim | Check For | Violation |
|-------------|-----------|-----------|
| "100% Natural" | Any synthetics (phenoxyethanol, dimethicone, PEG-, etc.) | Law 5: Natural Fallacy (-12) |
| "Fragrance-Free" | fragrance, parfum, perfume in ingredients | Law 19: False Claim (-15) |
| "Clinically Proven" | Missing study citation/details | Law 13: Clinical Ghost (-12) |
| "Dermatologist Tested" | No study size or methodology | Law 13: Clinical Ghost (-12) |
| "With [Hero Ingredient]" | If ingredient is position 6+ | Law 2: Fairy Dusting (-12) |
| "Premium/Luxury" | Water or cheap filler as #1 | Law 1: Water-Down (-15 to -25) |
| "Hypoallergenic" | Contains fragrance or known allergens | Law 19: False Claim (-12) |

### STEP 4: DYNAMIC SCORING BY CATEGORY
Base score: 85 points. Apply penalties WITH CONTEXT:

**Water as #1 Ingredient:**
- Premium Serum/Concentrate: -25 pts (DECEPTIVE)
- Toner/Mist: -3 pts (expected)
- Beverage: 0 pts (normal)
- Cleanser: -5 pts (somewhat expected)

**Fragrance/Parfum:**
- Baby product: -15 pts (UNACCEPTABLE)
- Sensitive skin product: -12 pts
- Regular adult cosmetic: -8 pts
- Perfumed body spray: -3 pts (expected)

### STEP 5: INGREDIENT FLAGS WITH CITATIONS
For EACH concerning ingredient, provide scientific citation:

Format: [Ingredient] → [Risk] → [Source]
Examples:
- "Methylparaben" → "Potential hormone disruptor" → "EU SCCS Opinion 2013"
- "Fragrance" → "Undisclosed chemicals, allergen" → "American Academy of Dermatology"
- "Trans Fat" → "Cardiovascular risk" → "FDA Ban 2018, AHA Guidelines"

### STEP 6: AWARD POSITIVE BONUSES
+5: Certified Organic (USDA, EU Organic)
+5: Third-party tested (NSF, USP, ConsumerLab)
+5: Full fragrance disclosure
+4: Fragrance-free
+4: EWG Verified
+3: Recyclable/sustainable packaging
+3: Cruelty-free certified
+3: Reef-safe
+2: Clean short ingredient list (<10 ingredients)
+2: Dermatologist developed

## THE 20 INTEGRITY LAWS:
1. Water-Down Deception (-15 base, -25 for serum): Premium claim but cheap filler #1
2. Fairy Dusting (-12): Hero ingredient below position #5
3. Split Sugar Trick (-18): 3+ sugar names hiding total
4. Low-Fat Trap (-10): Low fat but high sugar compensation
5. Natural Fallacy (-12): "Natural" with synthetics
6. Made-With Loophole (-8): "Made with X" but X is minimal
7. Serving Size Trick (-10): Unrealistic tiny servings
8. Slack Fill (-8): Package mostly empty
9. Spec Inflation (-15): "Up to X" unrealistic
10. Compatibility Lie (-12): "Universal" with exceptions
11. Military Grade Myth (-10): No real MIL-STD cert
12. Battery Fiction (-12): Unrealistic battery claims
13. Clinical Ghost (-12): "Clinically proven" no citation
14. Concentration Trick (-10): Active too diluted
15. Free Trap (-15): "Free" needs payment
16. Unlimited Lie (-18): "Unlimited" with caps
17. Lifetime Illusion (-10): "Lifetime" with exclusions
18. Photo vs Reality (-12): Photo much better
19. Fake Certification (-15): Claims unverified cert
20. Name Trick (-10): Name implies absent ingredient

## CONTEXT:
Location: {location}
User Profiles: {user_profiles}
User Allergies: {user_allergies}
{barcode_context}

## REQUIRED OUTPUT (Valid JSON):
{{
    "product_name": "Exact name from image",
    "brand": "Brand name",
    "product_type": "food/cosmetics/supplement/electronics/household/baby",
    "subtype": "specific type (cleanser, serum, vitamin, etc.)",
    "readable": true,
    "score": <0-100>,
    "front_claims": ["List all marketing claims from front of package"],
    "fine_print_alerts": [
        {{
            "text": "Exact disclaimer text found",
            "type": "allergen_trace/skin_warning/pregnancy/age_restriction/other",
            "severity": "high/medium/low"
        }}
    ],
    "violations": [
        {{
            "law": <1-20 or null>,
            "name": "Law/Violation name",
            "points": <negative number>,
            "evidence": "SPECIFIC evidence - quote exact text from package",
            "science": "Scientific basis/citation if applicable"
        }}
    ],
    "bonuses": [
        {{
            "name": "Bonus name",
            "points": <positive number>,
            "evidence": "What earned this bonus"
        }}
    ],
    "ingredients": ["full ingredient list if visible"],
    "ingredients_to_watch": [
        {{
            "name": "ingredient name",
            "reason": "why flagged",
            "severity": "high/medium/low",
            "source": "scientific source"
        }}
    ],
    "good_ingredients": ["beneficial ingredients"],
    "main_issue": "Primary concern or 'Clean formula' if none",
    "positive": "Main positive aspect",
    "tip": "Helpful consumer advice specific to this product",
    "confidence": "high/medium/low"
}}

## CRITICAL RULES:
1. EVERY deduction needs SPECIFIC evidence from the image
2. Apply DYNAMIC weights based on product category
3. SCAN for fine print disclaimers thoroughly
4. CROSS-REFERENCE front claims with back ingredients
5. CITE scientific sources for health flags
6. Award ALL applicable bonuses
7. If score < 100, violations array must explain why"""

def analyze_product(images, location, progress_callback, barcode_info=None, user_profiles=None, user_allergies=None):
    """
    Premium AI Analysis with:
    - Fine Print Engine
    - Claims vs Reality verification
    - Dynamic scoring by category
    - Scientific citations
    """
    progress_callback(0.1, "Reading product...")
    
    if not GEMINI_API_KEY:
        return {
            "product_name": "API Key Missing",
            "brand": "",
            "score": 0,
            "verdict": "UNCLEAR",
            "readable": False,
            "violations": [],
            "main_issue": "Please add GEMINI_API_KEY to secrets"
        }
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash-exp", 
                                   generation_config={"temperature": 0.1, "max_output_tokens": 8192})
    
    pil_images = []
    for img in images:
        img.seek(0)
        pil_images.append(Image.open(img))
    
    progress_callback(0.25, "Scanning fine print...")
    
    # Build context
    barcode_context = ""
    if barcode_info and barcode_info.get('found'):
        barcode_context = f"""
BARCODE DATABASE INFO (Use as reference):
- Product: {barcode_info.get('name', '')}
- Brand: {barcode_info.get('brand', '')}
- Category: {barcode_info.get('categories', '')}
- Database Ingredients: {barcode_info.get('ingredients', '')[:800]}
- Source: {barcode_info.get('source', '')}
NOTE: If image shows different info, trust the IMAGE."""
    
    progress_callback(0.4, "Cross-referencing claims...")
    
    prompt = ANALYSIS_PROMPT.format(
        location=f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}",
        user_profiles=', '.join(user_profiles) if user_profiles else 'None set',
        user_allergies=', '.join(user_allergies) if user_allergies else 'None set',
        barcode_context=barcode_context
    )
    
    progress_callback(0.6, "Applying dynamic scoring...")
    
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
                except:
                    continue
        
        if not result:
            return {
                "product_name": "Parse Error",
                "brand": "",
                "score": 0,
                "verdict": "UNCLEAR",
                "readable": False,
                "violations": [],
                "main_issue": "Could not parse AI response"
            }
        
        progress_callback(0.8, "Calculating final score...")
        
        # Ensure valid score
        score = result.get('score', 75)
        if isinstance(score, str):
            try:
                score = int(re.sub(r'[^\d]', '', score))
            except:
                score = 75
        score = max(0, min(100, score))
        
        # Ensure violations explain score
        violations = result.get('violations', [])
        bonuses = result.get('bonuses', [])
        
        if not violations and score < 85:
            missing = 85 - score
            violations = [{
                "law": None,
                "name": "Formula concerns",
                "points": -missing,
                "evidence": result.get('main_issue', 'Minor concerns detected in formulation')
            }]
        
        result['score'] = score
        result['verdict'] = get_verdict(score)
        result['violations'] = violations
        result['bonuses'] = bonuses
        
        # Apply learning consistency
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
        return {
            "product_name": "Analysis Error",
            "brand": "",
            "score": 0,
            "verdict": "UNCLEAR",
            "readable": False,
            "violations": [],
            "main_issue": f"Error: {str(e)[:100]}"
        }
# ═══════════════════════════════════════════════════════════════════════════════
# PREMIUM CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
.stApp { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
.main .block-container { padding: 0.5rem 1rem; max-width: 520px; }

/* Verdict Cards */
.verdict-exceptional { background: linear-gradient(135deg, #06b6d4 0%, #0891b2 50%, #0e7490 100%); }
.verdict-buy { background: linear-gradient(135deg, #22c55e 0%, #16a34a 50%, #15803d 100%); }
.verdict-caution { background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%); }
.verdict-avoid { background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%); }
.verdict-unclear { background: linear-gradient(135deg, #6b7280 0%, #4b5563 50%, #374151 100%); }

.verdict-card {
    border-radius: 24px;
    padding: 1.75rem;
    text-align: center;
    color: white;
    margin: 1rem 0;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2);
    position: relative;
    overflow: hidden;
}
.verdict-card::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    pointer-events: none;
}
.verdict-icon { font-size: 3.5rem; margin-bottom: 0.5rem; text-shadow: 0 2px 10px rgba(0,0,0,0.2); }
.verdict-text { font-size: 1.2rem; font-weight: 800; letter-spacing: 2px; margin: 0.3rem 0; text-transform: uppercase; }
.verdict-score { font-size: 3.5rem; font-weight: 900; text-shadow: 0 2px 10px rgba(0,0,0,0.2); }

/* Stats Row */
.stat-row { display: flex; gap: 0.5rem; margin: 0.75rem 0; }
.stat-box {
    flex: 1;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 0.75rem;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.stat-val { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }
.stat-lbl { font-size: 0.65rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }

/* Alert Boxes */
.alert-danger {
    background: linear-gradient(135deg, #fef2f2, #fee2e2);
    border: 2px solid #fca5a5;
    border-left: 4px solid #ef4444;
    border-radius: 12px;
    padding: 1rem;
    margin: 0.5rem 0;
}
.alert-warning {
    background: linear-gradient(135deg, #fffbeb, #fef3c7);
    border: 2px solid #fcd34d;
    border-left: 4px solid #f59e0b;
    border-radius: 12px;
    padding: 1rem;
    margin: 0.5rem 0;
}
.alert-info {
    background: linear-gradient(135deg, #eff6ff, #dbeafe);
    border: 2px solid #93c5fd;
    border-left: 4px solid #3b82f6;
    border-radius: 12px;
    padding: 1rem;
    margin: 0.5rem 0;
}
.alert-fine-print {
    background: linear-gradient(135deg, #fdf4ff, #f3e8ff);
    border: 2px solid #d8b4fe;
    border-left: 4px solid #a855f7;
    border-radius: 12px;
    padding: 1rem;
    margin: 0.5rem 0;
}

/* Issue/Positive Boxes */
.issue-box {
    background: linear-gradient(135deg, #fef3c7, #fde68a);
    border-left: 4px solid #f59e0b;
    padding: 0.85rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.positive-box {
    background: linear-gradient(135deg, #dcfce7, #bbf7d0);
    border-left: 4px solid #22c55e;
    padding: 0.85rem;
    border-radius: 0 12px 12px 0;
    margin: 0.5rem 0;
}
.bonus-box {
    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
    border-left: 4px solid #3b82f6;
    padding: 0.65rem;
    border-radius: 0 10px 10px 0;
    margin: 0.3rem 0;
}
.tip-box {
    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
    border: 1px solid #86efac;
    border-radius: 12px;
    padding: 0.85rem;
    margin: 0.5rem 0;
}

/* Law Violations */
.law-box {
    background: linear-gradient(135deg, #fef2f2, #fecaca);
    border-left: 4px solid #ef4444;
    padding: 0.85rem;
    border-radius: 0 12px 12px 0;
    margin: 0.4rem 0;
}
.law-title { font-weight: 700; color: #dc2626; }
.law-evidence { font-size: 0.85rem; color: #64748b; margin-top: 0.3rem; }
.law-science {
    font-size: 0.75rem;
    color: #6b7280;
    font-style: italic;
    margin-top: 0.25rem;
    background: rgba(239, 68, 68, 0.1);
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    display: inline-block;
}

/* Ingredients */
.ing-summary { display: flex; gap: 0.5rem; margin: 0.5rem 0; flex-wrap: wrap; }
.ing-badge {
    padding: 0.4rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.8rem;
}
.ing-watch { background: #fed7aa; color: #c2410c; }
.ing-good { background: #bbf7d0; color: #16a34a; }

/* Alternatives */
.alt-card {
    background: linear-gradient(135deg, #f0fdf4, #dcfce7);
    border: 2px solid #86efac;
    border-radius: 16px;
    padding: 1.1rem;
    margin: 0.75rem 0;
    box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
}
.alt-score {
    display: inline-block;
    background: linear-gradient(135deg, #22c55e, #16a34a);
    color: white;
    padding: 0.25rem 0.6rem;
    border-radius: 8px;
    font-weight: 700;
    font-size: 0.8rem;
    margin-left: 0.5rem;
}

/* History */
.history-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid #f1f5f9;
}
.history-score {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: white;
    font-size: 0.9rem;
    flex-shrink: 0;
}

/* Share Grid */
.share-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin: 0.5rem 0;
}
.share-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.75rem;
    border-radius: 12px;
    color: white;
    text-decoration: none;
    font-weight: 600;
    font-size: 0.75rem;
    transition: transform 0.2s, box-shadow 0.2s;
}
.share-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.share-btn span { font-size: 1.3rem; margin-bottom: 0.25rem; }

/* Progress */
.progress-box {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 2rem;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}
.progress-bar {
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    margin: 1rem 0;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899);
    transition: width 0.3s ease;
    border-radius: 4px;
}

/* Badges */
.loc-badge {
    background: linear-gradient(135deg, #dbeafe, #bfdbfe);
    color: #1d4ed8;
    padding: 0.35rem 0.75rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    display: inline-block;
}
.streak-badge {
    background: linear-gradient(135deg, #f59e0b, #ef4444);
    color: white;
    padding: 0.35rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
}
.category-badge {
    background: linear-gradient(135deg, #e0e7ff, #c7d2fe);
    color: #4338ca;
    padding: 0.25rem 0.6rem;
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 600;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    color: white !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 1.5rem !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f1f5f9;
    padding: 4px;
    border-radius: 12px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #64748b;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1rem;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #1e293b !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

/* Laws Display */
.law-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.85rem;
    margin: 0.4rem 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.law-card-title { font-weight: 700; color: #1e293b; }
.law-card-points { color: #ef4444; font-weight: 700; }
.law-card-desc { font-size: 0.85rem; color: #64748b; margin-top: 0.35rem; }
.law-card-tip { font-size: 0.8rem; color: #059669; margin-top: 0.35rem; }

/* Multiselect tags */
.stMultiSelect [data-baseweb="tag"] {
    background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
    border-radius: 8px !important;
}

/* Expanders */
[data-testid="stExpander"] {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin: 0.5rem 0;
}

/* Hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stCameraInput"] video { max-height: 200px !important; border-radius: 16px; }

/* Custom scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
</style>
"""
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION - Premium Edition
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_db()
    user_id = get_user_id()
    
    # Session state initialization
    if 'result' not in st.session_state:
        st.session_state.result = None
    if 'scan_id' not in st.session_state:
        st.session_state.scan_id = None
    if 'admin' not in st.session_state:
        st.session_state.admin = False
    if 'barcode_info' not in st.session_state:
        st.session_state.barcode_info = None
    if 'barcode_num' not in st.session_state:
        st.session_state.barcode_num = None
    if 'show_result' not in st.session_state:
        st.session_state.show_result = False
    
    # Location - auto-detect and save
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
    
    # Stats row
    st.markdown(f"""<div class='stat-row'>
        <div class='stat-box'><div class='stat-val'>{stats['scans']}</div><div class='stat-lbl'>Scans</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['avoided']}</div><div class='stat-lbl'>Avoided</div></div>
        <div class='stat-box'><div class='stat-val'>{stats['best_streak']}</div><div class='stat-lbl'>Best Streak</div></div>
    </div>""", unsafe_allow_html=True)
    
    # Main tabs
    tab_scan, tab_history, tab_profile, tab_laws = st.tabs(["📷 Scan", "📋 History", "👤 Profile", "⚖️ Laws"])
    
    with tab_scan:
        if st.session_state.result and st.session_state.show_result:
            display_result(st.session_state.result, user_id)
        else:
            # Input method selection
            input_method = st.radio("", ["📷 Camera", "📁 Upload", "📊 Barcode"], horizontal=True, label_visibility="collapsed")
            images = []
            
            if input_method == "📷 Camera":
                st.caption("📸 Point at product (front AND back for best analysis)")
                cam_img = st.camera_input("Take photo", label_visibility="collapsed")
                if cam_img:
                    images = [cam_img]
                    st.success("✅ Photo captured!")
                    if st.checkbox("➕ Add back of package photo"):
                        cam_img2 = st.camera_input("Back photo", label_visibility="collapsed", key="cam2")
                        if cam_img2:
                            images.append(cam_img2)
            
            elif input_method == "📁 Upload":
                uploaded = st.file_uploader("Upload product images", type=['png', 'jpg', 'jpeg', 'webp'], 
                                           accept_multiple_files=True, label_visibility="collapsed")
                if uploaded:
                    images = uploaded[:3]
                    st.success(f"✅ {len(images)} image(s) uploaded")
            
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
                            
                            progress_ph = st.empty()
                            def update_prog(pct, msg):
                                progress_ph.markdown(f"""<div class='progress-box'>
                                    <div style='font-weight: 600;'>{msg}</div>
                                    <div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div>
                                </div>""", unsafe_allow_html=True)
                            
                            barcode_info = smart_barcode_lookup(barcode_num, update_prog)
                            progress_ph.empty()
                            
                            if barcode_info.get('found'):
                                st.success(f"✅ **{barcode_info.get('name', '')}**")
                                if barcode_info.get('brand'):
                                    st.caption(f"by {barcode_info.get('brand')} • Source: {barcode_info.get('source', '')}")
                                
                                with st.expander("📋 Database info", expanded=False):
                                    if barcode_info.get('ingredients'):
                                        st.markdown(f"**Ingredients:** {barcode_info.get('ingredients', '')[:500]}...")
                                    if barcode_info.get('categories'):
                                        st.markdown(f"**Category:** {barcode_info.get('categories', '')[:100]}")
                                
                                st.session_state.barcode_info = barcode_info
                                images = [barcode_img]
                            else:
                                st.warning("Product not in databases. Try photo scan for full analysis.")
                        else:
                            st.error("Could not read barcode. Try a clearer image or use photo scan.")
            
            # Analyze button
            if images:
                if st.button("🔍 ANALYZE PRODUCT", use_container_width=True, type="primary"):
                    progress_ph = st.empty()
                    def update_prog(pct, msg):
                        icons = ['🔍', '📋', '⚖️', '✨']
                        icon = icons[min(int(pct * 4), 3)]
                        progress_ph.markdown(f"""<div class='progress-box'>
                            <div style='font-size: 2.5rem;'>{icon}</div>
                            <div style='font-weight: 600; margin: 0.5rem 0;'>{msg}</div>
                            <div class='progress-bar'><div class='progress-fill' style='width: {pct*100}%'></div></div>
                        </div>""", unsafe_allow_html=True)
                    
                    # Get user preferences for AI context
                    user_profiles = get_profiles()
                    user_allergies = get_allergies()
                    
                    bi = st.session_state.get('barcode_info')
                    result = analyze_product(images, st.session_state.loc, update_prog, bi, user_profiles, user_allergies)
                    progress_ph.empty()
                    
                    if result.get('readable', True) and result.get('score', 0) > 0:
                        # Create thumbnail
                        thumb = None
                        try:
                            images[0].seek(0)
                            img = Image.open(images[0])
                            img.thumbnail((100, 100))
                            buf = BytesIO()
                            img.save(buf, format='JPEG', quality=60)
                            thumb = buf.getvalue()
                        except:
                            pass
                        
                        # Save scan
                        scan_id = save_scan(result, user_id, thumb)
                        cloud_log_scan(result, st.session_state.loc.get('city', ''), 
                                      st.session_state.loc.get('country', ''), user_id)
                        cloud_save_product(result)
                        
                        # Store and show result
                        st.session_state.result = result
                        st.session_state.scan_id = scan_id
                        st.session_state.show_result = True
                        st.session_state.barcode_info = None
                        st.session_state.barcode_num = None
                        st.rerun()
                    else:
                        st.error("❌ Could not analyze. Please try a clearer photo showing product name and ingredients.")
    
    with tab_history:
        history = get_history(user_id, 30)
        if not history:
            st.info("📋 No scans yet! Start scanning products to build your history.")
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
        
        # Location
        st.markdown("**📍 Location**")
        col1, col2 = st.columns(2)
        with col1:
            city = st.text_input("City", value=st.session_state.loc.get('city', ''), key="city_input")
        with col2:
            country = st.text_input("Country", value=st.session_state.loc.get('country', ''), key="country_input")
        
        if st.button("Update Location", key="update_loc_btn"):
            code = save_location(city, country)
            st.session_state.loc = {'city': city, 'country': country, 'code': code, 
                                    'retailers': RETAILERS.get(code, RETAILERS['OTHER'])}
            st.success("✅ Location updated!")
            st.rerun()
        
        st.markdown("---")
        
        # Health Profiles - FIXED: Now properly saves and refreshes
        st.markdown("**🏥 Health Profiles**")
        st.caption("Smart alerts based on product type - Heart health only for food, Sensitive skin for cosmetics, etc.")
        
        current_profiles = get_profiles()
        profile_options = list(HEALTH_PROFILES.keys())
        
        new_profiles = st.multiselect(
            "Select your health profiles",
            options=profile_options,
            default=current_profiles,
            format_func=lambda x: f"{HEALTH_PROFILES[x]['icon']} {HEALTH_PROFILES[x]['name']}",
            key="profiles_multiselect"
        )
        
        if st.button("Save Health Profiles", key="save_profiles_btn"):
            save_profiles(new_profiles)
            st.success("✅ Health profiles saved!")
            st.rerun()
        
        st.markdown("---")
        
        # Allergens - FIXED: Now properly saves and refreshes
        st.markdown("**🚨 Allergen Alerts**")
        st.caption("Get warned when products contain your allergens")
        
        current_allergies = get_allergies()
        allergy_options = list(ALLERGENS.keys())
        
        new_allergies = st.multiselect(
            "Select your allergens",
            options=allergy_options,
            default=current_allergies,
            format_func=lambda x: f"{ALLERGENS[x]['icon']} {ALLERGENS[x]['name']}",
            key="allergies_multiselect"
        )
        
        if st.button("Save Allergen Alerts", key="save_allergies_btn"):
            save_allergies(new_allergies)
            st.success("✅ Allergen alerts saved!")
            st.rerun()
        
        st.markdown("---")
        
        # Admin
        st.markdown("**🔐 Admin**")
        admin_pw = st.text_input("Admin password", type="password", key="admin_pw_input")
        if admin_pw and hashlib.sha256(admin_pw.encode()).hexdigest() == ADMIN_HASH:
            st.session_state.admin = True
        
        if st.session_state.admin:
            st.markdown("### 📊 Admin Dashboard")
            conn = sqlite3.connect(LOCAL_DB)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM scans')
            total_scans = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM learned_products')
            learned = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM barcode_cache')
            barcodes = c.fetchone()[0]
            conn.close()
            
            st.markdown(f"""
            - **Total Scans:** {total_scans}
            - **Learned Products:** {learned}
            - **Cached Barcodes:** {barcodes}
            - **Cloud Status:** {'🟢 Connected' if supa_ok() else '🔴 Not configured'}
            """)
    
    with tab_laws:
        st.markdown("### ⚖️ The 20 Integrity Laws")
        st.caption("Transparent, evidence-based scoring with dynamic weights and scientific citations")
        
        categories = {
            "🧪 Ingredients (1-6)": [1, 2, 3, 4, 5, 6],
            "📦 Packaging (7, 8, 18)": [7, 8, 18],
            "📱 Electronics (9-12)": [9, 10, 11, 12],
            "💄 Beauty (13-14)": [13, 14],
            "📋 Services (15-17)": [15, 16, 17],
            "🏷️ Claims (19-20)": [19, 20]
        }
        
        for cat_name, law_nums in categories.items():
            with st.expander(cat_name, expanded=False):
                for num in law_nums:
                    if num in INTEGRITY_LAWS:
                        law = INTEGRITY_LAWS[num]
                        st.markdown(f"""<div class='law-card'>
                            <span class='law-card-title'>Law {num}: {law['name']}</span>
                            <span class='law-card-points'> ({law['base_points']} pts)</span>
                            <div class='law-card-desc'>{law['description']}</div>
                            <div class='law-card-tip'>💡 {law['tip']}</div>
                        </div>""", unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(f"""<center style='color: #94a3b8; font-size: 0.75rem;'>
        🌍 HonestWorld v{VERSION} • Premium Edition • Fine Print Engine • Claims Verification
    </center>""", unsafe_allow_html=True)


def display_result(result, user_id):
    """Display scan result with all premium features"""
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
    st.markdown(f"### {result.get('product_name', 'Unknown Product')}")
    if result.get('brand'):
        st.markdown(f"*by {result.get('brand')}*")
    if product_type != 'unknown':
        type_display = f"{product_type.title()}" + (f" • {subtype.replace('_', ' ').title()}" if subtype else "")
        st.markdown(f"<span class='category-badge'>{type_display}</span>", unsafe_allow_html=True)
    
    # Fine Print Alerts (NEW!)
    fine_print = result.get('fine_print_alerts', [])
    if fine_print:
        for fp in fine_print:
            st.markdown(f"""<div class='alert-fine-print'>
                <strong>📜 Fine Print Found</strong><br>
                <span style='font-size: 0.9rem;'>"{fp.get('text', '')}"</span>
            </div>""", unsafe_allow_html=True)
    
    # Health alerts - context aware
    user_profiles = get_profiles()
    user_allergies = get_allergies()
    alerts = check_health_alerts(result.get('ingredients', []), user_allergies, user_profiles, product_type, subtype)
    
    for alert in alerts:
        css_class = 'alert-danger' if alert['severity'] == 'high' else 'alert-warning'
        st.markdown(f"""<div class='{css_class}'>
            <strong>{alert['icon']} {alert['name']} {'Alert' if alert['severity'] == 'high' else 'Note'}</strong><br>
            <span style='font-size: 0.9rem;'>{alert.get('message', f"Contains: {alert['trigger']}")}</span>
        </div>""", unsafe_allow_html=True)
    
    # Law Violations (renamed from Deductions)
    violations = result.get('violations', [])
    if violations:
        with st.expander(f"⚖️ Laws ({len(violations)})", expanded=True):
            for v in violations:
                law_text = f"Law {v.get('law')}: " if v.get('law') else ""
                science_html = ""
                if v.get('science'):
                    science_html = f"<div class='law-science'>📚 {v.get('science')}</div>"
                
                st.markdown(f"""<div class='law-box'>
                    <div class='law-title'>{law_text}{v.get('name', 'Violation')} ({v.get('points', 0)} pts)</div>
                    <div class='law-evidence'>{v.get('evidence', '')}</div>
                    {science_html}
                </div>""", unsafe_allow_html=True)
    
    # Bonuses
    bonuses = result.get('bonuses', [])
    if bonuses:
        with st.expander(f"✨ Bonuses ({len(bonuses)})", expanded=False):
            for b in bonuses:
                st.markdown(f"""<div class='bonus-box'>
                    <strong>+{b.get('points', 0)} pts: {b.get('name', '')}</strong><br>
                    <span style='font-size: 0.85rem; color: #2563eb;'>{b.get('evidence', '')}</span>
                </div>""", unsafe_allow_html=True)
    
    # Main issue
    main_issue = result.get('main_issue', '')
    if main_issue and main_issue.lower() not in ['clean formula', 'none', '']:
        st.markdown(f"<div class='issue-box'>⚠️ <strong>Main Concern:</strong> {main_issue}</div>", unsafe_allow_html=True)
    
    # Positive
    if result.get('positive'):
        st.markdown(f"<div class='positive-box'>✅ <strong>Positive:</strong> {result.get('positive')}</div>", unsafe_allow_html=True)
    
    # Ingredients
    with st.expander("🧪 Ingredients", expanded=False):
        watch = result.get('ingredients_to_watch', [])
        if watch:
            st.markdown("**⚠️ Watch:**")
            for w in watch[:8]:
                if isinstance(w, dict):
                    science = get_science_citation(w.get('name', ''))
                    source_text = f" • *{science['sources'][0]}*" if science else ""
                    st.markdown(f"<span class='ing-badge ing-watch'>{w.get('name', '')}</span> {w.get('reason', '')}{source_text}", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='ing-badge ing-watch'>{w}</span>", unsafe_allow_html=True)
        
        good = result.get('good_ingredients', [])
        if good:
            st.markdown("**✅ Good:**")
            badges = " ".join([f"<span class='ing-badge ing-good'>{g}</span>" for g in good[:10]])
            st.markdown(f"<div class='ing-summary'>{badges}</div>", unsafe_allow_html=True)
        
        if result.get('ingredients'):
            with st.expander("Full list"):
                st.write(", ".join(result.get('ingredients', [])[:50]))
    
    # Tip
    if result.get('tip'):
        st.markdown(f"<div class='tip-box'>💡 <strong>Tip:</strong> {result.get('tip')}</div>", unsafe_allow_html=True)
    
    # Alternative - ALWAYS SHOW (even for good scores)
    alt = get_alternative(result.get('product_name', ''), product_type, subtype)
    alt_score_html = f"<span class='alt-score'>{alt['score']}/100</span>" if alt.get('score') else ''
    retailers = ', '.join(st.session_state.loc.get('retailers', ['Local stores'])[:3])
    
    st.markdown(f"""<div class='alt-card'>
        <strong>💚 {'Better Alternative' if verdict in ['CAUTION', 'AVOID'] else 'Similar Quality Option'}:</strong><br>
        <span style='font-size: 1.1rem; font-weight: 600;'>{alt['name']}</span> {alt_score_html}<br>
        <span style='color: #16a34a;'>{alt['why']}</span><br>
        <span style='font-size: 0.85rem; color: #64748b;'>Available at: {retailers}</span>
    </div>""", unsafe_allow_html=True)
    
    # Share section
    st.markdown("### 📤 Share Result")
    
    share_img = create_share_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict)
    story_img = create_story_image(result.get('product_name', 'Product'), result.get('brand', ''), score, verdict)
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Post (1080×1080)", data=image_to_bytes(share_img), 
                          file_name=f"honestworld_{score}.png", mime="image/png", use_container_width=True)
    with col2:
        st.download_button("📥 Story (1080×1920)", data=image_to_bytes(story_img), 
                          file_name=f"honestworld_story_{score}.png", mime="image/png", use_container_width=True)
    
    # Social share links
    share_text = f"Scanned {result.get('product_name', 'product')} with HonestWorld - Score: {score}/100 ({verdict}) #HonestWorld"
    encoded = urllib.parse.quote(share_text)
    
    st.markdown(f"""<div class='share-grid'>
        <a href='https://twitter.com/intent/tweet?text={encoded}' target='_blank' class='share-btn' style='background: #1DA1F2;'><span>𝕏</span>Twitter</a>
        <a href='https://www.facebook.com/sharer/sharer.php?quote={encoded}' target='_blank' class='share-btn' style='background: #4267B2;'><span>f</span>Facebook</a>
        <a href='https://wa.me/?text={encoded}' target='_blank' class='share-btn' style='background: #25D366;'><span>💬</span>WhatsApp</a>
        <a href='https://t.me/share/url?text={encoded}' target='_blank' class='share-btn' style='background: #0088cc;'><span>➤</span>Telegram</a>
        <a href='https://instagram.com' target='_blank' class='share-btn' style='background: linear-gradient(45deg, #f09433, #dc2743);'><span>📷</span>Instagram</a>
        <a href='https://tiktok.com' target='_blank' class='share-btn' style='background: #000;'><span>♪</span>TikTok</a>
    </div>""", unsafe_allow_html=True)
    
    # Scan another button
    st.markdown("")
    if st.button("🔄 Scan Another Product", use_container_width=True):
        st.session_state.result = None
        st.session_state.scan_id = None
        st.session_state.show_result = False
        st.rerun()


if __name__ == "__main__":
    main()
