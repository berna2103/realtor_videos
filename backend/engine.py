import os
import asyncio
import sys
import hashlib
import base64
import glob
import io
import requests
import random
import math
import numpy as np
import re
import json
import soundfile as sf
from kokoro import KPipeline

from PIL import Image, ImageDraw, ImageFont
from proglog import ProgressBarLogger

from moviepy import (
    ImageClip, VideoClip, CompositeVideoClip, concatenate_videoclips, 
    AudioFileClip, CompositeAudioClip, concatenate_audioclips, 
)

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

pipelines = {
    'a': KPipeline(lang_code='a'),
    'e': KPipeline(lang_code='e')
}

IG_WIDTH = 1080
IG_HEIGHT = 1350

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- HELPERS ---
def normalize_tts_text(text):
    if not text: return text
    text = re.sub(r'[\r\n]+', '. ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\bsqft\b', 'square feet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bft\.?\b', 'feet', text, flags=re.IGNORECASE)
    text = re.sub(r'\bbd\.?\b', 'bedroom', text, flags=re.IGNORECASE)
    text = re.sub(r'\bba\.?\b', 'bathroom', text, flags=re.IGNORECASE)
    return text.strip()

def set_progress(job_id, percent):
    if 'main' in sys.modules:
        main_mod = sys.modules['main']
        if hasattr(main_mod, 'jobs') and job_id in main_mod.jobs:
            main_mod.jobs[job_id]['progress'] = percent

class JobRenderLogger(ProgressBarLogger):
    def __init__(self, job_id, start_progress=50, end_progress=98):
        super().__init__()
        self.job_id = job_id
        self.start_progress = start_progress
        self.end_progress = end_progress

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            bar_data = self.bars.get(bar)
            if bar_data and bar_data.get('total'):
                total = bar_data['total']
                if total > 0:
                    fraction = value / total
                    current_prog = int(self.start_progress + (self.end_progress - self.start_progress) * fraction)
                    set_progress(self.job_id, current_prog)

BED_PATHS = [[(0.1, 0.2), (0.1, 0.8)], [(0.1, 0.6), (0.9, 0.6), (0.9, 0.8)], [(0.2, 0.6), (0.2, 0.4), (0.5, 0.4), (0.5, 0.6)]]
BATH_PATHS = [[(0.1, 0.5), (0.1, 0.8), (0.9, 0.8), (0.9, 0.5), (0.1, 0.5)], [(0.2, 0.8), (0.2, 0.9)], [(0.8, 0.8), (0.8, 0.9)], [(0.8, 0.5), (0.8, 0.1), (0.6, 0.1), (0.6, 0.2)]]
SQFT_PATHS = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)]]
MUSIC_MAP = {"top1": "music/top1.mp3", "top2": "music/top2.mp3", "top3": "music/top3.mp3", "top4": "music/top4.mp3", "top5": "music/top5.mp3"}

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(font_name, size, base_dir):
    fonts_dir = os.path.join(base_dir, 'fonts')
    if font_name and os.path.exists(fonts_dir):
        search_term = str(font_name).split()[0].lower()
        for file in os.listdir(fonts_dir):
            if file.lower().endswith('.ttf') and search_term in file.lower():
                font_path = os.path.join(fonts_dir, file)
                try: return ImageFont.truetype(font_path, int(size))
                except Exception: pass
    return ImageFont.load_default()

def ease_in_out(t, duration):
    p = max(0.0, min(1.0, t / duration))
    return p * p * (3 - 2 * p)

def draw_text_with_shadow(draw, pos, text, font, fill_color, shadow_color=(0, 0, 0, 200), offset=2):
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill_color)

def create_gradient_scrim(width, height, max_alpha=180):
    mask = Image.new('L', (1, height), color=0)
    for y in range(height):
        base_alpha = max_alpha * 0.5
        gradient_alpha = max_alpha * ((y / height) ** 1.5)
        alpha = int(min(base_alpha + gradient_alpha, max_alpha))
        mask.putpixel((0, y), alpha)
    mask = mask.resize((width, height))
    scrim = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    black = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    scrim.paste(black, (0, 0), mask=mask)
    return scrim

def draw_unit_icon(draw, paths, center_x, center_y, scale_factor, color):
    for path in paths:
        scaled_points = [(p[0] * scale_factor + center_x - (scale_factor/2), 
                          p[1] * scale_factor + center_y - (scale_factor/2)) for p in path]
        draw.line(scaled_points, fill=color, width=2)

