#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
========================================
UZBEK WIKIPEDIA BOT - LINGUISTIC EXCELLENCE
========================================
Version: 30.0 (OPENROUTER + LEAD-ONLY + POLAND)
Purpose: Production-grade Wikipedia article generation
Target: uz.wikipedia.org
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
import requests
import json
from typing import Optional, Tuple, Dict, Any, List
from datetime import datetime
from pathlib import Path

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

    OPENROUTER_API_KEY = "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"
    OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    AI_MODEL = "deepseek/deepseek-r1"

    TEMPERATURE = 0.2
    TOP_P = 0.95
    MAX_TOKENS = 4000

    MAX_RETRIES = 5
    INITIAL_RETRY_DELAY = 10
    MAX_RETRY_DELAY = 60
    RATE_LIMIT_DELAY = 30

    EDIT_DELAY = 10
    REQUEST_TIMEOUT = 120

    LOG_DIR = Path("logs")
    LOG_FILE = LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    @classmethod
    def validate(cls):
        if not cls.OPENROUTER_API_KEY or not cls.OPENROUTER_API_KEY.startswith("sk-or-"):
            raise ValueError("⚠️ CRITICAL: Invalid OpenRouter API key")
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
    """Fixes Uzbek Latin script diacritics using U+02BB modifier"""

    CORRECT_MODIFIER = 'ʻ'  # U+02BB

    WRONG_PATTERNS = ["'", "'", "`", "ʼ", "′"]

    @classmethod
    def fix_orthography(cls, text: str) -> str:
        if not text:
            return text

        # Priority: oʻ, gʻ letter pairs
        for wrong in cls.WRONG_PATTERNS:
            text = text.replace(f"o{wrong}", f"o{cls.CORRECT_MODIFIER}")
            text = text.replace(f"O{wrong}", f"O{cls.CORRECT_MODIFIER}")
            text = text.replace(f"g{wrong}", f"g{cls.CORRECT_MODIFIER}")
            text = text.replace(f"G{wrong}", f"G{cls.CORRECT_MODIFIER}")

        # Common word fixes
        critical_fixes = {
            "oʼzbek": f"o{cls.CORRECT_MODIFIER}zbek",
            "Oʼzbek": f"O{cls.CORRECT_MODIFIER}zbek",
            "boʼlgan": f"bo{cls.CORRECT_MODIFIER}lgan",
            "gʼarbiy": f"g{cls.CORRECT_MODIFIER}arbiy",
            "o'z": f"o{cls.CORRECT_MODIFIER}z",
            "O'z": f"O{cls.CORRECT_MODIFIER}z",
        }

        for wrong, correct in critical_fixes.items():
            text = text.replace(wrong, correct)

        return text

# ==========================================
# 🌐 ENGLISH WIKIPEDIA FETCHER (LEAD ONLY)
# ==========================================
class EnglishWikiFetcher:
    """Fetches lead section wikitext + extracts images"""

    @staticmethod
    def get_lead_wikitext(item: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        try:
            sitelinks = item.sitelinks
            if 'enwiki' not in sitelinks:
                return None, None, None

            enwiki_link = sitelinks['enwiki']
            title = enwiki_link.title if hasattr(enwiki_link, 'title') else str(enwiki_link)

            site = pywikibot.Site('en', 'wikipedia')
            page = pywikibot.Page(site, title)

            if not page.exists():
                return None, None, None

            full_text = page.text
            if not full_text or len(full_text.strip()) < 100:
                return None, None, None

            # Extract LEAD section (before first section header ==)
            lead_text = full_text.split('==')[0].strip()

            # Fallback if lead split is too short
            raw_wikitext = lead_text if len(lead_text) > 100 else full_text

            # EXTRACT IMAGE
            image_filename = EnglishWikiFetcher._extract_image(full_text)

            logger.debug(f"✅ Fetched lead for '{title}' ({len(raw_wikitext)} chars)")
            return raw_wikitext, title, image_filename

        except Exception as e:
            logger.error(f"Error fetching English wikitext: {e}")
            return None, None, None

    @staticmethod
    def _extract_image(wikitext: str) -> Optional[str]:
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
                image_name = re.sub(r'\[\[(?:File|Image|Fayl):', '', image_name, flags=re.IGNORECASE)
                image_name = re.sub(r'(?:File|Image|Fayl):', '', image_name, flags=re.IGNORECASE)
                image_name = re.sub(r'\]\].*$', '', image_name)
                image_name = re.sub(r'\|.*$', '', image_name)
                image_name = image_name.strip()

                if image_name and re.search(r'\.(jpg|jpeg|png|gif|svg|webp)$', image_name, re.IGNORECASE):
                    return image_name
        return None

# ==========================================
# 🧹 TEXT SANITIZER
# ==========================================
class TextSanitizer:
    @staticmethod
    def clean(text: str) -> str:
        if not text: return ""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'^```[a-z]*\n', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'\n```$', '', text, flags=re.MULTILINE)
        return text.strip('`').strip()

