import requests
import json
import time

def get_all_pokemon_forms():
    """Get all pokemon forms including variants"""
    all_forms = []
    
    # Get all species first
    url = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
    resp = requests.get(url)
    resp.raise_for_status()
    species_list = resp.json()['results']
    
    for species in species_list:
        # Get species details to find all varieties
        species_url = f"https://pokeapi.co/api/v2/pokemon-species/{species['name']}"
        species_resp = requests.get(species_url)
        if species_resp.status_code != 200:
            continue
            
        species_data = species_resp.json()
        
        # Get all varieties (forms) for this species
        for variety in species_data.get('varieties', []):
            if variety['is_default']:
                # Get the default form
                pokemon_name = variety['pokemon']['name']
                all_forms.append(pokemon_name)
            else:
                # Get variant forms
                pokemon_name = variety['pokemon']['name']
                all_forms.append(pokemon_name)
    
    return all_forms

def get_pokemon_data(name):
    """Get detailed pokemon data for a specific form"""
    url = f"https://pokeapi.co/api/v2/pokemon/{name}"
    resp = requests.get(url)
    if resp.status_code != 200:
        return None
    return resp.json()

def main():
    print("Fetching all Pokemon forms...")
    all_forms = get_all_pokemon_forms()
    print(f"Found {len(all_forms)} forms to fetch")
    
    pokedex = []
    for i, form_name in enumerate(all_forms):
        data = get_pokemon_data(form_name)
        if not data:
            print(f"Failed to fetch: {form_name}")
            continue
            
        # Check for mega/gmax in the form name
        is_mega = 'mega' in form_name
        is_gmax = 'gmax' in form_name or 'gigantamax' in form_name
        
        entry = {
            "id": data["id"],
            "name": data["name"],
            "types": [t["type"]["name"] for t in data["types"]],
            "base_stats": {s["stat"]["name"]: s["base_stat"] for s in data["stats"]},
            "abilities": [
                {"name": a["ability"]["name"], "is_hidden": a["is_hidden"]}
                for a in data["abilities"]
            ],
            "moves": [
                {
                    "name": m["move"]["name"],
                    "learn_method": m["version_group_details"][0]["move_learn_method"]["name"] if m["version_group_details"] else None,
                    "level_learned": m["version_group_details"][0]["level_learned_at"] if m["version_group_details"] else None,
                }
                for m in data["moves"]
            ],
            "forms": [f["name"] for f in data["forms"]],
            "is_mega": is_mega,
            "is_gmax": is_gmax,
            "varieties": [form_name],  # This form is its own variety
        }
        pokedex.append(entry)
        print(f"Fetched ({i+1}/{len(all_forms)}): {form_name} (ID: {data['id']})")
        time.sleep(0.5)  # Be nice to the API
    
    with open("pokedex_remastered.json", "w", encoding="utf-8") as f:
        json.dump(pokedex, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Completed! Saved {len(pokedex)} Pokemon forms to pokedex_remastered.json")

if __name__ == "__main__":
    main() 