def format_address(full_addr, hide_exact=False):
    if not hide_exact or not full_addr:
        return full_addr
    try:
        parts = [p.strip() for p in full_addr.split(',')]
        if len(parts) >= 3:
            city = parts[-2]
            state_zip = parts[-1].split()
            state = state_zip[0] if state_zip else ""
            return f"{city}, {state}"
    except Exception:
        pass
    return full_addr

def get_dynamic_cta(status_val, language, custom_cta_val=None):
    if custom_cta_val and custom_cta_val.strip(): 
        return custom_cta_val.strip().upper()
    cta_map = {
        "English": {
            "Just Sold": "VIEW OUR SUCCESS STORIES!",
            "Under Contract": "JOIN BACKUP LIST!",
            "Coming Soon": "GET EARLY ACCESS!",
            "Open House": "VISIT US THIS WEEKEND!",
            "Price Reduced": "NEW PRICE - SEE IT TODAY!",
            "Just Listed": "BE THE FIRST TO SEE IT!",
            "Home For Sale": "SCHEDULE A SHOWING!",
            "default": "SCHEDULE A SHOWING!"
        }
    }
    lang_dict = cta_map.get(language, cta_map["English"])
    return lang_dict.get(status_val, lang_dict["default"])


# --- INSTAGRAM CAROUSEL GENERATORS (100% VECTOR NO EXTERNAL LOGOS NEEDED) ---