# ==========================================
# 🤖 ARTICLE BUILDER - ACADEMIC UZBEK
# ==========================================
class ArticleBuilder:
    """Generates articles with OpenRouter and Lead-only logic"""

    SYSTEM_PROMPT = """# 🚨 PROTOCOL: UZBEK WIKIPEDIA SUPREMACY (V30.0)
# ROLE: SENIOR MEDIAWIKI ARCHITECT

You are a PROFESSIONAL LINGUIST specializing in Academic Uzbek.
Your goal is to produce EXACTLY 3 sentences of high-quality, native synthesis based on the provided English lead section.

## 🏛️ MODULE 1: THE INFOBOX (BILGIQUTI)
Use {{Bilgiquti aholi punkti}} template. Map data precisely.
Rules:
- maydon, aholi, AP markazi balandligi: Raw numbers ONLY.
- Timezones for Poland: vaqt mintaqasi = +1, DST = +2.

## 🔬 MODULE 2: PROSE & LINGUISTICS
- Sentence 1: '''{nomi}''' — [Administrative status] tarkibiga kiruvchi [Entity type]dir.
- Sentence 2: Historical context or founding.
- Sentence 3: Demographic or current status highlight.
- Grammar: SOV (Verb at end). Orthography: oʻ, gʻ (U+02BB).
- References: Preserve ALL <ref> tags from the source in their exact positions.

## 🧹 MODULE 3: SYSTEM INTEGRITY
- MANDATORY section: == Manbalar == with {{manbalar}}.
- If source has NO <ref> tags, add this line under == Manbalar ==:
  "Ushbu maqola inglizcha Vikipediyadagi [URL] maqolasi asosida yaratildi."
- Category: ONLY [[Turkum:Polsha aholi punktlari]].
- Output RAW MediaWiki only. NO chatter."""

    def __init__(self):
        self.endpoint = Config.OPENROUTER_ENDPOINT
        self.headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/DanikBotUZ",
            "X-Title": "UzbekWikiBot",
        }
        logger.info(f"✅ OpenRouter initialized: {Config.AI_MODEL}")

    def build_article(self, maʼlumotlar: Dict[str, Any], manba_matni: str, manba_nomi: str, tasvir_nomi: Optional[str] = None) -> Optional[str]:
        nomi = maʼlumotlar['nomi']
        ref_count = len(re.findall(r'<ref[^>]*>.*?</ref>', manba_matni, re.DOTALL))

        context_data = f"""WIKIDATA: nomi: {nomi}, mavqe: {maʼlumotlar.get('mavqe')}, mintaqa: {maʼlumotlar.get('mintaqa')}, tuman: {maʼlumotlar.get('tuman')}, aholi: {maʼlumotlar.get('aholi')}, maydon: {maʼlumotlar.get('maydon')}, balandlik: {maʼlumotlar.get('balandlik')}, koordinatalar: {maʼlumotlar.get('koordinatalar')}, tasvir: {tasvir_nomi}"""

        user_prompt = f"""{context_data}\n\nSOURCE URL: https://en.wikipedia.org/wiki/{manba_nomi.replace(' ', '_')}\n\nENGLISH LEAD (REF COUNT: {ref_count}):\n{manba_matni}\n\nEXECUTION: Generate 3 sentences. Preserve refs. Use Category [[Turkum:Polsha aholi punktlari]]."""

        logger.info(f"🤖 Generating via {Config.AI_MODEL}...")
        result = self._call_api(user_prompt)

        if result:
            cleaned = TextSanitizer.clean(result)
            fixed = UzbekOrthographyFixer.fix_orthography(cleaned)
            return fixed
        return None

    def _call_api(self, user_prompt: str) -> Optional[str]:
        for attempt in range(1, Config.MAX_RETRIES + 1):
            try:
                payload = {
                    "model": Config.AI_MODEL,
                    "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                    "temperature": Config.TEMPERATURE,
                    "max_tokens": Config.MAX_TOKENS,
                }
                response = requests.post(self.endpoint, headers=self.headers, data=json.dumps(payload), timeout=Config.REQUEST_TIMEOUT)
                if response.status_code == 200:
                    return response.json()['choices'][0]['message']['content']
                elif response.status_code == 429:
                    time.sleep(Config.RATE_LIMIT_DELAY)
                else:
                    logger.error(f"API Error: {response.status_code}")
            except Exception as e:
                logger.error(f"Attempt {attempt} failed: {e}")
                time.sleep(Config.INITIAL_RETRY_DELAY * attempt)
        return None

