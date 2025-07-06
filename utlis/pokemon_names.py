# utils/pokemon_names.py
import json

class PokemonNames:
    def __init__(self):
        self.altname_map = {}
        self._load_alt_names()
        self._generate_base_name_mappings()

    def _load_alt_names(self):
        try:
            with open("pokemon_altnames.json", "r", encoding="utf-8") as f:
                alt_list = json.load(f)
                for entry in alt_list:
                    canonical = entry["name"].lower()
                    for value in entry.values():
                        if isinstance(value, str):
                            self.altname_map[value.lower()] = canonical
        except Exception as e:
            print(f"Failed to load alternative names: {e}")

    def _extract_base_name(self, pokemon_name):
        """Extract base Pokemon name from full name"""
        name = pokemon_name.strip().lower()
        
        # Common prefixes to remove (event Pokemon, regional forms, etc.)
        prefixes_to_remove = [
            "sylvan", "verdant", "thorned", "twilight", "briar", "blooming", "spore",
            "shadow", "mega", "gigantamax", "gmax", "primal", "origin", "zen", "therian",
            "incarnate", "resolute", "ordinary", "pirouette", "aria", "step", "blade",
            "shield", "crowned", "ice", "shadow rider", "ice rider", "rapid strike",
            "single strike", "white striped", "blue striped", "red striped", "orange",
            "yellow", "green", "blue", "indigo", "violet", "roaming", "complete",
            "10 percent", "50 percent", "power construct", "disguised", "busted",
            "school", "solo", "meteor", "dawn wings", "dusk mane", "ultra",
            "alolan", "galarian", "hisuian", "paldean", "kantonian", "johtonian"
        ]
        
        # Common suffixes to remove (forms, sizes, etc.)
        suffixes_to_remove = [
            "two segment", "three segment", "four segment", "droopy", "curly", "stretchy",
            "plant", "sandy", "trash", "wash", "heat", "frost", "fan", "mow", "altered",
            "origin", "land", "sky", "normal", "attack", "defense", "speed", "red",
            "blue", "yellow", "orange", "pink", "green", "violet", "indigo", "white",
            "black", "brown", "gray", "grey", "silver", "gold", "copper", "steel",
            "rock", "ground", "flying", "poison", "fighting", "psychic", "bug", "ghost",
            "fire", "water", "grass", "electric", "ice", "dragon", "dark", "fairy",
            "normal mode", "zen mode", "standard mode", "therian forme", "incarnate forme",
            "male", "female", "size s", "size m", "size l", "size xl", "size xs",
            "small", "medium", "large", "super size", "amped", "low key", "full belly",
            "hangry", "gulping", "gorging", "noice", "antique", "phony", "crowned sword",
            "crowned shield", "eternamax", "gigantamax factor", "dynamax factor"
        ]
        
        # Split name into words
        words = name.split()
        if not words:
            return name
        
        # Remove prefixes
        while words and any(words[0].startswith(prefix) or " ".join(words[:len(prefix.split())]) == prefix 
                           for prefix in prefixes_to_remove):
            # Find the longest matching prefix
            longest_match = 0
            for prefix in prefixes_to_remove:
                prefix_words = prefix.split()
                if len(prefix_words) <= len(words):
                    if " ".join(words[:len(prefix_words)]) == prefix:
                        longest_match = max(longest_match, len(prefix_words))
            
            if longest_match > 0:
                words = words[longest_match:]
            else:
                break
        
        # Remove suffixes
        while words and any(" ".join(words[-len(suffix.split()):]) == suffix 
                           for suffix in suffixes_to_remove):
            # Find the longest matching suffix
            longest_match = 0
            for suffix in suffixes_to_remove:
                suffix_words = suffix.split()
                if len(suffix_words) <= len(words):
                    if " ".join(words[-len(suffix_words):]) == suffix:
                        longest_match = max(longest_match, len(suffix_words))
            
            if longest_match > 0:
                words = words[:-longest_match]
            else:
                break
        
        # Return the base name
        base_name = " ".join(words) if words else name
        return base_name.strip()

    def _generate_base_name_mappings(self):
        """Auto-generate base name mappings for Pokemon names"""
        try:
            with open("pokedex.json", "r", encoding="utf-8") as f:
                pokemon_data = json.load(f)
            
            for pokemon_id, data in pokemon_data.items():
                if "name" not in data:
                    continue
                
                full_name = data["name"].lower().replace("-", " ")
                base_name = self._extract_base_name(full_name)
                
                if base_name != full_name and len(base_name) > 2:
                    self.altname_map[base_name] = full_name
                    base_name_hyphen = base_name.replace(" ", "-")
                    full_name_hyphen = full_name.replace(" ", "-")
                    if base_name_hyphen != full_name_hyphen:
                        self.altname_map[base_name_hyphen] = full_name_hyphen
            
            print(f"✅ Generated {len([k for k in self.altname_map.keys() if self._is_auto_generated(k)])} base name mappings")
        except Exception as e:
            print(f"Failed to generate base name mappings: {e}")

    def _is_auto_generated(self, key):
        """Check if an altname mapping was auto-generated"""
        return len(key.split()) <= 2 and not key.endswith("'s") and not key.isdigit()

    def get_canonical_name(self, input_name):
        """Get the canonical name for any input"""
        input_name = input_name.lower().strip()
        # First check direct matches
        if input_name in self.altname_map:
            return self.altname_map[input_name]
        
        # Then check base names
        base_name = self._extract_base_name(input_name)
        if base_name != input_name and base_name in self.altname_map:
            return self.altname_map[base_name]
            
        return input_name  # Return original if no mapping found