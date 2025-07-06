from discord.ext import commands
from discord import app_commands, Embed, Interaction
from discord.ui import View, Button
import discord
from typing import Optional



    


class PokemonSlash(commands.Cog):
    def __init__(self, bot, collection, pokedex):
        self.bot = bot
        self.collection = collection
        self.pokedex = pokedex

    @app_commands.command(name="pokemon", description="View your Pokémon with optional filters")
    @app_commands.describe(
        name="Filter by Pokémon name",
        nickname="Filter by Pokémon nickname",
        nature="Filter by nature",
        level="Filter by level (exact match)",
        ivs="Filter by total IV % (e.g., 85)",
        stats="Filter by base stat (e.g., HP, Speed)",
        favorite="Show only favorited Pokémon (toggle)",
        shiny="Show only shiny Pokémon (toggle)"
    )
    async def pokemon(
        self,
        interaction: Interaction,
        name: Optional[str] = None,
        nickname: Optional[str] = None,
        nature: Optional[str] = None,
        level: Optional[int] = None,
        ivs: Optional[float] = None,
        stats: Optional[str] = None,
        favorite: bool = False,
        shiny: bool = False
    ):
        await interaction.response.defer()

        query = {"user_id": interaction.user.id}
        pokemon_list = await self.collection.find(query).sort("pokemon_number", 1).to_list(length=None)

        if not pokemon_list:
            return await interaction.followup.send("❌ You don't have any Pokémon yet. Use `/start` to begin.", ephemeral=True)

        def matches(p):
            if name and p["pokemon_name"].lower() != name.lower():
                return False
            if nickname and str(p.get("nickname", "")).lower() != nickname.lower():
                return False
            if nature and p.get("nature", "").lower() != nature.lower():
                return False
            if level and p.get("level") != level:
                return False
            if favorite and not p.get("favorite", False):
                return False
            if shiny and not p.get("shiny", False):
                return False
            if ivs is not None:
                total_iv = sum([p.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
                iv_percent = round((total_iv / 186) * 100, 1)
                if iv_percent < ivs:
                    return False
            if stats:
                poke_data = next((v for v in self.pokedex.values() if v["name"].lower() == p["pokemon_name"].lower()), None)
                if not poke_data or stats.lower() not in poke_data.get("stats", {}):
                    return False
            return True

        pokemon_list = list(filter(matches, pokemon_list))

        if not pokemon_list:
            return await interaction.followup.send("❌ No Pokémon found matching those filters.", ephemeral=True)

        def format_pokemon_line(p):
            poke_data = next((v for v in self.pokedex.values() if v["name"].lower() == p["pokemon_name"].lower().replace("-", " ")), None)
            emoji = ""
            if poke_data and 'id' in poke_data:
                emoji = self.bot.pokemon_emojis.get(str(poke_data["id"]), "")
                

            nickname_text = f'"{p["nickname"]}"' if p.get("nickname") else p["pokemon_name"]
            level = p["level"]
            total_iv = sum([p.get(iv, 0) for iv in ["hp_iv", "atk_iv", "def_iv", "sp_atk_iv", "sp_def_iv", "spd_iv"]])
            iv_percent = round((total_iv / 186) * 100, 1)

            status = ""
            if p.get("favorite"): status += "❤️"
            if p.get("shiny"): status += "✨"
            if p.get("xp_blocker"): status += "🚫"

            return f"`{p['pokemon_number']:>3}.` {emoji} {status} **{nickname_text}** • Lv. {level} • {iv_percent}%"

        per_page = 20
        pages = [pokemon_list[i:i+per_page] for i in range(0, len(pokemon_list), per_page)]
        embeds = []

        for i, page in enumerate(pages):
            embed = Embed(
                title=f"{interaction.user.display_name}'s Pokémon",
                description="\n".join(format_pokemon_line(p) for p in page),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Page {i+1}/{len(pages)} • Total: {len(pokemon_list)} Pokémon")
            embeds.append(embed)

        if len(embeds) == 1:
            return await interaction.followup.send(embed=embeds[0])

        class Pagination(View):
            def __init__(self, embeds, user):
                super().__init__(timeout=300)
                self.embeds = embeds
                self.index = 0
                self.user = user

            @discord.ui.button(label="◀️", style=discord.ButtonStyle.gray)
            async def previous(self, interaction: Interaction, _):
                if interaction.user != self.user:
                    return await interaction.response.send_message("❌ Only you can use this.", ephemeral=True)
                self.index = (self.index - 1) % len(self.embeds)
                await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

            @discord.ui.button(label="▶️", style=discord.ButtonStyle.gray)
            async def next(self, interaction: Interaction, _):
                if interaction.user != self.user:
                    return await interaction.response.send_message("❌ Only you can use this.", ephemeral=True)
                self.index = (self.index + 1) % len(self.embeds)
                await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

        await interaction.followup.send(embed=embeds[0], view=Pagination(embeds, interaction.user))

    @app_commands.command(name="nickname", description="Give your Pokémon a nickname or remove it")
    @app_commands.describe(number="Your Pokémon number", nickname="The nickname to give (leave blank to remove)")
    async def nickname(
        self,
        interaction: Interaction,
        number: int,
        nickname: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)

        pokemon = await self.collection.find_one({"user_id": interaction.user.id, "pokemon_number": number})

        if not pokemon:
            return await interaction.followup.send("❌ You don't have a Pokémon with that number!", ephemeral=True)

        if nickname is None:
            await self.collection.update_one(
                {"user_id": interaction.user.id, "pokemon_number": number},
                {"$unset": {"nickname": ""}}
            )
            await interaction.followup.send(f"✅ Removed nickname from **{pokemon['pokemon_name']}** #{number}!", ephemeral=True)
        else:
            await self.collection.update_one(
                {"user_id": interaction.user.id, "pokemon_number": number},
                {"$set": {"nickname": nickname}}
            )
            await interaction.followup.send(f"✅ **{pokemon['pokemon_name']}** #{number} is now nicknamed **{nickname}**!", ephemeral=True)

    @app_commands.command(name="favorite", description="Toggle a Pokémon as favorite")
    @app_commands.describe(number="Your Pokémon number")
    async def favorite(
        self,
        interaction: Interaction,
        number: int
    ):
        await interaction.response.defer(ephemeral=True)

        pokemon = await self.collection.find_one({"user_id": interaction.user.id, "pokemon_number": number})

        if not pokemon:
            return await interaction.followup.send("❌ You don't have a Pokémon with that number!", ephemeral=True)

        new_status = not pokemon.get("favorite", False)
        await self.collection.update_one(
            {"user_id": interaction.user.id, "pokemon_number": number},
            {"$set": {"favorite": new_status}}
        )

        status_text = "added to" if new_status else "removed from"
        heart = "❤️" if new_status else "💔"
        display_name = pokemon.get("nickname") or pokemon["pokemon_name"]

        await interaction.followup.send(f"{heart} **{display_name}** #{number} {status_text} favorites!", ephemeral=True)

    @app_commands.command(name="unfavorite", description="Remove a Pokémon from favorites")
    @app_commands.describe(number="Your Pokémon number")
    async def unfavorite(
        self,
        interaction: Interaction,
        number: int
    ):
        await interaction.response.defer(ephemeral=True)

        pokemon = await self.collection.find_one({"user_id": interaction.user.id, "pokemon_number": number})

        if not pokemon:
            return await interaction.followup.send("❌ You don't have a Pokémon with that number!", ephemeral=True)

        # Check if it's already not favorited
        if not pokemon.get("favorite", False):
            display_name = pokemon.get("nickname") or pokemon["pokemon_name"]
            return await interaction.followup.send(f"💔 **{display_name}** #{number} is not in your favorites!", ephemeral=True)

        # Remove from favorites
        await self.collection.update_one(
            {"user_id": interaction.user.id, "pokemon_number": number},
            {"$set": {"favorite": False}}
        )

        display_name = pokemon.get("nickname") or pokemon["pokemon_name"]
        await interaction.followup.send(f"💔 **{display_name}** #{number} removed from favorites!", ephemeral=True)



async def setup(bot):
    import json
    with open("pokedex.json", "r", encoding="utf-8") as f:
        pokedex = json.load(f)
    
    # Custom Pokemon data (no longer needed - merged into main pokedex)
    
    await bot.add_cog(PokemonSlash(bot, bot.pokemon_collection, pokedex))
