import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import random
import json
from typing import Dict, List, Optional
from theme_loader import theme

class QuestSystem(commands.Cog):
    def __init__(self, bot, pokemon_collection, user_profiles):
        self.bot = bot
        self.pokemon_collection = pokemon_collection
        self.user_profiles = user_profiles
        
        # Load boss leaders and their types from boss_data.json
        self.boss_leaders = self.load_boss_leaders()
        
        print(f"DEBUG: Loaded {len(self.boss_leaders)} boss leaders for quests: {list(self.boss_leaders.keys())}")
    
    def load_boss_leaders(self) -> dict:
        """Load boss leaders and their types from boss_data.json"""
        try:
            with open('boss_data.json', 'r', encoding='utf-8') as f:
                boss_data = json.load(f)
            
            boss_leaders = {}
            
            for boss_key, boss_info in boss_data.get("bosses", {}).items():
                # Only include gym leaders (you can add more conditions if needed)
                if "gym_leader" in boss_key.lower():
                    boss_name = boss_info.get("name", "")
                    
                    # Extract the type from the first Pokemon in the team
                    team = boss_info.get("team", [])
                    if team:
                        # Get the first Pokemon's moves to determine type
                        first_pokemon = team[0]
                        moves = first_pokemon.get("moves", [])
                        
                        # Count move types to determine the leader's primary type
                        type_counts = {}
                        for move in moves:
                            move_type = move.get("type", "").lower()
                            if move_type:
                                type_counts[move_type] = type_counts.get(move_type, 0) + 1
                        
                        # Get the most common type, or default to the first move's type
                        if type_counts:
                            primary_type = max(type_counts, key=type_counts.get)
                        elif moves:
                            primary_type = moves[0].get("type", "normal").lower()
                        else:
                            primary_type = "normal"
                        
                        boss_leaders[boss_name] = primary_type
                        print(f"DEBUG: Added {boss_name} ({primary_type} type) to quest rotation")
            
            return boss_leaders
            
        except FileNotFoundError:
            print("Warning: boss_data.json not found, using fallback boss leaders")
            return {
                "Gym Leader Brock": "rock",
                "Gym Leader Misty": "water", 
                "Gym Leader Surge": "electric",
                "Gym Leader Blaine": "fire"
            }
        except Exception as e:
            print(f"Error loading boss leaders: {e}")
            return {
                "Gym Leader Brock": "rock",
                "Gym Leader Misty": "water", 
                "Gym Leader Surge": "electric",
                "Gym Leader Blaine": "fire"
            }
        
        # Quest types and their requirements
        self.quest_types = {
            "boss_battle": {
                "name": "Defeat {boss_name}",
                "description": "Win a battle against {boss_name}",
                "reward": 500,
                "requirement": 1
            },
            "type_catch": {
                "name": "Catch {requirement} {type_name}-type Pokémon",
                "description": "Catch {requirement} Pokémon of {type_name} type",
                "reward": 500,
                "requirement": 5
            },
            "release": {
                "name": "Release {requirement} Pokémon",
                "description": "Release {requirement} Pokémon from your collection",
                "reward": 500,
                "requirement": 5
            }
        }

    def get_quest_date(self) -> str:
        """Get current date in GMT+2 timezone for quest generation"""
        gmt_plus_2 = timezone(timedelta(hours=2))
        current_time = datetime.now(gmt_plus_2)
        date_string = current_time.strftime("%Y-%m-%d")
        print(f"DEBUG: Current quest date: {date_string} (GMT+2)")
        return date_string

    def generate_daily_quests(self, date_string: str) -> Dict:
        """Generate consistent daily quests based on date"""
        # Use date as seed for consistent quest generation
        random.seed(date_string)
        
        # Select boss leader based on date (more predictable rotation)
        boss_names = list(self.boss_leaders.keys())
        # Use hash of date to select boss (more predictable than random)
        date_hash = hash(date_string)
        boss_index = date_hash % len(boss_names)
        boss_name = boss_names[boss_index]
        boss_type = self.boss_leaders[boss_name]
        
        print(f"DEBUG: Generated quests for date {date_string}")
        print(f"DEBUG: Date hash: {date_hash}, Boss index: {boss_index}")
        print(f"DEBUG: Selected boss: {boss_name} ({boss_type} type)")
        
        # Generate the three daily quests
        daily_quests = {
            "boss_battle": {
                "type": "boss_battle",
                "boss_name": boss_name,
                "target": boss_name,
                "progress": 0,
                "completed": False,
                "reward": 500
            },
            "type_catch": {
                "type": "type_catch",
                "pokemon_type": boss_type,
                "target": 5,
                "progress": 0,
                "completed": False,
                "reward": 500
            },
            "release": {
                "type": "release",
                "target": 5,
                "progress": 0,
                "completed": False,
                "reward": 500
            }
        }
        
        # Reset random seed
        random.seed()
        
        return daily_quests

    async def get_user_quests(self, user_id: int) -> Dict:
        """Get or create user's daily quests"""
        current_date = self.get_quest_date()
        
        # Find user's quest data
        user_data = await self.user_profiles.find_one({"user_id": user_id})
        
        if not user_data:
            # Create new user profile
            user_data = {
                "user_id": user_id,
                "coins": 0,
                "diamonds": 0,
                "quests": {},
                "quest_stats": {
                    "releases_today": 0,
                    "catches_today": {},
                    "boss_wins_today": {}
                }
            }
            await self.user_profiles.insert_one(user_data)
        
        # Check if quests need to be reset for new day
        stored_date = user_data.get("quest_date")
        print(f"DEBUG: User {user_id} - Stored date: {stored_date}, Current date: {current_date}")
        
        if "quests" not in user_data or stored_date != current_date:
            print(f"DEBUG: Generating new quests for user {user_id}")
            # Generate new daily quests
            daily_quests = self.generate_daily_quests(current_date)
            
            # Reset daily stats
            await self.user_profiles.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "quest_date": current_date,
                        "quests": daily_quests,
                        "quest_stats": {
                            "releases_today": 0,
                            "catches_today": {},
                            "boss_wins_today": {}
                        },
                        "daily_diamond_claimed": False
                    }
                }
            )
            return daily_quests
        
        return user_data.get("quests", {})

    async def update_quest_progress(self, user_id: int, quest_type: str, **kwargs):
        """Update quest progress for a user"""
        current_date = self.get_quest_date()
        user_quests = await self.get_user_quests(user_id)
        
        if quest_type == "boss_battle":
            boss_name = kwargs.get("boss_name")
            print(f"DEBUG: Checking boss battle quest - received boss_name: '{boss_name}'")
            if boss_name and "boss_battle" in user_quests:
                quest = user_quests["boss_battle"]
                print(f"DEBUG: Quest target: '{quest['target']}', Quest completed: {quest['completed']}")
                if quest["target"] == boss_name and not quest["completed"]:
                    print(f"DEBUG: Boss battle quest match found! Updating progress...")
                    quest["progress"] = 1
                    quest["completed"] = True
                    
                    # Update boss win stats
                    await self.user_profiles.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {f"quests.boss_battle": quest},
                            "$inc": {f"quest_stats.boss_wins_today.{boss_name}": 1}
                        }
                    )
                    return True
                else:
                    print(f"DEBUG: Boss battle quest mismatch - target: '{quest['target']}', received: '{boss_name}', completed: {quest['completed']}")
            else:
                print(f"DEBUG: No boss battle quest found or no boss_name provided")
        
        elif quest_type == "pokemon_catch":
            pokemon_type = kwargs.get("pokemon_type", "").lower()
            if pokemon_type and "type_catch" in user_quests:
                quest = user_quests["type_catch"]
                if quest["pokemon_type"] == pokemon_type and not quest["completed"]:
                    quest["progress"] = min(quest["progress"] + 1, quest["target"])
                    if quest["progress"] >= quest["target"]:
                        quest["completed"] = True
                    
                    # Update catch stats
                    await self.user_profiles.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {f"quests.type_catch": quest},
                            "$inc": {f"quest_stats.catches_today.{pokemon_type}": 1}
                        }
                    )
                    return quest["completed"]
        
        elif quest_type == "pokemon_release":
            if "release" in user_quests:
                quest = user_quests["release"]
                if not quest["completed"]:
                    quest["progress"] = min(quest["progress"] + 1, quest["target"])
                    if quest["progress"] >= quest["target"]:
                        quest["completed"] = True
                    
                    # Update release stats
                    await self.user_profiles.update_one(
                        {"user_id": user_id},
                        {
                            "$set": {f"quests.release": quest},
                            "$inc": {"quest_stats.releases_today": 1}
                        }
                    )
                    return quest["completed"]
        
        return False

    async def check_daily_completion(self, user_id: int) -> bool:
        """Check if user completed all daily quests"""
        user_quests = await self.get_user_quests(user_id)
        
        all_completed = all(
            quest.get("completed", False) 
            for quest in user_quests.values()
        )
        
        if all_completed:
            # Check if diamond reward already claimed
            user_data = await self.user_profiles.find_one({"user_id": user_id})
            if not user_data.get("daily_diamond_claimed", False):
                # Award diamond bonus
                await self.user_profiles.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"diamonds": 1},
                        "$set": {"daily_diamond_claimed": True}
                    }
                )
                return True
        
        return False

    async def claim_quest_reward(self, user_id: int, quest_key: str) -> Optional[int]:
        """Claim reward for a completed quest"""
        user_quests = await self.get_user_quests(user_id)
        
        if quest_key in user_quests:
            quest = user_quests[quest_key]
            if quest["completed"] and not quest.get("reward_claimed", False):
                reward_amount = quest["reward"]
                
                # Mark as claimed and award coins
                await self.user_profiles.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {f"quests.{quest_key}.reward_claimed": True},
                        "$inc": {"coins": reward_amount}
                    }
                )
                
                return reward_amount
        
        return None

    def create_progress_bar(self, current: int, total: int, length: int = 5) -> str:
        """Create a visual progress bar"""
        # Ensure values are integers
        try:
            current = int(current)
            total = int(total)
        except (ValueError, TypeError):
            return "▱" * length
        
        if total == 0:
            return "▱" * length
        
        filled = int((current / total) * length)
        filled = min(filled, length)  # Cap at length
        
        bar = "▰" * filled + "▱" * (length - filled)
        return bar
    
    def get_time_until_reset(self) -> str:
        """Get time remaining until daily reset (midnight GMT+2)"""
        gmt_plus_2 = timezone(timedelta(hours=2))
        now = datetime.now(gmt_plus_2)
        
        # Get next midnight GMT+2
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        time_diff = tomorrow - now
        hours = int(time_diff.total_seconds() // 3600)
        minutes = int((time_diff.total_seconds() % 3600) // 60)
        
        return f"{hours} hours and {minutes} minutes"

    def get_quest_embed(self, user_quests: Dict, user_data: Dict) -> discord.Embed:
        """Create modern quest display embed using theme system"""
        # Create themed embed
        embed = theme.create_embed(
            title="Daily Quests",
            description="Complete them before the timer runs out to receive rewards!",
            color_name="quest"
        )
        
        # Quest progress with theme formatting
        quest_text = ""
        total_completed = 0
        quest_count = len(user_quests)
        
        for quest_key, quest in user_quests.items():
            if quest_key == "boss_battle":
                quest_name = f"Beat {quest['boss_name']}"
                progress_bar = theme.get_progress_bar(quest['progress'], quest['target'])
                reward_text = f"+500 {theme.emoji('currency', 'coins')}"
            elif quest_key == "type_catch":
                quest_name = f"Catch {quest['target']} {quest['pokemon_type'].title()} type Pokémon"
                progress_bar = theme.get_progress_bar(quest['progress'], quest['target'])
                reward_text = f"+500 {theme.emoji('currency', 'coins')}"
            elif quest_key == "release":
                quest_name = f"Release {quest['target']} Pokémon"
                progress_bar = theme.get_progress_bar(quest['progress'], quest['target'])
                reward_text = f"+500 {theme.emoji('currency', 'coins')}"
            
            # Progress text with current/total (ensure integers)
            try:
                progress_current = int(quest['progress']) if not quest['completed'] else int(quest['target'])
                target_value = int(quest['target'])
            except (ValueError, TypeError):
                progress_current = 0
                target_value = 1
            
            progress_text = f"{progress_bar} {progress_current}/{target_value}"
            
            # Check if completed
            if quest["completed"]:
                total_completed += 1
            
            quest_text += f"{theme.format_text('bold', quest_name)}\n"
            quest_text += f"{progress_text}\n"
            quest_text += f"Reward: {reward_text}\n\n"
        
        embed.description = f"{embed.description}\n\n{quest_text}"
        
        # Completion bonus section with themed emojis
        completion_text = f"{theme.format_text('bold', f'Complete Daily Quests {total_completed}/{quest_count}')}"
        if total_completed == quest_count:
            diamond_claimed = user_data.get("daily_diamond_claimed", False)
            if diamond_claimed:
                completion_text += f" {theme.get_separator('arrow')} {theme.emoji('currency', 'diamonds')} Diamond Claimed! {theme.emoji('ui', 'check')}"
            else:
                completion_text += f" {theme.get_separator('arrow')} {theme.emoji('currency', 'diamonds')} {theme.format_text('bold', '1x Diamond')} {theme.emoji('quest', 'reward')}"
        else:
            completion_text += f" {theme.get_separator('arrow')} {theme.emoji('currency', 'diamonds')} {theme.format_text('bold', '1x Diamond')} {theme.emoji('quest', 'reward')}"
        
        embed.description += f"\n{completion_text}\n"
        
        # Time until reset with themed timer emoji
        time_remaining = self.get_time_until_reset()
        embed.description += f"\n{theme.emoji('quest', 'timer')} New quests in {theme.format_text('bold', time_remaining)}"
        
        return embed

    @commands.command(name="quest", aliases=["q", "quests"])
    async def quest_command(self, ctx, action=None):
        """View daily quests and claim rewards"""
        user_id = ctx.author.id
        
        # Get user's quests and profile data
        user_quests = await self.get_user_quests(user_id)
        user_data = await self.user_profiles.find_one({"user_id": user_id})
        
        if action and action.lower() == "claim":
            # Claim all available rewards
            total_claimed = 0
            claimed_rewards = []
            
            for quest_key, quest in user_quests.items():
                if quest["completed"] and not quest.get("reward_claimed", False):
                    reward = await self.claim_quest_reward(user_id, quest_key)
                    if reward:
                        total_claimed += reward
                        claimed_rewards.append(quest_key)
            
            # Check for diamond bonus
            diamond_awarded = await self.check_daily_completion(user_id)
            
            if total_claimed > 0 or diamond_awarded:
                embed = discord.Embed(
                    title="✅ Rewards Claimed!",
                    color=0x00ff00
                )
                
                reward_text = ""
                if total_claimed > 0:
                    reward_text += f"🪙 **{total_claimed:,} coins**\n"
                if diamond_awarded:
                    reward_text += f"💎 **1 diamond** (All quests bonus!)\n"
                
                embed.add_field(
                    name="💰 You Received:",
                    value=reward_text,
                    inline=False
                )
                
                return await ctx.reply(embed=embed)
            else:
                return await ctx.reply("❌ No rewards available to claim!")
        
        # Display quest status
        embed = self.get_quest_embed(user_quests, user_data)
        
        # Add claim button if there are rewards to claim
        unclaimed_rewards = any(
            quest["completed"] and not quest.get("reward_claimed", False)
            for quest in user_quests.values()
        )
        
        all_completed = all(quest["completed"] for quest in user_quests.values())
        diamond_unclaimed = all_completed and not user_data.get("daily_diamond_claimed", False)
        
        if unclaimed_rewards or diamond_unclaimed:
            class QuestClaimView(discord.ui.View):
                def __init__(self, quest_cog, user_id):
                    super().__init__(timeout=300)
                    self.quest_cog = quest_cog
                    self.user_id = user_id
                
                @discord.ui.button(label="💰 Claim Rewards", style=discord.ButtonStyle.green)
                async def claim_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if interaction.user.id != self.user_id:
                        return await interaction.response.send_message("❌ You can't claim someone else's rewards!", ephemeral=True)
                    
                    # Claim rewards
                    user_quests = await self.quest_cog.get_user_quests(self.user_id)
                    total_claimed = 0
                    
                    for quest_key, quest in user_quests.items():
                        if quest["completed"] and not quest.get("reward_claimed", False):
                            reward = await self.quest_cog.claim_quest_reward(self.user_id, quest_key)
                            if reward:
                                total_claimed += reward
                    
                    # Check diamond bonus
                    diamond_awarded = await self.quest_cog.check_daily_completion(self.user_id)
                    
                    # Create success message
                    reward_text = ""
                    if total_claimed > 0:
                        reward_text += f"🪙 **{total_claimed:,} coins**\n"
                    if diamond_awarded:
                        reward_text += f"💎 **1 diamond** (All quests bonus!)\n"
                    
                    embed = discord.Embed(
                        title="✅ Rewards Claimed!",
                        color=0x00ff00
                    )
                    embed.add_field(
                        name="💰 You Received:",
                        value=reward_text,
                        inline=False
                    )
                    
                    await interaction.response.edit_message(embed=embed, view=None)
            
            view = QuestClaimView(self, user_id)
            await ctx.reply(embed=embed, view=view)
        else:
            await ctx.reply(embed=embed)

    # Hook into existing systems for quest progress tracking
    async def on_pokemon_catch(self, user_id: int, pokemon_data: dict):
        """Called when a user catches a Pokemon"""
        # Get Pokemon types from the pokedex
        try:
            with open("pokedex.json", "r", encoding="utf-8") as f:
                pokedex = json.load(f)
            
            # Find the Pokemon data
            pokemon_name = pokemon_data.get("pokemon_name", "").lower()
            poke_data = None
            
            for pokemon_id, data in pokedex.items():
                if data["name"].lower() == pokemon_name:
                    poke_data = data
                    break
            
            if poke_data and "types" in poke_data:
                # Update quest progress for each type
                for pokemon_type in poke_data["types"]:
                    completed = await self.update_quest_progress(
                        user_id, 
                        "pokemon_catch", 
                        pokemon_type=pokemon_type.lower()
                    )
                    
                    if completed:
                        # Send completion notification
                        user = self.bot.get_user(user_id)
                        if user:
                            try:
                                embed = discord.Embed(
                                    title="✅ Quest Complete!",
                                    description=f"You completed the '{pokemon_type.title()}-type catch' quest!",
                                    color=0x00ff00
                                )
                                embed.add_field(name="Reward", value="500 coins (use `!quest claim` to collect)", inline=False)
                                await user.send(embed=embed)
                            except:
                                pass  # User has DMs disabled
        except Exception as e:
            print(f"Error updating catch quest progress: {e}")

    async def on_pokemon_release(self, user_id: int):
        """Called when a user releases a Pokemon"""
        completed = await self.update_quest_progress(user_id, "pokemon_release")
        
        if completed:
            # Send completion notification
            user = self.bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="✅ Quest Complete!",
                        description="You completed the 'Release Pokémon' quest!",
                        color=0x00ff00
                    )
                    embed.add_field(name="Reward", value="500 coins (use `!quest claim` to collect)", inline=False)
                    await user.send(embed=embed)
                except:
                    pass  # User has DMs disabled

    async def on_boss_victory(self, user_id: int, boss_name: str):
        """Called when a user defeats a boss"""
        print(f"DEBUG: Boss victory for user {user_id} against {boss_name}")
        completed = await self.update_quest_progress(
            user_id, 
            "boss_battle", 
            boss_name=boss_name
        )
        
        if completed:
            print(f"DEBUG: Quest completed for user {user_id} - Defeat {boss_name}")
            # Send completion notification
            user = self.bot.get_user(user_id)
            if user:
                try:
                    embed = discord.Embed(
                        title="✅ Quest Complete!",
                        description=f"You completed the 'Defeat {boss_name}' quest!",
                        color=0x00ff00
                    )
                    embed.add_field(name="Reward", value="500 coins (use `!quest claim` to collect)", inline=False)
                    await user.send(embed=embed)
                except:
                    pass  # User has DMs disabled
        else:
            print(f"DEBUG: Quest not completed for user {user_id} - Defeat {boss_name} (quest may not be active or already completed)")

async def setup(bot):
    pokemon_db = bot.pokemon_collection
    user_profiles_db = bot.db["user_profiles"]
    await bot.add_cog(QuestSystem(bot, pokemon_db, user_profiles_db)) 