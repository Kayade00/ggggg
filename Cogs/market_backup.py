import discord
from discord.ext import commands
from discord.ui import View, Button, Select
from datetime import datetime, timedelta
import os
import sys

Add the parent directory to sys.path so we can import from it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(file))))

from pokemon_filters import parse_command_with_filters, filter_pokemon_list, get_filter_help, PokemonFilter

class Market(commands.Cog):
def init(self, bot, pokemon_collection, user_profiles, market_collection):
self.bot = bot
self.pokemon_collection = pokemon_collection
self.user_profiles = user_profiles
self.market_collection = market_collection
self.filter_system = PokemonFilter()

