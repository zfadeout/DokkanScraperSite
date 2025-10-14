# scraper.py
# DokkanInfo scraper with clean nested JSON formatting

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ------------ Config -------------
BASE_URL = "https://dokkaninfo.com"
CARDS_INDEX_URL = f"{BASE_URL}/cards?sort=open_at"
OUTPUT_ROOT_DIR = Path("output/cards")
ASSETS_ROOT_DIR = Path("output/assets")
LOGS_DIR = Path("output/logs")

USER_AGENT_STRING = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DOWNLOAD_HEADERS = {"User-Agent": USER_AGENT_STRING, "Referer": BASE_URL}
PAGE_TIMEOUT_MS = 60_000
MAX_CARDS_TO_SCRAPE = 2
DELAY_BETWEEN_CARDS_SEC = 0

BROWSER_HEADLESS = False
BROWSER_SLOW_MO_MS = 200
ENABLE_BROWSER_TRACE = True

SECTION_HEADERS = [
    "Leader Skill",
    "Super Attack",
    "Ultra Super Attack",
    "Passive Skill",
    "Active Skill",
    "Activation Condition(s)",
    "Link Skills",
    "Categories",
    "Stats",
]

CATEGORY_FILTER_TOKENS = {
    "background", "icon", "rarity", "element", "eza", "undefined",
    "venatus", "show more", "links", "categories",
}
FILE_EXTENSION_PATTERN = re.compile(r"\.(png|jpg|jpeg|gif|webp)$", re.IGNORECASE)

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

def detect_rarity_and_type_from_images(image_urls: List[str]) -> Tuple[Optional[str], Optional[str]]:
    rarity = None
    rarity_patterns = {
        "LR": ["cha_rare_sm_lr", "cha_rare_lr", "/lr."],
        "UR": ["cha_rare_sm_ur", "cha_rare_ur"],
        "SSR": ["cha_rare_sm_ssr", "cha_rare_ssr"],
        "SR": ["cha_rare_sm_sr", "cha_rare_sr"],
        "R": ["cha_rare_sm_r", "cha_rare_r"],
        "N": ["cha_rare_sm_n", "cha_rare_n"],
    }
    for url in image_urls:
        url_lower = url.lower()
        for rarity_label, pattern_needles in rarity_patterns.items():
            if any(needle in url_lower for needle in pattern_needles):
                rarity = rarity_label
                break
        if rarity:
            break

    type_icon_filename = None
    for url in image_urls:
        if "cha_type_icon_" in url:
            type_icon_filename = Path(urlparse(url).path).name
            break

    logging.debug("Rarity detected: %s, type icon: %s", rarity, type_icon_filename)
    return rarity, type_icon_filename

