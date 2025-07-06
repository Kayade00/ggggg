import discord
from discord.ext import commands
import json
import random
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import io
import os

# Load Pokemon data for proper sprite ID lookup
with open('pokedex.json', 'r', encoding='utf-8') as f:
    POKEMON_DATA = json.load(f)

# Load and merge custom Pokemon data (like Shadow Legendaries)
try:
    with open("custom_pokemon.json", "r", encoding="utf-8") as f:
        CUSTOM_POKEMON = json.load(f)
    POKEMON_DATA.update(CUSTOM_POKEMON)
    print(f"Battle system loaded {len(CUSTOM_POKEMON)} custom Pokemon!")
except FileNotFoundError:
    print("No custom_pokemon.json file found - only base Pokemon available")
    CUSTOM_POKEMON = {}

class BattlePokemon:
    def calculate_stat(self, iv, level, base_stat, ev, is_hp=False):
        if is_hp:
            return ((2 * base_stat + iv + (ev // 4)) * level // 100) + level + 10
        return ((2 * base_stat + iv + (ev // 4)) * level // 100) + 5

    def __init__(self, pokemon_data: dict, is_user: bool = False, user_pokemon: dict = None):
        if is_user and user_pokemon:
            # User Pokemon from database
            # Use pokemon_id if available (for custom Pokemon like Shadow Legendaries), 
            # otherwise fall back to pokemon_number for regular Pokemon
            self.pokemon_id = user_pokemon.get('pokemon_id', user_pokemon.get('pokemon_number', 1))
            self.name = user_pokemon['pokemon_name']
            self.level = user_pokemon['level']
            self.nature = user_pokemon.get('nature', 'Hardy')
            self.nickname = user_pokemon.get('nickname')
            
            # Find Pokemon data (includes custom Pokemon like Shadow Legendaries)
            poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == self.name.lower()), None)
            if not poke_data:
                # Fallback to ID-based lookup
                poke_data = POKEMON_DATA.get(str(self.pokemon_id))
                if not poke_data:
                    # Last resort: try regular pokedex
                    with open('pokedex.json', 'r', encoding='utf-8') as f:
                        fallback_pokedex = json.load(f)
                    poke_data = fallback_pokedex.get(str(self.pokemon_id), fallback_pokedex["1"])  # Default to Bulbasaur
            
            base_stats = poke_data['stats']
            
            # Get IVs from user Pokemon data (handle both old and new field names)
            hp_iv = user_pokemon.get('hpiv', user_pokemon.get('hp_iv', 0))
            atk_iv = user_pokemon.get('atkiv', user_pokemon.get('atk_iv', 0))
            def_iv = user_pokemon.get('defiv', user_pokemon.get('def_iv', 0))
            spatk_iv = user_pokemon.get('spatkiv', user_pokemon.get('sp_atk_iv', 0))
            spdef_iv = user_pokemon.get('spdefiv', user_pokemon.get('sp_def_iv', 0))
            spd_iv = user_pokemon.get('spdiv', user_pokemon.get('spd_iv', 0))
            

            
            # Calculate stats exactly like !info command (EVs = 0)
            self.max_hp = self.calculate_stat(hp_iv, self.level, base_stats['hp'], 0, is_hp=True)
            self.attack = self.calculate_stat(atk_iv, self.level, base_stats['attack'], 0)
            self.defense = self.calculate_stat(def_iv, self.level, base_stats['defense'], 0)
            self.sp_attack = self.calculate_stat(spatk_iv, self.level, base_stats['special-attack'], 0)
            self.sp_defense = self.calculate_stat(spdef_iv, self.level, base_stats['special-defense'], 0)
            self.speed = self.calculate_stat(spd_iv, self.level, base_stats['speed'], 0)
            

            
            # Get moves from user Pokemon data
            moves_list = []
            move_fields = ['move1', 'move2', 'move3', 'move4']
            
            # Load moves data for move details
            try:
                with open('moves_data.json', 'r', encoding='utf-8') as f:
                    moves_data = json.load(f)
            except:
                moves_data = {}
            
            for field in move_fields:
                move_name = user_pokemon.get(field, 'None')
                if move_name and move_name != 'None':
                    # Get move details from moves_data.json or use defaults
                    move_found = False
                    
                    # Try exact match first
                    if move_name in moves_data:
                        move_data = moves_data[move_name]
                        move_found = True
                    else:
                        # Try lowercase match
                        move_name_lower = move_name.lower()
                        for key, data in moves_data.items():
                            if data.get("name", "").lower().replace("-", " ") == move_name_lower.replace("-", " "):
                                move_data = data
                                move_found = True
                                break
                    
                    if move_found:
                        power = move_data.get("power")
                        if power is None:  # Status moves have null power
                            power = 0
                        
                        moves_list.append({
                            "name": move_name,
                            "type": move_data.get("type", "Normal").capitalize(),
                            "power": power,
                            "accuracy": move_data.get("accuracy", 100),
                            "pp": move_data.get("pp", 35)
                        })
                    else:
                        # Default move if not in database
                        moves_list.append({
                            "name": move_name,
                            "type": "Normal",
                            "power": 40,
                            "accuracy": 100,
                            "pp": 35
                        })
            
            # If no moves, add Tackle as default
            if not moves_list:
                # Try to get Tackle from moves_data.json
                tackle_found = False
                for key, data in moves_data.items():
                    if data.get("name", "").lower() == "tackle":
                        tackle_power = data.get("power", 40)
                        if tackle_power is None:
                            tackle_power = 40
                        moves_list.append({
                            "name": "Tackle",
                            "type": data.get("type", "Normal").capitalize(),
                            "power": tackle_power,
                            "accuracy": data.get("accuracy", 100),
                            "pp": data.get("pp", 35)
                        })
                        tackle_found = True
                        break
                
                if not tackle_found:
                    moves_list.append({"name": "Tackle", "type": "Normal", "power": 40, "accuracy": 100, "pp": 35})
            
            self.moves = moves_list
        else:
            # Boss Pokemon
            self.pokemon_id = pokemon_data['pokemon_id']
            self.name = pokemon_data['name']
            self.level = pokemon_data['level']
            self.nature = pokemon_data['nature']
            self.ability = pokemon_data['ability']
            self.nickname = None
            
            # Boss stats
            self.max_hp = pokemon_data['stats']['hp']
            self.attack = pokemon_data['stats']['attack']
            self.defense = pokemon_data['stats']['defense']
            self.sp_attack = pokemon_data['stats']['sp_attack']
            self.sp_defense = pokemon_data['stats']['sp_defense']
            self.speed = pokemon_data['stats']['speed']
            
            self.moves = pokemon_data['moves']
        
        self.current_hp = self.max_hp
        self.status = None
        self.fainted = False

    def get_display_name(self):
        return self.nickname if self.nickname else self.name

    def take_damage(self, damage: int):
        self.current_hp = max(0, self.current_hp - damage)
        if self.current_hp == 0:
            self.fainted = True

    def heal(self, amount: int):
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        if self.current_hp > 0:
            self.fainted = False

class BattleView(discord.ui.View):
    def __init__(self, battle_manager, user_id: int):
        super().__init__(timeout=300)
        self.battle_manager = battle_manager
        self.user_id = user_id
        
        # Add move buttons for current Pokemon
        current_pokemon = battle_manager.user_team[battle_manager.user_active]
        for i, move in enumerate(current_pokemon.moves):
            if i < 4:  # Maximum 4 moves
                button = discord.ui.Button(
                    label=f"{move['name']} ({move['power']} PWR)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"move_{i}",
                    row=i // 2  # 2 buttons per row (rows 0-1)
                )
                button.callback = self.create_move_callback(i)
                self.add_item(button)
        
        # Add switch dropdown
        alive_pokemon = [p for i, p in enumerate(battle_manager.user_team) if not p.fainted and i != battle_manager.user_active]
        if alive_pokemon:
            switch_options = []
            for i, pokemon in enumerate(alive_pokemon):
                # Find actual index in team
                actual_index = next(j for j, p in enumerate(battle_manager.user_team) if p == pokemon)
                switch_options.append(discord.SelectOption(
                    label=f"{pokemon.get_display_name()}",
                    description=f"HP: {pokemon.current_hp}/{pokemon.max_hp}",
                    value=str(actual_index),
                    emoji="🔄"
                ))
            
            if switch_options:
                switch_select = discord.ui.Select(
                    placeholder="Switch Pokémon...",
                    options=switch_options,
                    row=2  # Row 2 for switch dropdown
                )
                switch_select.callback = self.switch_callback
                self.add_item(switch_select)
        
        # Add flee button
        flee_button = discord.ui.Button(
            label="Flee",
            style=discord.ButtonStyle.danger,
            emoji="🏃",
            row=3  # Row 3 for flee button to avoid width conflict
        )
        flee_button.callback = self.flee_callback
        self.add_item(flee_button)

    def create_move_callback(self, move_index: int):
        async def move_callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your battle!", ephemeral=True)
                return
            
            current_pokemon = self.battle_manager.user_team[self.battle_manager.user_active]
            if current_pokemon.fainted:
                await interaction.response.send_message("Your Pokémon has fainted!", ephemeral=True)
                return
                
            await self.battle_manager.process_turn(interaction, "move", move_index)
        return move_callback

    async def switch_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return

        # Get the select component that triggered this callback
        select = [item for item in self.children if isinstance(item, discord.ui.Select) and item.placeholder == "Switch Pokémon..."][0]
        switch_index = int(select.values[0])
        await self.battle_manager.process_turn(interaction, "switch", switch_index)

    async def flee_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your battle!", ephemeral=True)
            return
        
        await self.battle_manager.flee_battle(interaction)



class BattleManager:
    def __init__(self, user_id: int, boss_data: dict, user_team: List[dict]):
        self.user_id = user_id
        self.boss_data = boss_data
        self.battle_log = []
        self.turn_count = 0
        self.battle_message = None  # Store reference to main battle message
        
        # Initialize teams
        self.user_team = [BattlePokemon(None, is_user=True, user_pokemon=p) for p in user_team]
        self.boss_team = [BattlePokemon(p) for p in boss_data['team']]
        
        self.user_active = 0
        self.boss_active = 0
        
        # Battle visuals - set once and persist throughout battle
        self.battle_environment = None
        self.battle_weather = None
        
        # Turn action tracking for combined log
        self.current_turn_user_action = ""
        self.current_turn_boss_action = ""
        
        # Load complete type effectiveness chart from file
        try:
            with open('type_chart.json', 'r', encoding='utf-8') as f:
                self.type_chart = json.load(f)
        except FileNotFoundError:
            print("Warning: type_chart.json not found, using fallback type chart")
            # Fallback type chart (simplified)
            self.type_chart = {
                "Normal": {"Rock": 0.5, "Steel": 0.5, "Ghost": 0},
                "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2, "Bug": 2, "Rock": 0.5, "Dragon": 0.5, "Steel": 2},
                "Water": {"Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2, "Rock": 2, "Dragon": 0.5},
                "Electric": {"Water": 2, "Electric": 0.5, "Grass": 0.5, "Ground": 0, "Flying": 2, "Dragon": 0.5},
                "Grass": {"Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5, "Flying": 0.5, "Bug": 0.5, "Rock": 2, "Dragon": 0.5, "Steel": 0.5},
                "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 0.5, "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": 0.5},
                "Fighting": {"Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2, "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": 0.5},
                "Poison": {"Grass": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0, "Fairy": 2},
                "Ground": {"Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2, "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2},
                "Flying": {"Electric": 0.5, "Grass": 2, "Ice": 0.5, "Fighting": 2, "Bug": 2, "Rock": 0.5, "Steel": 0.5},
                "Psychic": {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0, "Steel": 0.5},
                "Bug": {"Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2, "Ghost": 0.5, "Dark": 2, "Steel": 0.5, "Fairy": 0.5},
                "Rock": {"Fire": 2, "Ice": 2, "Fighting": 0.5, "Ground": 0.5, "Flying": 2, "Bug": 2, "Steel": 0.5},
                "Ghost": {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5},
                "Dragon": {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
                "Dark": {"Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5, "Fairy": 0.5},
                "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2, "Rock": 2, "Steel": 0.5, "Fairy": 2},
                "Fairy": {"Fire": 0.5, "Fighting": 2, "Poison": 0.5, "Dragon": 2, "Dark": 2, "Steel": 0.5}
            }

    def get_type_effectiveness(self, move_type: str, defender_types: List[str]) -> float:
        effectiveness = 1.0
        move_type_lower = move_type.lower()
        
        for def_type in defender_types:
            def_type_lower = def_type.lower()
            if move_type_lower in self.type_chart and def_type_lower in self.type_chart[move_type_lower]:
                type_multiplier = self.type_chart[move_type_lower][def_type_lower]
                effectiveness *= type_multiplier
        
        return effectiveness

    def calculate_damage(self, attacker: BattlePokemon, defender: BattlePokemon, move: dict) -> Tuple[int, float]:
        if move['power'] == 0:
            return 0, 1.0

        # Find defender types by name (includes custom Pokemon like Shadow Legendaries)
        defender_poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == defender.name.lower()), None)
        if defender_poke_data:
            defender_types = defender_poke_data['types']
        else:
            # Fallback to ID-based lookup
            defender_poke_data = POKEMON_DATA.get(str(defender.pokemon_id))
            if defender_poke_data:
                defender_types = defender_poke_data['types']
            else:
                # Last resort: assume Normal type
                defender_types = ["Normal"]
        
        # Find attacker types by name (includes custom Pokemon like Shadow Legendaries)
        attacker_poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == attacker.name.lower()), None)
        if attacker_poke_data:
            attacker_types = attacker_poke_data['types']
        else:
            # Fallback to ID-based lookup
            attacker_poke_data = POKEMON_DATA.get(str(attacker.pokemon_id))
            if attacker_poke_data:
                attacker_types = attacker_poke_data['types']
            else:
                # Last resort: assume Normal type
                attacker_types = ["Normal"]

        # Determine if move is physical or special from moves_data.json
        try:
            with open('moves_data.json', 'r', encoding='utf-8') as f:
                moves_data = json.load(f)
            
            move_data = None
            # Find move data
            for key, data in moves_data.items():
                if data.get("name", "").lower().replace("-", " ") == move['name'].lower().replace("-", " "):
                    move_data = data
                    break
            
            if move_data and 'damage_class' in move_data:
                is_physical = move_data['damage_class'] == 'physical'
            else:
                # Fallback to type-based determination
                physical_types = ["normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel"]
                is_physical = move['type'].lower() in physical_types
        except:
            # Fallback if moves_data.json fails
            physical_types = ["normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel"]
            is_physical = move['type'].lower() in physical_types

        if is_physical:
            attack = attacker.attack
            defense = defender.defense
        else:
            attack = attacker.sp_attack
            defense = defender.sp_defense

        # Gen 5+ damage formula: ((((2 * Level / 5 + 2) * Power * Attack / Defense) / 50) + 2) * modifiers
        level = attacker.level
        power = move['power']
        
        # Base damage calculation
        damage = ((((2 * level / 5 + 2) * power * attack / defense) / 50) + 2)
        
        # Type effectiveness
        effectiveness = self.get_type_effectiveness(move['type'], defender_types)
        damage *= effectiveness
        
        # STAB (Same Type Attack Bonus) - 1.5x if move type matches attacker type
        stab_multiplier = 1.0
        if move['type'].lower() in [t.lower() for t in attacker_types]:
            stab_multiplier = 1.5
            damage *= stab_multiplier

        # Debug logging for battle calculations
        print(f"DEBUG: {attacker.name} used {move['name']}")
        print(f"  Attacker types: {attacker_types}")
        print(f"  Defender types: {defender_types}")
        print(f"  Move type: {move['type']}")
        print(f"  Base damage: {((((2 * level / 5 + 2) * power * attack / defense) / 50) + 2):.2f}")
        print(f"  Type effectiveness: {effectiveness}x")
        print(f"  STAB: {stab_multiplier}x")
        print(f"  Final damage: {int(damage)}")

        return int(damage), effectiveness

    async def process_turn(self, interaction: discord.Interaction, action: str, action_data: int):
        # Store original Pokemon that are queuing moves
        original_user_pokemon = self.user_team[self.user_active]
        original_boss_pokemon = self.boss_team[self.boss_active]

        if action == "move":
            user_move = original_user_pokemon.moves[action_data]
            user_action = ("move", user_move)
        elif action == "switch":
            user_action = ("switch", action_data)
        else:
            return

        # Boss action (random move)
        boss_move = random.choice(original_boss_pokemon.moves)
        boss_action = ("move", boss_move)

        # Determine turn order
        user_speed = original_user_pokemon.speed if action == "move" else float('inf')  # Switching is priority
        boss_speed = original_boss_pokemon.speed

        if user_speed >= boss_speed:
            first_action = ("user", user_action)
            second_action = ("boss", boss_action)
        else:
            first_action = ("boss", boss_action)
            second_action = ("user", user_action)

        # Execute first action
        first_actor, first_action_info = first_action
        if first_actor == "user":
            await self.execute_user_action(first_action_info)
        else:
            await self.execute_boss_action(first_action_info)

        # Check for fainted Pokemon after first action
        first_turn_faint = False
        if self.user_team[self.user_active].fainted:
            alive_user = [i for i, p in enumerate(self.user_team) if not p.fainted]
            if not alive_user:
                await self.end_battle(interaction, False)
                return
            # Force switch if there are alive Pokemon
            self.user_active = alive_user[0]
            self.battle_log.append(f"Go! {self.user_team[self.user_active].get_display_name()}!")
            first_turn_faint = True

        if self.boss_team[self.boss_active].fainted:
            alive_boss = [i for i, p in enumerate(self.boss_team) if not p.fainted]
            if not alive_boss:
                await self.end_battle(interaction, True)
                return
            # Boss switches to next Pokemon
            self.boss_active = alive_boss[0]
            self.battle_log.append(f"{self.boss_data['name']} sent out {self.boss_team[self.boss_active].name}!")
            first_turn_faint = True

        # Execute second action only if the acting Pokémon is still alive
        second_actor, second_action_info = second_action
        action_type, _ = second_action_info
        
        # Check if the Pokémon that was supposed to act second is still alive
        should_execute_second = True
        if second_actor == "user" and action_type == "move":
            # Check if the user's active Pokemon was the one that originally queued this action
            # If user Pokemon fainted and was switched, don't execute the old move
            if first_turn_faint and first_actor == "boss":
                should_execute_second = False
                move_name = second_action_info[1]['name'] if len(second_action_info) > 1 and isinstance(second_action_info[1], dict) else "its move"
                self.battle_log.append(f"{original_user_pokemon.get_display_name()} fainted before it could use {move_name}!")
        elif second_actor == "boss" and action_type == "move":
            # Check if the boss's active Pokemon was the one that originally queued this action
            # If boss Pokemon fainted and was switched, don't execute the old move
            if first_turn_faint and first_actor == "user":
                should_execute_second = False
                move_name = second_action_info[1]['name'] if len(second_action_info) > 1 and isinstance(second_action_info[1], dict) else "its move"
                self.battle_log.append(f"{original_boss_pokemon.name} fainted before it could use {move_name}!")
        
        if should_execute_second:
            if second_actor == "user":
                await self.execute_user_action(second_action_info)
            else:
                await self.execute_boss_action(second_action_info)

        # Check for fainted Pokemon after second action (if executed)
        if should_execute_second:
            if self.user_team[self.user_active].fainted:
                alive_user = [i for i, p in enumerate(self.user_team) if not p.fainted]
                if not alive_user:
                    await self.end_battle(interaction, False)
                    return
                # Force switch if there are alive Pokemon
                self.user_active = alive_user[0]
                self.battle_log.append(f"Go! {self.user_team[self.user_active].get_display_name()}!")

            if self.boss_team[self.boss_active].fainted:
                alive_boss = [i for i, p in enumerate(self.boss_team) if not p.fainted]
                if not alive_boss:
                    await self.end_battle(interaction, True)
                    return
                # Boss switches to next Pokemon
                self.boss_active = alive_boss[0]
                self.battle_log.append(f"{self.boss_data['name']} sent out {self.boss_team[self.boss_active].name}!")

        # Combine both actions into a single log entry
        combined_log = ""
        if self.current_turn_user_action:
            combined_log += self.current_turn_user_action
        if self.current_turn_boss_action:
            if combined_log:
                combined_log += "\n" + self.current_turn_boss_action
            else:
                combined_log = self.current_turn_boss_action
        
        if combined_log:
            self.battle_log.append(combined_log)
        
        # Reset action tracking for next turn
        self.current_turn_user_action = ""
        self.current_turn_boss_action = ""
        
        self.turn_count += 1
        await self.update_battle_display(interaction)

    async def execute_user_action(self, action_info):
        action_type, data = action_info
        user_pokemon = self.user_team[self.user_active]
        boss_pokemon = self.boss_team[self.boss_active]

        if action_type == "move":
            move = data
            damage, effectiveness = self.calculate_damage(user_pokemon, boss_pokemon, move)
            boss_pokemon.take_damage(damage)
            
            effectiveness_text = ""
            if effectiveness > 1:
                effectiveness_text = " It's super effective!"
            elif effectiveness < 1 and effectiveness > 0:
                effectiveness_text = " It's not very effective..."
            elif effectiveness == 0:
                effectiveness_text = " It doesn't affect the target..."

            # Store user action for combined log
            self.current_turn_user_action = f"{user_pokemon.get_display_name()} used {move['name']}! Dealt {damage} damage.{effectiveness_text}"

        elif action_type == "switch":
            new_index = data
            self.user_active = new_index
            self.current_turn_user_action = f"Go! {self.user_team[self.user_active].get_display_name()}!"

    async def execute_boss_action(self, action_info):
        action_type, data = action_info
        boss_pokemon = self.boss_team[self.boss_active]
        user_pokemon = self.user_team[self.user_active]

        if action_type == "move":
            move = data
            damage, effectiveness = self.calculate_damage(boss_pokemon, user_pokemon, move)
            user_pokemon.take_damage(damage)
            
            effectiveness_text = ""
            if effectiveness > 1:
                effectiveness_text = " It's super effective!"
            elif effectiveness < 1 and effectiveness > 0:
                effectiveness_text = " It's not very effective..."
            elif effectiveness == 0:
                effectiveness_text = " It doesn't affect the target..."

            # Store boss action for combined log
            self.current_turn_boss_action = f"{boss_pokemon.name} used {move['name']}! Dealt {damage} damage.{effectiveness_text}"

    async def update_battle_display(self, interaction: discord.Interaction):
        view = BattleView(self, self.user_id)
        battle_image = await self.create_battle_image()
        
        # If we have a stored battle message, edit it directly
        if self.battle_message:
            try:
                await self.battle_message.edit(content="", view=view, attachments=[battle_image])
                # Just respond to the interaction to acknowledge it
                if not interaction.response.is_done():
                    await interaction.response.defer()
                return
            except (discord.NotFound, discord.HTTPException):
                # Battle message was deleted, fall back to interaction
                self.battle_message = None
        
        # Fallback to interaction-based updates
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(content="", view=view, attachments=[battle_image])
            else:
                await interaction.edit_original_response(content="", view=view, attachments=[battle_image])
        except discord.NotFound:
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    await interaction.followup.edit_message(interaction.message.id, content="", view=view, attachments=[battle_image])
                else:
                    new_message = await interaction.followup.send(content="", view=view, file=battle_image)
                    self.battle_message = new_message
            except (discord.NotFound, discord.HTTPException):
                new_message = await interaction.followup.send(content="", view=view, file=battle_image)
                self.battle_message = new_message
        except discord.HTTPException:
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    await interaction.followup.edit_message(interaction.message.id, content="", view=view, attachments=[battle_image])
                else:
                    new_message = await interaction.followup.send(content="", view=view, file=battle_image)
                    self.battle_message = new_message
            except (discord.NotFound, discord.HTTPException):
                new_message = await interaction.followup.send(content="", view=view, file=battle_image)
                self.battle_message = new_message





    def get_pokemon_sprite_id(self, pokemon_name: str) -> Optional[int]:
        """Get the correct sprite ID for a Pokemon by looking up its name in pokedex data"""
        poke_data = next((d for d in POKEMON_DATA.values() if isinstance(d, dict) and d.get("name", "").lower() == pokemon_name.lower()), None)
        if poke_data and 'id' in poke_data:
            return poke_data['id']
        return None

    async def create_battle_image(self) -> discord.File:
        """Create an epic battle scene image with enhanced visuals"""
        from .battle_visuals import BattleVisualEffects
        
        user_pokemon = self.user_team[self.user_active]
        boss_pokemon = self.boss_team[self.boss_active]
        
        # Create enhanced visuals
        visual_effects = BattleVisualEffects()
        
        # Set environment and weather once at battle start, then reuse
        if self.battle_environment is None:
            # Check if this is an arena battle
            boss_name = self.boss_data.get('name', '').lower()
            is_arena_battle = 'arena' in boss_name or 'champion' in boss_name or 'elite' in boss_name
            
            # Choose environment once and store it
            self.battle_environment = visual_effects.choose_battle_environment(is_arena_battle=is_arena_battle)
            
            # Set weather once and store it (but not for arena battles)
            if not is_arena_battle:
                if 'ice' in boss_name:
                    self.battle_weather = 'snow'
                elif 'fire' in boss_name:
                    self.battle_weather = None  # Clear skies for desert/volcano environment
                elif random.random() < 0.3:  # 30% chance of weather
                    self.battle_weather = random.choice(['rain', 'snow', 'sandstorm'])
                else:
                    self.battle_weather = None
            else:
                self.battle_weather = None
        
        # Prepare Pokemon data for the visual system
        user_data = {
            'pokemon_name': user_pokemon.name,
            'pokemon_id': user_pokemon.pokemon_id,
            'nickname': user_pokemon.nickname,
            'level': user_pokemon.level,
            'current_hp': user_pokemon.current_hp,
            'max_hp': user_pokemon.max_hp,
            'shiny': getattr(user_pokemon, 'shiny', False)
        }
        
        boss_data = {
            'name': boss_pokemon.name,
            'pokemon_id': boss_pokemon.pokemon_id,
            'level': boss_pokemon.level,
            'current_hp': boss_pokemon.current_hp,
            'max_hp': boss_pokemon.max_hp,
            'shiny': getattr(boss_pokemon, 'shiny', False)
        }
        
        # Check if this is an arena battle (for the visual effects system)
        boss_name = self.boss_data.get('name', '').lower()
        is_arena_battle = 'arena' in boss_name or 'champion' in boss_name or 'elite' in boss_name
        
        # Get the latest battle log entry
        latest_log = self.battle_log[-1] if self.battle_log else "Battle started!"
        
        # Create the epic battle scene using stored environment and weather
        return await visual_effects.create_epic_battle_scene(
            user_data, boss_data, self.battle_environment, self.battle_weather, is_arena_battle=is_arena_battle, battle_log=latest_log
        )

    async def flee_battle(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Battle Ended",
            description="You fled from the battle!",
            color=0x808080
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def end_battle(self, interaction: discord.Interaction, victory: bool):
        # Remove from active battles
        battle_cog = interaction.client.get_cog("Battle")
        if battle_cog and self.user_id in battle_cog.active_battles:
            del battle_cog.active_battles[self.user_id]
        
        if victory:
            embed = discord.Embed(
                title="🎉 Victory!",
                description=f"You defeated {self.boss_data['name']}!\n\n💰 Earned {self.boss_data['reward_credits']} credits!",
                color=0x00FF00
            )
            
            # Award credits to user
            try:
                user_profiles_db = interaction.client.db["user_profiles"]
                
                # Ensure user profile exists
                profile = await user_profiles_db.find_one({"user_id": self.user_id})
                if not profile:
                    new_profile = {
                        "user_id": self.user_id,
                        "coins": self.boss_data['reward_credits'],
                        "diamonds": 0,
                        "created_at": datetime.utcnow()
                    }
                    await user_profiles_db.insert_one(new_profile)
                else:
                    # Update existing profile
                    await user_profiles_db.update_one(
                        {"user_id": self.user_id},
                        {"$inc": {"coins": self.boss_data['reward_credits']}}
                    )
                
                embed.add_field(
                    name="💰 Rewards",
                    value=f"**{self.boss_data['reward_credits']} coins** added to your balance!",
                    inline=False
                )
                
                # Update quest progress for boss victory
                try:
                    quest_cog = interaction.client.get_cog("QuestSystem")
                    if quest_cog:
                        # Extract gym leader name for quest matching
                        boss_name = self.boss_data['name']
                        if "Gym Leader" in boss_name:
                            # Convert "Gym Leader Brock" -> "Brock", "Gym Leader Surge" -> "Lt. Surge"
                            short_name = boss_name.replace("Gym Leader ", "")
                            if short_name == "Surge":
                                short_name = "Lt. Surge"
                            await quest_cog.on_boss_victory(self.user_id, short_name)
                        else:
                            await quest_cog.on_boss_victory(self.user_id, boss_name)
                except Exception as e:
                    print(f"Error updating quest progress: {e}")
                
            except Exception as e:
                print(f"Error awarding credits: {e}")
                embed.add_field(
                    name="⚠️ Reward Error",
                    value="There was an error processing your reward. Please contact an admin.",
                    inline=False
                )
            
        else:
            embed = discord.Embed(
                title="💀 Defeat...",
                description=f"{self.boss_data['name']} defeated your team!",
                color=0xFF0000
            )
            embed.add_field(
                name="💡 Tip",
                value="Train your Pokémon, learn better moves, and try again!",
                inline=False
            )

        try:
            await interaction.response.edit_message(embed=embed, view=None)
        except discord.NotFound:
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                await interaction.followup.send(embed=embed, view=None)
        except discord.HTTPException:
            try:
                await interaction.followup.edit_message(interaction.message.id, embed=embed, view=None)
            except (discord.NotFound, discord.HTTPException):
                await interaction.followup.send(embed=embed, view=None)

class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_battles = {}
        
        # Load boss data
        with open('boss_data.json', 'r', encoding='utf-8') as f:
            self.boss_data = json.load(f)



class BossSelectionView(discord.ui.View):
    def __init__(self, battle_cog, user_id: int, selected_pokemon: list = None):
        super().__init__(timeout=60)
        self.battle_cog = battle_cog
        self.user_id = user_id
        self.selected_pokemon = selected_pokemon or []

        # Dynamically build options from boss_data
        options = []
        for boss_key, boss in self.battle_cog.boss_data['bosses'].items():
            label = boss.get('name', boss_key.replace('_', ' ').title())
            desc = f"{boss.get('title', '')} (Reward: {boss.get('reward_credits', '?')} credits)"
            emoji = None
            # Try to pick an emoji based on type or name (optional, fallback to None)
            if 'rock' in label.lower():
                emoji = '🪨'
            elif 'water' in label.lower() or 'misty' in label.lower():
                emoji = '💧'
            elif 'electric' in label.lower() or 'surge' in label.lower():
                emoji = '⚡'
            elif 'fire' in label.lower() or 'blaine' in label.lower():
                emoji = '🔥'
            # Add more emoji logic as needed
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=boss_key,
                emoji=emoji
            ))
        select = discord.ui.Select(
            placeholder="Choose a boss to battle...",
            options=options
        )
        select.callback = self.boss_select
        self.add_item(select)

    async def boss_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your selection!", ephemeral=True)
            return

        select = [item for item in self.children if isinstance(item, discord.ui.Select)][0]
        boss_key = select.values[0]
        boss_data = self.battle_cog.boss_data['bosses'][boss_key]
        
        # Use selected Pokemon if available, otherwise get user's team from database
        if self.selected_pokemon:
            user_team = []
            for pokemon in self.selected_pokemon:
                # Include all Pokemon data including IVs
                user_team.append(pokemon)  # Pass the entire Pokemon data
        else:
            # Fallback: get user's first 3 Pokemon from database
            user_pokemon_cursor = self.battle_cog.bot.pokemon_collection.find({"user_id": self.user_id}).limit(3)
            user_pokemon_list = await user_pokemon_cursor.to_list(length=3)
            
            if len(user_pokemon_list) < 3:
                await interaction.response.send_message("❌ You need at least 3 Pokémon to battle!", ephemeral=True)
                return
            
            # Pass the entire Pokemon data including IVs
            user_team = user_pokemon_list

        # Start battle
        battle_manager = BattleManager(self.user_id, boss_data, user_team)
        self.battle_cog.active_battles[self.user_id] = battle_manager

        # Initial battle display
        view = BattleView(battle_manager, self.user_id)
        battle_image = await battle_manager.create_battle_image()
        
        await interaction.response.edit_message(content="", view=view, attachments=[battle_image])
        
        # Store the battle message for future updates
        battle_manager.battle_message = await interaction.original_response()

async def setup(bot):
    await bot.add_cog(Battle(bot)) 