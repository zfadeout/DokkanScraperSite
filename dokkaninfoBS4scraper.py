# dokkaninfoBS4scraper.py
# Advanced Dokkan scraper with pagination, indexing, and clean nested JSON formatting

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

from bs4 import BeautifulSoup, NavigableString, Tag
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ------------ Config -------------
BASE_URL = "https://dokkaninfo.com"
CARDS_INDEX_URL = f"{BASE_URL}/cards?sort=open_at"

OUTPUT_ROOT_DIR = Path("output/cards")
ASSETS_ROOT_DIR = Path("output/assets")
INDEX_FILE_PATH = OUTPUT_ROOT_DIR / "CARDS_INDEX.json"
LOGS_DIR = Path("output/logs")

USER_AGENT_STRING = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

PAGE_TIMEOUT_MS = 60_000
DELAY_BETWEEN_CARDS_SEC = 0.6
MAX_PAGES_TO_SCRAPE = 200
MAX_NEW_CARDS_TO_SAVE = 10

SECTION_HEADERS = [
    "Leader Skill",
    "Super Attack",
    "Ultra Super Attack",
    "Passive Skill",
    "Active Skill",
    "Activation Condition(s)",
    "Transformation Condition(s)",
    "Link Skills",
    "Categories",
    "Stats",
]

CATEGORY_FILTER_TOKENS = {
    "background", "icon", "rarity", "element", "eza", "undefined",
    "venatus", "show more", "links", "categories",
}
FILE_EXTENSION_PATTERN = re.compile(r"\.(png|jpg|jpeg|gif|webp)$", re.IGNORECASE)

CARD_ID_FROM_HREF_PATTERN = re.compile(r"/cards/(\d+)")
CARD_ID_FROM_SRC_PATTERN = re.compile(r"card_(\d+)_", re.IGNORECASE)

VALID_TYPE_SUFFIXES = {"str", "teq", "int", "agl", "phy"}

# ------------ Logging -------------
def setup_logging() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file_path = LOGS_DIR / f"run-{timestamp}.log"

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("Logging to %s", log_file_path)
    return log_file_path

# ------------ Index helpers -------------
def load_index() -> Dict[str, dict]:
    if INDEX_FILE_PATH.exists():
        try:
            return json.loads(INDEX_FILE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning("Failed to read index (%s). Starting fresh.", e)
    return {}

def save_index(index_data: Dict[str, dict]) -> None:
    INDEX_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE_PATH.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")

# ------------ Helpers -------------
def sanitize_filename(name: str) -> str:
    name = (
        name.replace(":", " -")
        .replace("/", "-")
        .replace("\\", "-")
        .replace("|", "-")
        .replace("*", "x")
        .replace("?", "")
        .replace('"', "'")
        .strip()
    )
    name = re.sub(r"\s+", " ", name)
    return name.rstrip(" .")

def extract_character_id_from_url(url: str) -> Optional[str]:
    match = CARD_ID_FROM_HREF_PATTERN.search(url)
    return match.group(1) if match else None

def extract_ids_from_col5_images(page_html: str) -> List[str]:
    """Extract card IDs from header row, skipping first tile"""
    soup = BeautifulSoup(page_html, "lxml")

    required_classes = {"row", "cursor-pointer", "unselectable", "border", "border-2", "border-dark", "margin-top-bottom-5"}
    header_div = None
    for div in soup.find_all("div"):
        div_classes = set(div.get("class") or [])
        if required_classes.issubset(div_classes):
            header_div = div
            break

    if not header_div:
        return []

    col5_tiles = header_div.find_all("div", class_=lambda v: v and "col-5" in v.split())
    if not col5_tiles:
        return []

    extracted_ids: List[str] = []
    seen_ids: Set[str] = set()

    for tile in col5_tiles[1:]:  # Skip first tile
        img = tile.find("img")
        if not img:
            continue
        src = img.get("src") or ""
        match = CARD_ID_FROM_SRC_PATTERN.search(src)
        if match:
            card_id = match.group(1)
            if card_id not in seen_ids:
                seen_ids.add(card_id)
                extracted_ids.append(card_id)

    return extracted_ids

def build_next_index_url(current_url: str) -> str:
    """Increment page parameter in URL"""
    parsed_url = urlparse(current_url)
    query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    if "page" not in query_params:
        query_params["page"] = "2"
    else:
        try:
            query_params["page"] = str(int(query_params["page"]) + 1)
        except Exception:
            query_params["page"] = "2"
    new_query_string = urlencode(query_params, doseq=True)
    return urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query_string, parsed_url.fragment))

# ------------ TEXT parsing -------------
def _split_sections(page_text: str) -> Dict[str, List[str]]:
    text_lines = [re.sub(r"\s+", " ", line).strip() for line in page_text.splitlines()]
    header_indices: List[Tuple[str, int]] = []
    for line_index, line in enumerate(text_lines):
        if line in SECTION_HEADERS:
            header_indices.append((line, line_index))

    sections_dict: Dict[str, List[str]] = {}
    for i, (header_name, start_index) in enumerate(header_indices):
        end_index = len(text_lines)
        if i + 1 < len(header_indices):
            end_index = header_indices[i + 1][1]
        content_block = [line for line in text_lines[start_index + 1:end_index] if line != ""]
        sections_dict[header_name] = content_block
    return sections_dict

def _condense_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _dedup_sentences(text: str) -> str:
    sentence_parts = [part.strip() for part in re.split(r'(?<=[.!?])\s+', text) if part.strip()]
    output_parts = []
    seen_sentences = set()
    for part in sentence_parts:
        if part not in seen_sentences:
            seen_sentences.add(part)
            output_parts.append(part)
    return " ".join(output_parts)

