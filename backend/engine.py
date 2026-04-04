import os
import asyncio
import sys
import hashlib
import base64
import glob
import io
import edge_tts
import numpy as np
import requests
import random
import math

from PIL import Image, ImageDraw, ImageFont
from proglog import ProgressBarLogger

from moviepy import (
    ImageClip, 
    VideoClip,
    CompositeVideoClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeAudioClip,
    concatenate_audioclips, 
)

# Fix for MoviePy 1.0.3 & Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

# --- PROGRESS REPORTING HELPERS ---
def set_progress(job_id, percent):
    """Safely updates the progress in the main thread's jobs dict without circular imports."""
    if 'main' in sys.modules:
        main_mod = sys.modules['main']
        if hasattr(main_mod, 'jobs') and job_id in main_mod.jobs:
            main_mod.jobs[job_id]['progress'] = percent

class JobRenderLogger(ProgressBarLogger):
    """Custom MoviePy Logger to track the frame-by-frame render status."""
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

# --- ICONS & PATHS ---
BED_PATHS = [[(0.1, 0.2), (0.1, 0.8)], [(0.1, 0.6), (0.9, 0.6), (0.9, 0.8)], [(0.2, 0.6), (0.2, 0.4), (0.5, 0.4), (0.5, 0.6)]]
BATH_PATHS = [[(0.1, 0.5), (0.1, 0.8), (0.9, 0.8), (0.9, 0.5), (0.1, 0.5)], [(0.2, 0.8), (0.2, 0.9)], [(0.8, 0.8), (0.8, 0.9)], [(0.8, 0.5), (0.8, 0.1), (0.6, 0.1), (0.6, 0.2)]]
SQFT_PATHS = [[(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8), (0.2, 0.2)]]

MUSIC_MAP = {"Upbeat": "music/Upbeat.mp3", "Luxury": "music/Luxury.mp3", "Motivation": "music/Motivation.mp3"}

# --- HELPER FUNCTIONS ---
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

# --- GLOBAL CTA GENERATOR ---
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
        },
        "Spanish": {
            "Just Sold": "¡MIRA NUESTROS ÉXITOS!",
            "Under Contract": "¡LISTA DE ESPERA!",
            "Coming Soon": "¡ACCESO ANTICIPADO!",
            "Open House": "¡VEN ESTE FIN DE SEMANA!",
            "Price Reduced": "¡NUEVO PRECIO - VISÍTALO HOY!",
            "Just Listed": "¡SÉ EL PRIMERO EN VERLO!",
            "Home For Sale": "¡AGENDA TU CITA!",
            "default": "¡AGENDA TU CITA!"
        }
    }
    lang_dict = cta_map.get(language, cta_map["English"])
    return lang_dict.get(status_val, lang_dict["default"])

