import os
import re
import requests
import json
from typing import List
from pydantic import BaseModel
import PIL.Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, "raw_photos")
os.makedirs(INPUT_FOLDER, exist_ok=True)

# --- MODELS FOR BATCH RESPONSE ---

class SceneAnalysis(BaseModel):
    image_index: int
    room_type: str
    caption: str
    effect: str

class VideoScript(BaseModel):
    scenes: List[SceneAnalysis]

# --- SCRAPING LOGIC ---

def fetch_zillow_data(url: str):
    """Scrapes Zillow using RapidAPI and downloads the first 15 images."""
    match = re.search(r'([0-9]+)_zpid', url)
    if not match: raise ValueError("Invalid Zillow URL. Make sure it contains a ZPID.")
    zpid = match.group(1)
    
    api_url = f"https://api.pullapi.com/zillow/property/{zpid}"
    headers = {
        "x-api-key": RAPIDAPI_KEY, 
        "x-rapidapi-key": RAPIDAPI_KEY, 
        "x-rapidapi-host": "zillow-scraper-api.p.rapidapi.com"
    }
    
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Primary API failed, trying backup: {e}")
        api_url = f"https://zillow-scraper-api.p.rapidapi.com/zillow/property/{zpid}"
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()

    data = response.json().get("data", {})
    
    meta = {
        "address": "", "price": "", "beds": "", "baths": "", 
        "sqft": "", "agent": "", "brokerage": "", 
        "mls_source": "", "mls_number": "", "description": data.get("description", "")
    }

    if data.get("address") and data.get("city"):
        meta["address"] = f"{data.get('address')}, {data.get('city')}, {data.get('state', '')}"
    if data.get("price"): meta["price"] = f"{data.get('price'):,}"
    if data.get("bedrooms"): meta["beds"] = str(data.get("bedrooms"))
    if data.get("bathrooms"): meta["baths"] = str(data.get("bathrooms"))
    
    # Square footage extraction logic
    sqft_val = data.get("living_area_sqft") or data.get("livingArea") or data.get("livingAreaValue")
    if sqft_val:
        meta["sqft"] = f"{int(sqft_val):,}"

    # Extract images
    image_urls = data.get("image_urls", [])
    unique_urls = list(dict.fromkeys(image_urls))
    
    # Clear old photos
    for f in os.listdir(INPUT_FOLDER):
        try: os.remove(os.path.join(INPUT_FOLDER, f))
        except: pass

    downloaded_paths = []
    for i, img_url in enumerate(unique_urls[:15]):
        try:
            res = requests.get(img_url, timeout=10)
            res.raise_for_status()
            file_path = os.path.join(INPUT_FOLDER, f"{zpid}_{i:02d}.jpg") 
            with open(file_path, 'wb') as f:
                f.write(res.content)
            downloaded_paths.append(file_path)
        except Exception as e:
            print(f"Failed to download image: {e}")
            
    return meta, downloaded_paths

# --- NEW ENHANCED BATCH ANALYSIS ---

def analyze_scenes_batch(image_paths: List[str], language: str, meta_data: dict):
    """Uses Gemini 2.0 Flash to see all images at once and create a flowing story."""
    client = genai.Client(api_key=API_KEY)
    
    # Load all images into memory
    images = [PIL.Image.open(path) for path in image_paths]
    
    prompt = f"""
You are an award-winning real estate video director and compliant property marketing specialist.

Analyze ALL provided images AND the MLS property description below to understand the home:

ADDRESS:
{meta_data.get('address')}

MLS DESCRIPTION (SOURCE OF TRUTH):
\"\"\"
{meta_data.get('description')}
\"\"\"

GOAL:
Create a cinematic walkthrough that feels like a buyer experiencing the home in real time—not just viewing it.

The captions should guide the viewer naturally from space to space, like an in-person showing.

--------------------------------------------------
TRUTH & COMPLIANCE RULES (CRITICAL):
- ONLY mention features explicitly stated in the MLS description OR clearly visible in images
- If a feature is not stated AND not clearly visible, DO NOT mention it
- NEVER assume materials (e.g., hardwood, quartz, marble) unless explicitly confirmed
- NEVER infer upgrades, condition, or quality not stated
- Stay compliant with Fair Housing laws:
  - Do NOT reference people, demographics, families, income, religion, or protected classes
  - Do NOT use exclusionary or biased language
- Avoid prohibited terms: "perfect", "best", "guaranteed", "dream home"

--------------------------------------------------
VOICE & TONE (CRITICAL):
- Write like you're guiding a buyer in person
- Use inviting, experiential language (what can they do/feel here)
- Use natural second-person phrasing when appropriate (e.g., "step into", "unwind in")
- Focus on lifestyle, not just features

GOOD EXAMPLES:
- "Step into the kitchen—cook and gather"
- "Relax here after a long day"
- "Enjoy mornings filled with natural light"
- "Host friends in this open living space"

BAD EXAMPLES:
- "This home features a kitchen"
- "Spacious living room with windows"
- "Beautiful hardwood flooring throughout"

STYLE RULES:
- Use subtle action verbs: step into, unwind, gather, enjoy, relax, host
- Avoid robotic or repetitive phrasing
- Do NOT start consecutive captions with the same word
- Keep tone natural—not overly poetic or exaggerated
- If referencing MLS features, blend into lifestyle:
  Example: "updated kitchen" → "Cook with ease in the updated kitchen"

--------------------------------------------------
STRUCTURE & FLOW:
- Follow a logical walkthrough:
  exterior → entry → living → kitchen → bedrooms → bathrooms → basement → outdoor
- Each caption must connect naturally to the previous one
- No random jumps between spaces

EMOTIONAL FLOW:
- Beginning: welcoming (arrival, curb appeal)
- Middle: connection (living spaces, kitchen, gathering)
- End: relaxation (bedrooms, backyard, comfort)

FEATURE PRIORITY:
- Prioritize features explicitly mentioned in MLS description
- Use images to support flow and context, not to invent details

--------------------------------------------------
VISUAL DIRECTION:
- Exterior shots → "drone", "slow aerial", "cinematic pan"
- Interior wide shots → "slow dolly", "parallax", "push-in"
- Detail shots → "macro", "focus pull"

Choose effects that match the scene naturally.

--------------------------------------------------
STRICT RULES:
- MAX 14 words per caption
- Language: {language}

--------------------------------------------------
OUTPUT FORMAT (STRICT JSON ARRAY):
Return ONE JSON array with {len(images)} objects.

Each object must include:
- "image_index": integer
- "room_type": string
- "caption": string (max 14 words)
- "effect": string

--------------------------------------------------
FINAL CHECK (MANDATORY BEFORE OUTPUT):
- Remove any feature not supported by MLS description or image
- Ensure captions feel natural and human (not robotic)
- Ensure compliance with Fair Housing and advertising standards
- Ensure smooth narrative flow from first to last caption
"""

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=[prompt] + images,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VideoScript,
                temperature=0.3
            )
        )
        data = json.loads(response.text)
        return data.get("scenes", [])
    except Exception as e:
        print(f"Gemini Batch Error: {e}")
        return []

def generate_fb_post_content(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    prompt = f"""
    Generate a compelling Facebook post for this property in {language}.
    Address: {meta.get('address')}
    Description: {meta.get('description', '')}
    Include emojis, a strong headline, and standard contact info (708-314-0477).
    """
    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text
    except Exception:
        return "Check out our new listing! Contact us at 708-314-0477 for details."