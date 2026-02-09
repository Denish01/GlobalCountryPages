"""
GlobalCountryPages Configuration
"""
import os
from pathlib import Path

# Load .env file if present
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Groq model
GROQ_MODEL = "llama-3.3-70b-versatile"

# Site settings
SITE_NAME = "Global Country Guide"
SITE_URL = "https://yourusername.github.io/GlobalCountryPages"
SITE_DESCRIPTION = "Comprehensive country guides covering 249 countries and territories worldwide."

# Generation settings
PAGES_PER_RUN = 200
RATE_LIMIT_DELAY = 2  # seconds between API calls
MAX_RETRIES = 3

# Continent colors for HTML theming
CONTINENT_COLORS = {
    "africa": {"primary": "#E67E22", "secondary": "#F39C12", "name": "Africa"},
    "asia": {"primary": "#E74C3C", "secondary": "#C0392B", "name": "Asia"},
    "europe": {"primary": "#3498DB", "secondary": "#2980B9", "name": "Europe"},
    "north-america": {"primary": "#27AE60", "secondary": "#229954", "name": "North America"},
    "south-america": {"primary": "#8E44AD", "secondary": "#7D3C98", "name": "South America"},
    "oceania": {"primary": "#16A085", "secondary": "#138D75", "name": "Oceania"},
    "antarctica": {"primary": "#5DADE2", "secondary": "#3498DB", "name": "Antarctica"},
}

# ISO to flag emoji mapping (first 2 letters of ISO code -> regional indicator symbols)
def iso_to_flag(iso_code):
    """Convert ISO 3166-1 alpha-2 code to flag emoji."""
    if not iso_code or len(iso_code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso_code.upper())