def create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status, agent, broker, phone, mls_source, mls_number, theme_color, base_dir, custom_cta=None, logo_path=None):
    if not show_details and not show_price: return []
    color_white, color_light_gray = (255, 255, 255, 255), (210, 210, 210, 255)
    color_pill_fill, color_pill_outline = (25, 25, 25, 140), (255, 255, 255, 40)

    overlay_img = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    scrim = create_gradient_scrim(tw, th)
    overlay_img.paste(scrim, (0, 0), mask=scrim)
    
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_max_w, logo_max_h = int(tw * 0.4), int(th * 0.12)
            logo_img.thumbnail((logo_max_w, logo_max_h), Image.Resampling.LANCZOS)
            lx = (tw - logo_img.width) // 2
            ly = int(th * 0.05) 
            overlay_img.paste(logo_img, (lx, ly), logo_img) 
        except Exception as e:
            print(f"Failed to draw logo: {e}")

    draw = ImageDraw.Draw(overlay_img)
    
    y_status = int(th * 0.22) if logo_path else int(th * 0.20)
    y_price, y_pill, y_addr, y_agent, y_cta = int(th * 0.32), int(th * 0.62), int(th * 0.74), int(th * 0.85), int(th * 0.91)

    status_font_size = int(th * 0.080)
    f_status = get_font(font_choice, status_font_size, base_dir)
    f_price = get_font(font_choice, int(th * 0.050), base_dir)
    f_pill = get_font(font_choice, int(th * 0.022), base_dir)
    f_addr = get_font(font_choice, int(th * 0.024), base_dir)
    f_agent = get_font(font_choice, int(th * 0.028), base_dir) 
    f_cta = get_font(font_choice, int(th * 0.035), base_dir)   

    if status:
        status_text = status.strip()
        max_width = int(tw * 0.90) 
        bbox = draw.textbbox((0, 0), status_text, font=f_status)
        while (bbox[2] - bbox[0]) > max_width and status_font_size > 10:
            status_font_size -= 2
            f_status = get_font(font_choice, status_font_size, base_dir)
            bbox = draw.textbbox((0, 0), status_text, font=f_status)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_status), status_text, f_status, color_white)

    if show_price and price:
        p_str = f"${int(float(str(price).replace('$', '').replace(',', ''))):,}"
        bbox = draw.textbbox((0, 0), p_str, font=f_price)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_price), p_str, f_price, color_white)

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

    if addr:
        bbox = draw.textbbox((0, 0), addr, font=f_addr)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_addr), addr, f_addr, color_light_gray)

    if phone:
        txt = f"Agent Contact: {phone}"
        bbox = draw.textbbox((0, 0), txt, font=f_agent)
        x_pos = (tw - (bbox[2] - bbox[0])) // 2
        draw_text_with_shadow(draw, (x_pos, y_agent), txt, f_agent, (255, 255, 255, 255))

    # --- Use Global CTA logic ---
    cta_text = get_dynamic_cta(status, lang, custom_cta)

    bbox = draw.textbbox((0, 0), cta_text, font=f_cta)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x_pos = (tw - text_w) // 2
    
    pad_x = int(tw * 0.04)
    pad_y = int(th * 0.015)
    btn_color = theme_color if theme_color else (220, 50, 50, 255)
    draw.rounded_rectangle(
        [x_pos - pad_x, y_cta - pad_y, x_pos + text_w + pad_x, y_cta + text_h + pad_y],
        radius=int(th * 0.015),
        fill=btn_color
    )

    adjusted_y_cta = y_cta - bbox[1]
    draw_text_with_shadow(draw, (x_pos, adjusted_y_cta), cta_text, f_cta, color_white)

    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    overlay_img.save(temp)
    return [ImageClip(temp).with_duration(dur)]

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None, theme_color="#552448"):
    if not text: return []
    
    rgb_highlight = hex_to_rgb(theme_color) + (255,)
    font = get_font(font_choice, int(target_h * 0.027), base_dir)
    text = str(text).upper().strip()
    words = text.split()
    draw_t = ImageDraw.Draw(Image.new('RGBA', (1,1)))
    space_w = int(draw_t.textlength(" ", font=font))
    
    lines_data, current_line_words, current_line_w, max_h_line = [], [], 0, 0
    for word in words:
        bbox = draw_t.textbbox((0,0), word, font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if current_line_words and (current_line_w + space_w + w) > (target_w * 0.8):
            lines_data.append((current_line_w, max_h_line, current_line_words))
            current_line_words, current_line_w, max_h_line = [(word, w, h)], w, h
        else:
            current_line_w += (space_w if current_line_words else 0) + w
            max_h_line = max(max_h_line, h)
            current_line_words.append((word, w, h))
    if current_line_words: lines_data.append((current_line_w, max_h_line, current_line_words))

    bw, bh = int(max([ld[0] for ld in lines_data]) + (target_w * 0.05)), int(sum([ld[1] for ld in lines_data]) + (len(lines_data) * target_h * 0.01) + (target_w * 0.05))
    x1, y1 = (target_w - bw) // 2, int(target_h * 0.85)
    
    bg_overlay = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    draw_bg = ImageDraw.Draw(bg_overlay)
    draw_bg.rounded_rectangle([x1, y1, x1+bw, y1+bh], radius=15, fill=(40, 40, 40, 220), outline=(255, 255, 255, 60), width=2)
    
    word_positions, curr_y, word_idx = [], y1 + (target_w * 0.025), 0
    for line_w, line_h, words_in_line in lines_data:
        curr_x = (target_w - line_w) // 2
        for word_text, w, h in words_in_line:
            word_positions.append((word_idx, word_text, curr_x, curr_y))
            draw_bg.text((curr_x, curr_y), word_text, font=font, fill=(255, 255, 255))
            curr_x += w + space_w
            word_idx += 1
        curr_y += line_h + (target_h * 0.01)

    hash_id = hashlib.md5(text.encode()).hexdigest()[:8]
    base_temp = os.path.join(base_dir, f"temp_cap_base_{job_id}_{hash_id}.png") 
    bg_overlay.save(base_temp)
    
    def pop_base(t):
        if t > 0.5: return (0, 0)
        p = t / 0.5
        c1 = 1.70158
        ease = 1 + (c1 + 1) * ((p - 1) ** 3) + c1 * ((p - 1) ** 2)
        y_offset = int(80 * (1 - ease))
        return (0, y_offset)

    layers = [ImageClip(base_temp).with_duration(duration).with_position(pop_base)]
    
    def word_pop(t):
        if t > 0.15: return (0, 0)
        p = t / 0.15
        y_offset = int(12 * (1 - p)**2)
        return (0, y_offset)

    if timings and len(timings) > 0 and len(word_positions) > 0:
        ratio = len(timings) / len(word_positions)
        
        for w_idx, word_text, x, y in word_positions:
            start_idx = int(w_idx * ratio)
            end_idx = min(int((w_idx + 1) * ratio - 0.001), len(timings) - 1)
            
            s = timings[start_idx][0]
            e = timings[end_idx][1]
            
            if s >= duration: continue
            
            hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
            ImageDraw.Draw(hl_img).text((x, y), word_text, font=font, fill=rgb_highlight)
            hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_{hash_id}_{w_idx}.png") 
            hl_img.save(hl_temp)
            
            hl_clip = ImageClip(hl_temp).with_start(s).with_duration(min(e + 0.1, duration) - s)
            layers.append(hl_clip.with_position(word_pop))
            
    return layers

# --- UPDATED END SCREEN SIGNATURE ---
def create_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir, is_own_listing, status, custom_cta=None, logo_path=None):
    rgb_theme = hex_to_rgb(theme_color)
    img_bg = Image.new('RGB', (target_w, target_h), (10, 10, 12)) 
    ImageDraw.Draw(img_bg).rectangle([0, 0, target_w, 6], fill=rgb_theme)

    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_max_w, logo_max_h = int(target_w * 0.4), int(target_h * 0.15)
            logo_img.thumbnail((logo_max_w, logo_max_h), Image.Resampling.LANCZOS)
            lx = (target_w - logo_img.width) // 2
            ly = int(target_h * 0.08) 
            img_bg.paste(logo_img, (lx, ly), logo_img) 
        except Exception as e:
            print(f"Failed to draw logo on end screen: {e}")

    temp_bg = os.path.join(base_dir, f"temp_end_bg_{job_id}.png") 
    img_bg.save(temp_bg)
    
    def _text_clip(text, base_size, color, y, start, job_id, name):
        if not text: return None
        size = base_size
        font = get_font(font_choice, size, base_dir)
        txt_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        bbox = draw.textbbox((0, 0), text, font=font)
        
        max_width = target_w * 0.90
        while (bbox[2] - bbox[0]) > max_width and size > 12:
            size -= 2
            font = get_font(font_choice, size, base_dir)
            bbox = draw.textbbox((0, 0), text, font=font)

        draw.text(((target_w - (bbox[2]-bbox[0])) / 2, y), text, font=font, fill=color)
        path = os.path.join(base_dir, f"temp_end_txt_{name}_{job_id}.png") 
        txt_img.save(path)
        return ImageClip(path).with_start(start).with_duration(max(0.1, duration - start))

    layers, curr_y, fade = [ImageClip(temp_bg).with_duration(duration)], int(target_h * 0.25), 0.5
    
    if is_own_listing:
        courtesy_text = "Presentado por:" if language == "Spanish" else "Presented by:"
    else:
        courtesy_text = "Cortesía de:" if language == "Spanish" else "Listing Courtesy of:"
    
    # --- GET DYNAMIC CTA ---
    dynamic_cta = get_dynamic_cta(status, language, custom_cta)

    elements_to_draw = [
        (dynamic_cta, int(target_h * 0.045), (160, 160, 170), "cta"), 
        (phone, int(target_h * 0.065), (255, 255, 255), "ph"), 
        (website, int(target_h * 0.035), (200, 200, 255), "web"), 
        (courtesy_text, int(target_h * 0.020), (180, 180, 190), "courtesy"), 
        (agent_name.upper(), int(target_h * 0.030), (255, 255, 255), "ag"), 
        (brokerage, int(target_h * 0.022), (140, 140, 150), "br")
    ]
    
    for t, base_sz, c, n in elements_to_draw:
        clip = _text_clip(t, base_sz, c, curr_y, fade, job_id, n)
        if clip: layers.append(clip)
        
        if n == "cta": curr_y += 80
        elif n == "ph": curr_y += 110  # Maintained your padding change here
        elif n == "web": curr_y += 70
        elif n == "courtesy": curr_y += 30
        else: curr_y += 50
        fade += 0.6
    
    mls_txt = f"Source: {mls_source} | MLS# {mls_number}" if (mls_source or mls_number) else ""
    mls_clip = _text_clip(mls_txt, int(target_h * 0.016), (80, 80, 90), target_h - 60, 2.5, job_id, "mls")
    if mls_clip: layers.append(mls_clip)
    
    return CompositeVideoClip(layers, size=(target_w, target_h)).with_duration(duration)