def draw_vector_map_pin(draw, x, y, scale=1.0):
    """Draws a beautiful, crisp vector map pin using pure math."""
    w = int(45 * scale)
    h = int(65 * scale)
    
    # Drop Shadow
    draw.ellipse((x - w//3, y - w//8, x + w//3, y + w//8), fill=(0, 0, 0, 140))
    
    # Pin Geometry
    head_radius = w // 2
    cy = y - h + head_radius
    
    # Red Pin Body (Triangle pointing down)
    draw.polygon([
        (x - head_radius * 0.85, cy + head_radius * 0.4), 
        (x + head_radius * 0.85, cy + head_radius * 0.4), 
        (x, y)
    ], fill=(225, 29, 72, 255))
    
    # Red Pin Head (Circle)
    draw.ellipse((x - head_radius, cy - head_radius, x + head_radius, cy + head_radius), fill=(225, 29, 72, 255))
    
    # White Inner Cutout
    dot_radius = int(head_radius * 0.35)
    draw.ellipse((x - dot_radius, cy - dot_radius, x + dot_radius, cy + dot_radius), fill=(255, 255, 255, 255))

def draw_vector_eho_logo(draw, get_font_func, x, y, size=50, base_dir=""):
    """Draws the Equal Housing Opportunity house logo perfectly using vectors."""
    color = (150, 150, 150, 255) # Light gray
    thickness = max(2, int(size * 0.08))
    
    # House Roof
    peak = (x + size//2, y)
    left = (x, y + size*0.45)
    right = (x + size, y + size*0.45)
    draw.line([left, peak, right], fill=color, width=thickness)
    
    # House Body
    body_left = x + size * 0.15
    body_right = x + size * 0.85
    body_bottom = y + size
    draw.line([(body_left, y + size*0.35), (body_left, body_bottom), (body_right, body_bottom), (body_right, y + size*0.35)], fill=color, width=thickness)
    
    # Equals Sign (=)
    eq_left = x + size * 0.35
    eq_right = x + size * 0.65
    draw.line([(eq_left, y + size*0.65), (eq_right, y + size*0.65)], fill=color, width=thickness)
    draw.line([(eq_left, y + size*0.80), (eq_right, y + size*0.80)], fill=color, width=thickness)
    
    # Text
    font = get_font_func("Montserrat", int(size * 0.35), base_dir)
    draw.text((x + size + 15, y + size*0.1), "EQUAL HOUSING", font=font, fill=color)
    draw.text((x + size + 15, y + size*0.5), "OPPORTUNITY", font=font, fill=color)

def create_circular_avatar(img_path, size):
    try:
        img = Image.open(img_path).convert("RGBA")
        min_dim = min(img.width, img.height)
        left = (img.width - min_dim)/2
        top = (img.height - min_dim)/2
        img = img.crop((left, top, left+min_dim, top+min_dim))
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        out = Image.new('RGBA', (size, size), (0,0,0,0))
        out.paste(img, (0,0), mask=mask)
        draw_out = ImageDraw.Draw(out)
        draw_out.ellipse((2, 2, size-2, size-2), outline=(255,255,255,255), width=8)
        return out
    except Exception as e:
        print(f"Avatar error: {e}")
        return None

def resize_and_crop(img_path):
    img = Image.open(img_path).convert("RGBA")
    img_aspect = img.width / img.height
    target_aspect = IG_WIDTH / IG_HEIGHT
    if img_aspect > target_aspect:
        new_height = IG_HEIGHT
        new_width = int(new_height * img_aspect)
    else:
        new_width = IG_WIDTH
        new_height = int(new_width / img_aspect)
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = (new_width - IG_WIDTH) / 2
    top = (new_height - IG_HEIGHT) / 2
    return img.crop((left, top, left + IG_WIDTH, top + IG_HEIGHT))

def create_carousel_cover(img_path, location, specs, tagline, price, base_dir):
    base_img = resize_and_crop(img_path)
    
    # 1. Custom Scrim: Only covers the bottom 1/3rd of the image
    scrim = Image.new('RGBA', (IG_WIDTH, IG_HEIGHT), (0,0,0,0))
    scrim_draw = ImageDraw.Draw(scrim)
    
    start_y = int(IG_HEIGHT * 0.66)
    for y in range(start_y, IG_HEIGHT):
        progress = (y - start_y) / (IG_HEIGHT - start_y)
        alpha = int(220 * (progress ** 1.5))
        scrim_draw.line([(0, y), (IG_WIDTH, y)], fill=(0, 0, 0, alpha))
        
    base_img.paste(scrim, (0, 0), scrim)
    
    draw = ImageDraw.Draw(base_img)
    
    font_location = get_font("Playfair-Bold", 140, base_dir) 
    font_tagline = get_font("Montserrat-Bold", 40, base_dir)      
    font_specs = get_font("Montserrat-Bold", 45, base_dir)        
    font_price = get_font("Montserrat-Bold", 85, base_dir)        
    
    y_specs = IG_HEIGHT - 120
    y_location = y_specs - 150
    y_tagline = y_location - 60
    
    def draw_centered(text, font, y, fill=(255, 255, 255, 255), stroke=1):
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (IG_WIDTH - (bbox[2] - bbox[0])) / 2
        draw.text((x, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=fill)
    
    # 2. Draw Top Price 
    if price:
        p_str = f"${int(float(str(price).replace('$', '').replace(',', ''))):,}"
        draw_centered(p_str, font_price, 80, stroke=2)
    
    # 3. Draw Bottom Details
    loc_text = location.upper()
    bbox_loc = draw.textbbox((0, 0), loc_text, font=font_location)
    loc_w = bbox_loc[2] - bbox_loc[0]
    loc_h = bbox_loc[3] - bbox_loc[1]
    
    pin_size = 85
    total_w = pin_size + 25 + loc_w
    start_x = (IG_WIDTH - total_w) / 2
    
    # FIX: Pushed the pin down. We calculate 90% of the text height so the tip rests perfectly on the baseline.
    pin_y = y_location + int(loc_h * 0.90) 
    draw_vector_map_pin(draw, start_x + (pin_size//2), pin_y, scale=1.2)
    
    # Flat Location Text
    text_x = start_x + pin_size + 25
    draw.text((text_x, y_location), loc_text, font=font_location, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(255, 255, 255, 255))
    
    draw_centered(specs.upper(), font_specs, y_specs, stroke=1)
    draw_centered(tagline.upper(), font_tagline, y_tagline, stroke=1)
    
    return base_img.convert("RGB")
def create_carousel_end_card(agent_name, brokerage, phone, social_handle, base_dir, headshot_path=None, logo_path=None):
    img = Image.new('RGB', (IG_WIDTH, IG_HEIGHT), (25, 27, 30))
    draw = ImageDraw.Draw(img)
    
    font_xl = get_font("Playfair-Bold", 100, base_dir)
    font_large = get_font("Montserrat", 50, base_dir)
    font_medium = get_font("Montserrat", 40, base_dir)
    font_small = get_font("Montserrat", 28, base_dir)
    font_tiny = get_font("Montserrat", 20, base_dir)
    
    y = 120
    
    text_ready = "Ready to Tour?"
    bbox_r = draw.textbbox((0, 0), text_ready, font=font_xl)
    x_r = (IG_WIDTH - (bbox_r[2] - bbox_r[0])) / 2
    draw.text((x_r, y), text_ready, font=font_xl, fill=(255, 255, 255))
    y += 180
    
    if headshot_path and os.path.exists(headshot_path):
        avatar_size = 400
        avatar = create_circular_avatar(headshot_path, avatar_size)
        if avatar:
            ax = int((IG_WIDTH - avatar_size) / 2)
            img.paste(avatar, (ax, int(y)), mask=avatar)
            y += avatar_size + 50
    else:
        y += 100 
    
    def draw_c(text, font, y_pos, color):
        if not text: return y_pos
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (IG_WIDTH - (bbox[2] - bbox[0])) / 2
        draw.text((x, y_pos), text, font=font, fill=color)
        return y_pos + (bbox[3] - bbox[1]) + 20

    y = draw_c(agent_name.upper() if agent_name else "AGENT NAME", font_large, y, (255, 255, 255))
    y = draw_c("Licensed Real Estate Broker (IL)", font_small, y, (150, 150, 150))
    y += 20
    
    if phone: y = draw_c(phone, font_medium, y, (200, 200, 200))
    if social_handle: y = draw_c(f"IG: {social_handle}", font_medium, y, (200, 200, 200))
    y += 50
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((400, 140), Image.Resampling.LANCZOS)
            lx = int((IG_WIDTH - logo_img.width) / 2)
            img.paste(logo_img, (lx, int(y)), mask=logo_img)
            y += logo_img.height + 30
        except: pass
        
    y = draw_c(brokerage.upper() if brokerage else "BROKERAGE NAME", font_medium, y, (255, 255, 255))
    
    # 5. Programmatic Vector EHO Logo & MLS Compliance Footer (FIXED TYPO HERE)
    footer_y = IG_HEIGHT - 130
    draw_vector_eho_logo(draw, get_font, (IG_WIDTH//2) - 130, footer_y, size=45, base_dir=base_dir)
    
    mls_text = "REALTOR® | Information deemed reliable but not guaranteed."
    bbox_m = draw.textbbox((0, 0), mls_text, font=font_tiny)
    draw.text(((IG_WIDTH - (bbox_m[2] - bbox_m[0])) / 2, footer_y + 65), mls_text, font=font_tiny, fill=(100, 100, 100))

    return img
# --- VIDEO GENERATORS ---
def create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status, agent, broker, phone, mls_source, mls_number, theme_color, base_dir, custom_cta=None, logo_path=None, hide_exact_addr=False):
    if not show_details and not show_price: return []
    color_white, color_light_gray = (255, 255, 255, 255), (210, 210, 210, 255)
    color_pill_fill, color_pill_outline = (25, 25, 25, 140), (255, 255, 255, 40)

    overlay_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    scrim = create_gradient_scrim(tw, th)
    overlay_img.paste(scrim, (0, 0), mask=scrim)
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((int(tw * 0.4), int(th * 0.12)), Image.Resampling.LANCZOS)
            overlay_img.paste(logo_img, ((tw - logo_img.width) // 2, int(th * 0.05)), logo_img) 
        except Exception as e:
            pass

    draw = ImageDraw.Draw(overlay_img)
    
    y_status = int(th * 0.22) if logo_path else int(th * 0.20)
    y_price, y_pill, y_addr, y_agent, y_cta = int(th * 0.32), int(th * 0.55), int(th * 0.64), int(th * 0.71), int(th * 0.78)
    status_font_size = int(th * 0.080)
    f_status = get_font(font_choice, status_font_size, base_dir)
    f_price = get_font(font_choice, int(th * 0.050), base_dir)
    f_pill = get_font(font_choice, int(th * 0.022), base_dir)
    f_addr = get_font(font_choice, int(th * 0.024), base_dir)
    f_agent = get_font(font_choice, int(th * 0.028), base_dir) 
    f_cta = get_font(font_choice, int(th * 0.035), base_dir)   

    if status:
        bbox = draw.textbbox((0, 0), status.strip(), font=f_status)
        draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, y_status), status.strip(), f_status, color_white)

    if show_price and price:
        p_str = f"${int(float(str(price).replace('$', '').replace(',', ''))):,}"
        bbox = draw.textbbox((0, 0), p_str, font=f_price)
        draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, y_price), p_str, f_price, color_white)

    if show_details:
        details = []
        if beds: details.append(('bed', str(beds) + " beds"))
        if baths: details.append(('bath', str(baths) + " baths"))
        if sqft: details.append(('sqft', str(sqft) + " Sqft."))
        if details:
            pill_h, icon_draw_scale = int(th * 0.06), int(th * 0.06 * 0.4)
            gap_icon_text, gap_items, ext_padding = int(tw * 0.015), int(tw * 0.04), int(tw * 0.06)
            blocks_data, total_content_width = [], 0
            for icon_type, txt_val in details:
                txt_w = draw.textbbox((0, 0), txt_val, font=f_pill)[2]
                block_w = icon_draw_scale + gap_icon_text + txt_w
                blocks_data.append((icon_type, txt_val, block_w))
                total_content_width += block_w
            pill_w = total_content_width + (len(details) - 1) * gap_items + (ext_padding * 2)
            px, py = (tw - pill_w) // 2, y_pill
            draw.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=pill_h // 2, fill=color_pill_fill, outline=color_pill_outline, width=2)
            curr_x, icon_center_y = px + ext_padding, py + (pill_h // 2)
            for icon_type, txt_val, block_w in blocks_data:
                paths = BED_PATHS if icon_type == 'bed' else BATH_PATHS if icon_type == 'bath' else SQFT_PATHS
                draw_unit_icon(draw, paths, curr_x + (icon_draw_scale // 2), icon_center_y, icon_draw_scale, color_light_gray)
                curr_x += icon_draw_scale + gap_icon_text
                txt_bbox = draw.textbbox((0, 0), txt_val, font=f_pill)
                draw.text((curr_x, py + (pill_h - (txt_bbox[3] - txt_bbox[1])) // 2 - int(th * 0.005)), txt_val, font=f_pill, fill=color_light_gray)
                curr_x += (block_w - icon_draw_scale - gap_icon_text) + gap_items

    display_addr = format_address(addr, hide_exact_addr)
    if display_addr:
        bbox = draw.textbbox((0, 0), display_addr, font=f_addr)
        draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, y_addr), display_addr, f_addr, color_light_gray)

    if phone:
        txt = f"Agent Contact: {phone}"
        bbox = draw.textbbox((0, 0), txt, font=f_agent)
        draw_text_with_shadow(draw, ((tw - (bbox[2] - bbox[0])) // 2, y_agent), txt, f_agent, (255, 255, 255, 255))

    cta_text = get_dynamic_cta(status, lang, custom_cta)
    bbox = draw.textbbox((0, 0), cta_text, font=f_cta)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x_pos = (tw - text_w) // 2
    pad_x, pad_y = int(tw * 0.04), int(th * 0.015)
    
    draw.rounded_rectangle([x_pos - pad_x, y_cta - pad_y, x_pos + text_w + pad_x, y_cta + text_h + pad_y], radius=int(th * 0.015), fill=theme_color if theme_color else (220, 50, 50, 255))
    draw_text_with_shadow(draw, (x_pos, y_cta - bbox[1]), cta_text, f_cta, color_white)

    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    overlay_img.save(temp)
    return [ImageClip(temp).with_duration(dur)]

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None, theme_color="#552448"):
    if not text or not timings: return []
    text = normalize_tts_text(text)
    rgb_highlight = hex_to_rgb(theme_color) + (255,)
    font = get_font(font_choice, int(target_h * 0.045), base_dir)
    words = str(text).upper().strip().split()
    y_pos = int(target_h * 0.85) 
    
    matched_words = []
    t_idx = 0
    for w_idx, word_text in enumerate(words):
        clean_visual = "".join(c for c in word_text.lower() if c.isalnum())
        if not clean_visual: continue
        s_time, e_time = None, None
        spoken_acc = ""
        while t_idx < len(timings):
            ts, te, t_word = timings[t_idx]
            if s_time is None: s_time = ts
            e_time = te
            spoken_acc += "".join(c for c in t_word.lower() if c.isalnum())
            t_idx += 1
            if clean_visual in spoken_acc or spoken_acc in clean_visual: break
        if s_time is not None and s_time < duration:
            matched_words.append({"idx": w_idx, "text": word_text, "start": s_time, "end": e_time})

    layers = []
    for i in range(len(matched_words)):
        curr = matched_words[i]
        adjusted_end = min(curr['end'] + 0.05, matched_words[i+1]['start'] if i + 1 < len(matched_words) else duration, duration)
        if curr['start'] >= adjusted_end: continue

        hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
        draw = ImageDraw.Draw(hl_img)
        bbox = draw.textbbox((0, 0), curr['text'], font=font)
        draw_text_with_shadow(draw, ((target_w - (bbox[2] - bbox[0])) // 2, y_pos), curr['text'], font, rgb_highlight)
        
        hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_word_{curr['idx']}.png")
        hl_img.save(hl_temp)
        layers.append(ImageClip(hl_temp).with_start(curr['start']).with_duration(adjusted_end - curr['start']))
        
    return layers

def create_video_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir, is_own_listing, status, custom_cta=None, logo_path=None):
    img_bg = Image.new('RGB', (target_w, target_h), (10, 10, 12)) 
    ImageDraw.Draw(img_bg).rectangle([0, 0, target_w, 6], fill=hex_to_rgb(theme_color))

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((int(target_w * 0.4), int(target_h * 0.15)), Image.Resampling.LANCZOS)
            img_bg.paste(logo_img, ((target_w - logo_img.width) // 2, int(target_h * 0.08)), logo_img) 
        except: pass

    temp_bg = os.path.join(base_dir, f"temp_end_bg_{job_id}.png") 
    img_bg.save(temp_bg)
    
    def _text_clip(text, base_size, color, y, start, job_id, name):
        if not text: return None
        font = get_font(font_choice, base_size, base_dir)
        txt_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text(((target_w - (bbox[2]-bbox[0])) / 2, y), text, font=font, fill=color)
        path = os.path.join(base_dir, f"temp_end_txt_{name}_{job_id}.png") 
        txt_img.save(path)
        return ImageClip(path).with_start(start).with_duration(max(0.1, duration - start))

    layers, curr_y, fade = [ImageClip(temp_bg).with_duration(duration)], int(target_h * 0.25), 0.5
    courtesy_text = "Presentado por:" if language == "Spanish" and is_own_listing else "Presented by:" if is_own_listing else "Cortesía de:" if language == "Spanish" else "Listing Courtesy of:"
    
    for t, base_sz, c, n in [
        (get_dynamic_cta(status, language, custom_cta), int(target_h * 0.045), (160, 160, 170), "cta"), 
        (phone, int(target_h * 0.065), (255, 255, 255), "ph"), 
        (website, int(target_h * 0.035), (200, 200, 255), "web"), 
        (courtesy_text, int(target_h * 0.020), (180, 180, 190), "courtesy"), 
        (agent_name.upper(), int(target_h * 0.030), (255, 255, 255), "ag"), 
        (brokerage, int(target_h * 0.022), (140, 140, 150), "br")
    ]:
        clip = _text_clip(t, base_sz, c, curr_y, fade, job_id, n)
        if clip: layers.append(clip)
        curr_y += 80 if n == "cta" else 110 if n == "ph" else 70 if n == "web" else 30 if n == "courtesy" else 50
        fade += 0.6
    
    mls_clip = _text_clip(f"Source: {mls_source} | MLS# {mls_number}" if (mls_source or mls_number) else "", int(target_h * 0.016), (80, 80, 90), int(target_h * 0.88), 2.5, job_id, "mls")
    if mls_clip: layers.append(mls_clip)
    return CompositeVideoClip(layers, size=(target_w, target_h)).with_duration(duration)

async def generate_kokoro_audio_async(text, voice, output_path):
    def _run_kokoro():
        timings = []
        audio_chunks = []
        clean_text = normalize_tts_text(text)
        generator = pipelines.get(voice[0], pipelines['a'])(clean_text, voice=voice, speed=1, split_pattern=r'(?<=[.,!?])\s+')
        chunk_offset_seconds = 0.0
        sample_rate = 24000 
        
        for result in generator:
            audio_chunks.append(result.audio)
            current_text, current_start = [], None
            for token in (getattr(result, "tokens", []) or []):
                t_text = getattr(token, "text", "")
                if not t_text: continue
                if current_start is None and getattr(token, "start_ts", None) is not None:
                    current_start = chunk_offset_seconds + float(token.start_ts)
                current_text.append(t_text)
                if getattr(token, "whitespace", ""):
                    word_text = "".join(current_text).strip()
                    if word_text: timings.append((current_start, chunk_offset_seconds + float(token.end_ts) if getattr(token, "end_ts", None) else current_start + 0.5, word_text))
                    current_text, current_start = [], None
            if current_text and current_start is not None:
                word_text = "".join(current_text).strip()
                if word_text: timings.append((current_start, chunk_offset_seconds + float(getattr(token, "end_ts")) if getattr(token, "end_ts", None) else current_start + 0.5, word_text))
            chunk_offset_seconds += len(result.audio) / sample_rate
            
        if audio_chunks: sf.write(output_path, np.concatenate(audio_chunks), sample_rate)
        return timings
    return await asyncio.to_thread(_run_kokoro)

def create_animated_clip(job_id, i, scene_data, tw, th, is_first, addr, price, beds, baths, sqft, lang, font_choice, show_price, show_details, voice_model, status_choice, agent_name, brokerage, phone, mls_source, mls_number, target_slide_dur, timing_mode, theme_color, logo_path, base_dir, vo_data=None, custom_cta=None, show_captions=True):
    dur = target_slide_dur
    vo_clip, vo_timings = None, None
    
    if vo_data:
        try:
            vo_clip = AudioFileClip(vo_data["path"])
            vo_timings = vo_data["timings"]
            dur = max(target_slide_dur, vo_clip.duration + 0.3)
        except: pass

    img_path = scene_data['image_path']
    if not os.path.exists(img_path) and scene_data.get('image_url', '').startswith('http'):
        try:
            r = requests.get(scene_data['image_url'], timeout=15)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, 'wb') as f: f.write(r.content)
        except: pass

    effect = str(scene_data.get('effect', 'auto')).strip().lower()
    if effect == "auto" or not effect: effect = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left", "pan_up", "pan_down", "pan_up_left", "pan_down_right", "drone_push", "drone_pull", "luxury_breathe", "3d_pan_right", "3d_pan_left"])

    clip = ImageClip(img_path)
    clip = clip.resized(height=th * 1.35) if (clip.w / clip.h) > (tw / th) else clip.resized(width=tw * 1.35)
    base_frame = clip.get_frame(0)
    h_base, w_base, _ = base_frame.shape
    base_pil = Image.fromarray(base_frame)

    def make_frame(t):
        progress = ease_in_out(t, dur)
        if effect == "pan_right": return base_frame[int((h_base - th) / 2):int((h_base - th) / 2)+th, int((w_base - tw) * progress):int((w_base - tw) * progress)+tw]
        elif effect == "pan_left": return base_frame[int((h_base - th) / 2):int((h_base - th) / 2)+th, int((w_base - tw) * (1 - progress)):int((w_base - tw) * (1 - progress))+tw]
        elif effect == "pan_up": return base_frame[int((h_base - th) * (1 - progress)):int((h_base - th) * (1 - progress))+th, int((w_base - tw) / 2):int((w_base - tw) / 2)+tw]
        elif effect == "pan_down": return base_frame[int((h_base - th) * progress):int((h_base - th) * progress)+th, int((w_base - tw) / 2):int((w_base - tw) / 2)+tw]
        elif effect == "pan_up_left": return base_frame[int((h_base - th) * (1 - progress)):int((h_base - th) * (1 - progress))+th, int((w_base - tw) * (1 - progress)):int((w_base - tw) * (1 - progress))+tw]
        elif effect == "pan_down_right": return base_frame[int((h_base - th) * progress):int((h_base - th) * progress)+th, int((w_base - tw) * progress):int((w_base - tw) * progress)+tw]
        elif effect == "3d_pan_right":
            x_offset, y_offset, tilt = (w_base - tw) * progress, (h_base - th) / 2, int(th * 0.08)
            left_tilt, right_tilt = tilt * progress, tilt * (1 - progress)
            return np.array(base_pil.transform((tw, th), Image.QUAD, (x_offset, y_offset - left_tilt, x_offset, y_offset + th + left_tilt, x_offset + tw, y_offset + th + right_tilt, x_offset + tw, y_offset - right_tilt), resample=Image.Resampling.BICUBIC))
        elif effect == "3d_pan_left":
            x_offset, y_offset, tilt = (w_base - tw) * (1 - progress), (h_base - th) / 2, int(th * 0.08)
            left_tilt, right_tilt = tilt * (1 - progress), tilt * progress
            return np.array(base_pil.transform((tw, th), Image.QUAD, (x_offset, y_offset - left_tilt, x_offset, y_offset + th + left_tilt, x_offset + tw, y_offset + th + right_tilt, x_offset + tw, y_offset - right_tilt), resample=Image.Resampling.BICUBIC))
        elif effect == "drone_push":
            zoom = 1.05 + (0.10 * progress) 
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).rotate(-1.5 + (3.0 * progress), resample=Image.Resampling.BICUBIC).resize((tw, th), Image.Resampling.LANCZOS))
        elif effect == "drone_pull":
            zoom = 1.15 - (0.10 * progress) 
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).rotate(1.5 - (3.0 * progress), resample=Image.Resampling.BICUBIC).resize((tw, th), Image.Resampling.LANCZOS))
        elif effect == "luxury_breathe":
            zoom = 1.0 + (0.12 * math.sin(progress * (math.pi / 2)))
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))
        elif effect == "zoom_out":
            zoom = 1.15 - (0.15 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))
        else: 
            zoom = 1.0 + (0.15 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x, y = int((w_base - new_w) / 2), int((h_base - new_h) / 2)
            return np.array(Image.fromarray(base_frame[y:y+new_h, x:x+new_w]).resize((tw, th), Image.Resampling.LANCZOS))

    layers = [VideoClip(make_frame, duration=dur)]

    if is_first:
        layers.extend(create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status_choice, agent_name, brokerage, phone, mls_source, mls_number, theme_color, base_dir, custom_cta=custom_cta, logo_path=logo_path))
    elif show_captions:
        layers.extend(create_glass_caption(job_id, scene_data.get('caption', ''), dur, tw, th, font_choice, base_dir, vo_timings, theme_color))
        
    final = CompositeVideoClip(layers, size=(tw, th)).with_duration(dur)
    if vo_clip: final = final.with_audio(vo_clip)
    return final

async def render_cinematic_video(job_id, req, output_path, base_dir):
    set_progress(job_id, 2)
    clips, final = [], None
    req_dict = req if isinstance(req, dict) else req.model_dump()
    meta, scenes = req_dict.get('meta', {}), req_dict.get('scenes', [])
    logo_file_path = None
    actual_custom_cta = req_dict.get('custom_cta') or meta.get('custom_cta')
    status_choice = req_dict.get('status_choice', 'Just Listed')

    VOICE_MAP = {
        "English-US-Bella": "af_bella",
        "English-US-Heart": "af_heart",
        "English-US-Fenrir": "am_fenrir",
        "English-US-Michael": "am_michael",
        "Spanish-Dora": "ef_dora",
        "Spanish-Alex": "em_alex"
    }

    try:
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        set_progress(job_id, 5)

        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)
        requested_voice = req_dict.get('voice', 'English-US-Bella')
        lang = req_dict.get('language', 'English')
        voice_id = VOICE_MAP.get(requested_voice, "af_bella")

        set_progress(job_id, 10)

        vo_tasks, vo_map = [], {}
        enable_voice = req_dict.get('enable_voice', True) 

        if enable_voice:
            for s in scenes:
                if s.get('enable_vo') and s.get('caption'):
                    p = os.path.join(base_dir, f"temp_vo_{job_id}_{s['id']}.wav")
                    vo_tasks.append(generate_kokoro_audio_async(s['caption'], voice_id, p))
                    vo_map[s['id']] = {"path": p}
        
            if vo_tasks:
                set_progress(job_id, 15)
                results = await asyncio.gather(*vo_tasks)
                for sid, res in zip(vo_map.keys(), results):
                    vo_map[sid]["timings"] = res

        set_progress(job_id, 25)

        total_scenes = len(scenes)
        for i, scene in enumerate(scenes):
            clips.append(create_animated_clip(
                job_id, i, scene, tw, th, (i==0), 
                meta.get('address',''), meta.get('price',''), 
                meta.get('beds',''), meta.get('baths',''), meta.get('sqft',''), 
                lang, req_dict.get('font','Montserrat'), 
                req_dict.get('show_price', True), req_dict.get('show_details', True), 
                voice_id, status_choice, meta.get('agent',''), 
                meta.get('brokerage',''), meta.get('phone',''), 
                meta.get('mls_source',''), meta.get('mls_number',''), 
                3.5, 'Auto', req_dict.get('primary_color','#552448'), 
                logo_file_path, base_dir, vo_data=vo_map.get(scene['id']), 
                custom_cta=actual_custom_cta, show_captions=req_dict.get('show_captions', True)   
            ))
            if total_scenes > 0:
                set_progress(job_id, 25 + int(((i + 1) / total_scenes) * 20))

        clips.append(create_video_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), 
            meta.get('phone',''), meta.get('website',''), 5.0, lang, 
            meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Roboto'), req_dict.get('primary_color','#552448'), base_dir, 
            req_dict.get('is_own_listing', True), status=status_choice, 
            custom_cta=actual_custom_cta, logo_path=logo_file_path
        ))

        set_progress(job_id, 48)
        final = concatenate_videoclips(clips)
        
        m_choice = req_dict.get('music')
        if m_choice and m_choice != "none":
            m_file = None
            if m_choice in MUSIC_MAP:
                m_file = os.path.join(base_dir, MUSIC_MAP[m_choice])
            elif m_choice.startswith("http"):
                m_file = os.path.join(base_dir, f"temp_music_{job_id}.mp3")
                try:
                    r = requests.get(m_choice, timeout=15)
                    if r.status_code == 200:
                        with open(m_file, 'wb') as f: 
                            f.write(r.content)
                except requests.RequestException as e:
                    pass

            if m_file and os.path.exists(m_file):
                bg = AudioFileClip(m_file)
                if bg.duration < final.duration: 
                    bg = concatenate_audioclips([bg] * (int(final.duration / bg.duration) + 1))
                bg = bg.with_duration(final.duration).with_volume_scaled(0.08)
                
                if final.audio: final.audio = CompositeAudioClip([bg, final.audio])
                else: final.audio = bg

        set_progress(job_id, 50)
        render_logger = JobRenderLogger(job_id, start_progress=50, end_progress=99)
        final.write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac", 
            threads=4, preset="medium", logger=render_logger, 
            bitrate="8000k", ffmpeg_params=["-movflags", "faststart"]
        )
        return True

    finally:
        for c in clips: 
            try: c.close()
            except: pass
        if final:
            try: final.close()
            except: pass
        for tf in glob.glob(os.path.join(base_dir, f"temp_*{job_id}*")):
            try: os.remove(tf)
            except: pass