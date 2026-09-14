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

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, "raw_photos")
os.makedirs(INPUT_FOLDER, exist_ok=True)

class SceneAnalysis(BaseModel):
    image_index: int
    room_type: str
    caption: str
    effect: str

class VideoScript(BaseModel):
    scenes: List[SceneAnalysis]

def fetch_zillow_data(url: str):
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
    
    sqft_val = data.get("living_area_sqft") or data.get("livingArea") or data.get("livingAreaValue")
    if sqft_val:
        meta["sqft"] = f"{int(sqft_val):,}"

    lat = data.get("latitude") or data.get("lat")
    lng = data.get("longitude") or data.get("lng")
    
    if not lat and data.get("location"):
        lat = data.get("location", {}).get("latitude")
        lng = data.get("location", {}).get("longitude")
        
    meta["latitude"] = lat
    meta["longitude"] = lng

    image_urls = data.get("image_urls", [])
    unique_urls = list(dict.fromkeys(image_urls))
    
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

def analyze_scenes_batch(image_paths: List[str], language: str, meta_data: dict):
    client = genai.Client(api_key=API_KEY)
    num_scenes = len(image_paths)
    if num_scenes == 0: return []
    
    prompt = f"""
You are an award-winning real estate copywriter. Write a highly engaging, flowing voiceover script for a property video.
STRICT LANGUAGE: {language}.
ADDRESS: {meta_data.get('address')}
MLS DESCRIPTION: {meta_data.get('description')}
NEIGHBORHOOD CONTEXT: {meta_data.get('neighborhood_context')}

Write EXACTLY {num_scenes} sequential captions. 
- Max 14 words per caption.
Return ONLY a valid JSON array with EXACTLY {num_scenes} objects.
Each object must contain: "image_index" (int), "room_type" (str), "caption" (str), "effect" (str - zoom_in, zoom_out, pan_right, pan_left, pan_up, luxury_breathe)
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash', 
            contents=[prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=VideoScript, temperature=0.4)
        )
        data = json.loads(response.text)
        return data.get("scenes", [])
    except Exception as e:
        print(f"Gemini Script Error: {e}")
        return []
    
def generate_fb_post_content(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    address = meta.get('address', 'this stunning new listing')
    price = meta.get('price', '')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')
    phone = meta.get('phone', '') 
    mls_source = meta.get('mls_source', '')
    mls_number = meta.get('mls_number', '')

    prompt = f"""
    Write a professional, high-energy Facebook real estate post in {language}.
    Address: {address} | Price: {price}
    Details: {meta.get('description', '')}
    
    1. Catchy headline based on the city/area.
    2. 3 bullet points highlighting best features.
    3. Call to Action to call/text {phone}.
    4. Sign-off: "Listing Courtesy of: {agent}, {brokerage}" | {mls_source} MLS# {mls_number}
    """
    try:
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
        return response.text
    except Exception:
        return f"New listing available at {address}! Call or text {phone} for more details. Courtesy of {brokerage}."

# --- NEW: INSTAGRAM CAROUSEL CAPTION GENERATOR ---
def generate_ig_caption(meta, language="English"):
    client = genai.Client(api_key=API_KEY)
    address = meta.get('address', 'this stunning new listing')
    price = meta.get('price', '')
    agent = meta.get('agent', '')
    brokerage = meta.get('brokerage', '')

    prompt = f"""
    Write a highly aesthetic Instagram Carousel caption for a real estate listing in {language}.
    Address: {address} | Price: {price}
    Details: {meta.get('description', '')}
    
    STRUCTURE:
    1. A short, aesthetic hook (e.g., "Step inside your new sanctuary ✨" or "Chicago living at its finest 🏙️").
    2. A brief 2-sentence summary of the vibe/interior.
    3. A clear call to action: "👉 Swipe left to take the tour!"
    4. "Link in bio for full details or DM me to schedule a private showing."
    5. Required Compliance Line at the very bottom: "Listed by {agent} | {brokerage} | Licensed in IL"
    6. 5-7 highly relevant real estate hashtags.
    """
    try:
        response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
        return response.text
    except Exception:
        return f"Step inside {address} ✨\n\nSwipe left to take the tour! 👉\n\nDM to schedule a showing.\n\nListed by {agent} | {brokerage} | Licensed in IL"