# ==========================================
# 🗂️ WIKIDATA EXTRACTOR
# ==========================================
class WikidataExtractor:
    @staticmethod
    def extract(item: Any) -> Optional[Dict[str, Any]]:
        try:
            item.get()
            nomi = item.labels.get('uz') or item.labels.get('en')
            if not nomi: return None

            hierarchy = WikidataExtractor._get_hierarchy(item)
            pop = WikidataExtractor._get_claim_value(item, 'P1082', int)
            area = WikidataExtractor._get_claim_value(item, 'P2046', float)
            elev = WikidataExtractor._get_claim_value(item, 'P2044', float)
            postal = WikidataExtractor._get_claim_value(item, 'P281', str)
            mavqe = WikidataExtractor._get_mavqe(item)
            lat, lon = WikidataExtractor._get_coords(item)

            return {
                'nomi': nomi, 'mavqe': mavqe, 'mintaqa': hierarchy.get('mintaqa'),
                'tuman': hierarchy.get('tuman'), 'aholi': pop, 'maydon': area,
                'balandlik': elev, 'koordinatalar': f"{lat}, {lon}" if lat else None,
                'pochta': postal
            }
        except: return None

    @staticmethod
    def _get_mavqe(item: Any) -> str:
        if 'P31' not in item.claims: return "aholi punkti"
        qid = item.claims['P31'][0].getTarget().id
        mapping = {'Q532': 'qishloq', 'Q486972': 'aholi punkti', 'Q515': 'shahar', 'Q123705': 'mahalla'}
        return mapping.get(qid, "aholi punkti")

    @staticmethod
    def _get_hierarchy(item: Any) -> Dict[str, str]:
        hierarchy = {}
        curr = item
        for _ in range(5):
            if 'P131' not in curr.claims: break
            parent = curr.claims['P131'][0].getTarget()
            parent.get()
            label = parent.labels.get('uz') or parent.labels.get('en')
            if 'P31' in parent.claims:
                type_qid = parent.claims['P31'][0].getTarget().id
                if type_qid == 'Q15008': hierarchy['mintaqa'] = label
                elif type_qid == 'Q22714': hierarchy['tuman'] = label
            curr = parent
        return hierarchy

    @staticmethod
    def _get_claim_value(item, prop, converter=None):
        if prop not in item.claims: return None
        try:
            target = item.claims[prop][0].getTarget()
            val = target.amount if hasattr(target, 'amount') else target
            return converter(val) if converter else val
        except: return None

    @staticmethod
    def _get_coords(item):
        if 'P625' not in item.claims: return None, None
        try:
            c = item.claims['P625'][0].getTarget()
            return c.lat, c.lon
        except: return None, None

# ==========================================
# 🚀 BOT ENGINE
# ==========================================
class UzbekWikiBot:
    def __init__(self):
        Config.validate()
        self.builder = ArticleBuilder()
        self.fetcher = EnglishWikiFetcher()
        self.extractor = WikidataExtractor()
        self.site = pywikibot.Site('uz', 'wikipedia')
        self.repo = self.site.data_repository()
        if not Config.SIMULATION_OR_DRAFT_MODE: self.site.login()

    def run(self):
        query = f"SELECT DISTINCT ?item WHERE {{ ?item wdt:P31/wdt:P279* wd:Q486972; wdt:P17 wd:{Config.COUNTRY_QID}. }}"
        generator = pagegenerators.WikidataSPARQLPageGenerator(query, site=self.repo)
        count = 0
        for item in generator:
            if count >= Config.MAX_ARTICLES: break
            data = self.extractor.extract(item)
            if not data: continue

            page = pywikibot.Page(self.site, self._get_title(data['nomi']))
            if page.exists(): continue

            lead_text, en_title, img = self.fetcher.get_lead_wikitext(item)
            if not lead_text: continue

            article = self.builder.build_article(data, lead_text, en_title, img)
            if article:
                page.text = article
                page.save(summary=f"Bot: en:{en_title} tarjimasi", bot=True)
                count += 1
                time.sleep(Config.EDIT_DELAY)

    def _get_title(self, name):
        return f"Foydalanuvchi:{Config.BOT_USERNAME}/Qoralama/{name}" if Config.SIMULATION_OR_DRAFT_MODE else name

if __name__ == "__main__":
    try: UzbekWikiBot().run()
    except Exception as e:
        logger.critical(f"Fatal: {e}")
        sys.exit(1)
