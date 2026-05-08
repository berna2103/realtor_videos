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
        "mls_source": "", "mls_number": "", "description": data.get("description", ""),
        "neighborhood_context": data.get("neighborhoodRegion", {}).get("name", "")

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

    lat = data.get("latitude") or data.get("lat")
    lng = data.get("longitude") or data.get("lng")
    
    # Fallback if nested
    if not lat and data.get("location"):
        lat = data.get("location", {}).get("latitude")
        lng = data.get("location", {}).get("longitude")
        
    meta["latitude"] = lat
    meta["longitude"] = lng

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

# def analyze_scenes_batch(image_paths: List[str], language: str, meta_data: dict):
#     """Uses Gemini 2.0 Flash to see all images at once and create a flowing story."""
#     client = genai.Client(api_key=API_KEY)
    
#     # Load all images into memory
#     images = [PIL.Image.open(path) for path in image_paths]
    
#     prompt = f"""
# You are an award-winning real estate video director AND a strict compliance-driven local neighborhood expert.

# Your job is to create a cinematic walkthrough that makes the buyer fall in love with the home first, and the location second.

# STRICT LANGUAGE REQUIREMENT: You must write all captions in {language}.

# --------------------------------------------------
# INPUTS

# ADDRESS:
# {meta_data.get('address')}

# MLS DESCRIPTION (PRIMARY SOURCE OF TRUTH):
# \"\"\"
# {meta_data.get('description')}
# \"\"\"

# NEIGHBORHOOD CONTEXT:
# \"\"\"
# {meta_data.get('neighborhood_context')}
# \"\"\"

# --------------------------------------------------
# THE "ANTI-OBVIOUS" RULE (CRITICAL)

# - NEVER state basic, expected functional features. 
# - Do NOT say "the bathroom has a toilet and shower", "the kitchen has cabinets and an oven", or "the bedroom has a bed and windows". Assume the buyer is intelligent.
# - INSTEAD: Focus on the "vibe", selling points, finishes, natural light, space, or architectural details. 
# - Example Bad: "This bathroom has a mirror and shower."
# - Example Good: "A crisp, spa-like retreat to start your day."
# - Example Bad: "The living room has wood floors and walls."
# - Example Good: "An expansive, sun-drenched gathering space."

# --------------------------------------------------
# THE TWO-ACT NARRATIVE ARC (CRITICAL)

# Your video script MUST follow this exact two-part structure based on the number of images:

# ACT 1: THE HOME (First 60-70% of scenes)
# - Focus strictly on the physical property, interior features, finishes, and layout (following the Anti-Obvious Rule).
# - VISUAL ACCURACY: You must ONLY describe what is clearly visible in the image.

# ACT 2: THE NEIGHBORHOOD EXPERT (Final 30-40% of scenes)
# - If NEIGHBORHOOD CONTEXT is provided, you MUST pivot to selling the location and lifestyle.
# - Speak like a true local expert pitching the area based ONLY on the provided context.
# - EXCEPTION TO VISUAL ACCURACY: During Act 2, you may talk about the neighborhood (e.g., walkability, parks, vibe) even if the current image is a bedroom, backyard, or window view. Connect the home to the location (e.g., "Just steps outside, you'll find...", "Living here puts you minutes from...").
# - If NEIGHBORHOOD CONTEXT is empty, simply finish summarizing the home's best features.

# --------------------------------------------------
# ANTI-HALLUCINATION GUARANTEE (CRITICAL)

# - NEVER invent restaurants, parks, schools, stores, or amenities.
# - NEVER assume materials (e.g., quartz, marble) unless explicitly stated in MLS.
# - If uncertain, OMIT the detail completely.

# --------------------------------------------------
# VISUAL EFFECTS (STRICT)

# You MUST choose ONE effect from this list ONLY for each scene:
# zoom_in, zoom_out, pan_right, pan_left,
# pan_up, pan_down, pan_up_left, pan_down_right,
# drone_push, drone_pull, luxury_breathe,
# 3d_pan_right, 3d_pan_left

# Effect rules:
# - Exterior → drone_push or drone_pull
# - Wide interiors → pan_left / pan_right / zoom_in
# - Detail shots → zoom_in
# - Vertical spaces → pan_up / pan_down
# - Premium feel → luxury_breathe
# - Depth shots → 3d_pan_left / 3d_pan_right

