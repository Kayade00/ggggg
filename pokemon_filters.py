import re
from typing import List, Dict, Any, Optional, Tuple

class PokemonFilter:
    """Advanced Pokemon filtering system"""
    
    def __init__(self):
        self.filters = {}
    
    def parse_filters(self, args: List[str], market_mode: bool = False) -> Tuple[Dict[str, Any], List[str]]:
        """
        Parse command arguments and extract filters
        Returns: (filters_dict, remaining_args)
        """
        filters = {}
        remaining_args = []
        i = 0
        
        while i < len(args):
            arg = args[i]
            
            # Name filter
            if arg in ['--name', '--n']:
                if i + 1 < len(args):
                    filters['name'] = args[i + 1].lower()
                    i += 2
                else:
                    i += 1
            
            # Evolution line filter
            elif arg in ['--evolution', '--evo']:
                if i + 1 < len(args):
                    filters['evolution'] = args[i + 1].lower()
                    i += 2
                else:
                    i += 1
            
            # IV filters with comparison operators
            elif arg in ['--hpiv', '--atkiv', '--defiv', '--spatkiv', '--spdefiv', '--spdiv']:
                iv_stat = arg[2:]  # Remove '--' prefix
                if i + 1 < len(args):
                    try:
                        # Check for comparison operators
                        next_arg = args[i + 1]
                        operator = '='
                        value = None
                        
                        # Check if next_arg contains an operator (e.g., ">=50")
                        if any(op in next_arg for op in ['>', '<', '>=', '<=', '=']):
                            # Extract operator and value from combined string
                            for op in ['>=', '<=', '>', '<', '=']:
                                if op in next_arg:
                                    operator = op
                                    value_str = next_arg.replace(op, '').strip()
                                    if value_str:
                                        value = int(value_str)
                                    i += 2
                                    break
                        elif next_arg in ['>', '<', '>=', '<=', '=']:
                            operator = next_arg
                            if i + 2 < len(args):
                                value = int(args[i + 2])
                                i += 3
                            else:
                                i += 2
                        else:
                            # Direct value
                            value = int(next_arg)
                            i += 2
                        
                        if value is not None:
                            filters[iv_stat] = {'operator': operator, 'value': value}
                    except ValueError:
                        i += 1
                else:
                    i += 1
            
            # Level filters
            elif arg in ['--level', '--lv']:
                if i + 1 < len(args):
                    try:
                        next_arg = args[i + 1]
                        operator = '='
                        value = None
                        
                        # Check if next_arg contains an operator (e.g., ">=50")
                        if any(op in next_arg for op in ['>', '<', '>=', '<=', '=']):
                            # Extract operator and value from combined string
                            for op in ['>=', '<=', '>', '<', '=']:
                                if op in next_arg:
                                    operator = op
                                    value_str = next_arg.replace(op, '').strip()
                                    if value_str:
                                        value = int(value_str)
                                    i += 2
                                    break
                        elif next_arg in ['>', '<', '>=', '<=', '=']:
                            operator = next_arg
                            if i + 2 < len(args):
                                value = int(args[i + 2])
                                i += 3
                            else:
                                i += 2
                        else:
                            value = int(next_arg)
                            i += 2
                        
                        if value is not None:
                            filters['level'] = {'operator': operator, 'value': value}
                    except ValueError:
                        i += 1
                else:
                    i += 1
            
            # Total IV filter
            elif arg in ['--iv', '--totaliv']:
                if i + 1 < len(args):
                    try:
                        next_arg = args[i + 1]
                        operator = '='
                        value = None
                        
                        # Check if next_arg contains an operator (e.g., ">=70")
                        if any(op in next_arg for op in ['>', '<', '>=', '<=', '=']):
                            # Extract operator and value from combined string
                            for op in ['>=', '<=', '>', '<', '=']:
                                if op in next_arg:
                                    operator = op
                                    value_str = next_arg.replace(op, '').strip()
                                    if value_str:
                                        value = int(value_str)
                                    i += 2
                                    break
                        elif next_arg in ['>', '<', '>=', '<=', '=']:
                            operator = next_arg
                            if i + 2 < len(args):
                                value = int(args[i + 2])
                                i += 3
                            else:
                                i += 2
                        else:
                            value = int(next_arg)
                            i += 2
                        
                        if value is not None:
                            filters['totaliv'] = {'operator': operator, 'value': value}
                    except ValueError:
                        i += 1
                else:
                    i += 1
            
            # Shiny filter
            elif arg in ['--shiny', '--s']:
                filters['shiny'] = True
                i += 1
            
            # Favorite filter
            elif arg in ['--favorite', '--fav']:
                filters['favorite'] = True
                i += 1
            
            # Legendary/Mythical filters (for future use)
            elif arg in ['--legendary', '--legend']:
                filters['legendary'] = True
                i += 1
            
            elif arg in ['--mythical', '--myth']:
                filters['mythical'] = True
                i += 1
            
            # Price filters (for market only)
            elif market_mode and arg in ['--price', '--p']:
                if i + 1 < len(args):
                    try:
                        next_arg = args[i + 1]
                        operator = '='
                        value = None
                        # Check if next_arg contains an operator (e.g., ">=50")
                        if any(op in next_arg for op in ['>', '<', '>=', '<=', '=']):
                            for op in ['>=', '<=', '>', '<', '=']:
                                if op in next_arg:
                                    operator = op
                                    value_str = next_arg.replace(op, '').strip()
                                    if value_str:
                                        value = int(value_str)
                                    i += 2
                                    break
                        elif next_arg in ['>', '<', '>=', '<=', '=']:
                            operator = next_arg
                            if i + 2 < len(args):
                                value = int(args[i + 2])
                                i += 3
                            else:
                                i += 2
                        else:
                            value = int(next_arg)
                            i += 2
                        if value is not None:
                            filters['price'] = {'operator': operator, 'value': value}
                    except ValueError:
                        i += 1
                else:
                    i += 1
            
            else:
                remaining_args.append(arg)
                i += 1
        
        return filters, remaining_args
    
    def apply_filters(self, pokemon_list: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply filters to a list of Pokemon"""
        if not filters:
            return pokemon_list
        
        filtered_list = []
        
        for pokemon in pokemon_list:
            if self._matches_filters(pokemon, filters):
                filtered_list.append(pokemon)
        
        return filtered_list
    
    def _matches_filters(self, pokemon: Dict, filters: Dict[str, Any]) -> bool:
        """Check if a single Pokemon matches all filters"""
        
        # Name filter
        if 'name' in filters:
            pokemon_name = pokemon.get('pokemon_name', '').lower()
            nickname = (pokemon.get('nickname') or '').lower()
            if filters['name'] not in pokemon_name and filters['name'] not in nickname:
                return False
        
        # Evolution line filter (simplified - just check if the filter name is in the pokemon name)
        if 'evolution' in filters:
            pokemon_name = pokemon.get('pokemon_name', '').lower()
            if filters['evolution'] not in pokemon_name:
                # Could add more sophisticated evolution line checking here
                return False
        
        # IV filters
        iv_stats = ['hpiv', 'atkiv', 'defiv', 'spatkiv', 'spdefiv', 'spdiv']
        for stat in iv_stats:
            if stat in filters:
                pokemon_iv = pokemon.get(f'{stat[:-2]}_iv', 0)  # Remove 'iv' suffix
                filter_data = filters[stat]
                operator = filter_data['operator']
                value = filter_data['value']
                
                if not self._compare_values(pokemon_iv, operator, value):
                    return False
        
        # Level filter
        if 'level' in filters:
            pokemon_level = pokemon.get('level', 1)
            filter_data = filters['level']
            operator = filter_data['operator']
            value = filter_data['value']
            
            if not self._compare_values(pokemon_level, operator, value):
                return False
        
        # Total IV filter
        if 'totaliv' in filters:
            # Calculate total IV percentage
            total_iv = sum([
                pokemon.get('hp_iv', 0),
                pokemon.get('atk_iv', 0),
                pokemon.get('def_iv', 0),
                pokemon.get('sp_atk_iv', 0),
                pokemon.get('sp_def_iv', 0),
                pokemon.get('spd_iv', 0)
            ])
            total_iv_percent = round((total_iv / 186) * 100, 1)
            
            filter_data = filters['totaliv']
            operator = filter_data['operator']
            value = filter_data['value']
            
            print(f"DEBUG: Pokemon {pokemon.get('pokemon_name', 'Unknown')} - Total IV: {total_iv}, Percentage: {total_iv_percent}%, Filter: {operator} {value}")
            
            if not self._compare_values(total_iv_percent, operator, value):
                print(f"DEBUG: Pokemon {pokemon.get('pokemon_name', 'Unknown')} - FAILED IV filter")
                return False
        
        # Shiny filter
        if 'shiny' in filters and filters['shiny']:
            if not pokemon.get('shiny', False):
                return False
        
        # Favorite filter
        if 'favorite' in filters and filters['favorite']:
            if not pokemon.get('favorite', False):
                return False
        
        # Price filter (for market listings)
        if 'price' in filters and 'price' in pokemon:
            pokemon_price = pokemon.get('price', 0)
            filter_data = filters['price']
            operator = filter_data['operator']
            value = filter_data['value']
            
            if not self._compare_values(pokemon_price, operator, value):
                return False
        
        return True
    
    def _compare_values(self, pokemon_value: int, operator: str, filter_value: int) -> bool:
        """Compare two values based on the operator"""
        if operator == '=':
            return pokemon_value == filter_value
        elif operator == '>':
            return pokemon_value > filter_value
        elif operator == '<':
            return pokemon_value < filter_value
        elif operator == '>=':
            return pokemon_value >= filter_value
        elif operator == '<=':
            return pokemon_value <= filter_value
        return False
    
    def get_filter_description(self, filters: Dict[str, Any], market_mode: bool = False) -> str:
        """Generate a human-readable description of active filters"""
        if not filters:
            return "No filters applied"
        
        descriptions = []
        
        if 'name' in filters:
            descriptions.append(f"Name contains '{filters['name']}'")
        
        if 'evolution' in filters:
            descriptions.append(f"Evolution line '{filters['evolution']}'")
        
        if 'shiny' in filters:
            descriptions.append("Shiny only")
        
        if 'favorite' in filters:
            descriptions.append("Favorites only")
        
        # IV filters
        iv_names = {
            'hpiv': 'HP IV',
            'atkiv': 'Attack IV',
            'defiv': 'Defense IV',
            'spatkiv': 'Sp. Attack IV',
            'spdefiv': 'Sp. Defense IV',
            'spdiv': 'Speed IV'
        }
        
        for stat, name in iv_names.items():
            if stat in filters:
                filter_data = filters[stat]
                op = filter_data['operator']
                val = filter_data['value']
                descriptions.append(f"{name} {op} {val}")
        
        if 'level' in filters:
            filter_data = filters['level']
            op = filter_data['operator']
            val = filter_data['value']
            descriptions.append(f"Level {op} {val}")
        
        if 'totaliv' in filters:
            filter_data = filters['totaliv']
            op = filter_data['operator']
            val = filter_data['value']
            descriptions.append(f"Total IV {op} {val}%")
        
        if market_mode and 'price' in filters:
            filter_data = filters['price']
            op = filter_data['operator']
            val = filter_data['value']
            descriptions.append(f"Price {op} {val:,} coins")
        
        return " | ".join(descriptions)

# Helper functions
def parse_command_with_filters(command_args: List[str], market_mode: bool = False) -> Tuple[Dict[str, Any], List[str]]:
    """Helper function to parse command arguments with filters"""
    filter_system = PokemonFilter()
    return filter_system.parse_filters(command_args, market_mode=market_mode)

def filter_pokemon_list(pokemon_list: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
    """Helper function to filter a Pokemon list"""
    filter_system = PokemonFilter()
    return filter_system.apply_filters(pokemon_list, filters)

def get_filter_help() -> str:
    return """
**Available Filters:**
`--name <name>` or `--n <name>` - Filter by Pokemon name/nickname
`--evolution <name>` or `--evo <name>` - Filter by evolution line
`--level <op> <value>` or `--lv <op> <value>` - Filter by level
`--iv <op> <value>` or `--totaliv <op> <value>` - Filter by total IV percentage
`--hpiv <op> <value>` - Filter by HP IV
`--atkiv <op> <value>` - Filter by Attack IV
`--defiv <op> <value>` - Filter by Defense IV
`--spatkiv <op> <value>` - Filter by Sp. Attack IV
`--spdefiv <op> <value>` - Filter by Sp. Defense IV
`--spdiv <op> <value>` - Filter by Speed IV
`--shiny` or `--s` - Show only shiny Pokemon
`--favorite` or `--fav` - Show only favorite Pokemon
`--price <op> <value>` or `--p <op> <value>` - Filter by price (market only)

**Operators:** `>`, `<`, `>=`, `<=`, `=` (default)
**Examples:**
`!pokemon --n pikachu --iv >= 80 --shiny`
`!market search --evo eevee --price < 10000 --level >= 50`
"""
