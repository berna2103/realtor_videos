import os
import time
import asyncio
import hashlib
import base64
import glob
import io
import threading
import edge_tts
import numpy as np
import requests

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from moviepy import (
    ImageClip, 
    CompositeVideoClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeAudioClip,
    concatenate_audioclips, 
    vfx, 
    afx
)


# Fix for MoviePy 1.0.3 & Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS



# --- HELPER FUNCTIONS ---
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# --- FONT & MUSIC MAPPING ---
FONT_MAP = {
    "Roboto": "fonts/Roboto-Bold.ttf",
    "Inter": "fonts/Inter-Bold.ttf",
    "Cinzel": "fonts/Cinzel-Bold.ttf",
    "Playfair": "fonts/PlayfairDisplay-Bold.ttf",
    "Prata": "fonts/Prata-Bold.ttf",
}

MUSIC_MAP = {
    "Upbeat": "music/Upbeat.mp3",
    "Luxury": "music/Luxury.mp3",
    "Motivation": "music/Motivation.mp3"
}

def get_font(font_name, size, base_dir):
    fonts_dir = os.path.join(base_dir, 'fonts')
    if font_name and os.path.exists(fonts_dir):
        search_term = str(font_name).split()[0].lower()
        for file in os.listdir(fonts_dir):
            if file.lower().endswith('.ttf') and search_term in file.lower():
                font_path = os.path.join(fonts_dir, file)
                try: return ImageFont.truetype(font_path, int(size))
                except Exception: pass
                    
    system_fonts = ["arial.ttf", "Helvetica.ttc", "tahoma.ttf", "verdana.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    for sys_font in system_fonts:
        try: return ImageFont.truetype(sys_font, int(size))
        except: continue
            
    return ImageFont.load_default()

def ease_in_out(t, duration):
    p = max(0.0, min(1.0, t / duration))
    return p * p * (3 - 2 * p)

def wrap_text_by_pixels(text, font, max_pixels):
    if not text: return []
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    words = str(text).split()
    lines, current_line = [], []
    for word in words:
        test_line = ' '.join(current_line + [word]) if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_pixels: current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line: lines.append(' '.join(current_line))
    return lines

def create_title_overlay(job_id, target_w, target_h, address, price, beds, baths, sqft, duration,
                         language, font_choice, show_price, show_details, status_choice,
                         agent_name, brokerage, phone, mls_source, mls_number,
                         theme_color, base_dir, logo_path=None):

    # ---------- BASE IMAGE ----------
    img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    overlay = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 120))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    white = (255, 255, 255, 255)

    # ---------- SMART SCALING ----------
    scale_ref = min(target_w, target_h)
    max_w = int(target_w * 0.90)

    def get_fitted_font(text, font_choice, starting_size, base_dir):
        if not text: return get_font(font_choice, starting_size, base_dir)
        size = starting_size
        font = get_font(font_choice, size, base_dir)
        dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        
        while size > 12: 
            bbox = dummy_draw.textbbox((0, 0), str(text), font=font)
            if (bbox[2] - bbox[0]) <= max_w:
                break
            size -= 4
            font = get_font(font_choice, size, base_dir)
        return font

    # ---------- STRINGS & FONTS ----------
    title = status_choice.title()
    price_str = f"${price}" if (show_price and price) else ""
    cta_text = f"Schedule a Showing • {phone}" if phone else ""

    title_font = get_fitted_font(title, font_choice, int(scale_ref * 0.16), base_dir)
    price_font = get_fitted_font(price_str, font_choice, int(scale_ref * 0.12), base_dir)
    pill_font  = get_font(font_choice, int(scale_ref * 0.045), base_dir)
    addr_font  = get_font(font_choice, int(scale_ref * 0.05), base_dir)
    cta_font   = get_fitted_font(cta_text, font_choice, int(scale_ref * 0.045), base_dir)

    # ---------- TITLE ----------
    bbox = draw.textbbox((0, 0), title, font=title_font)
    t_w, t_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    title_pos = ((target_w - t_w)//2, int(target_h * 0.32)) 
    draw.text(title_pos, title, font=title_font, fill=white)

    # ---------- PRICE ----------
    if price_str:
        bbox = draw.textbbox((0, 0), price_str, font=price_font)
        p_w, p_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        price_pos = ((target_w - p_w)//2, title_pos[1] + t_h + 10)
        draw.text(price_pos, price_str, font=price_font, fill=(230,230,230,255))

    # ---------- GLASS PILL WITH ICONS ----------
    pill_y2 = None
    if show_details:
        parts = []
        if beds: parts.append(f"🛏 {beds}")
        if baths: parts.append(f"🛁 {baths}")
        if sqft: parts.append(f"⬜ {sqft}")

        if parts:
            pill_text = "   ".join(parts)
            bbox = draw.textbbox((0, 0), pill_text, font=pill_font)
            p_w, p_h = bbox[2]-bbox[0], bbox[3]-bbox[1]

            pad_x, pad_y = int(scale_ref*0.04), int(scale_ref*0.02)
            pill_w = p_w + pad_x * 2
            pill_h = p_h + pad_y * 2

            pill_x1 = (target_w - pill_w)//2
            pill_y1 = int(target_h * 0.55)
            pill_y2 = pill_y1 + pill_h

            pill_area = img.crop((pill_x1, pill_y1, pill_x1+pill_w, pill_y2))
            blurred = pill_area.filter(ImageFilter.GaussianBlur(18))
            img.paste(blurred, (pill_x1, pill_y1))

            glass = Image.new('RGBA', (pill_w, pill_h), (255,255,255,60))
            img.paste(glass, (pill_x1, pill_y1), glass)

            draw.text(((target_w - p_w)//2, pill_y1 + pad_y - 5), pill_text, font=pill_font, fill=white)

    # ---------- CTA ----------
    if cta_text:
        bbox = draw.textbbox((0,0), cta_text, font=cta_font)
        c_w, c_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        cta_y = pill_y2 + int(target_h * 0.05) if pill_y2 else int(target_h*0.65)
        draw.text(((target_w - c_w)//2, cta_y), cta_text, font=cta_font, fill=(255,255,255,230))

    # ---------- ADDRESS (WITH WORD WRAP) ----------
    if address:
        address_lines = wrap_text_by_pixels(address, addr_font, max_w)
        start_y = int(target_h * 0.80)
        line_spacing = int(target_h * 0.01) 
        
        for line in address_lines:
            bbox = draw.textbbox((0, 0), line, font=addr_font)
            line_w = bbox[2] - bbox[0]
            line_h = bbox[3] - bbox[1]
            
            x_pos = (target_w - line_w) // 2
            draw.text((x_pos, start_y), line, font=addr_font, fill=(200, 200, 200, 255))
            start_y += line_h + line_spacing

    # ---------- SAVE BASE ----------
    temp = os.path.join(base_dir, f"temp_title_{job_id}.png")
    img.save(temp)

    base_clip = ImageClip(temp).with_duration(duration)

    # =========================================================
    # 🎬 ANIMATIONS (CapCut Style)
    # =========================================================
    animated = base_clip.with_effects([
        vfx.FadeIn(0.8),
        vfx.FadeOut(0.8)
    ]).resized(lambda t: 1 + 0.05 * (t/duration))

    # =========================================================
    # ✨ GRADIENT LIGHT SWEEP
    # =========================================================
    sweep = np.zeros((target_h, target_w, 4), dtype=np.uint8)

    for x in range(target_w):
        alpha = int(120 * (1 - abs((x / target_w) - 0.5) * 2))
        sweep[:, x] = [255, 255, 255, max(0, alpha)]

    sweep_img = Image.fromarray(sweep, 'RGBA')
    sweep_path = os.path.join(base_dir, f"temp_sweep_{job_id}.png")
    sweep_img.save(sweep_path)

    sweep_clip = (
        ImageClip(sweep_path)
        .with_duration(duration)
        .with_opacity(0.25)
        .with_position(lambda t: (int(-target_w + (t/duration)*(2*target_w)), 0))
    )

    return CompositeVideoClip(
        [animated, sweep_clip],
        size=(target_w, target_h)
    ).with_duration(duration)

def create_glass_caption(job_id, text, duration, target_w, target_h, font_choice, base_dir, timings=None):
    if not text: return []
    base_font_size = int(target_h * 0.027)
    font = get_font(font_choice, base_font_size, base_dir)
    text = str(text).upper().strip()
    words = text.split()
    max_text_width_px = target_w * 0.8
    draw_t = ImageDraw.Draw(Image.new('RGBA', (1,1)))
    space_w = int(draw_t.textlength(" ", font=font))
    
    lines_data, current_line_words, current_line_w, max_h_line = [], [], 0, 0
    for word in words:
        bbox = draw_t.textbbox((0,0), word, font=font)
        w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if current_line_words and (current_line_w + space_w + w) > max_text_width_px:
            lines_data.append((current_line_w, max_h_line, current_line_words))
            current_line_words, current_line_w, max_h_line = [(word, w, h)], w, h
        else:
            if current_line_words: current_line_w += space_w + w
            else: current_line_w = w
            max_h_line = max(max_h_line, h)
            current_line_words.append((word, w, h))
    if current_line_words: lines_data.append((current_line_w, max_h_line, current_line_words))

    max_w = max([ld[0] for ld in lines_data]) if lines_data else 0
    total_h = sum([ld[1] for ld in lines_data]) + (max(0, len(lines_data) - 1)) * (target_h * 0.01)
    
    padding = int(target_w * 0.05)
    bw, bh = int(max_w + padding), int(total_h + padding)
    x1, y1 = (target_w - bw) // 2, int(target_h * 0.85)
    
    word_positions, curr_y, word_idx = [], y1 + (padding // 2), 0
    for line_w, line_h, words_in_line in lines_data:
        curr_x = (target_w - line_w) // 2
        for word_text, w, h in words_in_line:
            word_positions.append((word_idx, word_text, curr_x, curr_y))
            curr_x += w + space_w
            word_idx += 1
        curr_y += line_h + (target_h * 0.01)

    bg_overlay = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    draw_bg = ImageDraw.Draw(bg_overlay)
    draw_bg.rounded_rectangle([x1, y1, x1+bw, y1+bh], radius=15, fill=(40, 40, 40, 220), outline=(255, 255, 255, 60), width=2)
    for w_idx, word_text, x, y in word_positions:
        draw_bg.text((x, y), word_text, font=font, fill=(255, 255, 255))
        
    hash_id = hashlib.md5(text.encode()).hexdigest()[:8]
    base_temp = os.path.join(base_dir, f"temp_cap_base_{job_id}_{hash_id}.png") 
    bg_overlay.save(base_temp)
    
    layers = [ImageClip(base_temp).with_duration(duration)]
    
    if timings:
        for w_idx, word_text, x, y in word_positions:
            if w_idx < len(timings):
                start_time, end_time, _ = timings[w_idx]
                if start_time >= duration: continue
                end_time = min(end_time + 0.3, duration)
                if end_time <= start_time: continue
                
                hl_img = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
                draw_hl = ImageDraw.Draw(hl_img)
                draw_hl.text((x, y), word_text, font=font, fill=(218, 165, 32, 255))
                hl_temp = os.path.join(base_dir, f"temp_hl_{job_id}_{hash_id}_{w_idx}.png") 
                hl_img.save(hl_temp)
                layers.append(ImageClip(hl_temp).with_start(start_time).with_duration(end_time - start_time))
                
    return layers

def create_end_screen(job_id, target_w, target_h, agent_name, brokerage, phone, website, duration, language, mls_source, mls_number, font_choice, theme_color, base_dir):
    from PIL import Image, ImageDraw, ImageOps
    rgb_theme = hex_to_rgb(theme_color)
    
    bg_color = (10, 10, 12)
    img_bg = Image.new('RGB', (target_w, target_h), bg_color) 
    draw_bg = ImageDraw.Draw(img_bg)
    draw_bg.rectangle([0, 0, target_w, 6], fill=rgb_theme)
    
    temp_bg = os.path.join(base_dir, f"temp_end_bg_{job_id}.png") 
    img_bg.save(temp_bg)
    base_clip = ImageClip(temp_bg).with_duration(duration)

    f_cta = get_font(font_choice, int(target_h * 0.045), base_dir)
    f_phone = get_font(font_choice, int(target_h * 0.065), base_dir)
    f_website = get_font(font_choice, int(target_h * 0.035), base_dir)
    f_name = get_font(font_choice, int(target_h * 0.030), base_dir)
    f_broker = get_font(font_choice, int(target_h * 0.022), base_dir)
    f_mls = get_font(font_choice, int(target_h * 0.016), base_dir)
    
    cta_text = "¡AGENDA TU CITA!" if language == "Spanish" else "SCHEDULE A SHOWING!"
    phone_text = phone if phone else ""
    website_text = website if website else ""
    agent_text = agent_name.upper() if agent_name else ""
    broker_text = brokerage if brokerage else ""
    mls_text = f"Source: {mls_source} | MLS# {mls_number}" if (mls_source or mls_number) else ""

    def _create_text_clip(text, font, fill_color, y_pos, start_time, clip_duration, job_id, unique_name):
        if not text: return None
        txt_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        bbox = txt_draw.textbbox((0, 0), text, font=font)
        txt_draw.text(((target_w - (bbox[2]-bbox[0])) / 2, y_pos), text, font=font, fill=fill_color)
        temp_path = os.path.join(base_dir, f"temp_end_txt_{unique_name}_{job_id}.png") 
        txt_img.save(temp_path)
        return (ImageClip(temp_path)
                .with_start(start_time)
                .with_duration(max(0.1, clip_duration - start_time)))

    curr_y = int(target_h * 0.30)
    fade_start = 0.5  
    fade_step = 0.6   
    layers = [base_clip]

    cta_clip = _create_text_clip(cta_text, f_cta, (160, 160, 170), curr_y, fade_start, duration, job_id, "cta")
    if cta_clip: layers.append(cta_clip)
    curr_y += 80
    fade_start += fade_step

    phone_clip = _create_text_clip(phone_text, f_phone, (255, 255, 255), curr_y, fade_start, duration, job_id, "phone")
    if phone_clip: layers.append(phone_clip)
    curr_y += 70
    fade_start += fade_step
    
    website_clip = _create_text_clip(website_text, f_website, (200, 200, 255), curr_y, fade_start, duration, job_id, "website")
    if website_clip: layers.append(website_clip)
    curr_y += 70
    fade_start += fade_step

    agent_clip = _create_text_clip(agent_text, f_name, (255, 255, 255), curr_y, fade_start, duration, job_id, "agent")
    if agent_clip: layers.append(agent_clip)
    curr_y += 50
    fade_start += fade_step

    broker_clip = _create_text_clip(broker_text, f_broker, (140, 140, 150), curr_y, fade_start, duration, job_id, "broker")
    if broker_clip: layers.append(broker_clip)
    
    mls_clip = _create_text_clip(mls_text, f_mls, (80, 80, 90), target_h - 60, fade_start, duration, job_id, "mls")
    if mls_clip: layers.append(mls_clip)

    final_end_screen = CompositeVideoClip(layers, size=(target_w, target_h))
    return final_end_screen.with_duration(duration)

def generate_edge_audio(text, voice, output_path):
    timings = []
    
    async def _amain():
        communicate = edge_tts.Communicate(text, voice)
        with open(output_path, "wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": 
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 10000000.0
                    end = (chunk["offset"] + chunk["duration"]) / 10000000.0
                    timings.append((start, end, chunk["text"]))
                    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            new_loop.run_until_complete(_amain())
            new_loop.close()
            
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
    else:
        asyncio.run(_amain())
        
    return timings

def create_animated_clip(job_id, i, scene_data, tw, th, is_first, addr, price, beds, baths, sqft, lang, font_choice, show_price, show_details, voice_model, status_choice, agent_name, brokerage, phone, mls_source, mls_number, target_slide_dur, timing_mode, theme_color, logo_path, base_dir):
    dur = target_slide_dur
    vo_clip, vo_timings = None, None
    
    # ... existing voiceover code ...
    if scene_data.get('enable_vo') and scene_data.get('caption'):
        try:
            vo_path = os.path.join(base_dir, f"temp_vo_{job_id}_{scene_data['id']}.mp3") 
            vo_timings = generate_edge_audio(scene_data['caption'], voice_model, vo_path)
            vo_clip = AudioFileClip(vo_path)
            dur = max(target_slide_dur, vo_clip.duration + 0.3)
        except: pass

    # --- NEW: JUST-IN-TIME IMAGE RECOVERY ---
    img_path = scene_data['image_path']
    img_url = scene_data.get('image_url')
    
    # If Railway wiped the file, download it from Supabase back to local disk
    if not os.path.exists(img_path) and img_url and img_url.startswith('http'):
        r = requests.get(img_url)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            with open(img_path, 'wb') as f:
                f.write(r.content)
    # ----------------------------------------

    base = ImageClip(img_path).resized(height=th)
    
    animated = base.resized(lambda t: 1.0 + 0.15 * ease_in_out(t, dur))

    if is_first: 
        overlay_layers = [create_title_overlay(job_id, tw, th, addr, price, beds, baths, sqft, dur, lang, font_choice, show_price, show_details, status_choice, agent_name, brokerage, phone, mls_source, mls_number, theme_color, base_dir)]
    else: 
        overlay_layers = create_glass_caption(job_id, scene_data['caption'], dur, tw, th, font_choice, base_dir, vo_timings)
        
    layers = [animated.with_duration(dur)]
    layers.extend(overlay_layers)
    
    # LOGO MASKING FIX (The Green Square Destroyer)
    if logo_path and os.path.exists(logo_path):
        logo_canvas = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        logo_img = Image.open(logo_path).convert("RGBA")
        
        logo_w = int(tw * 0.16)
        logo_img.thumbnail((logo_w, logo_w), Image.Resampling.LANCZOS)
        
        logo_canvas.paste(logo_img, (40, 40), mask=logo_img)
        
        logo_temp = os.path.join(base_dir, f"temp_logo_overlay_{job_id}_{i}.png")
        logo_canvas.save(logo_temp)
        layers.append(ImageClip(logo_temp).with_duration(dur))

    final_clip = CompositeVideoClip(layers, size=(tw, th)).with_duration(dur)
    if vo_clip: final_clip = final_clip.with_audio(vo_clip)
    return final_clip

def render_cinematic_video(job_id, req, output_path, base_dir):
    clips = []
    final = None
    logo_file_path = None
    req_dict = req if isinstance(req, dict) else req.model_dump()
    meta = req_dict.get('meta', {})
    scenes = req_dict.get('scenes', [])
    
    try:
        if req_dict.get('logo_data') and ',' in req_dict.get('logo_data'):
            logo_data = base64.b64decode(req_dict.get('logo_data').split(',', 1)[1])
            logo_file_path = os.path.join(base_dir, f"temp_logo_{job_id}.png")
            Image.open(io.BytesIO(logo_data)).save(logo_file_path)

        # Optimization: Use 720p for faster rendering
        tw, th = (720, 1280) if "Vertical" in req_dict.get('format', 'Vertical') else (1280, 720)

        for i, scene in enumerate(scenes):
            clips.append(create_animated_clip(
                job_id, i, scene, tw, th, (i==0), meta.get('address',''), meta.get('price',''), 
                meta.get('beds',''), meta.get('baths',''), meta.get('sqft',''), req_dict.get('language','English'),
                req_dict.get('font','Montserrat'), True, True, req_dict.get('voice','en-US-ChristopherNeural'),
                req_dict.get('status_choice','Just Listed'), meta.get('agent',''), meta.get('brokerage',''),
                meta.get('phone',''), meta.get('mls_source',''), meta.get('mls_number',''), 3.0, 'Auto',
                req_dict.get('primary_color','#552448'), logo_file_path, base_dir
            ))

        end_screen = create_end_screen(
            job_id, tw, th, meta.get('agent',''), meta.get('brokerage',''), meta.get('phone',''), meta.get('website',''), 5.0, 
            req_dict.get('language','English'), meta.get('mls_source',''), meta.get('mls_number',''), 
            req_dict.get('font','Montserrat'), req_dict.get('primary_color','#552448'), base_dir
        )
        clips.append(end_screen)

        final = concatenate_videoclips(clips)

        music_choice = req_dict.get('music')
        if music_choice and music_choice != "none" and music_choice in MUSIC_MAP:
            music_file = os.path.join(base_dir, MUSIC_MAP[music_choice])
            if os.path.exists(music_file):
                bg_music = AudioFileClip(music_file)
                
                if bg_music.duration < final.duration:
                    bg_music = concatenate_audioclips([bg_music] * (int(final.duration / bg_music.duration) + 1))
                
                bg_music = bg_music.with_duration(final.duration).with_volume_scaled(0.08)
                
                if final.audio: 
                    final.audio = CompositeAudioClip([bg_music, final.audio])
                else: 
                    final.audio = bg_music

        final.write_videofile(
            output_path, fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            # bitrate="3000k",
            threads=4, 
            preset="ultrafast", 
            logger=None, 
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