def _clean_leader(content_block: List[str]) -> Optional[str]:
    if not content_block:
        return None
    leader_text = _condense_spaces(" ".join(content_block))
    leader_text = _dedup_sentences(leader_text)
    leader_text = re.sub(
        r'("Exploding Rage"\s*Category\s+Ki\s*\+\d+\s+and\s+HP,\s*ATK\s*&\s*DEF\s*\+\d+%)\s*\1',
        r"\1",
        leader_text,
        flags=re.IGNORECASE,
    )
    return leader_text or None

def _clean_super_like(content_block: List[str]) -> Tuple[Optional[str], Optional[str]]:
    if not content_block:
        return None, None
    attack_name = content_block[0]
    remaining_lines = content_block[1:]
    effect_parts: List[str] = []
    for line in remaining_lines:
        if not line:
            continue
        if re.fullmatch(r"\d+\s*%$", line):
            continue
        if re.search(r"\bSA\s*Lv\b", line, flags=re.IGNORECASE):
            continue
        effect_parts.append(line)
    effect_text = "; ".join(effect_parts)
    effect_text = re.sub(r"\s*;\s*", "; ", effect_text)
    effect_text = re.sub(r"\s*Raises ATK & DEF\s*Causes", " Raises ATK & DEF; Causes", effect_text, flags=re.IGNORECASE)
    effect_text = _condense_spaces(effect_text)
    return (attack_name or None), (effect_text or None)

def parse_passive_from_soup(soup: BeautifulSoup) -> Tuple[Optional[str], List[Dict[str, object]]]:
    """Parse passive skill with structured conditions from HTML"""
    passive_name = None
    passive_sections = []
    
    # Find the Passive Skill section
    passive_label = soup.find("b", string="Passive Skill")
    if not passive_label:
        return None, []
    
    # Get the passive name from the adjacent column
    passive_row = passive_label.find_parent("div", class_="row")
    if passive_row:
        name_col = passive_row.find("div", class_="col-sm-8")
        if name_col:
            passive_name_tag = name_col.find("b")
            if passive_name_tag:
                passive_name = passive_name_tag.get_text(strip=True)
            else:
                passive_name = name_col.get_text(strip=True)
    
    # Find the content row (next row with bg- class)
    content_row = None
    if passive_row:
        next_sibling = passive_row.find_next_sibling("div")
        while next_sibling and not content_row:
            sibling_classes = next_sibling.get("class") or []
            if any("bg-" in cls for cls in sibling_classes):
                content_row = next_sibling
                break
            next_sibling = next_sibling.find_next_sibling("div")
    
    if not content_row:
        return passive_name, []
    
    # Parse the structured content
    content_div = content_row.find("div", class_="col")
    if not content_div:
        # Try finding any div with text content
        content_div = content_row.find("div", class_=lambda c: c and "col" in str(c))
    
    if not content_div:
        return passive_name, []
    
    # Find all strong tags (condition headers) and their associated ul tags
    current_section = None
    
    for element in content_div.descendants:
        if isinstance(element, Tag):
            if element.name == "strong":
                # Start a new section
                condition_text = element.get_text(strip=True)
                if condition_text and condition_text not in SECTION_HEADERS:
                    current_section = {
                        "condition": condition_text,
                        "effects": []
                    }
                    passive_sections.append(current_section)
            elif element.name == "li" and current_section is not None:
                # Parse effects from list items
                effect_text = element.get_text(" ", strip=True)
                # Clean up arrow images text
                effect_text = re.sub(r'\s*up green arrow\s*', ' ↑', effect_text)
                effect_text = _condense_spaces(effect_text)
                if effect_text and effect_text not in current_section["effects"]:
                    current_section["effects"].append(effect_text)
    
    # If we didn't find any sections, return empty
    if not passive_sections:
        return passive_name, []
    
    return passive_name, passive_sections

def _clean_active(content_block: List[str]) -> Tuple[Optional[str], Optional[str]]:
    if not content_block:
        return None, None
    active_name = content_block[0]
    active_body = []
    for line in content_block[1:]:
        if line in SECTION_HEADERS or re.fullmatch(r"Link Skills", line, re.IGNORECASE):
            break
        active_body.append(line)
    active_effect = _condense_spaces("; ".join([_condense_spaces(text) for text in active_body if text]))
    return (active_name or None), (active_effect or None)

def _clean_activation(content_block: List[str]) -> Optional[str]:
    if not content_block:
        return None
    activation_text = _condense_spaces(" ".join(content_block))
    for header in SECTION_HEADERS:
        activation_text = activation_text.replace(header, "")
    return activation_text.strip() or None

def _clean_links(content_block: List[str]) -> List[str]:
    output_links: List[str] = []
    seen_links = set()
    for line in content_block or []:
        cleaned_link = _condense_spaces(line)
        if not cleaned_link or cleaned_link in seen_links:
            continue
        seen_links.add(cleaned_link)
        output_links.append(cleaned_link)
    return output_links