# --------------------------------------------------
# CAPTION RULES (STRICT)

# - Max 14 words per caption.
# - Preferred: 8–12 words.
# - One main idea per caption.
# - No more than ONE "and" per caption.
# - No vague filler words (beautiful, amazing, stunning) unless tied to a visible feature.

# --------------------------------------------------
# OUTPUT FORMAT (STRICT)

# Return ONLY a valid JSON array with {len(images)} objects.

# Each object must contain:
# - "image_index": integer
# - "room_type": string (based on visual inference)
# - "caption": string (max 14 words)
# - "effect": string (must be from allowed list)

# RULES:
# - No explanations
# - No markdown formatting block (e.g. no ```json)
# - Output length MUST equal exactly {len(images)}
# """
#     try:
#         response = client.models.generate_content(
#             model='gemini-2.0-flash', 
#             contents=[prompt] + images,
#             config=types.GenerateContentConfig(
#                 response_mime_type="application/json",
#                 response_schema=VideoScript,
#                 temperature=0.3
#             )
#         )
#         data = json.loads(response.text)
#         return data.get("scenes", [])
#     except Exception as e:
#         print(f"Gemini Batch Error: {e}")
#         return []

def analyze_scenes_batch(image_paths: List[str], language: str, meta_data: dict):
    """Uses Gemini 2.0 Flash to write a cohesive script strictly from text data."""
    client = genai.Client(api_key=API_KEY)
    
    num_scenes = len(image_paths)
    if num_scenes == 0:
        return []
    
    prompt = f"""
You are an award-winning real estate copywriter. Your job is to write a highly engaging, flowing voiceover script for a property video.

STRICT LANGUAGE REQUIREMENT: You must write all captions in {language}.

--------------------------------------------------
INPUT DATA

ADDRESS:
{meta_data.get('address')}

MLS DESCRIPTION:
\"\"\"
{meta_data.get('description')}
\"\"\"

NEIGHBORHOOD CONTEXT:
\"\"\"
{meta_data.get('neighborhood_context')}
\"\"\"

--------------------------------------------------
YOUR TASK

You must write a script broken down into EXACTLY {num_scenes} sequential captions. 
The video will be a slideshow of {num_scenes} photos. You do not know what the photos look like, so write a script that flows naturally as a general property tour.

NARRATIVE ARC:
1. First 40-60% of captions: Sell the home. Highlight the best architectural features, renovations, space, and vibe mentioned in the MLS Description. 
2. Final 50-60% of captions: Pivot to the Neighborhood Context. Sell the location, walkability, nearby amenities, and the lifestyle. 

--------------------------------------------------
COPYWRITING RULES (STRICT)

- NEVER state the obvious (e.g., "This home has a kitchen" or "Here is a bedroom").
- INSTEAD: Focus on emotional hooks, luxury, natural light, and lifestyle (e.g., "A sun-drenched space perfect for entertaining" or "Your private morning retreat").
- NEVER invent amenities, parks, or materials that are not explicitly mentioned in the text inputs.
- Max 14 words per caption. (Preferred: 8–12 words).
- Make it sound like a continuous, flowing commercial.

--------------------------------------------------
OUTPUT FORMAT (STRICT)

Return ONLY a valid JSON array with EXACTLY {num_scenes} objects.

Each object must contain:
- "image_index": integer (Must go in order from 0 to {num_scenes - 1})
- "room_type": string (Make a logical guess of the progression, e.g., "Exterior", "Living Area", "Kitchen", "Primary Suite", "Lifestyle")
- "caption": string (The spoken script line)
- "effect": string (Choose one randomly from: zoom_in, zoom_out, pan_right, pan_left, pan_up, luxury_breathe)

RULES:
- No markdown formatting block (e.g. no ```json)
- Output length MUST equal exactly {num_scenes}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            # Notice we are NO LONGER passing the images array here!
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VideoScript,
                temperature=0.4 # Slightly higher temperature for better creative writing
            )
        )
        data = json.loads(response.text)
        return data.get("scenes", [])
    except Exception as e:
        print(f"Gemini Script Error: {e}")
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