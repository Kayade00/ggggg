import discord
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import io
import os
import random
import aiohttp
import json
from typing import Optional, Tuple, Dict, List
import math

class BattleVisualEffects:
    def __init__(self):
        self.load_pokemon_data()
        
        # Available battle backgrounds
        self.available_backgrounds = [
            "arena",
            "desert", 
            "lake",
            "land",
            "mountain",
            "night",
            "sky"
        ]
        
        # Fallback colors if background images fail to load
        self.fallback_colors = {
            "arena": (64, 64, 64),
            "desert": (244, 164, 96),
            "lake": (70, 130, 180),
            "land": (34, 139, 34),
            "mountain": (105, 105, 105),
            "night": (25, 25, 112),
            "sky": (135, 206, 235)
        }
        
        # Weather effects
        self.weather_effects = {
            "rain": {"particles": 200, "color": (173, 216, 230), "angle": -15},
            "snow": {"particles": 150, "color": (255, 250, 250), "angle": -5},
            "sandstorm": {"particles": 300, "color": (244, 164, 96), "angle": 45},
            "hail": {"particles": 100, "color": (240, 248, 255), "angle": -30}
        }
        
        # Move effect colors and patterns
        self.move_effects = {
            "fire": {"colors": [(255, 69, 0), (255, 140, 0), (255, 215, 0)], "pattern": "burst"},
            "water": {"colors": [(0, 191, 255), (30, 144, 255), (100, 149, 237)], "pattern": "wave"},
            "electric": {"colors": [(255, 255, 0), (255, 215, 0), (255, 255, 224)], "pattern": "bolt"},
            "grass": {"colors": [(34, 139, 34), (0, 128, 0), (124, 252, 0)], "pattern": "spiral"},
            "ice": {"colors": [(173, 216, 230), (176, 224, 230), (240, 248, 255)], "pattern": "crystal"},
            "fighting": {"colors": [(255, 69, 0), (255, 99, 71), (255, 160, 122)], "pattern": "impact"},
            "psychic": {"colors": [(186, 85, 211), (147, 112, 219), (221, 160, 221)], "pattern": "ripple"},
            "dark": {"colors": [(105, 105, 105), (128, 128, 128), (169, 169, 169)], "pattern": "shadow"},
            "ghost": {"colors": [(138, 43, 226), (72, 61, 139), (123, 104, 238)], "pattern": "fade"},
            "dragon": {"colors": [(148, 0, 211), (138, 43, 226), (75, 0, 130)], "pattern": "spiral"}
        }

    def load_pokemon_data(self):
        """Load Pokemon data for sprite lookups"""
        try:
            with open('pokedex.json', 'r', encoding='utf-8') as f:
                self.pokemon_data = json.load(f)
        except:
            self.pokemon_data = {}

    def get_pokemon_sprite_id(self, pokemon_name: str) -> Optional[int]:
        """Get the correct sprite ID for a Pokemon"""
        poke_data = next((d for d in self.pokemon_data.values() if isinstance(d, dict) and d.get("name", "").lower() == pokemon_name.lower()), None)
        if poke_data and 'id' in poke_data:
            return poke_data['id']
        return None

    def choose_battle_environment(self, is_arena_battle: bool = False, boss_name: Optional[str] = None) -> str:
        """Choose appropriate environment - arena for arena battles, random for others"""
        if is_arena_battle:
            return "arena"
        
        # For non-arena battles, choose randomly from all available backgrounds
        return random.choice(self.available_backgrounds)

    def load_background_image(self, environment: str, width: int, height: int) -> Image.Image:
        """Load background image or create fallback"""
        bg_path = f"battle_backgrounds/{environment}.png"
        
        if os.path.exists(bg_path):
            try:
                # Load and resize background image
                bg_image = Image.open(bg_path).convert("RGB")
                if bg_image.size != (width, height):
                    bg_image = bg_image.resize((width, height), Image.Resampling.LANCZOS)
                return bg_image
            except Exception as e:
                print(f"Error loading background {bg_path}: {e}")
        
        # Fallback: create simple colored background
        fallback_color = self.fallback_colors.get(environment, self.fallback_colors["land"])
        return Image.new('RGB', (width, height), fallback_color)

    def draw_trees(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw forest trees in background"""
        for i in range(5):
            x = random.randint(50, width - 100)
            tree_height = random.randint(60, 120)
            y = height - 80 - tree_height
            
            # Tree trunk
            draw.rectangle([x - 5, y + tree_height - 30, x + 5, height - 80], fill=(101, 67, 33))
            # Tree leaves
            draw.ellipse([x - 25, y, x + 25, y + tree_height - 20], fill=(0, 100, 0))

    def draw_cave_details(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw cave stalactites and rocks"""
        for i in range(8):
            x = random.randint(0, width)
            stala_height = random.randint(20, 60)
            # Stalactites
            draw.polygon([(x, 0), (x - 10, stala_height), (x + 10, stala_height)], fill=(169, 169, 169))
        
        # Rocks on ground
        for i in range(6):
            x = random.randint(0, width)
            y = height - random.randint(40, 80)
            draw.ellipse([x - 15, y, x + 15, y + 20], fill=(105, 105, 105))

    def draw_volcano_effects(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw lava flows and volcanic rocks"""
        # Lava streams
        for i in range(3):
            x = random.randint(100, width - 100)
            for y in range(height - 80, height, 5):
                lava_width = random.randint(8, 15)
                draw.ellipse([x - lava_width//2, y, x + lava_width//2, y + 3], fill=(255, 69, 0))
                x += random.randint(-5, 5)

    def draw_waves(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw ocean waves"""
        wave_y = height - 40
        for x in range(0, width, 20):
            wave_height = 5 + 3 * math.sin(x * 0.1)
            draw.arc([x, wave_y - wave_height, x + 40, wave_y + wave_height], 
                    start=0, end=180, fill=(0, 191, 255), width=3)

    def draw_snow_ground(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw snow drifts and icicles"""
        # Snow drifts
        for i in range(10):
            x = random.randint(0, width)
            y = height - random.randint(20, 60)
            drift_width = random.randint(30, 80)
            draw.ellipse([x - drift_width//2, y, x + drift_width//2, y + 20], fill=(255, 255, 255))

    def draw_city_skyline(self, draw: ImageDraw.ImageDraw, width: int, height: int, bg: dict):
        """Draw city buildings in background"""
        for i in range(8):
            building_width = random.randint(40, 80)
            building_height = random.randint(80, 150)
            x = i * (width // 8) + random.randint(-20, 20)
            y = height - 80 - building_height
            
            # Building
            draw.rectangle([x, y, x + building_width, height - 80], fill=(105, 105, 105))
            
            # Windows
            for window_y in range(y + 10, height - 90, 20):
                for window_x in range(x + 5, x + building_width - 5, 15):
                    if random.random() > 0.3:  # Some windows are lit
                        draw.rectangle([window_x, window_y, window_x + 8, window_y + 12], 
                                     fill=(255, 255, 0))

    def draw_stars(self, draw: ImageDraw.ImageDraw, width: int, height: int):
        """Draw stars for space environment"""
        for i in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height - 80)
            brightness = random.randint(100, 255)
            size = random.randint(1, 3)
            draw.ellipse([x, y, x + size, y + size], fill=(brightness, brightness, brightness))

    def draw_grass_texture(self, draw: ImageDraw.ImageDraw, width: int, height: int, bg: dict):
        """Enhanced grass texture"""
        for i in range(0, width, 15):
            for j in range(height - 80, height, 8):
                if (i + j) % 30 == 0:
                    grass_height = random.randint(5, 12)
                    draw.rectangle([i, j - grass_height, i + 2, j], fill=bg["accent"])

    def draw_weather_effect(self, image: Image.Image, weather: str):
        """Add weather particle effects"""
        if weather not in self.weather_effects:
            return
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        effect = self.weather_effects[weather]
        
        for _ in range(effect["particles"]):
            x = random.randint(0, width)
            y = random.randint(0, height - 50)
            
            if weather == "rain":
                # Rain drops
                end_x = x + math.sin(math.radians(effect["angle"])) * 15
                end_y = y + math.cos(math.radians(effect["angle"])) * 15
                draw.line([(x, y), (end_x, end_y)], fill=effect["color"], width=2)
            
            elif weather == "snow":
                # Snowflakes
                size = random.randint(2, 4)
                draw.ellipse([x, y, x + size, y + size], fill=effect["color"])
            
            elif weather == "sandstorm":
                # Sand particles
                size = random.randint(1, 3)
                draw.ellipse([x, y, x + size, y + size], fill=effect["color"])
            
            elif weather == "hail":
                # Hail stones
                size = random.randint(3, 6)
                draw.ellipse([x, y, x + size, y + size], fill=effect["color"])

    def draw_move_effect(self, image: Image.Image, move_type: str, center_x: int, center_y: int, intensity: float = 1.0):
        """Draw visual effect for move type"""
        if move_type.lower() not in self.move_effects:
            return
        
        draw = ImageDraw.Draw(image)
        effect = self.move_effects[move_type.lower()]
        colors = effect["colors"]
        pattern = effect["pattern"]
        
        # Scale effect by intensity
        radius = int(40 * intensity)
        
        if pattern == "burst":
            # Fire/explosion burst
            for i in range(12):
                angle = i * 30
                end_x = center_x + math.cos(math.radians(angle)) * radius
                end_y = center_y + math.sin(math.radians(angle)) * radius
                
                for j, color in enumerate(colors):
                    inner_radius = radius - (j * 10)
                    if inner_radius > 0:
                        inner_x = center_x + math.cos(math.radians(angle)) * inner_radius
                        inner_y = center_y + math.sin(math.radians(angle)) * inner_radius
                        draw.line([(center_x, center_y), (inner_x, inner_y)], fill=color, width=3)
        
        elif pattern == "wave":
            # Water wave effect
            for i in range(5):
                wave_radius = radius - (i * 8)
                if wave_radius > 0:
                    color = colors[i % len(colors)]
                    draw.arc([center_x - wave_radius, center_y - wave_radius//2, 
                             center_x + wave_radius, center_y + wave_radius//2],
                            start=0, end=360, fill=color, width=2)
        
        elif pattern == "bolt":
            # Electric bolt
            for i in range(6):
                angle = random.randint(0, 360)
                bolt_length = random.randint(radius//2, radius)
                end_x = center_x + math.cos(math.radians(angle)) * bolt_length
                end_y = center_y + math.sin(math.radians(angle)) * bolt_length
                
                # Zigzag lightning
                mid_x = (center_x + end_x) // 2 + random.randint(-10, 10)
                mid_y = (center_y + end_y) // 2 + random.randint(-10, 10)
                
                color = colors[i % len(colors)]
                draw.line([(center_x, center_y), (mid_x, mid_y)], fill=color, width=3)
                draw.line([(mid_x, mid_y), (end_x, end_y)], fill=color, width=3)
        
        elif pattern == "spiral":
            # Grass/Dragon spiral
            for i in range(50):
                angle = i * 7.2  # 360/50 = 7.2 degrees per step
                spiral_radius = (i / 50) * radius
                x = center_x + math.cos(math.radians(angle)) * spiral_radius
                y = center_y + math.sin(math.radians(angle)) * spiral_radius
                
                color = colors[i % len(colors)]
                draw.ellipse([x-2, y-2, x+2, y+2], fill=color)
        
        elif pattern == "crystal":
            # Ice crystal formation
            for i in range(8):
                angle = i * 45
                crystal_length = radius
                end_x = center_x + math.cos(math.radians(angle)) * crystal_length
                end_y = center_y + math.sin(math.radians(angle)) * crystal_length
                
                # Draw crystal line
                color = colors[i % len(colors)]
                draw.line([(center_x, center_y), (end_x, end_y)], fill=color, width=2)
                
                # Draw crystal points
                for j in range(3):
                    point_dist = crystal_length * (0.3 + j * 0.3)
                    point_x = center_x + math.cos(math.radians(angle)) * point_dist
                    point_y = center_y + math.sin(math.radians(angle)) * point_dist
                    draw.ellipse([point_x-3, point_y-3, point_x+3, point_y+3], fill=color)
        
        elif pattern == "impact":
            # Fighting impact circles
            for i in range(4):
                impact_radius = radius - (i * 10)
                if impact_radius > 0:
                    color = colors[i % len(colors)]
                    draw.ellipse([center_x - impact_radius, center_y - impact_radius,
                                center_x + impact_radius, center_y + impact_radius],
                               outline=color, width=3)
        
        elif pattern == "ripple":
            # Psychic ripple effect
            for i in range(6):
                ripple_radius = radius - (i * 6)
                if ripple_radius > 0:
                    color = colors[i % len(colors)]
                    # Create ripple with varying opacity
                    draw.ellipse([center_x - ripple_radius, center_y - ripple_radius,
                                center_x + ripple_radius, center_y + ripple_radius],
                               outline=color, width=2)

    async def load_pokemon_sprite(self, pokemon_name: str, pokemon_id: Optional[int] = None, 
                                is_shiny: bool = False, is_back: bool = False) -> Optional[Image.Image]:
        """Load Pokemon sprite with multiple fallback sources"""
        sprite_id = self.get_pokemon_sprite_id(pokemon_name) or pokemon_id
        if not sprite_id:
            return None
        
        # Try local sprites first
        sprite_folder = "full_shiny" if is_shiny else "full"
        local_path = f"{sprite_folder}/{sprite_id}{'_full' if is_shiny else ''}.png"
        
        if os.path.exists(local_path):
            try:
                sprite = Image.open(local_path).convert("RGBA")
                return sprite.resize((220, 220), Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"Error loading local sprite: {e}")
        
        # Online sprite sources
        sprite_type = "back" if is_back else "front"
        shiny_prefix = "shiny/" if is_shiny else ""
        
        urls = [
            f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{shiny_prefix}{sprite_type}/{sprite_id}.png",
            f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{sprite_id}.png"
        ]
        
        for url in urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            sprite_data = await response.read()
                            sprite = Image.open(io.BytesIO(sprite_data)).convert("RGBA")
                            return sprite.resize((220, 220), Image.Resampling.LANCZOS)
            except Exception as e:
                continue
        
        return None

    def add_pokemon_shadow(self, image: Image.Image, x: int, y: int, sprite_width: int, sprite_height: int):
        """Add shadow beneath Pokemon"""
        draw = ImageDraw.Draw(image)
        shadow_y = y + sprite_height - 10
        shadow_width = sprite_width // 2
        
        # Draw elliptical shadow
        draw.ellipse([x + sprite_width//4, shadow_y, x + sprite_width//4 + shadow_width, shadow_y + 20], 
                     fill=(0, 0, 0, 100))

    def enhance_image_quality(self, image: Image.Image) -> Image.Image:
        """Apply post-processing effects for better visual quality"""
        # Slight sharpening
        sharpening_filter = ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)
        image = image.filter(sharpening_filter)
        
        # Enhance contrast slightly
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)
        
        # Enhance colors
        color_enhancer = ImageEnhance.Color(image)
        image = color_enhancer.enhance(1.1)
        
        return image

    async def create_epic_battle_scene(self, user_pokemon: dict, boss_pokemon: dict, 
                                     environment: Optional[str] = None, weather: Optional[str] = None,
                                     move_effect: Optional[dict] = None, is_arena_battle: bool = False,
                                     battle_log: Optional[str] = None) -> discord.File:
        """Create an epic battle scene with all enhancements"""
        
        # Determine environment
        if not environment:
            environment = self.choose_battle_environment(is_arena_battle=is_arena_battle, boss_name=boss_pokemon.get('name', ''))
        
        # Create base image (1000x700 to accommodate battle log area)
        width, height = 1000, 700
        
        # Load background image instead of drawing
        image = self.load_background_image(environment, width, height)
        
        # Add weather effects
        if weather:
            self.draw_weather_effect(image, weather)
        
        # Load and place user Pokemon (left side, back sprite)
        user_x, user_y = 120, height - 350
        user_sprite = await self.load_pokemon_sprite(
            user_pokemon.get('pokemon_name', ''),
            user_pokemon.get('pokemon_id'),
            user_pokemon.get('shiny', False),
            is_back=True
        )
        
        if user_sprite:
            self.add_pokemon_shadow(image, user_x, user_y, 220, 220)
            image.paste(user_sprite, (user_x, user_y), user_sprite)
        else:
            # Fallback silhouette
            draw = ImageDraw.Draw(image)
            draw.ellipse([user_x + 35, user_y + 35, user_x + 185, user_y + 185], fill=(50, 50, 50))
        
        # Load and place boss Pokemon (right side, front sprite)
        boss_x, boss_y = width - 350, height - 400
        boss_sprite = await self.load_pokemon_sprite(
            boss_pokemon.get('name', ''),
            boss_pokemon.get('pokemon_id'),
            boss_pokemon.get('shiny', False),
            is_back=False
        )
        
        if boss_sprite:
            self.add_pokemon_shadow(image, boss_x, boss_y, 220, 220)
            image.paste(boss_sprite, (boss_x, boss_y), boss_sprite)
        else:
            # Fallback silhouette
            draw = ImageDraw.Draw(image)
            draw.ellipse([boss_x + 35, boss_y + 35, boss_x + 185, boss_y + 185], fill=(50, 50, 50))
        
        # Add move effects if provided
        if move_effect:
            effect_x = boss_x + 110 if move_effect['target'] == 'boss' else user_x + 110
            effect_y = boss_y + 110 if move_effect['target'] == 'boss' else user_y + 110
            self.draw_move_effect(image, move_effect['type'], effect_x, effect_y, move_effect.get('intensity', 1.0))
        
        # Add Pokemon info overlays
        draw = ImageDraw.Draw(image)
        
        # Try to load font
        try:
            font_large = ImageFont.truetype("arial.ttf", 32)
            font_medium = ImageFont.truetype("arial.ttf", 24)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
        
        # User Pokemon info (bottom left)
        user_name = user_pokemon.get('nickname') or user_pokemon.get('pokemon_name', 'Unknown')
        user_text = f"{user_name} (Lv.{user_pokemon.get('level', 1)})"
        draw.text((20, height - 60), user_text, fill=(255, 255, 255), font=font_medium, 
                 stroke_width=2, stroke_fill=(0, 0, 0))
        
        # Boss Pokemon info (top right)
        boss_name = boss_pokemon.get('name', 'Unknown')
        boss_text = f"{boss_name} (Lv.{boss_pokemon.get('level', 1)})"
        text_bbox = draw.textbbox((0, 0), boss_text, font=font_medium)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text((width - text_width - 20, 30), boss_text, fill=(255, 255, 255), font=font_medium,
                 stroke_width=2, stroke_fill=(0, 0, 0))
        
        # Enhanced HP bars positioned above Pokemon sprites
        # User HP bar (above user Pokemon)
        user_hp = user_pokemon.get('current_hp', user_pokemon.get('max_hp', 100))
        user_max_hp = user_pokemon.get('max_hp', 100)
        user_hp_ratio = user_hp / user_max_hp if user_max_hp > 0 else 0
        
        user_hp_bar_x = user_x - 20
        user_hp_bar_y = user_y - 50
        
        # HP bar background
        draw.rounded_rectangle([user_hp_bar_x, user_hp_bar_y, user_hp_bar_x + 260, user_hp_bar_y + 30], radius=10, 
                              fill=(50, 50, 50), outline=(255, 255, 255), width=2)
        
        # HP bar fill
        hp_width = int(235 * user_hp_ratio)
        if user_hp_ratio > 0.5:
            hp_color = (0, 255, 0)
        elif user_hp_ratio > 0.2:
            hp_color = (255, 255, 0)
        else:
            hp_color = (255, 0, 0)
        
        if hp_width > 0:
            draw.rounded_rectangle([user_hp_bar_x + 2, user_hp_bar_y + 2, user_hp_bar_x + 2 + hp_width, user_hp_bar_y + 28], radius=8, fill=hp_color)
        
        # User Pokemon name and HP text
        user_name = user_pokemon.get('nickname') or user_pokemon.get('pokemon_name', 'Unknown')
        user_text = f"{user_name} (Lv.{user_pokemon.get('level', 1)})"
        hp_text = f"HP: {user_hp}/{user_max_hp}"
        draw.text((user_hp_bar_x + 5, user_hp_bar_y - 25), user_text, fill=(255, 255, 255), font=font_medium, 
                 stroke_width=2, stroke_fill=(0, 0, 0))
        draw.text((user_hp_bar_x + 5, user_hp_bar_y + 5), hp_text, fill=(255, 255, 255), font=font_medium)
        
        # Boss HP bar (above boss Pokemon)
        boss_hp = boss_pokemon.get('current_hp', boss_pokemon.get('max_hp', 100))
        boss_max_hp = boss_pokemon.get('max_hp', 100)
        boss_hp_ratio = boss_hp / boss_max_hp if boss_max_hp > 0 else 0
        
        boss_hp_bar_x = boss_x - 20
        boss_hp_bar_y = boss_y - 50
        
        # HP bar background
        draw.rounded_rectangle([boss_hp_bar_x, boss_hp_bar_y, boss_hp_bar_x + 260, boss_hp_bar_y + 30], radius=10,
                              fill=(50, 50, 50), outline=(255, 255, 255), width=2)
        
        # HP bar fill
        boss_hp_width = int(235 * boss_hp_ratio)
        if boss_hp_ratio > 0.5:
            hp_color = (0, 255, 0)
        elif boss_hp_ratio > 0.2:
            hp_color = (255, 255, 0)
        else:
            hp_color = (255, 0, 0)
        
        if boss_hp_width > 0:
            draw.rounded_rectangle([boss_hp_bar_x + 2, boss_hp_bar_y + 2, boss_hp_bar_x + 2 + boss_hp_width, boss_hp_bar_y + 28], radius=8, fill=hp_color)
        
        # Boss Pokemon name and HP text
        boss_name = boss_pokemon.get('name', 'Unknown')
        boss_text = f"{boss_name} (Lv.{boss_pokemon.get('level', 1)})"
        boss_hp_text = f"HP: {boss_hp}/{boss_max_hp}"
        draw.text((boss_hp_bar_x + 5, boss_hp_bar_y - 25), boss_text, fill=(255, 255, 255), font=font_medium,
                 stroke_width=2, stroke_fill=(0, 0, 0))
        draw.text((boss_hp_bar_x + 5, boss_hp_bar_y + 5), boss_hp_text, fill=(255, 255, 255), font=font_medium)
        
        # Battle Log Area (beneath Pokemon sprites)
        if battle_log:
            log_area_y = height - 140  # Position at bottom with more margin
            log_area_height = 120  # Increased height for better text spacing
            
            # Draw battle log background
            draw.rounded_rectangle([20, log_area_y, width - 20, log_area_y + log_area_height], 
                                 radius=15, fill=(0, 0, 0, 180), outline=(255, 255, 255), width=2)
            
            # Battle log title
            draw.text((30, log_area_y + 10), "📜 Latest Action", fill=(255, 215, 0), font=font_medium,
                     stroke_width=1, stroke_fill=(0, 0, 0))
            
            # Process battle log text (handle existing newlines first)
            log_text = battle_log
            max_chars_per_line = 75  # Reduced for better fitting
            line_height = 25  # Increased line spacing
            
            # First split by existing newlines (for combined user/boss actions)
            initial_lines = log_text.split('\n')
            final_lines = []
            
            # Then handle word wrapping for each line
            for line in initial_lines:
                if len(line) <= max_chars_per_line:
                    final_lines.append(line)
                else:
                    # Word wrap this line
                    words = line.split(' ')
                    current_line = ""
                    
                    for word in words:
                        if len(current_line + word + " ") <= max_chars_per_line:
                            current_line += word + " "
                        else:
                            if current_line:
                                final_lines.append(current_line.strip())
                            current_line = word + " "
                    
                    if current_line:
                        final_lines.append(current_line.strip())
            
            # Draw each line with proper spacing (limit to 4 lines to fit in area)
            for i, line in enumerate(final_lines[:4]):
                draw.text((30, log_area_y + 40 + i * line_height), line, fill=(255, 255, 255), font=font_medium,
                         stroke_width=1, stroke_fill=(0, 0, 0))
        
        # Apply final enhancements
        image = self.enhance_image_quality(image)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        image.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        
        return discord.File(img_bytes, filename='epic_battle_scene.png') 