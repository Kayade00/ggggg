import json

def convert_to_original_format():
    # Load the remastered pokedex
    with open("pokedex_remastered.json", "r", encoding="utf-8") as f:
        remastered_data = json.load(f)
    
    # Convert to original format
    original_format = {}
    
    for pokemon in remastered_data:
        pokemon_id = str(pokemon["id"])
        
        # Convert to original format
        original_format[pokemon_id] = {
            "id": pokemon["id"],
            "name": pokemon["name"],
            "species": pokemon["name"],  # Use name as species
            "height": pokemon.get("height", 0),  # Default to 0 if not present
            "weight": pokemon.get("weight", 0),  # Default to 0 if not present
            "types": pokemon["types"],
            "stats": pokemon["base_stats"],  # Convert base_stats to stats
            "abilities": pokemon["abilities"],
            "moves": pokemon["moves"]
        }
        
        # Add custom fields if they exist
        if pokemon.get("custom"):
            original_format[pokemon_id]["custom"] = pokemon["custom"]
        if pokemon.get("event_exclusive"):
            original_format[pokemon_id]["event_exclusive"] = pokemon["event_exclusive"]
        if pokemon.get("event_tag"):
            original_format[pokemon_id]["event_tag"] = pokemon["event_tag"]
        if pokemon.get("description"):
            original_format[pokemon_id]["description"] = pokemon["description"]
    
    # Save as pokedex_compatible.json
    with open("pokedex_compatible.json", "w", encoding="utf-8") as f:
        json.dump(original_format, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Converted {len(remastered_data)} Pokémon to original format")
    print("Saved as pokedex_compatible.json")
    print("This file is compatible with your existing commands!")

if __name__ == "__main__":
    convert_to_original_format() 