def _parse_stats(content_block: List[str], page_text: str) -> Dict[str, object]:
    stats_dict: Dict[str, object] = {}
    cost_match = re.search(r"\bCost\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if cost_match:
        stats_dict["Cost"] = int(cost_match.group(1))
    max_level_match = re.search(r"\bMax\s*Lv\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if max_level_match:
        stats_dict["Max Lv"] = int(max_level_match.group(1))
    sa_level_match = re.search(r"\bSA\s*Lv\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if sa_level_match:
        stats_dict["SA Lv"] = int(sa_level_match.group(1))

    def parse_stat_row(stat_key: str) -> Optional[Dict[str, int]]:
        row_pattern = re.compile(rf"^{stat_key}\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)$", flags=re.IGNORECASE)
        for line in content_block:
            match = row_pattern.match(line)
            if match:
                return {
                    "Base Min": int(match.group(1).replace(",", "")),
                    "Base Max": int(match.group(2).replace(",", "")),
                    "55%": int(match.group(3).replace(",", "")),
                    "100%": int(match.group(4).replace(",", "")),
                }
        return None

    for stat_key in ["HP", "ATK", "DEF"]:
        stat_row = parse_stat_row(stat_key)
        if stat_row:
            stats_dict[stat_key] = stat_row
    return stats_dict

def parse_stats_from_soup(soup: BeautifulSoup, page_text: str) -> Dict[str, object]:
    """Parse stats table with all percentage columns from HTML"""
    stats_dict: Dict[str, object] = {}
    
    # Parse Cost, Max Lv, SA Lv from text
    cost_match = re.search(r"\bCost\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if cost_match:
        stats_dict["Cost"] = int(cost_match.group(1))
    max_level_match = re.search(r"\bMax\s*Lv\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if max_level_match:
        stats_dict["Max Lv"] = int(max_level_match.group(1))
    sa_level_match = re.search(r"\bSA\s*Lv\s*:\s*(\d+)", page_text, flags=re.IGNORECASE)
    if sa_level_match:
        stats_dict["SA Lv"] = int(sa_level_match.group(1))
    
    # Find the stats table
    stats_table = None
    for table in soup.find_all("table"):
        header_row = table.find("tr")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
            if "Stats" in headers or ("HP" in str(table) and "ATK" in str(table) and "DEF" in str(table)):
                stats_table = table
                break
    
    if not stats_table:
        return stats_dict
    
    # Get all header columns
    header_row = stats_table.find("tr")
    headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
    
    logging.debug("Found stats table headers: %s", headers)
    
    # Parse each stat row
    for row in stats_table.find_all("tr")[1:]:  # Skip header row
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        
        stat_name = cells[0].get_text(strip=True)
        if stat_name not in ["HP", "ATK", "DEF"]:
            continue
        
        stat_values = {}
        for i, cell in enumerate(cells[1:], start=1):
            if i < len(headers):
                column_name = headers[i]
                value_text = cell.get_text(strip=True).replace(",", "")
                try:
                    stat_values[column_name] = int(value_text)
                except ValueError:
                    continue
        
        if stat_values:
            stats_dict[stat_name] = stat_values
            logging.debug("Parsed %s stats: %s", stat_name, stat_values)
    
    return stats_dict

def _parse_release(page_text: str) -> Tuple[Optional[str], Optional[str]]:
    release_match = re.search(
        r"Release Date\s+([0-9/.\-]+)\s+([0-9: ]+[APMapm]{2})\s+([A-Z]{2,4})",
        page_text,
        flags=re.IGNORECASE,
    )
    if release_match:
        return f"{release_match.group(1)} {release_match.group(2)}", release_match.group(3)
    return None, None

def _clean_categories_python(categories: List[str]) -> List[str]:
    output_categories = []
    seen_categories = set()
    for category in categories or []:
        category = (category or "").strip().strip("•· ")
        if not category:
            continue
        category_lower = category.lower()
        if category_lower in CATEGORY_FILTER_TOKENS:
            continue
        if FILE_EXTENSION_PATTERN.search(category):
            continue
        if re.fullmatch(r"[\d\s%:]+", category):
            continue
        if category in SECTION_HEADERS or "Links:" in category or "Show More" in category:
            continue
        if category in seen_categories:
            continue
        seen_categories.add(category)
        output_categories.append(category)
    return output_categories

def parse_categories_from_soup(soup: BeautifulSoup) -> List[str]:
    categories_strategy1 = [(img.get("alt") or img.get("title") or "") for img in soup.select('a[href*="/categories/"] img')]
    categories_strategy1 = [cat for cat in categories_strategy1 if cat]

    categories_strategy2 = [(img.get("alt") or img.get("title") or "") for img in soup.select('img[src*="/card_category/label/"]')]
    categories_strategy2 = [cat for cat in categories_strategy2 if cat]

    categories_strategy3 = []
    category_element: Optional[Tag] = None
    for element in soup.find_all(string=True):
        if isinstance(element, NavigableString) and str(element).strip() == "Categories":
            category_element = element.parent if isinstance(element.parent, Tag) else None
            if category_element:
                break
    if category_element:
        for sibling in category_element.next_siblings:
            if isinstance(sibling, NavigableString):
                sibling_text = str(sibling).strip()
                if sibling_text in SECTION_HEADERS:
                    break
                continue
            if isinstance(sibling, Tag):
                sibling_text = sibling.get_text(strip=True)
                if sibling_text in SECTION_HEADERS:
                    break
                for img in sibling.find_all("img"):
                    src = img.get("src") or ""
                    if "/card_category/label/" in src:
                        label = img.get("alt") or img.get("title") or ""
                        if label:
                            categories_strategy3.append(label)
                for anchor in sibling.find_all("a"):
                    href = anchor.get("href") or ""
                    if "/categories/" in href:
                        anchor_text = anchor.get_text(strip=True)
                        if anchor_text:
                            categories_strategy3.append(anchor_text)

    merged_categories = []
    seen_categories = set()
    for category_pool in (categories_strategy1, categories_strategy2, categories_strategy3):
        for category in category_pool:
            category_clean = category.strip()
            if category_clean and category_clean not in seen_categories:
                seen_categories.add(category_clean)
                merged_categories.append(category_clean)
    return _clean_categories_python(merged_categories)

# ------------ Rarity & Type detection -------------
def detect_rarity_from_dom(soup: BeautifulSoup, image_urls_fallback: List[str]) -> Optional[str]:
    rarity_map = {
        "lr": "LR",
        "ur": "UR",
        "ssr": "SSR",
        "sr": "SR",
        "r": "R",
        "n": "N",
    }

    rarity_node = soup.select_one("div.card-icon-item.card-icon-item-rarity.card-info-above-thumb img[src]")
    if rarity_node:
        src = (rarity_node.get("src") or "").lower()
        match = re.search(r"cha_rare(?:_sm)?_(lr|ur|ssr|sr|r|n)\.png", src)
        if match:
            rarity_key = match.group(1).lower()
            return rarity_map.get(rarity_key)

    for url in image_urls_fallback or []:
        url_lower = url.lower()
        match = re.search(r"cha_rare(?:_sm)?_(lr|ur|ssr|sr|r|n)\.png", url_lower)
        if match:
            rarity_key = match.group(1).lower()
            return rarity_map.get(rarity_key)
    return None

def detect_type_token_from_dom(soup: BeautifulSoup) -> Optional[str]:
    """Find type from row classes"""
    candidates = soup.select("div.row.justify-content-center.align-items-center.padding-top-bottom-10.border.border-2")
    if not candidates:
        return None

    class_list = candidates[0].get("class") or []
    type_token = None
    for class_name in class_list:
        if class_name.startswith("border-") or class_name.startswith("bg-"):
            suffix = class_name.split("-", 1)[-1].strip().lower()
            if suffix in VALID_TYPE_SUFFIXES:
                type_token = suffix
    return type_token

# ------------ Domains parser -------------
def detect_type_suffix_from_classes(class_list: List[str]) -> Optional[str]:
    type_suffix = None
    for class_name in class_list or []:
        if class_name.startswith("border-") or class_name.startswith("bg-"):
            suffix = class_name.split("-", 1)[-1].strip().lower()
            if suffix in VALID_TYPE_SUFFIXES:
                type_suffix = suffix
    return type_suffix

# ------------ Domains parser -------------
def detect_type_suffix_from_classes(class_list: List[str]) -> Optional[str]:
    type_suffix = None
    for class_name in class_list or []:
        if class_name.startswith("border-") or class_name.startswith("bg-"):
            suffix = class_name.split("-", 1)[-1].strip().lower()
            if suffix in VALID_TYPE_SUFFIXES:
                type_suffix = suffix
    return type_suffix

def parse_domains(soup: BeautifulSoup) -> List[Dict[str, Optional[str]]]:
    """Parse domain effect blocks"""
    domains_list: List[Dict[str, Optional[str]]] = []
    for bold_node in soup.find_all("b", string=re.compile(r"^\s*Domain Effect\(s\)\s*$", re.IGNORECASE)):
        outer_row = bold_node.find_parent("div", class_=re.compile(r"\brow\b"))
        if not outer_row:
            continue
        bold_elements = outer_row.find_all("b")
        domain_name = None
        if len(bold_elements) >= 2:
            domain_name = bold_elements[1].get_text(strip=True)

        container = outer_row.find_parent("div", class_=re.compile(r"\bborder\b"))
        type_suffix = None
        if container:
            type_suffix = detect_type_suffix_from_classes(container.get("class") or [])

        effect_text = None
        effect_row = outer_row.find_next_sibling("div")
        hops = 0
        while effect_row and hops < 3 and not effect_text:
            if effect_row.get("class") and any(c.startswith("bg-") and c.endswith("-2") for c in effect_row.get("class")):
                effect_text = effect_row.get_text(" ", strip=True)
                break
            deep = effect_row.find("div", class_=re.compile(r"\bbg-.*-2\b"))
            if deep:
                effect_text = deep.get_text(" ", strip=True)
                break
            effect_row = effect_row.find_next_sibling("div")
            hops += 1

        domains_list.append({
            "name": domain_name,
            "effect": effect_text,
            "type": (type_suffix.upper() if type_suffix else None),
        })

    seen_domains = set()
    unique_domains = []
    for domain in domains_list:
        domain_key = (domain.get("name") or "", domain.get("effect") or "")
        if domain_key in seen_domains:
            continue
        seen_domains.add(domain_key)
        unique_domains.append(domain)
    return unique_domains

def parse_eza_info(soup: BeautifulSoup) -> Dict[str, object]:
    """Parse EZA/SEZA information from the card page"""
    eza_info = {
        "has_eza": False,
        "eza_step": None,
        "is_seza": False,
        "release_date": None,
        "eza_release_date": None
    }
    
    # Look for EZA/PRE-EZA toggle buttons
    eza_toggle = None
    for row in soup.find_all("div", class_="row"):
        if "PRE-EZA" in row.get_text() and "EZA" in row.get_text():
            eza_toggle = row
            break
    
    if not eza_toggle:
        return eza_info
    
    # If EZA toggle exists, the card has EZA
    eza_info["has_eza"] = True
    
    # Find the Step selector
    step_row = eza_toggle.find_next_sibling("div", class_="row")
    if step_row and "Step:" in step_row.get_text():
        # Look for the selected step value
        multiselect_single = step_row.find("span", class_="multiselect__single")
        if multiselect_single:
            step_text = multiselect_single.get_text(strip=True)
            try:
                step_number = int(step_text)
                eza_info["eza_step"] = step_number
                
                # Step 4 = SEZA (Super Extreme Z-Awakening)
                if step_number == 4:
                    eza_info["is_seza"] = True
            except ValueError:
                pass
    
    # Find Release Date section
    release_section = None
    for div in soup.find_all("div"):
        if "Release Date" in div.get_text() and "EZA Release Date" in div.get_text():
            release_section = div
            break
    
    if release_section:
        # Parse release dates
        text_content = release_section.get_text("\n", strip=True)
        
        # Find regular release date
        release_match = re.search(r"Release Date\s+(\d+/\d+/\d+\s+\d+:\d+:\d+\s+[AP]M\s+[A-Z]+)", text_content)
        if release_match:
            eza_info["release_date"] = release_match.group(1).strip()
        
        # Find EZA release date
        eza_release_match = re.search(r"EZA Release Date\s+(\d+/\d+/\d+\s+\d+:\d+:\d+\s+[AP]M\s+[A-Z]+)", text_content)
        if eza_release_match:
            eza_info["eza_release_date"] = eza_release_match.group(1).strip()
    
    return eza_info
    """Parse domain effect blocks"""
    domains_list: List[Dict[str, Optional[str]]] = []
    for bold_node in soup.find_all("b", string=re.compile(r"^\s*Domain Effect\(s\)\s*$", re.IGNORECASE)):
        outer_row = bold_node.find_parent("div", class_=re.compile(r"\brow\b"))
        if not outer_row:
            continue
        bold_elements = outer_row.find_all("b")
        domain_name = None
        if len(bold_elements) >= 2:
            domain_name = bold_elements[1].get_text(strip=True)

        container = outer_row.find_parent("div", class_=re.compile(r"\bborder\b"))
        type_suffix = None
        if container:
            type_suffix = detect_type_suffix_from_classes(container.get("class") or [])

        effect_text = None
        effect_row = outer_row.find_next_sibling("div")
        hops = 0
        while effect_row and hops < 3 and not effect_text:
            if effect_row.get("class") and any(c.startswith("bg-") and c.endswith("-2") for c in effect_row.get("class")):
                effect_text = effect_row.get_text(" ", strip=True)
                break
            deep = effect_row.find("div", class_=re.compile(r"\bbg-.*-2\b"))
            if deep:
                effect_text = deep.get_text(" ", strip=True)
                break
            effect_row = effect_row.find_next_sibling("div")
            hops += 1

        domains_list.append({
            "name": domain_name,
            "effect": effect_text,
            "type": (type_suffix.upper() if type_suffix else None),
        })

    seen_domains = set()
    unique_domains = []
    for domain in domains_list:
        domain_key = (domain.get("name") or "", domain.get("effect") or "")
        if domain_key in seen_domains:
            continue
        seen_domains.add(domain_key)
        unique_domains.append(domain)
    return unique_domains

def format_metadata_output(metadata: Dict[str, object]) -> Dict[str, object]:
    """Format metadata in clean nested structure without special characters"""
    
    def format_stats_by_percentage(stats: Dict) -> Dict:
        """Format stats separated by percentage levels"""
        if not stats:
            return {}
        
        # Extract base stats (Cost, Max Lv, SA Lv)
        base_info = {}
        for key in ["Cost", "Max Lv", "SA Lv"]:
            if key in stats:
                base_info[key] = stats[key]
        
        # Extract HP, ATK, DEF stats
        hp_stats = stats.get("HP", {})
        atk_stats = stats.get("ATK", {})
        def_stats = stats.get("DEF", {})
        
        if not hp_stats and not atk_stats and not def_stats:
            return {"general_info": base_info}
        
        # Get all percentage columns available
        all_percentages = set()
        for stat_dict in [hp_stats, atk_stats, def_stats]:
            if isinstance(stat_dict, dict):
                all_percentages.update(stat_dict.keys())
        
        # Remove base columns
        percentage_columns = sorted([p for p in all_percentages if "%" in str(p)], 
                                   key=lambda x: float(str(x).replace("%", "")))
        base_columns = ["Base Min", "Base Max"]
        
        result = {"general_info": base_info}
        
        # Add base stats
        if any(col in all_percentages for col in base_columns):
            base_stats = {}
            if hp_stats and isinstance(hp_stats, dict):
                hp_base = {k: v for k, v in hp_stats.items() if k in base_columns}
                if hp_base:
                    base_stats["HP"] = hp_base
            if atk_stats and isinstance(atk_stats, dict):
                atk_base = {k: v for k, v in atk_stats.items() if k in base_columns}
                if atk_base:
                    base_stats["ATK"] = atk_base
            if def_stats and isinstance(def_stats, dict):
                def_base = {k: v for k, v in def_stats.items() if k in base_columns}
                if def_base:
                    base_stats["DEF"] = def_base
            
            if base_stats:
                result["base_stats"] = base_stats
        
        # Add each percentage level
        for percentage in percentage_columns:
            percentage_stats = {}
            
            if hp_stats and isinstance(hp_stats, dict) and percentage in hp_stats:
                percentage_stats["HP"] = hp_stats[percentage]
            if atk_stats and isinstance(atk_stats, dict) and percentage in atk_stats:
                percentage_stats["ATK"] = atk_stats[percentage]
            if def_stats and isinstance(def_stats, dict) and percentage in def_stats:
                percentage_stats["DEF"] = def_stats[percentage]
            
            if percentage_stats:
                clean_key = f"hidden_potential_{percentage.replace('%', '_percent')}"
                result[clean_key] = percentage_stats
        
        return result
    
    def format_passive_sections(sections: List[Dict]) -> List[Dict]:
        """Format passive skill sections with proper structure"""
        if not sections:
            return []
        
        formatted = []
        for section in sections:
            condition = section.get("condition", "")
            effects = section.get("effects", [])
            
            formatted.append({
                "condition": condition if condition else "Basic effect(s)",
                "effects": effects
            })
        
        return formatted
    
    super_attack = metadata.get("super_attack", {})
    ultra_attack = metadata.get("ultra_super_attack", {})
    passive_skill = metadata.get("passive_skill", {})
    active_skill = metadata.get("active_skill", {})
    
    super_name = super_attack.get("name")
    super_effect = super_attack.get("effect")
    formatted_super = {
        "name": super_name if super_name else None,
        "effect": super_effect if super_effect else None
    }
    
    ultra_name = ultra_attack.get("name")
    ultra_effect = ultra_attack.get("effect")
    formatted_ultra = {
        "name": ultra_name if ultra_name else None,
        "effect": ultra_effect if ultra_effect else None
    }
    
    passive_name = passive_skill.get("name")
    passive_sections = passive_skill.get("sections", [])
    formatted_passive = {
        "name": passive_name if passive_name else None,
        "structured_effects": format_passive_sections(passive_sections)
    }
    
    active_name = active_skill.get("name")
    active_effect = active_skill.get("effect")
    active_conditions = active_skill.get("activation_conditions")
    formatted_active = {
        "name": active_name if active_name else None,
        "effect": active_effect if active_effect else None,
        "activation_conditions": active_conditions if active_conditions else None
    }
    
    rarity = metadata.get("rarity_detected")
    type_upper = metadata.get("type_token_upper")
    type_lower = metadata.get("type_token")
    
    display_name = metadata.get("display_name", "")
    page_title = metadata.get("page_title", "")
    
    if rarity and type_upper:
        display_with_type = f"[{rarity}] [{type_upper}] {display_name}"
        display_bracketed = f"[{rarity}] [{type_upper}] [{display_name}]"
    else:
        display_with_type = display_name
        display_bracketed = f"[{display_name}]"
    
    categories = metadata.get("categories", [])
    link_skills = metadata.get("link_skills", [])
    
    domains = metadata.get("domains", [])
    formatted_domains = []
    if domains:
        for domain in domains:
            formatted_domains.append({
                "name": domain.get('name', 'Unknown'),
                "effect": domain.get('effect', None),
                "type": domain.get('type', 'N/A')
            })
    
    # Format EZA info
    eza_data = metadata.get("eza_info", {})
    formatted_eza = {
        "has_eza": eza_data.get("has_eza", False),
        "eza_step": eza_data.get('eza_step'),
        "is_seza": eza_data.get("is_seza", False),
        "original_release_date": eza_data.get('release_date'),
        "eza_release_date": eza_data.get('eza_release_date')
    }
    
    restructured = {
        "card_identification": {
            "page_title": page_title,
            "display_name": display_name,
            "display_name_with_type": display_with_type,
            "display_name_with_type_bracketed": display_bracketed,
            "character_id": metadata.get('character_id', 'unknown')
        },
        
        "release_details": {
            "release_date": metadata.get('release_date', 'Unknown'),
            "timezone": metadata.get('timezone', 'Unknown')
        },
        
        "leader_ability": {
            "leader_skill": metadata.get("leader_skill")
        },
        
        "attack_techniques": {
            "super_attack": formatted_super,
            "ultra_super_attack": formatted_ultra
        },
        
        "passive_skill": formatted_passive,
        
        "active_skill": formatted_active,
        
        "link_skills": link_skills,
        
        "categories": categories,
        
        "base_statistics": format_stats_by_percentage(metadata.get("stats", {})),
        
        "extreme_z_awakening": formatted_eza,
        
        "domain_effects": formatted_domains,
        
        "metadata": {
            "source_url": metadata.get('source_url', 'Unknown'),
            "rarity_detected": rarity if rarity else "UNKNOWN",
            "type_token": type_lower if type_lower else "unknown",
            "type_token_upper": type_upper if type_upper else "UNKNOWN",
            "type_icon_filename": metadata.get('type_icon_filename', 'none')
        },
        
        "image_resources": metadata.get("image_urls", [])
    }
    
    return restructured

# ------------ Scraping core -------------
def scrape_card_from_html(page_html: str, page_url: str) -> Dict[str, object]:
    soup = BeautifulSoup(page_html, "lxml")
    page_text = soup.get_text("\n", strip=True)

    sections_dict = _split_sections(page_text)

    leader_skill = _clean_leader(sections_dict.get("Leader Skill") or [])
    super_attack_name, super_attack_effect = _clean_super_like(sections_dict.get("Super Attack") or [])
    ultra_attack_name, ultra_attack_effect = _clean_super_like(sections_dict.get("Ultra Super Attack") or [])

    if not super_attack_name:
        super_fallback_match = re.search(r"Super Attack\s+([\s\S]*?)\s+Ultra Super Attack", page_text, flags=re.IGNORECASE)
        if super_fallback_match:
            fallback_block = [line.strip() for line in super_fallback_match.group(1).splitlines() if line.strip()]
            fallback_name, fallback_effect = _clean_super_like(fallback_block)
            super_attack_name = super_attack_name or fallback_name
            super_attack_effect = super_attack_effect or fallback_effect

    if not ultra_attack_name:
        ultra_fallback_match = re.search(
            r"Ultra Super Attack\s+([\s\S]*?)\s+(Passive Skill|Active Skill|Link Skills|Categories|Stats|Transformation Condition\(s\))",
            page_text,
            flags=re.IGNORECASE,
        )
        if ultra_fallback_match:
            fallback_block = [line.strip() for line in ultra_fallback_match.group(1).splitlines() if line.strip()]
            fallback_name, fallback_effect = _clean_super_like(fallback_block)
            ultra_attack_name = ultra_attack_name or fallback_name
            ultra_attack_effect = ultra_attack_effect or fallback_effect

    # Parse passive skill with structured format from HTML
    passive_skill_name, passive_sections = parse_passive_from_soup(soup)

    active_skill_name, active_skill_effect = _clean_active(sections_dict.get("Active Skill") or [])
    activation_conditions = _clean_activation(sections_dict.get("Activation Condition(s)") or [])
    link_skills = _clean_links(sections_dict.get("Link Skills") or [])

    final_categories = parse_categories_from_soup(soup)
    stats_dict = parse_stats_from_soup(soup, page_text)
    release_date, timezone = _parse_release(page_text)

    image_urls = []
    seen_image_urls = set()
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        absolute_url = urljoin(page_url, src)
        if absolute_url not in seen_image_urls:
            seen_image_urls.add(absolute_url)
            image_urls.append(absolute_url)

    rarity_detected = detect_rarity_from_dom(soup, image_urls)
    type_token = detect_type_token_from_dom(soup)
    type_token_upper = type_token.upper() if type_token else None

    type_icon_filename = None
    for url in image_urls:
        if "cha_type_icon_" in url.lower():
            type_icon_filename = url.split("/")[-1]
            break

    h1_element = soup.select_one("h1")
    base_display_name = (
        h1_element.get_text(strip=True)
        if (h1_element and h1_element.get_text(strip=True))
        else (soup.title.string.strip() if (soup.title and soup.title.string) else "")
    )
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""

    prefix_parts = []
    if rarity_detected:
        prefix_parts.append(rarity_detected)
    if type_token_upper:
        prefix_parts.append(f"[{type_token_upper}]")
    prefix = " ".join(prefix_parts)
    display_name_with_type = f"{prefix} {base_display_name}".strip() if prefix else base_display_name
    display_name_with_type_bracketed = f"{prefix} [{base_display_name}]".strip() if prefix else f"[{base_display_name}]"

    character_id = extract_character_id_from_url(page_url)

    domains_list = parse_domains(soup)
    eza_info = parse_eza_info(soup)

    metadata_dict = {
        "page_title": page_title,
        "display_name": base_display_name,
        "display_name_and_typing": display_name_with_type,
        "display_name_and_typing_extended": display_name_with_type_bracketed,
        "character_id": character_id,
        "release_date": release_date,
        "timezone": timezone,
        "leader_skill": leader_skill,
        "super_attack": {"name": super_attack_name, "effect": super_attack_effect},
        "ultra_super_attack": {"name": ultra_attack_name, "effect": ultra_attack_effect},
        "passive_skill": {
            "name": passive_skill_name,
            "sections": passive_sections,
        },
        "active_skill": {
            "name": active_skill_name,
            "effect": active_skill_effect,
            "activation_conditions": activation_conditions,
        },
        "link_skills": link_skills,
        "categories": final_categories,
        "stats": stats_dict,
        "domains": domains_list,
        "eza_info": eza_info,
        "source_url": page_url,
        "rarity_detected": rarity_detected,
        "type_token": type_token,
        "type_token_upper": type_token_upper,
        "type_icon_filename": type_icon_filename,
        "image_urls": image_urls,
    }
    return metadata_dict
def save_assets_separately(metadata: Dict[str, object], card_directory: Path) -> None:
    """Save assets to dedicated assets folder with character naming"""
    # Get proper display name with type
    display_name = metadata.get("display_name", "Unknown Card")
    rarity = metadata.get("rarity_detected")
    type_upper = metadata.get("type_token_upper")
    character_id = metadata.get("character_id") or "unknown"
    
    # Build proper display name with type
    if rarity and type_upper:
        display_name_bracketed = f"[{rarity}] [{type_upper}] [{display_name}]"
    else:
        display_name_bracketed = f"[{display_name}]"
    
    # Create folder name for assets
    assets_folder_name = sanitize_filename(f"{display_name_bracketed} - {character_id}")
    dedicated_assets_dir = ASSETS_ROOT_DIR / assets_folder_name
    dedicated_assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy assets from card directory to dedicated assets folder
    card_assets_dir = card_directory / "assets"
    if card_assets_dir.exists():
        import shutil
        for asset_file in card_assets_dir.rglob("*"):
            if asset_file.is_file():
                # Maintain subdirectory structure and original filenames
                relative_path = asset_file.relative_to(card_assets_dir)
                target_file = dedicated_assets_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(asset_file, target_file)
        logging.info("Copied assets to dedicated folder: %s", dedicated_assets_dir)
    
    # Create metadata file in assets folder
    asset_metadata = {
        "character_name": display_name,
        "character_id": character_id,
        "rarity": rarity,
        "type": type_upper,
        "source_url": metadata.get("source_url"),
        "asset_count": len(metadata.get("image_urls", []))
    }
    (dedicated_assets_dir / "asset_info.json").write_text(
        json.dumps(asset_metadata, ensure_ascii=False, indent=2), 
        encoding="utf-8"
    )

def write_card_outputs_and_update_index(metadata: Dict[str, object], index_data: Dict[str, dict]) -> None:
    base_display_name = metadata.get("display_name") or "Unknown Card"
    rarity_detected = metadata.get("rarity_detected")
    type_token_upper = metadata.get("type_token_upper")
    character_id = metadata.get("character_id") or "unknown"

    # Build proper display name with type for folder
    if rarity_detected and type_token_upper:
        display_name_bracketed = f"[{rarity_detected}] [{type_token_upper}] [{base_display_name}]"
    else:
        display_name_bracketed = f"[{base_display_name}]"
    
    folder_name = sanitize_filename(f"{display_name_bracketed} - {character_id}")
    card_directory = OUTPUT_ROOT_DIR / folder_name
    card_directory.mkdir(parents=True, exist_ok=True)

    text_parts = []
    def add_line(key, value):
        if value is None:
            return
        if isinstance(value, (dict, list)):
            text_parts.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            text_parts.append(f"{key}: {value}")

    add_line("leader_skill", metadata.get("leader_skill"))
    add_line("super_attack", metadata.get("super_attack"))
    add_line("ultra_super_attack", metadata.get("ultra_super_attack"))
    add_line("passive_skill", metadata.get("passive_skill"))
    add_line("active_skill", metadata.get("active_skill"))
    add_line("link_skills", metadata.get("link_skills"))
    add_line("categories", metadata.get("categories"))
    add_line("stats", metadata.get("stats"))
    add_line("domains", metadata.get("domains"))
    add_line("rarity_detected", rarity_detected)
    add_line("type_token", metadata.get("type_token"))

    page_text_content = "\n".join(text_parts)
    (card_directory / "PAGE_TEXT.txt").write_text(page_text_content, encoding="utf-8")

    formatted_metadata = format_metadata_output(metadata)
    (card_directory / "METADATA.json").write_text(json.dumps(formatted_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    source_url = metadata.get("source_url") or ""
    (card_directory / "ATTRIBUTION.txt").write_text(
        "Data and image asset links collected from DokkanInfo.\n"
        f"Source page: {source_url}\n"
        "Site: https://dokkaninfo.com\n\n"
        "Notes:\n"
        "- Personal/educational use.\n"
        "- Respect the site's Terms and original owners' rights.\n"
        "- If you share output, credit: 'Data/images via dokkaninfo.com'.\n",
        encoding="utf-8",
    )

    if character_id and character_id != "unknown":
        # Build display_name_with_type for index
        if rarity_detected and type_token_upper:
            display_name_with_type = f"[{rarity_detected}] [{type_token_upper}] {base_display_name}"
        else:
            display_name_with_type = base_display_name
            
        index_data[character_id] = {
            "url": metadata.get("source_url"),
            "display_name": base_display_name,
            "display_name_with_type": display_name_with_type,
            "display_name_with_type_bracketed": display_name_bracketed,
            "rarity": rarity_detected,
            "type": type_token_upper,
            "folder": str(card_directory),
            "saved_at": datetime.utcnow().isoformat() + "Z",
        }
        save_index(index_data)
        logging.info("Index updated for ID %s", character_id)
        save_assets_separately(metadata, card_directory)

# ------------ Main orchestration -------------
def main():
    log_file_path = setup_logging()
    logging.info("Starting DokkanInfo advanced scraper with pagination and clean nested JSON formatting")
    OUTPUT_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    index_data = load_index()
    seen_card_ids: Set[str] = set(index_data.keys())
    if seen_card_ids:
        logging.info("Loaded %d existing IDs from index; they will be skipped.", len(seen_card_ids))

    new_cards_saved = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        browser_context = browser.new_context(
            user_agent=USER_AGENT_STRING,
            locale="en-US",
            viewport={"width": 1400, "height": 900},
        )
        page = browser_context.new_page()

        current_index_url = CARDS_INDEX_URL
        pages_processed = 0

        while pages_processed < MAX_PAGES_TO_SCRAPE:
            if new_cards_saved >= MAX_NEW_CARDS_TO_SAVE:
                logging.info("Reached MAX_NEW_CARDS=%d; stopping crawl.", MAX_NEW_CARDS_TO_SAVE)
                break

            try:
                logging.info("Opening index page: %s", current_index_url)
                page.goto(current_index_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(700)
            except PWTimeoutError as e:
                logging.warning("Index page load timeout: %s", e)
                break

            container_selector = "div.row.d-flex.flex-wrap.justify-content-center"
            try:
                card_hrefs = page.eval_on_selector_all(
                    f'{container_selector} a.col-auto[href^="/cards/"]',
                    "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
                )
            except Exception:
                card_hrefs = []

            card_links = []
            seen_hrefs = set()
            for href in card_hrefs:
                if not href or not href.startswith("/cards/"):
                    continue
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)
                card_links.append(urljoin(BASE_URL, href))

            if not card_links:
                logging.info("No more cards found in container on this page.")
                next_index_url = build_next_index_url(current_index_url)
                if next_index_url == current_index_url:
                    logging.info("Next URL equals current URL; stopping.")
                    break
                current_index_url = next_index_url
                pages_processed += 1
                continue

            logging.info("Found %d card links on this page.", len(card_links))

            for card_index, card_url in enumerate(card_links, start=1):
                if new_cards_saved >= MAX_NEW_CARDS_TO_SAVE:
                    logging.info("Reached MAX_NEW_CARDS=%d; stopping crawl.", MAX_NEW_CARDS_TO_SAVE)
                    break

                url_card_id = extract_character_id_from_url(card_url)
                if url_card_id and url_card_id in seen_card_ids:
                    logging.info("Page card %d/%d: ID %s already indexed — skipping open.", card_index, len(card_links), url_card_id)
                    continue

                logging.info("Page card %d/%d -> %s", card_index, len(card_links), card_url)
                try:
                    page.goto(card_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.25)")
                    page.wait_for_timeout(800)
                except PWTimeoutError as e:
                    logging.warning("Card load timeout: %s", e)
                    continue

                page_html = page.content()
                card_metadata = scrape_card_from_html(page_html, card_url)

                character_id = card_metadata.get("character_id")
                if character_id and character_id in seen_card_ids:
                    logging.info("Card %s already scraped; skipping save.", character_id)
                else:
                    if character_id:
                        seen_card_ids.add(character_id)
                    write_card_outputs_and_update_index(card_metadata, index_data)
                    new_cards_saved += 1
                    logging.info("Scraped card ID %s (new_cards_saved=%d)", character_id or "unknown", new_cards_saved)

                related_card_ids = extract_ids_from_col5_images(page_html)
                if related_card_ids:
                    logging.info("Found %d related IDs (skipping first tile): %s", len(related_card_ids), ", ".join(related_card_ids))

                for related_id in related_card_ids:
                    if new_cards_saved >= MAX_NEW_CARDS_TO_SAVE:
                        break
                    if related_id in seen_card_ids:
                        logging.info("Related ID %s already indexed; skipping.", related_id)
                        continue

                    related_url = f"{BASE_URL}/cards/{related_id}"
                    logging.info("Opening related URL directly: %s", related_url)
                    try:
                        page.goto(related_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                        page.wait_for_timeout(700)
                    except PWTimeoutError as e:
                        logging.warning("Related page load timeout for %s: %s", related_url, e)
                        continue

                    related_html = page.content()
                    related_metadata = scrape_card_from_html(related_html, related_url)
                    related_character_id = related_metadata.get("character_id") or related_id
                    if related_character_id in seen_card_ids:
                        logging.info("ID %s already scraped after load; skipping save.", related_character_id)
                        continue
                    seen_card_ids.add(related_character_id)
                    write_card_outputs_and_update_index(related_metadata, index_data)
                    new_cards_saved += 1
                    logging.info("Scraped related card ID %s (new_cards_saved=%d)", related_character_id, new_cards_saved)

                    time.sleep(DELAY_BETWEEN_CARDS_SEC)

                time.sleep(DELAY_BETWEEN_CARDS_SEC)

            if new_cards_saved >= MAX_NEW_CARDS_TO_SAVE:
                break

            next_index_url = build_next_index_url(current_index_url)
            if next_index_url == current_index_url:
                logging.info("Next URL equals current URL after processing; stopping.")
                break
            current_index_url = next_index_url
            pages_processed += 1

        browser.close()
    logging.info("Run completed. Log file: %s", log_file_path)

if __name__ == "__main__":
    main()