       #!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
========================================
UZBEK WIKIPEDIA BOT - LINGUISTIC EXCELLENCE
========================================
Version: 25.0 (ORTHOGRAPHY + REFERENCE PRESERVATION)
Purpose: Production-grade Wikipedia article generation
Target: uz.wikipedia.org
Compliance: Stuttgart Quality Standard
========================================
"""

import pywikibot
from pywikibot import pagegenerators
import os
import glob
import sys
import re
import logging
import time
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from pathlib import Path

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

# ==========================================
# 🔧 CONFIGURATION
# ==========================================
class Config:
    """Centralized configuration with validation"""
    SIMULATION_OR_DRAFT_MODE = False
    BOT_USERNAME = "DanikBotUZ"

    COUNTRY_QID = 'Q36'
    COUNTRY_NAME = 'Polsha'
    MAX_ARTICLES = 1

    GITHUB_TOKEN = "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"
    GITHUB_ENDPOINT = "https://models.github.ai/inference"
    AI_MODEL = "meta/Llama-4-Scout-17B-16E-Instruct"

    TEMPERATURE = 0.2
    TOP_P = 0.95
    MAX_TOKENS = 8000

    MAX_RETRIES = 12
    INITIAL_RETRY_DELAY = 30
    MAX_RETRY_DELAY = 120
    RATE_LIMIT_DELAY = 60

    EDIT_DELAY = 50
    REQUEST_TIMEOUT = 180

    LOG_DIR = Path("logs")
    LOG_FILE = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    @classmethod
    def validate(cls):
        if not cls.GITHUB_TOKEN or not cls.GITHUB_TOKEN.startswith("github_pat_"):
            raise ValueError("⚠️ CRITICAL: Invalid GitHub token")
        cls.LOG_DIR.mkdir(exist_ok=True)

# ==========================================
# 📊 LOGGING
# ==========================================
class BotLogger:
    def __init__(self):
        Config.LOG_DIR.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))

        self.logger = logging.getLogger('UzbekWikiBot')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, msg): self.logger.info(msg)
    def warning(self, msg): self.logger.warning(msg)
    def error(self, msg): self.logger.error(msg)
    def debug(self, msg): self.logger.debug(msg)
    def critical(self, msg): self.logger.critical(msg)

logger = BotLogger()

# ==========================================
# 🔤 UZBEK ORTHOGRAPHY PROCESSOR
# ==========================================
class UzbekOrthographyFixer:
    """
    CRITICAL MODULE: Fixes Uzbek Latin script diacritics
    Converts incorrect apostrophes to proper Unicode modifier letter (U+02BB)
    """

    # The CORRECT Uzbek modifier letter turning comma
    CORRECT_MODIFIER = 'ʻ'  # U+02BB

    # Common incorrect representations
    WRONG_PATTERNS = [
        "'",   # ASCII apostrophe
        "'",   # Right single quotation mark
        "`",   # Grave accent
        "ʼ",   # U+02BC modifier letter apostrophe
        "′",   # Prime symbol
    ]

    @classmethod
    def fix_orthography(cls, text: str) -> str:
        """
        Apply comprehensive Uzbek orthography fixes
        Priority: oʻ, gʻ letter pairs
        """
        if not text:
            return text

        logger.debug("🔤 Applying Uzbek orthography corrections...")

        original_text = text

        # STAGE 1: Fix o' combinations
        # Pattern: o followed by any wrong apostrophe
        for wrong in cls.WRONG_PATTERNS:
            text = text.replace(f"o{wrong}", f"o{cls.CORRECT_MODIFIER}")
            text = text.replace(f"O{wrong}", f"O{cls.CORRECT_MODIFIER}")

        # STAGE 2: Fix g' combinations
        for wrong in cls.WRONG_PATTERNS:
            text = text.replace(f"g{wrong}", f"g{cls.CORRECT_MODIFIER}")
            text = text.replace(f"G{wrong}", f"G{cls.CORRECT_MODIFIER}")

        # STAGE 3: Common Uzbek words - ensure correctness
        uzbek_words = {
            r'\bo\'': f'bo{cls.CORRECT_MODIFIER}',
            r'\bg\'': f'g{cls.CORRECT_MODIFIER}',
            r'\bO\'': f'O{cls.CORRECT_MODIFIER}',
            r'\bG\'': f'G{cls.CORRECT_MODIFIER}',
        }

        for pattern, replacement in uzbek_words.items():
            text = re.sub(pattern, replacement, text)

        # STAGE 4: Fix within common Uzbek terms
        critical_fixes = {
            "oʼzbek": f"o{cls.CORRECT_MODIFIER}zbek",
            "Oʼzbek": f"O{cls.CORRECT_MODIFIER}zbek",
            "boʼlgan": f"bo{cls.CORRECT_MODIFIER}lgan",
            "gʼarbiy": f"g{cls.CORRECT_MODIFIER}arbiy",
            "joʼlashgan": f"jo{cls.CORRECT_MODIFIER}lashgan",
            "shaʼrida": f"sha{cls.CORRECT_MODIFIER}rida",
        }

        for wrong, correct in critical_fixes.items():
            text = text.replace(wrong, correct)

        if text != original_text:
            logger.debug("✅ Orthography corrections applied")

        return text

# ==========================================
# 🌐 ENGLISH WIKIPEDIA FETCHER (ENHANCED)
# ==========================================
class EnglishWikiFetcher:
    """Fetches COMPLETE raw wikitext + extracts images"""

    @staticmethod
    def get_full_wikitext(item: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Fetch COMPLETE raw wikitext AND extract main image
        Returns: (wikitext, title, image_filename)
        """
        try:
            sitelinks = item.sitelinks

            if 'enwiki' not in sitelinks:
                logger.debug(f"No enwiki sitelink for {item.id}")
                return None, None, None

            enwiki_link = sitelinks['enwiki']
            title = enwiki_link.title if hasattr(enwiki_link, 'title') else str(enwiki_link)

            site = pywikibot.Site('en', 'wikipedia')
            page = pywikibot.Page(site, title)

            if not page.exists():
                logger.warning(f"English article '{title}' does not exist")
                return None, None, None

            # Get COMPLETE raw wikitext
            raw_wikitext = page.text

            if not raw_wikitext or len(raw_wikitext.strip()) < 100:
                logger.warning(f"English article '{title}' has insufficient content")
                return None, None, None

            # EXTRACT IMAGE from infobox
            image_filename = EnglishWikiFetcher._extract_image(raw_wikitext)

            logger.debug(f"✅ Fetched wikitext for '{title}' ({len(raw_wikitext)} chars)")
            if image_filename:
                logger.debug(f"📸 Found image: {image_filename}")

            return raw_wikitext, title, image_filename

        except Exception as e:
            logger.error(f"Error fetching English wikitext: {type(e).__name__}: {e}")
            return None, None, None

    @staticmethod
    def _extract_image(wikitext: str) -> Optional[str]:
        """
        Extract main image from English infobox
        Searches for: image_skyline, image, image_map, etc.
        """
        # Patterns to search for image parameters in infoboxes
        image_patterns = [
            r'\|\s*image_skyline\s*=\s*([^\|\n]+)',
            r'\|\s*image\s*=\s*([^\|\n]+)',
            r'\|\s*image_photo\s*=\s*([^\|\n]+)',
            r'\|\s*photo\s*=\s*([^\|\n]+)',
        ]

        for pattern in image_patterns:
            match = re.search(pattern, wikitext, re.IGNORECASE)
            if match:
                image_name = match.group(1).strip()

                # Clean up the image name
                image_name = re.sub(r'\[\[File:', '', image_name, flags=re.IGNORECASE)
                image_name = re.sub(r'\[\[Image:', '', image_name, flags=re.IGNORECASE)
                image_name = re.sub(r'\]\].*$', '', image_name)
                image_name = re.sub(r'\|.*$', '', image_name)
                image_name = image_name.strip()

                # Validate it's an actual image file
                if image_name and re.search(r'\.(jpg|jpeg|png|gif|svg)$', image_name, re.IGNORECASE):
                    return image_name

        return None

