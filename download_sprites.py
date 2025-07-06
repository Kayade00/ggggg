import requests
import json
import os
import time
from PIL import Image
import io

def download_sprite(url, filepath):
    """Download sprite from URL and save to filepath"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Open image to verify it's valid
        img = Image.open(io.BytesIO(response.content))
        img.save(filepath)
        return True
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return False

def get_pokemon_sprite_urls(pokemon_id):
    """Get sprite URLs for a Pokémon from PokeAPI"""
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Get official art URLs
        official_art = data['sprites']['other']['official-artwork']['front_default']
        official_art_shiny = data['sprites']['other']['official-artwork']['front_shiny']
        
        return official_art, official_art_shiny
    except Exception as e:
        print(f"❌ Failed to get sprite URLs for ID {pokemon_id}: {e}")
        return None, None

def main():
    # Load pokedex to get all Pokémon IDs
    with open("pokedex_compatible.json", "r", encoding="utf-8") as f:
        pokedex = json.load(f)
    
    # Create folders if they don't exist
    os.makedirs("full", exist_ok=True)
    os.makedirs("full_shiny", exist_ok=True)
    
    # Get all unique Pokémon IDs
    pokemon_ids = set()
    for pokemon_id, data in pokedex.items():
        pokemon_ids.add(int(pokemon_id))
    
    pokemon_ids = sorted(pokemon_ids)
    total_pokemon = len(pokemon_ids)
    
    print(f"🎯 Downloading sprites for {total_pokemon} Pokémon...")
    
    successful_downloads = 0
    failed_downloads = 0
    
    for i, pokemon_id in enumerate(pokemon_ids, 1):
        print(f"📥 [{i}/{total_pokemon}] Downloading sprites for Pokémon ID {pokemon_id}...")
        
        # Get sprite URLs
        normal_url, shiny_url = get_pokemon_sprite_urls(pokemon_id)
        
        if normal_url and shiny_url:
            # Download normal sprite
            normal_filepath = f"full/{pokemon_id}.png"
            if download_sprite(normal_url, normal_filepath):
                print(f"  ✅ Normal sprite saved: {normal_filepath}")
                successful_downloads += 1
            else:
                failed_downloads += 1
            
            # Download shiny sprite
            shiny_filepath = f"full_shiny/{pokemon_id}_full.png"
            if download_sprite(shiny_url, shiny_filepath):
                print(f"  ✨ Shiny sprite saved: {shiny_filepath}")
                successful_downloads += 1
            else:
                failed_downloads += 1
        else:
            print(f"  ❌ No sprite URLs found for ID {pokemon_id}")
            failed_downloads += 2
        
        # Be nice to the API
        time.sleep(0.5)
    
    print(f"\n🎉 Download complete!")
    print(f"✅ Successful downloads: {successful_downloads}")
    print(f"❌ Failed downloads: {failed_downloads}")
    print(f"📁 Files saved to 'full/' and 'full_shiny/' folders")

if __name__ == "__main__":
    main() 