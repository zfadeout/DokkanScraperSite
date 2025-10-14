# dokkan_api.py
# Flask API server to serve Dokkan card data from scraped metadata

import json
import logging
import requests
from pathlib import Path
from typing import List, Dict, Optional

from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# ------------ Config -------------
OUTPUT_ROOT_DIR = Path("output/cards")
API_HOST = "127.0.0.1"
API_PORT = 5000

DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://dokkaninfo.com"
}

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)

# ------------ Data Loading -------------
def load_all_cards() -> List[Dict]:
    """Load all card metadata from output/cards directory"""
    cards = []
    
    if not OUTPUT_ROOT_DIR.exists():
        logging.warning(f"Output directory not found: {OUTPUT_ROOT_DIR}")
        return cards
    
    # Find all METADATA.json files
    metadata_files = list(OUTPUT_ROOT_DIR.rglob("METADATA.json"))
    logging.info(f"Found {len(metadata_files)} card metadata files")
    
    for metadata_file in metadata_files:
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                
            # Extract key information for the frontend
            card_data = extract_card_data(metadata)
            if card_data:
                cards.append(card_data)
                
        except Exception as e:
            logging.error(f"Failed to load {metadata_file}: {e}")
            continue
    
    logging.info(f"Successfully loaded {len(cards)} cards")
    return cards

def extract_card_data(metadata: Dict) -> Optional[Dict]:
    """Extract and format card data from metadata for frontend"""
    try:
        card_id = metadata.get("card_identification", {})
        release = metadata.get("release_details", {})
        leader = metadata.get("leader_ability", {})
        attacks = metadata.get("attack_techniques", {})
        passive = metadata.get("passive_skill", {})
        active = metadata.get("active_skill", {})
        stats = metadata.get("base_statistics", {})
        eza = metadata.get("extreme_z_awakening", {})
        domains = metadata.get("domain_effects", [])
        meta = metadata.get("metadata", {})
        images = metadata.get("image_resources", [])
        
        # Extract asset URLs
        assets = extract_assets(images, card_id.get("character_id", ""))
        
        # Format passive effects
        passive_text = format_passive_effects(passive.get("structured_effects", []))
        
        # Build card object
        card = {
            "id": card_id.get("character_id", "unknown"),
            "name": card_id.get("display_name", "Unknown"),
            "displayNameWithType": card_id.get("display_name_with_type", ""),
            "displayNameBracketed": card_id.get("display_name_with_type_bracketed", ""),
            "pageTitle": card_id.get("page_title", ""),
            
            # Type and Rarity
            "rarity": meta.get("rarity_detected", "UNKNOWN"),
            "type": meta.get("type_token_upper", "UNKNOWN"),
            
            # Release Info
            "releaseDate": release.get("release_date", "Unknown"),
            "timezone": release.get("timezone", "Unknown"),
            
            # Skills
            "leaderSkill": leader.get("leader_skill"),
            "superAttack": {
                "name": attacks.get("super_attack", {}).get("name"),
                "effect": attacks.get("super_attack", {}).get("effect")
            },
            "ultraSuperAttack": {
                "name": attacks.get("ultra_super_attack", {}).get("name"),
                "effect": attacks.get("ultra_super_attack", {}).get("effect")
            },
            "passiveSkill": {
                "name": passive.get("name"),
                "text": passive_text,
                "structured": passive.get("structured_effects", [])
            },
            "activeSkill": {
                "name": active.get("name"),
                "effect": active.get("effect"),
                "conditions": active.get("activation_conditions")
            },
            
            # Categories and Links
            "categories": metadata.get("categories", []),
            "linkSkills": metadata.get("link_skills", []),
            
            # Stats
            "stats": format_stats(stats),
            
            # EZA Info
            "eza": {
                "hasEza": eza.get("has_eza", False),
                "ezaStep": eza.get("eza_step"),
                "isSeza": eza.get("is_seza", False),
                "originalReleaseDate": eza.get("original_release_date"),
                "ezaReleaseDate": eza.get("eza_release_date")
            },
            
            # Domain Effects
            "domains": domains,
            
            # Assets
            "assets": assets,
            
            # Source
            "sourceUrl": meta.get("source_url", "")
        }
        
        return card
        
    except Exception as e:
        logging.error(f"Failed to extract card data: {e}")
        return None

