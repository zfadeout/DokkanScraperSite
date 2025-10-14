DokkanBattle Scraper
A comprehensive Python toolkit for scraping card data from DokkanInfo.com for educational and archival purposes.Table of Contents

Overview
Features
Prerequisites
Installation
Project Structure
Usage
Configuration
Output Format
Troubleshooting
Legal & Ethical Considerations
Contributing
OverviewThis project provides two web scrapers that collect Dragon Ball Z Dokkan Battle card information from DokkanInfo.com:
scraper.py - Basic scraper with image downloading
dokkaninfoBS4scraper.py - Advanced scraper with pagination and indexing
Both scrapers extract comprehensive card data including leader skills, passive skills, super attacks, categories, transformations, and more.FeaturesCommon Features (Both Scrapers)

✅ Extracts complete card metadata (leader skill, passive, super attacks, etc.)
✅ Detects card rarity (LR, UR, SSR, SR, R, N)
✅ Identifies card type (STR, TEQ, INT, AGL, PHY)
✅ Parses transformation conditions
✅ Detects giant form transformations
✅ Identifies reversible exchange mechanics
✅ Extracts link skills and categories
✅ Captures domain effects
✅ Comprehensive logging system
✅ Browser automation with Playwright
scraper.py Specific Features

📥 Downloads all card images and assets
🎯 Scrapes 2 cards by default (configurable)
📸 Takes full-page screenshots
🐌 Runs in slow-motion mode for visibility
dokkaninfoBS4scraper.py Specific Features

📑 Pagination support (scrapes multiple pages)
💾 Maintains persistent index to avoid re-scraping
🔗 Extracts and follows related card IDs
🚫 No image downloads (faster scraping)
⚡ Processes up to 10 new cards by default
🔄 Resumes from where it left off
Prerequisites
Python 3.9 or higher
Windows, macOS, or Linux
Visual Studio Code (recommended) or any Python IDE
Internet connection
~500MB free disk space (for Chromium browser)