# ==========================================
# 🧹 TEXT SANITIZER
# ==========================================
class TextSanitizer:
    """Minimal sanitization - preserve wikitext structure"""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""

        # Remove ONLY AI meta-commentary, preserve ALL wikitext
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove code fences if AI added them
        text = re.sub(r'^```[a-z]*\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'\n```$', '', text, flags=re.MULTILINE)
        text = text.strip('`')

        # Remove "Here is..." type preambles
        text = re.sub(r'^(Here is|Here\'s|Below is|The translated).*?:?\s*\n+', '', text, flags=re.IGNORECASE)

        text = text.strip()
        return text

# ==========================================
# 🤖 AI TRANSLATOR - REFERENCE PRESERVATION
# ==========================================
class AITranslator:
    """Translates with STRICT reference preservation and grammar rules"""

    SYSTEM_PROMPT = """# 🚨 UZBEK WIKIPEDIA TRANSLATION PROTOCOL V5.0

You are a PROFESSIONAL COMPUTATIONAL LINGUIST specializing in Academic Uzbek.

## 🎯 MISSION: 2-3 SENTENCES ONLY
- Output: EXACTLY 2 to 3 short, dense, high-quality sentences.
- Never exceed 3 sentences.
- Style: "Featured Snippet" style - fast to read, 100% accurate.
- Tone: Academic, scientific, precise.

## 📜 CRITICAL RULE #1: REFERENCE PRESERVATION (NON-NEGOTIABLE)
**REFERENCES ARE SACRED - NEVER DELETE OR MODIFY**
Every <ref>...</ref> tag from English MUST appear in the EXACT same position in Uzbek.
- Keep <ref> tags EXACTLY as they appear in English.
- Do NOT translate content INSIDE <ref> tags.
- If English has ==References==, convert to == Manbalar == with {{manbalar}}.

## 📜 CRITICAL RULE #2: UZBEK LATIN ORTHOGRAPHY
- Use: oʻ (not o' or o’)
- Use: gʻ (not g' or g’)
- Use the Unicode modifier letter ʻ (U+02BB).

## 📜 CRITICAL RULE #3: SOV GRAMMAR (Subject-Object-Verb)
**VERB MUST BE AT THE END OF SENTENCE**
- First sentence: '''[Name]''' — [Country]ning [region] qismida joylashgan [entity type]dir.

## 📜 CRITICAL RULE #4: INFOBOX & FORMATTING
- Convert English infobox to {{Bilgiquti aholi punkti}}.
- Keep [[internal links]], '''bold''', ''italic''.
- Add image: | tasvir = filename.jpg
- End with [[Turkum:...]] categories.

NO preamble. NO commentary. START with infobox."""

    def __init__(self):
        try:
            self.client = ChatCompletionsClient(
                endpoint=Config.GITHUB_ENDPOINT,
                credential=AzureKeyCredential(Config.GITHUB_TOKEN)
            )
            logger.info(f"✅ GitHub Models initialized: {Config.AI_MODEL}")
        except Exception as e:
            logger.critical(f"Failed to initialize AI client: {e}")
            raise

    def translate_full_article(self,
                              wikidata: Dict[str, Any],
                              english_wikitext: str,
                              english_title: str,
                              image_filename: Optional[str] = None) -> Optional[str]:
        """Translate COMPLETE English wikitext to Uzbek"""

        name = wikidata['name']
        region = wikidata.get('region', 'Poland')

        # Count references for validation
        ref_count = len(re.findall(r'<ref[^>]*>.*?</ref>', english_wikitext, re.DOTALL))
        logger.info(f"📚 Source has {ref_count} references to preserve")

        # Build context
        context_data = f"""WIKIDATA CONTEXT:
- Name: {name}
- Region: {region}
- Country: {Config.COUNTRY_NAME}
- Population: {wikidata.get('pop', 'N/A')}
- Area: {wikidata.get('area', 'N/A')} km²
- Coordinates: {wikidata.get('coords_lat', 'N/A')}, {wikidata.get('coords_lon', 'N/A')}
- Postal: {wikidata.get('postal', 'N/A')}
- Main Image: {image_filename if image_filename else 'N/A'}
"""

        user_prompt = f"""{context_data}

SOURCE: en.wikipedia.org/wiki/{english_title.replace(' ', '_')}

ENGLISH WIKITEXT (CONTAINS {ref_count} REFERENCES):
{english_wikitext}

---

TRANSLATION INSTRUCTIONS:
1. **LIMIT: MAX 2-3 SHORT SENTENCES.** No more.
2. **REFERENCES:** Preserve ALL {ref_count} <ref> tags in the text.
3. **INFOBOX:** Use {{{{Bilgiquti aholi punkti}}}}. Set `| tasvir = {image_filename if image_filename else ''}`.
4. **GRAMMAR:** Strict SOV. Orthography: oʻ, gʻ.
5. **CATEGORIES:** Add [[Turkum:{Config.COUNTRY_NAME} shaharlari]].

OUTPUT RAW WIKITEXT ONLY.

BEGIN TRANSLATION:"""

        logger.info(f"🤖 Translating via {Config.AI_MODEL}...")
        result = self._call_api_with_retry(user_prompt)

        if result:
            cleaned = TextSanitizer.clean(result)
            fixed = UzbekOrthographyFixer.fix_orthography(cleaned)
            uzbek_ref_count = len(re.findall(r'<ref[^>]*>.*?</ref>', fixed, re.DOTALL))

            if uzbek_ref_count < ref_count:
                logger.warning(f"⚠️ Reference loss: {ref_count} → {uzbek_ref_count}")
            else:
                logger.info(f"✅ All {uzbek_ref_count} references preserved")

            return fixed

        logger.error("❌ Translation failed")
        return None

    def _call_api_with_retry(self, user_prompt: str) -> Optional[str]:
        """Call API with exponential backoff"""
        retry_delay = Config.INITIAL_RETRY_DELAY
        for attempt in range(1, Config.MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    time.sleep(retry_delay)
                response = self.client.complete(
                    messages=[
                        SystemMessage(content=self.SYSTEM_PROMPT),
                        UserMessage(content=user_prompt)
                    ],
                    temperature=Config.TEMPERATURE,
                    top_p=Config.TOP_P,
                    max_tokens=Config.MAX_TOKENS,
                    model=Config.AI_MODEL
                )
                if response and response.choices:
                    return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                retry_delay *= 2
        return None

# ==========================================
# 🗂️ WIKIDATA EXTRACTOR
# ==========================================
class WikidataExtractor:
    """Extracts structured data from Wikidata"""

    @staticmethod
    def extract(item: Any) -> Optional[Dict[str, Any]]:
        try:
            item.get()

            labels = item.labels
            name = labels.get('uz') or labels.get('en')

            if not name:
                return None

            region = WikidataExtractor._get_region(item)
            pop = WikidataExtractor._get_claim_value(item, 'P1082', int)
            area = WikidataExtractor._get_claim_value(item, 'P2046', float)
            elev = WikidataExtractor._get_claim_value(item, 'P2044', float)
            postal = WikidataExtractor._get_claim_value(item, 'P281', str)

            coords_lat, coords_lon = WikidataExtractor._get_coordinates(item)

            return {
                'name': name,
                'region': region,
                'pop': pop,
                'area': area,
                'elev': elev,
                'postal': postal,
                'coords_lat': coords_lat,
                'coords_lon': coords_lon
            }

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None

    @staticmethod
    def _get_region(item: Any) -> Optional[str]:
        if 'P131' not in item.claims:
            return None
        try:
            region_item = item.claims['P131'][0].getTarget()
            region_item.get()
            return region_item.labels.get('uz') or region_item.labels.get('en')
        except:
            return None

    @staticmethod
    def _get_claim_value(item: Any, prop: str, converter=None):
        if prop not in item.claims:
            return None
        try:
            target = item.claims[prop][0].getTarget()
            if hasattr(target, 'amount'):
                value = target.amount
                return converter(value) if converter else value
            return converter(target) if converter else target
        except:
            return None

    @staticmethod
    def _get_coordinates(item: Any) -> Tuple[Optional[float], Optional[float]]:
        if 'P625' not in item.claims:
            return None, None
        try:
            coord = item.claims['P625'][0].getTarget()
            return coord.lat, coord.lon
        except:
            return None, None

# ==========================================
# 🚀 MAIN BOT ENGINE
# ==========================================
class UzbekWikiBot:
    """Main bot orchestrator - System Integrity Preserved"""

    def __init__(self):
        Config.validate()
        self.translator = AITranslator()
        self.fetcher = EnglishWikiFetcher()
        self.extractor = WikidataExtractor()

        self._cleanup_lock_files()

        self.site = pywikibot.Site('uz', 'wikipedia')
        self.repo = self.site.data_repository()

        if not Config.SIMULATION_OR_DRAFT_MODE:
            try:
                self.site.login()
                logger.info("✅ Logged in to uz.wikipedia.org")
            except Exception as e:
                logger.warning(f"Login warning: {e}")
        else:
            logger.info("🧪 DRAFT MODE ENABLED")

    def _cleanup_lock_files(self):
        """Remove Pywikibot lock files"""
        for pattern in ["*.lwp", "pywikibot-*.lwp", "apicache-*.sqlite3"]:
            for file in glob.glob(pattern):
                try:
                    os.remove(file)
                except:
                    pass

    def _get_page_title(self, name: str) -> str:
        """Determine page title based on mode (SYSTEM INTEGRITY)"""
        if Config.SIMULATION_OR_DRAFT_MODE:
            return f"Foydalanuvchi:{Config.BOT_USERNAME}/Qoralama/{name}"
        return name

    def run(self):
        """Main execution loop (SYSTEM INTEGRITY PRESERVED)"""
        logger.info("=" * 60)
        logger.info(f"🤖 UZBEK WIKI BOT v25.0 (LINGUISTIC EXCELLENCE)")
        logger.info(f"📍 Target: {Config.COUNTRY_NAME} (Q{Config.COUNTRY_QID})")
        logger.info(f"🎯 Max: {Config.MAX_ARTICLES} | Draft: {Config.SIMULATION_OR_DRAFT_MODE}")
        logger.info(f"🔤 Orthography: ENABLED | 📚 References: PROTECTED")
        logger.info("=" * 60)

        # SPARQL QUERY - PRESERVED (SYSTEM INTEGRITY)
        query = f"""
        SELECT DISTINCT ?item WHERE {{
          ?item wdt:P31/wdt:P279* wd:Q486972;
                wdt:P17 wd:{Config.COUNTRY_QID}.
        }}
        LIMIT 100
        """

        generator = pagegenerators.WikidataSPARQLPageGenerator(query, site=self.repo)

        count = 0
        skipped = 0
        failed = 0

        for item in generator:
            if count >= Config.MAX_ARTICLES:
                break

            try:
                # WIKIDATA EXTRACTION - PRESERVED (SYSTEM INTEGRITY)
                data = self.extractor.extract(item)
                if not data:
                    skipped += 1
                    continue

                name = data['name']
                logger.info(f"\n{'=' * 60}")
                logger.info(f"[{count + 1}] {name} ({item.id})")

                page_title = self._get_page_title(name)
                page = pywikibot.Page(self.site, page_title)

                if page.exists():
                    logger.info(f"⭐️ SKIP: Already exists")
                    skipped += 1
                    continue

                # ENHANCED: Fetch wikitext + image
                english_wikitext, english_title, image_filename = self.fetcher.get_full_wikitext(item)

                if not english_wikitext:
                    logger.info(f"⭐️ SKIP: No English source")
                    skipped += 1
                    continue

                logger.info(f"📖 Source: en:{english_title} ({len(english_wikitext)} chars)")
                if image_filename:
                    logger.info(f"📸 Image: {image_filename}")

                # ENHANCED: Translate with image info
                uzbek_article = self.translator.translate_full_article(
                    data, english_wikitext, english_title, image_filename
                )

                if not uzbek_article:
                    logger.error(f"❌ FAIL: Translation failed")
                    failed += 1
                    continue

                # FINAL ORTHOGRAPHY PASS (safety layer)
                uzbek_article = UzbekOrthographyFixer.fix_orthography(uzbek_article)

                self._save_article(page, uzbek_article, english_title, name)
                count += 1

            except KeyboardInterrupt:
                logger.critical("⚠️ INTERRUPTED")
                break
            except Exception as e:
                logger.error(f"💥 ERROR: {type(e).__name__}: {e}")
                failed += 1

        logger.info("\n" + "=" * 60)
        logger.info(f"📊 STATISTICS")
        logger.info(f"✅ Created: {count} | ⭐️ Skipped: {skipped} | ❌ Failed: {failed}")
        logger.info(f"📄 Log: {Config.LOG_FILE}")
        logger.info("=" * 60)

    def _save_article(self, page, content: str, source: str, name: str):
        """Save article (SYSTEM INTEGRITY PRESERVED)"""
        try:
            page.text = content

            summary = f"Bot: Ingliz Vikipediyadan tarjima ([[en:{source}]])"
            if Config.SIMULATION_OR_DRAFT_MODE:
                summary = f"Qoralama: {summary}"

            page.save(summary=summary, bot=True, minor=False)
            logger.info(f"✅ SAVED: {page.title()}")

            # EDIT DELAY - PRESERVED (SYSTEM INTEGRITY)
            time.sleep(Config.EDIT_DELAY)

        except pywikibot.exceptions.CaptchaError:
            logger.critical("🛑 CAPTCHA - Manual intervention required")
            sys.exit(1)
        except pywikibot.exceptions.EditConflictError:
            logger.error("⚠️ Edit conflict - skipping")
        except pywikibot.exceptions.SpamblacklistError as e:
            logger.error(f"⚠️ Spam blacklist: {e}")
        except pywikibot.exceptions.LockedPageError:
            logger.error("⚠️ Page locked")
        except Exception as e:
            logger.error(f"❌ Save failed: {e}")
            raise

# ==========================================
# 🎬 ENTRY POINT
# ==========================================
if __name__ == "__main__":
    try:
        bot = UzbekWikiBot()
        bot.run()
    except Exception as e:
        logger.critical(f"💀 FATAL: {e}")
        sys.exit(1)