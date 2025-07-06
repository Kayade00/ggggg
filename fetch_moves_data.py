import requests
import json
import time

def fetch_move_data(move_id):
    """Fetch move data from PokeAPI"""
    try:
        response = requests.get(f"https://pokeapi.co/api/v2/move/{move_id}")
        if response.status_code == 200:
            data = response.json()
            
            # Extract relevant move information
            move_info = {
                "id": data["id"],
                "name": data["name"],
                "accuracy": data["accuracy"],
                "power": data["power"],
                "pp": data["pp"],
                "priority": data["priority"],
                "type": data["type"]["name"] if data["type"] else None,
                "damage_class": data["damage_class"]["name"] if data["damage_class"] else None,
                "effect_chance": data["effect_chance"],
                "target": data["target"]["name"] if data["target"] else None,
                "description": None,
                "short_effect": None
            }
            
            # Get English description
            for effect_entry in data.get("effect_entries", []):
                if effect_entry["language"]["name"] == "en":
                    move_info["description"] = effect_entry["effect"]
                    move_info["short_effect"] = effect_entry["short_effect"]
                    break
            
            # Get flavor text (description from games)
            for flavor_text in data.get("flavor_text_entries", []):
                if flavor_text["language"]["name"] == "en":
                    move_info["flavor_text"] = flavor_text["flavor_text"]
                    break
            
            return move_info
        else:
            print(f"Failed to fetch move {move_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching move {move_id}: {e}")
        return None

def fetch_all_moves():
    """Fetch all moves from PokeAPI and save to JSON file"""
    print("Fetching move list from PokeAPI...")
    
    # First, get the list of all moves
    try:
        response = requests.get("https://pokeapi.co/api/v2/move?limit=2000")
        if response.status_code != 200:
            print(f"Failed to fetch move list: {response.status_code}")
            return
        
        moves_list = response.json()
        total_moves = len(moves_list["results"])
        print(f"Found {total_moves} moves to fetch...")
        
    except Exception as e:
        print(f"Error fetching move list: {e}")
        return
    
    moves_data = {}
    failed_moves = []
    
    for i, move in enumerate(moves_list["results"], 1):
        # Extract move ID from URL
        move_id = int(move["url"].split("/")[-2])
        
        print(f"Fetching move {i}/{total_moves}: {move['name']} (ID: {move_id})")
        
        move_data = fetch_move_data(move_id)
        if move_data:
            moves_data[str(move_id)] = move_data
        else:
            failed_moves.append(move_id)
        
        # Rate limiting - be nice to the API
        if i % 10 == 0:
            print(f"Progress: {i}/{total_moves} moves fetched...")
            time.sleep(1)
        else:
            time.sleep(0.1)
    
    # Save to JSON file
    print("Saving moves data to moves_data.json...")
    try:
        with open("moves_data.json", "w", encoding="utf-8") as f:
            json.dump(moves_data, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully saved {len(moves_data)} moves to moves_data.json")
        
        if failed_moves:
            print(f"Failed to fetch {len(failed_moves)} moves: {failed_moves}")
            
    except Exception as e:
        print(f"Error saving to file: {e}")

def create_sample_moves():
    """Create a sample moves file with some common moves for testing"""
    print("Creating sample moves data...")
    
    sample_moves = {
        "1": {
            "id": 1,
            "name": "pound",
            "accuracy": 100,
            "power": 40,
            "pp": 35,
            "priority": 0,
            "type": "normal",
            "damage_class": "physical",
            "effect_chance": None,
            "target": "selected-pokemon",
            "description": "Pounds with forelegs or tail.",
            "short_effect": "Inflicts regular damage with no additional effect."
        },
        "33": {
            "id": 33,
            "name": "tackle",
            "accuracy": 100,
            "power": 40,
            "pp": 35,
            "priority": 0,
            "type": "normal",
            "damage_class": "physical",
            "effect_chance": None,
            "target": "selected-pokemon",
            "description": "Charges straight ahead.",
            "short_effect": "Inflicts regular damage with no additional effect."
        },
        "45": {
            "id": 45,
            "name": "growl",
            "accuracy": 100,
            "power": None,
            "pp": 40,
            "priority": 0,
            "type": "normal",
            "damage_class": "status",
            "effect_chance": None,
            "target": "all-opponents",
            "description": "Lowers the foe's Attack one stage.",
            "short_effect": "Lowers the target's Attack by one stage."
        }
    }
    
    try:
        with open("moves_data.json", "w", encoding="utf-8") as f:
            json.dump(sample_moves, f, indent=2, ensure_ascii=False)
        print("Sample moves data created successfully!")
    except Exception as e:
        print(f"Error creating sample file: {e}")

if __name__ == "__main__":
    print("Pokemon Moves Data Fetcher")
    print("=" * 30)
    
    choice = input("Choose an option:\n1. Fetch all moves from PokeAPI (takes ~30-60 minutes)\n2. Create sample moves file for testing\nEnter choice (1 or 2): ")
    
    if choice == "1":
        print("\nWarning: This will fetch ~900+ moves and may take 30-60 minutes!")
        confirm = input("Continue? (y/n): ").lower()
        if confirm == "y":
            fetch_all_moves()
        else:
            print("Operation cancelled.")
    elif choice == "2":
        create_sample_moves()
    else:
        print("Invalid choice. Please run the script again.") 