def download_assets(urls: List[str], destination_dir: Path) -> List[str]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    saved_files: List[str] = []
    for url in urls:
        try:
            parsed_url = urlparse(url)
            url_path = Path(parsed_url.path)
            subdirectory = destination_dir / Path(*[part for part in url_path.parts[:-1] if part not in ("/", "")])
            subdirectory.mkdir(parents=True, exist_ok=True)
            target_file = subdirectory / url_path.name

            if target_file.exists() and target_file.stat().st_size > 0:
                saved_files.append(str(target_file))
                continue

            with requests.get(url, headers=DOWNLOAD_HEADERS, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(target_file, "wb") as file:
                    for chunk in response.iter_content(65536):
                        if chunk:
                            file.write(chunk)
            saved_files.append(str(target_file))
        except Exception as e:
            logging.warning("Asset failed: %s -> %s", url, e)
    return saved_files

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

def _clean_leader(content_block: List[str]) -> Optional[str]:
    if not content_block:
        return None
    leader_text = content_block[0].strip()
    sentence_parts = [part.strip() for part in re.split(r'(?<=[.])\s+', leader_text) if part.strip()]
    seen_sentences = set()
    deduped_parts = []
    for part in sentence_parts:
        if part not in seen_sentences:
            seen_sentences.add(part)
            deduped_parts.append(part)
    leader_text = " ".join(deduped_parts)
    leader_text = re.sub(
        r'("Exploding Rage"\s*Category\s+Ki\s*\+\d+\s+and\s+HP,\s*ATK\s*&\s*DEF\s*\+\d+%)\s*\1',
        r"\1",
        leader_text,
        flags=re.IGNORECASE,
    )
    return leader_text

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
    active_effect = "; ".join([_condense_spaces(text) for text in active_body if text])
    active_effect = _condense_spaces(active_effect)
    return (active_name or None), (active_effect or None)

def _clean_activation(content_block: List[str]) -> Optional[str]:
    if not content_block:
        return None
    activation_text = " ".join(content_block)
    activation_text = _condense_spaces(activation_text)
    for header in SECTION_HEADERS:
        activation_text = activation_text.replace(header, "")
    return activation_text.strip() or None

def _clean_links(content_block: List[str]) -> List[str]:
    output_links: List[str] = []
    seen_links = set()
    for line in content_block or []:
        cleaned_link = _condense_spaces(line)
        if not cleaned_link:
            continue
        if cleaned_link in seen_links:
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

def detect_type_suffix_from_classes(class_list: List[str]) -> Optional[str]:
    type_suffix = None
    for class_name in class_list or []:
        if class_name.startswith("border-") or class_name.startswith("bg-"):
            suffix = class_name.split("-", 1)[-1].strip().lower()
            if suffix in VALID_TYPE_SUFFIXES:
                type_suffix = suffix
    return type_suffix

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

def save_assets_separately(metadata: Dict[str, object], assets_directory: Path) -> None:
    """Save assets to dedicated assets folder with character naming"""
    # Get the proper display name with type from formatted metadata
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
    
    # Copy assets from card assets directory to dedicated assets folder
    # Keep the original filenames from the URLs
    if assets_directory.exists():
        for asset_file in assets_directory.rglob("*"):
            if asset_file.is_file():
                # Keep original filename structure
                relative_path = asset_file.relative_to(assets_directory)
                target_file = dedicated_assets_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                import shutil
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

# ------------ Main -------------
def main():
    log_file_path = setup_logging()
    logging.info("Starting DokkanInfo scraper (non-headless)")

    OUTPUT_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        logging.info("Launching Chromium (headless=%s, slow_mo=%sms)", BROWSER_HEADLESS, BROWSER_SLOW_MO_MS)
        browser = playwright.chromium.launch(headless=BROWSER_HEADLESS, slow_mo=BROWSER_SLOW_MO_MS)
        browser_context = browser.new_context(
            user_agent=USER_AGENT_STRING, 
            locale="en-US", 
            viewport={"width": 1400, "height": 900}
        )
        page = browser_context.new_page()

        def _handle_browser_console(message):
            try:
                message_type = message.type() if callable(getattr(message, "type", None)) else getattr(message, "type", None)
                message_text = message.text() if callable(getattr(message, "text", None)) else getattr(message, "text", None)
                logging.debug("BROWSER %s: %s", message_type, message_text)
            except Exception as e:
                logging.debug("BROWSER console log skipped (%s)", e)
        page.on("console", _handle_browser_console)

        trace_file_path = None
        try:
            if ENABLE_BROWSER_TRACE:
                trace_file_path = LOGS_DIR / f"trace-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
                logging.info("Tracing enabled -> %s", trace_file_path)
                try:
                    browser_context.tracing.start(screenshots=True, snapshots=True, sources=False)
                except Exception as e:
                    logging.warning("Tracing start failed: %s", e)
        except Exception as e:
            logging.warning("Tracing init failed: %s", e)

        try:
            logging.info("Opening index: %s", CARDS_INDEX_URL)
            page.goto(CARDS_INDEX_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(1200)

            card_hrefs = page.eval_on_selector_all(
                'a.col-auto[href^="/cards/"]',
                "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
            )
            card_links = [urljoin(BASE_URL, href) for href in card_hrefs if href and href.startswith("/cards/")]
            logging.info("Found %d card links on screen", len(card_links))
            logging.debug("First 10 links: %s", card_links[:10])

            if not card_links:
                raise RuntimeError("No card anchors found matching a.col-auto[href^='/cards/'] on the index.")

            for card_index, card_url in enumerate(card_links[:MAX_CARDS_TO_SCRAPE], start=1):
                logging.info("Processing card %d/%d -> %s", card_index, min(MAX_CARDS_TO_SCRAPE, len(card_links)), card_url)
                page.goto(card_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                page.wait_for_timeout(1500)

                screenshot_dir = LOGS_DIR / "screens"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot_file = screenshot_dir / f"card-{card_index}.png"
                try:
                    screenshot_bytes = page.screenshot(full_page=True)
                    screenshot_file.write_bytes(screenshot_bytes)
                    logging.info("Saved page screenshot: %s", screenshot_file)
                except Exception as e:
                    logging.warning("Screenshot failed: %s", e)

                page_text = page.inner_text("body")
                page_html = page.content()
                
                soup = BeautifulSoup(page_html, "lxml")

                image_urls_raw = page.eval_on_selector_all(
                    "img",
                    "els => els.map(e => e.getAttribute('src')).filter(Boolean)",
                )
                absolute_image_urls = []
                seen_image_urls = set()
                for src in image_urls_raw:
                    try:
                        absolute_url = urljoin(page.url, src)
                        if absolute_url not in seen_image_urls:
                            seen_image_urls.add(absolute_url)
                            absolute_image_urls.append(absolute_url)
                    except Exception:
                        continue
                image_urls = absolute_image_urls
                logging.info("Found %d images", len(image_urls))

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
                        r"Ultra Super Attack\s+([\s\S]*?)\s+(Passive Skill|Active Skill|Link Skills|Categories|Stats)",
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
                
                rarity_detected = detect_rarity_from_dom(soup, image_urls)
                type_token = detect_type_token_from_dom(soup)
                type_token_upper = type_token.upper() if type_token else None

                type_icon_filename = None
                for url in image_urls:
                    if "cha_type_icon_" in url.lower():
                        type_icon_filename = url.split("/")[-1]
                        break

                try:
                    h1_text = page.text_content("h1") or ""
                    display_name = h1_text.strip() if h1_text.strip() else (page.title() or "").strip()
                except Exception:
                    display_name = (page.title() or "").strip()
                page_title = page.title()

                character_id = re.search(r"/cards/(\d+)", card_url)
                character_id = character_id.group(1) if character_id else "unknown"

                # Build proper display name with type for folder
                if rarity_detected and type_token_upper:
                    display_name_bracketed = f"[{rarity_detected}] [{type_token_upper}] [{display_name}]"
                else:
                    display_name_bracketed = f"[{display_name}]"
                
                folder_name = sanitize_filename(f"{display_name_bracketed} - {character_id}")
                card_directory = OUTPUT_ROOT_DIR / folder_name
                assets_directory = card_directory / "assets"
                card_directory.mkdir(parents=True, exist_ok=True)

                (card_directory / "page.html").write_text(page_html, encoding="utf-8")
                (card_directory / "PAGE_TEXT.txt").write_text(page_text, encoding="utf-8")

                

                domains_list = parse_domains(soup)

                eza_info = parse_eza_info(soup)

                raw_metadata = {
                    "page_title": page_title,
                    "display_name": display_name,
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
                    "source_url": card_url,
                    "rarity_detected": rarity_detected,
                    "type_icon_filename": type_icon_filename,
                    "type_token": type_token,
                    "type_token_upper": type_token_upper,
                    "image_urls": image_urls,
                }
                
                formatted_metadata = format_metadata_output(raw_metadata)
                
                (card_directory / "METADATA.json").write_text(
                    json.dumps(formatted_metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logging.info("Wrote METADATA.json")

                saved_assets = download_assets(image_urls, assets_directory)
                logging.info("Saved %d assets into %s", len(saved_assets), assets_directory)

                (card_directory / "ATTRIBUTION.txt").write_text(
                    "Data and image asset links collected from DokkanInfo.\n"
                    f"Source page: {card_url}\n"
                    "Site: https://dokkaninfo.com\n\n"
                    "Notes:\n"
                    "- Personal/educational use.\n"
                    "- Respect the site's Terms and original owners' rights.\n"
                    "- If you share output, credit: 'Data/images via dokkaninfo.com'.\n",
                    encoding="utf-8",
                )

                # Save assets to dedicated folder
                # Save assets to dedicated folder (use raw_metadata with proper fields)
                raw_metadata["display_name_with_type_bracketed"] = formatted_metadata["card_identification"]["display_name_with_type_bracketed"]
                save_assets_separately(raw_metadata, assets_directory)

                time.sleep(DELAY_BETWEEN_CARDS_SEC)

        except PWTimeoutError as e:
            logging.exception("Playwright timeout: %s", e)
        except Exception as e:
            logging.exception("Unexpected error: %s", e)
        finally:
            if ENABLE_BROWSER_TRACE:
                try:
                    if hasattr(browser_context.tracing, "export"):
                        browser_context.tracing.stop()
                        try:
                            browser_context.tracing.export(path=str(trace_file_path))
                            logging.info("Saved trace: %s", trace_file_path)
                        except Exception as trace_error:
                            logging.warning("Trace export failed: %s", trace_error)
                    else:
                        browser_context.tracing.stop(path=str(trace_file_path))
                        logging.info("Saved trace (stop with path): %s", trace_file_path)
                except Exception as trace_error:
                    logging.warning("Tracing stop failed: %s", trace_error)
            browser.close()
            logging.info("Browser closed. Log file: %s", log_file_path)


if __name__ == "__main__":
    main()