def extract_assets(image_urls: List[str], character_id: str) -> Dict[str, Optional[str]]:
    """Extract key asset URLs from image list"""
    assets = {
        "rarity": None,
        "type": None,
        "background": None,
        "character": None,
        "effect": None,
        "cutin": None
    }
    
    logging.debug(f"Extracting assets for character {character_id} from {len(image_urls)} URLs")
    
    for url in image_urls:
        url_lower = url.lower()
        
        # Rarity icon
        if "cha_rare_sm_" in url_lower or "cha_rare_" in url_lower:
            if not assets["rarity"]:
                assets["rarity"] = url
                logging.debug(f"Found rarity: {url}")
        
        # Type icon
        elif "cha_type_icon_" in url_lower:
            if not assets["type"]:
                assets["type"] = url
                logging.debug(f"Found type: {url}")
        
        # Card assets with character ID
        elif character_id and character_id in url:
            if "_bg." in url_lower or "_bg.png" in url_lower:
                assets["background"] = url
                logging.debug(f"Found background: {url}")
            elif "_character." in url_lower or "_character.png" in url_lower:
                assets["character"] = url
                logging.debug(f"Found character: {url}")
            elif "_effect." in url_lower or "_effect.png" in url_lower:
                assets["effect"] = url
                logging.debug(f"Found effect: {url}")
            elif "_cutin." in url_lower or "_cutin.png" in url_lower:
                assets["cutin"] = url
                logging.debug(f"Found cutin: {url}")
        
        # Fallback: Try to find character images without strict ID matching
        elif "/character/card/" in url_lower:
            if "_character." in url_lower and not assets["character"]:
                assets["character"] = url
                logging.debug(f"Found character (fallback): {url}")
            elif "_bg." in url_lower and not assets["background"]:
                assets["background"] = url
                logging.debug(f"Found background (fallback): {url}")
            elif "_effect." in url_lower and not assets["effect"]:
                assets["effect"] = url
                logging.debug(f"Found effect (fallback): {url}")
            elif "_cutin." in url_lower and not assets["cutin"]:
                assets["cutin"] = url
                logging.debug(f"Found cutin (fallback): {url}")
    
    # Log what we found
    logging.info(f"Character {character_id} assets: bg={bool(assets['background'])}, char={bool(assets['character'])}, effect={bool(assets['effect'])}")
    
    return assets

def format_passive_effects(structured_effects: List[Dict]) -> str:
    """Format structured passive effects into readable text"""
    if not structured_effects:
        return ""
    
    parts = []
    for section in structured_effects:
        condition = section.get("condition", "")
        effects = section.get("effects", [])
        
        if condition and effects:
            effect_text = "; ".join(effects)
            parts.append(f"{condition}: {effect_text}")
        elif effects:
            parts.append("; ".join(effects))
    
    return " | ".join(parts)

def format_stats(stats: Dict) -> Dict:
    """Format stats for frontend"""
    formatted = {
        "generalInfo": stats.get("general_info", {}),
        "baseStats": stats.get("base_stats", {}),
        "hiddenPotential": {}
    }
    
    # Extract all hidden potential percentages
    for key, value in stats.items():
        if key.startswith("hidden_potential_"):
            percentage = key.replace("hidden_potential_", "").replace("_percent", "%")
            formatted["hiddenPotential"][percentage] = value
    
    return formatted

# ------------ API Routes -------------

@app.route('/api/cards', methods=['GET'])
def get_cards():
    """Get all cards with optional filtering"""
    try:
        # Load cards (in production, cache this)
        cards = load_all_cards()
        
        # Apply filters from query params
        rarity_filter = request.args.get('rarity')
        type_filter = request.args.get('type')
        search_query = request.args.get('search', '').lower()
        
        filtered_cards = cards
        
        if rarity_filter and rarity_filter != 'ALL':
            filtered_cards = [c for c in filtered_cards if c['rarity'] == rarity_filter]
        
        if type_filter and type_filter != 'ALL':
            filtered_cards = [c for c in filtered_cards if c['type'] == type_filter]
        
        if search_query:
            filtered_cards = [
                c for c in filtered_cards 
                if search_query in c['name'].lower() 
                or search_query in c.get('displayNameWithType', '').lower()
            ]
        
        return jsonify({
            "success": True,
            "count": len(filtered_cards),
            "cards": filtered_cards
        })
        
    except Exception as e:
        logging.error(f"Error in get_cards: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/cards/<card_id>', methods=['GET'])
def get_card(card_id):
    """Get a specific card by ID"""
    try:
        cards = load_all_cards()
        card = next((c for c in cards if c['id'] == card_id), None)
        
        if not card:
            return jsonify({
                "success": False,
                "error": f"Card with ID {card_id} not found"
            }), 404
        
        return jsonify({
            "success": True,
            "card": card
        })
        
    except Exception as e:
        logging.error(f"Error in get_card: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        cards = load_all_cards()
        
        # Calculate stats
        rarity_counts = {}
        type_counts = {}
        
        for card in cards:
            rarity = card.get('rarity', 'UNKNOWN')
            card_type = card.get('type', 'UNKNOWN')
            
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            type_counts[card_type] = type_counts.get(card_type, 0) + 1
        
        return jsonify({
            "success": True,
            "stats": {
                "totalCards": len(cards),
                "byRarity": rarity_counts,
                "byType": type_counts
            }
        })
        
    except Exception as e:
        logging.error(f"Error in get_stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/proxy-image', methods=['GET'])
def proxy_image():
    """Proxy images to avoid CORS issues"""
    image_url = request.args.get('url')
    
    if not image_url:
        return jsonify({"success": False, "error": "No URL provided"}), 400
    
    try:
        # Fetch the image from dokkaninfo.com
        response = requests.get(image_url, headers=DOWNLOAD_HEADERS, timeout=10)
        response.raise_for_status()
        
        # Return the image with appropriate headers
        return Response(
            response.content,
            mimetype=response.headers.get('Content-Type', 'image/png'),
            headers={
                'Cache-Control': 'public, max-age=86400',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        logging.error(f"Error proxying image {image_url}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "status": "healthy",
        "message": "Dokkan API is running"
    })

# ------------ Main -------------
if __name__ == '__main__':
    logging.info("Starting Dokkan API Server...")
    logging.info(f"Loading cards from: {OUTPUT_ROOT_DIR.absolute()}")
    
    # Test load cards on startup
    cards = load_all_cards()
    logging.info(f"API ready with {len(cards)} cards")
    
    app.run(
        host=API_HOST,
        port=API_PORT,
        debug=True
    )