async def generate_edge_audio_async(text, voice, output_path):
    timings = []
    communicate = edge_tts.Communicate(text, voice)
    with open(output_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                timings.append((chunk["offset"]/10000000.0, (chunk["offset"]+chunk["duration"])/10000000.0, chunk["text"]))
    return timings

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
    img_url = scene_data.get('image_url', '')

    if not os.path.exists(img_path) and img_url.startswith('http'):
        try:
            r = requests.get(img_url, timeout=15)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, 'wb') as f: 
                    f.write(r.content)
        except requests.RequestException as e:
            print(f"Warning: Failed to fetch image {img_url} - {e}")

    all_effects = [
        "zoom_in", "zoom_out", "pan_right", "pan_left", 
        "pan_up", "pan_down", "pan_up_left", "pan_down_right",
        "drone_push", "drone_pull", "luxury_breathe",
        "3d_pan_right", "3d_pan_left"
    ]
      
    raw_effect = scene_data.get('effect', 'auto')
    effect = str(raw_effect).strip().lower() if raw_effect else "auto"

    if effect == "auto":
        effect = random.choice(all_effects)

    scale_factor = 1.35  
    
    clip = ImageClip(img_path)
    img_aspect = clip.w / clip.h
    video_aspect = tw / th
    
    if img_aspect > video_aspect:
        clip = clip.resized(height=th * scale_factor)
    else:
        clip = clip.resized(width=tw * scale_factor)
        
    base_frame = clip.get_frame(0)
    h_base, w_base, _ = base_frame.shape
    base_pil = Image.fromarray(base_frame)

    def make_frame(t):
        progress = ease_in_out(t, dur)

        if effect == "pan_right":
            x = int((w_base - tw) * progress)
            y = int((h_base - th) / 2)
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_left":
            x = int((w_base - tw) * (1 - progress))
            y = int((h_base - th) / 2)
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_up":
            x = int((w_base - tw) / 2)
            y = int((h_base - th) * (1 - progress))
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_down":
            x = int((w_base - tw) / 2)
            y = int((h_base - th) * progress)
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_up_left":
            x = int((w_base - tw) * (1 - progress))
            y = int((h_base - th) * (1 - progress))
            return base_frame[y:y+th, x:x+tw]
        elif effect == "pan_down_right":
            x = int((w_base - tw) * progress)
            y = int((h_base - th) * progress)
            return base_frame[y:y+th, x:x+tw]
        
        elif effect == "3d_pan_right":
            x_offset = (w_base - tw) * progress
            y_offset = (h_base - th) / 2
            tilt = int(th * 0.08)
            
            left_tilt = tilt * progress
            x0, y0 = x_offset, y_offset - left_tilt
            x1, y1 = x_offset, y_offset + th + left_tilt
            
            right_tilt = tilt * (1 - progress)
            x2, y2 = x_offset + tw, y_offset + th + right_tilt
            x3, y3 = x_offset + tw, y_offset - right_tilt
            
            quad = (x0, y0, x1, y1, x2, y2, x3, y3)
            return np.array(base_pil.transform((tw, th), Image.QUAD, quad, resample=Image.Resampling.BICUBIC))
            
        elif effect == "3d_pan_left":
            x_offset = (w_base - tw) * (1 - progress)
            y_offset = (h_base - th) / 2
            tilt = int(th * 0.08)
            
            left_tilt = tilt * (1 - progress)
            x0, y0 = x_offset, y_offset - left_tilt
            x1, y1 = x_offset, y_offset + th + left_tilt
            
            right_tilt = tilt * progress
            x2, y2 = x_offset + tw, y_offset + th + right_tilt
            x3, y3 = x_offset + tw, y_offset - right_tilt
            
            quad = (x0, y0, x1, y1, x2, y2, x3, y3)
            return np.array(base_pil.transform((tw, th), Image.QUAD, quad, resample=Image.Resampling.BICUBIC))

        elif effect == "zoom_out":
            zoom = 1.15 - (0.15 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            pil_img = Image.fromarray(cropped).resize((tw, th), Image.Resampling.LANCZOS)
            return np.array(pil_img)
        elif effect == "drone_push":
            angle = -1.5 + (3.0 * progress)
            zoom = 1.05 + (0.10 * progress) 
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            pil_img = Image.fromarray(cropped)
            rotated = pil_img.rotate(angle, resample=Image.Resampling.BICUBIC)
            return np.array(rotated.resize((tw, th), Image.Resampling.LANCZOS))
        elif effect == "drone_pull":
            angle = 1.5 - (3.0 * progress)
            zoom = 1.15 - (0.10 * progress) 
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            pil_img = Image.fromarray(cropped)
            rotated = pil_img.rotate(angle, resample=Image.Resampling.BICUBIC)
            return np.array(rotated.resize((tw, th), Image.Resampling.LANCZOS))
        elif effect == "luxury_breathe":
            breathe_progress = math.sin(progress * (math.pi / 2)) 
            zoom = 1.0 + (0.12 * breathe_progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            pil_img = Image.fromarray(cropped).resize((tw, th), Image.Resampling.LANCZOS)
            return np.array(pil_img)
        else: 
            zoom = 1.0 + (0.15 * progress)
            new_w, new_h = int(tw / zoom), int(th / zoom)
            x = int((w_base - new_w) / 2)
            y = int((h_base - new_h) / 2)
            cropped = base_frame[y:y+new_h, x:x+new_w]
            pil_img = Image.fromarray(cropped).resize((tw, th), Image.Resampling.LANCZOS)
            return np.array(pil_img)

    animated_base = VideoClip(make_frame, duration=dur)
    layers = [animated_base]

    if is_first:
        layers.extend(create_title_overlay(
                job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, 
                font_choice, show_price, show_details, status_choice, 
                agent_name, brokerage, phone, mls_source, mls_number, 
                theme_color, base_dir, custom_cta=custom_cta, logo_path=logo_path
            ))
    else:
        if show_captions:
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
        "Deep/Luxury": "en-US-EricNeural",
        "Friendly/Fast": "en-US-GuyNeural",
        "Professional/Clean": "en-US-AndrewNeural",
        "Female/Warm": "en-US-AvaNeural",
        "Spanish/Mexico-Male": "es-MX-JorgeNeural",
        "Spanish/Mexico-Female": "es-MX-DaliaNeural",
        "Spanish/Spain-Male": "es-ES-AlvaroNeural",
        "Spanish/US-Male": "es-US-AlonsoNeural"
    }

    try:
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        set_progress(job_id, 5)

        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)

        requested_voice = req_dict.get('voice', 'Professional/Clean')
        lang = req_dict.get('language', 'English')
        
        if lang == "Spanish" and "en-US" in VOICE_MAP.get(requested_voice, "en-US"):
            voice_id = "es-MX-JorgeNeural"
        else:
            voice_id = VOICE_MAP.get(requested_voice, "en-US-AndrewNeural")

        set_progress(job_id, 10)

        vo_tasks, vo_map = [], {}
        enable_voice = req_dict.get('enable_voice', True) 

        if enable_voice:
            for s in scenes:
                if s.get('enable_vo') and s.get('caption'):
                    p = os.path.join(base_dir, f"temp_vo_{job_id}_{s['id']}.mp3")
                    vo_tasks.append(generate_edge_audio_async(s['caption'], voice_id, p))
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
                job_id, 
                i, 
                scene, 
                tw, 
                th, 
                (i==0), 
                meta.get('address',''), 
                meta.get('price',''), 
                meta.get('beds',''), 
                meta.get('baths',''), 
                meta.get('sqft',''), 
                lang, 
                req_dict.get('font','Montserrat'), 
                req_dict.get('show_price', True), 
                req_dict.get('show_details', True), 
                voice_id, 
                status_choice, 
                meta.get('agent',''), 
                meta.get('brokerage',''), 
                meta.get('phone',''), 
                meta.get('mls_source',''), 
                meta.get('mls_number',''), 
                3.5, 
                'Auto', 
                req_dict.get('primary_color','#552448'), 
                logo_file_path, 
                base_dir, 
                vo_data=vo_map.get(scene['id']), 
                custom_cta=actual_custom_cta,
                show_captions=req_dict.get('show_captions', True)   
            ))
            if total_scenes > 0:
                set_progress(job_id, 25 + int(((i + 1) / total_scenes) * 20))

        # --- UPDATED END SCREEN CALL ---
        clips.append(create_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), 
            meta.get('phone',''), meta.get('website',''), 5.0, lang, 
            meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Roboto'), req_dict.get('primary_color','#552448'), base_dir, 
            req_dict.get('is_own_listing', True),
            status=status_choice, 
            custom_cta=actual_custom_cta,
            logo_path=logo_file_path
        ))

        set_progress(job_id, 48)

        final = concatenate_videoclips(clips)
        m_choice = req_dict.get('music')
        if m_choice and m_choice != "none" and m_choice in MUSIC_MAP:
            m_file = os.path.join(base_dir, MUSIC_MAP[m_choice])
            if os.path.exists(m_file):
                bg = AudioFileClip(m_file)
                if bg.duration < final.duration: 
                    bg = concatenate_audioclips([bg] * (int(final.duration / bg.duration) + 1))
                bg = bg.with_duration(final.duration).with_volume_scaled(0.08)
                
                if final.audio:
                    final.audio = CompositeAudioClip([bg, final.audio])
                else:
                    final.audio = bg

        set_progress(job_id, 50)

        render_logger = JobRenderLogger(job_id, start_progress=50, end_progress=99)
        final.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            threads=4, 
            preset="ultrafast", 
            logger=render_logger, 
            ffmpeg_params=["-movflags", "faststart"]
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