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
    for i, img_url in enumerate(unique_urls[:20]):
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
LANGUAGE SETTING (CRITICAL):
- You MUST write all captions in {language}.

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

STYLE RULES:
- Use subtle action verbs: step into, unwind, gather, enjoy, relax, host
- Avoid robotic or repetitive phrasing
- Do NOT start consecutive captions with the same word
- Keep tone natural—not overly poetic or exaggerated

--------------------------------------------------
STRUCTURE & FLOW:
- Follow a logical walkthrough:
  exterior → entry → living → kitchen → bedrooms → bathrooms → basement → outdoor
- Each caption must connect naturally to the previous one
- No random jumps between spaces

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
    
    # Dynamically pull contact info from meta to avoid hardcoding
    phone = meta.get('phone', 'Contact for details')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')
    mls_info = f"{meta.get('mls_source', '')} MLS#: {meta.get('mls_number', '')}"

    prompt = f"""
    Generate a compelling Facebook post for this property in {language}.
    Address: {meta.get('address')}
    Description: {meta.get('description', '')}
    
    Include emojis, a strong headline, and the following contact details:
    Phone: {phone}
    Listing Courtesy of: {agent}, {brokerage}
    {mls_info}
    
    Do NOT include any hardcoded locations like "Hyde Park" or "Chicago" unless they are in the address provided.
    """
    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text
    except Exception:
        return f"Check out our new listing at {meta.get('address')}! Contact us at {phone} for details."
    
def generate_fb_post_content(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    
    # Safely extract data from the meta dictionary
    # This prevents the "Chicago" fallback by using the actual scraped address
    address = meta.get('address', 'this stunning new listing')
    price = meta.get('price', '')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')
    phone = meta.get('phone', '') # No more hardcoded 708 number here
    mls_source = meta.get('mls_source', '')
    mls_number = meta.get('mls_number', '')
    description = meta.get('description', '')

    # The prompt now forces the AI to define the "Vibe" based on the Address
    prompt = f"""
    Write a professional, high-energy Facebook real estate post.
    
    STRICT LANGUAGE REQUIREMENT: All content must be written in {language}.
    
    PROPERTY DATA:
    - Address: {address}
    - Price: {price}
    - Details: {description}
    
    CONTACT & BRANDING:
    - Agent Name: {agent}
    - Brokerage: {brokerage}
    - Phone/Text: {phone}
    - Compliance: {mls_source} | MLS# {mls_number}

    POST STRUCTURE:
    1. Hook: Catchy headline based on the city/area found in the Address.
    2. Body: 3 bullet points highlighting the best features from the Details.
    3. Call to Action: Invite them to call or text {phone}.
    4. Sign-off: "Listing Courtesy of: [Agent Name], [Brokerage]" followed by the MLS info.

    RULES:
    - DO NOT mention Chicago, Hyde Park, or Woodlawn unless those names appear in the Address above.
    - Use emojis relevant to the property type.
    - If the language is Spanish, use an inviting, professional tone (e.g., "¡Oportunidad Única!").
    """
    
    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text
    except Exception:
        # Emergency fallback localized to the two main supported languages
        if language == "Spanish":
            return f"¡Nueva propiedad disponible en {address}! Contáctanos al {phone} para más información. Cortesía de {brokerage}."
        return f"New listing available at {address}! Call or text {phone} for more details. Courtesy of {brokerage}."
    
    # client = genai.Client(api_key=API_KEY)
    # prompt = f"""
    # Generate a compelling Facebook post for this property in {language}.
    # Address: {meta.get('address')}
    # Description: {meta.get('description', '')}
    # Include emojis, a strong headline, and standard contact info (708-314-0477).
    # """
    # try:
    #     response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
    #     return response.text
    # except Exception:
    #     return "Check out our new listing! Contact us at 708-314-0477 for details."