import json
import os

def load_and_modify_json(filename):
    # Extract the base name of the file (without extension)
    name_without_extension = os.path.splitext(os.path.basename(filename))[0]
    
    # Load the JSON data
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Modify the "name" field in the JSON to match the filename
    data['name'] = name_without_extension
    
    # Save the updated JSON back to the same file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"Updated 'name' to '{name_without_extension}' in {filename}")
    return data

# Example usage
file_path = 'pokedex.json'  # Replace with your actual JSON file name
load_and_modify_json(file_path)
