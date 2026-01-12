# -*- coding: utf-8 -*-

import os
import time
import json
import logging
import asyncio
import threading
import re
from dataclasses import dataclass
from typing import Dict, Optional, List

import requests
from dotenv import load_dotenv
from telegram import Bot

# ================= CONFIG =================

load_dotenv()

@dataclass(frozen=True)
class Config:
    TELEGRAM_TOKEN: str
    CHAT_ID: int

    CHECK_INTERVAL: int = 180  # seconds

    MIN_VOLUME: float = 100_000
    MIN_SPREAD: float = 0.05
    MAX_SPREAD: float = 0.5

    MIN_VOLUME_DELTA: float = 0
    MIN_PRICE_MOVE: float = 0
    PERSISTENCE_CYCLES: int = 1

    MAX_ALERTS_PER_CYCLE: int = 6
    TELEGRAM_DELAY: float = 0.8

    DATA_FILE: str = "market_state.json"
    REFERRAL_CODE: str = "selenka"

    API_URL: str = "https://gamma-api.polymarket.com/markets"
    API_LIMIT: int = 500
    MAX_PAGES: int = 10
    REQUEST_TIMEOUT: int = 10


def load_config() -> Config:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID")
    return Config(TELEGRAM_TOKEN=token, CHAT_ID=int(chat_id))


# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("live-spread-bot")


# ================= MODELS =================

@dataclass
class Market:
    id: str
    question: str
    volume: float
    best_bid: float
    best_ask: float
    spread: float
    event_slug: Optional[str] = None
    group_item_title: Optional[str] = None


# ================= STATE =================

class MarketState:
    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, Dict] = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def update(self, m: Market):
        prev = self.data.get(m.id)
        self.data[m.id] = {
            "volume": m.volume,
            "best_bid": m.best_bid,
            "best_ask": m.best_ask,
            "last_seen": time.time(),
            "persistence": (prev.get("persistence", 0) + 1) if prev else 1
        }

    def get(self, market_id: str) -> Optional[Dict]:
        return self.data.get(market_id)


# ================= TELEGRAM =================

class TelegramNotifier:
    def __init__(self, token: str, chat_id: int, delay: float):
        self.bot = Bot(token=token)
        self.chat_id = chat_id
        self.delay = delay

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def send(self, text: str):
        coro = self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            disable_web_page_preview=True
        )
        asyncio.run_coroutine_threadsafe(coro, self.loop)
        time.sleep(self.delay)


# ================= BOT =================

class LiveSpreadBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.state = MarketState(cfg.DATA_FILE)
        self.notifier = TelegramNotifier(
            cfg.TELEGRAM_TOKEN,
            cfg.CHAT_ID,
            cfg.TELEGRAM_DELAY
        )

    def fetch(self) -> List[dict]:
        markets = []
        offset = 0
        for _ in range(self.cfg.MAX_PAGES):
            r = self.session.get(
                self.cfg.API_URL,
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": self.cfg.API_LIMIT,
                    "offset": offset
                },
                timeout=self.cfg.REQUEST_TIMEOUT
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            markets.extend(batch)
            offset += self.cfg.API_LIMIT
        return markets

    def parse(self, raw: dict) -> Optional[Market]:
        try:
            bid = float(raw.get("bestBid", 0))
            ask = float(raw.get("bestAsk", 1))
            spread = max(float(raw.get("spread", 0)), ask - bid)

            # Extract event slug for link generation
            event_slug = None
            events = raw.get("events", [])
            if events and len(events) > 0:
                event_slug = events[0].get("slug")

            # Get group item title for nested markets
            group_item_title = raw.get("groupItemTitle")

            return Market(
                id=str(raw["id"]),
                question=raw.get("question", "No title"),
                volume=float(raw.get("volumeNum", 0)),
                best_bid=bid,
                best_ask=ask,
                spread=spread,
                event_slug=event_slug,
                group_item_title=group_item_title,
            )
        except Exception:
            return None

    def clean_question(self, question: str) -> str:
        """Remove any URLs from the question text."""
        # Remove URLs (http/https)
        cleaned = re.sub(r'https?://[^\s]+', '', question)
        # Remove any leftover whitespace
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    def generate_market_link(self, m: Market) -> str:
        """Generate Polymarket link with referral code.
        
        Uses the event slug from the parent event, even if this is a nested market.
        Returns a link with the referral code appended.
        """
        if m.event_slug:
            link = f"https://polymarket.com/event/{m.event_slug}?via={self.cfg.REFERRAL_CODE}"
            log.debug(f"Generated link for market {m.id}: {link} (event_slug={m.event_slug})")
            return link
        else:
            # Fallback if no event slug available
            log.warning(f"No event slug for market {m.id}, using fallback link")
            return f"https://polymarket.com?via={self.cfg.REFERRAL_CODE}"

    def is_live(self, m: Market) -> Optional[float]:
        prev = self.state.get(m.id)
        if not prev:
            return None

        volume_delta = m.volume - prev["volume"]
        price_move = abs(m.best_bid - prev["best_bid"]) + abs(m.best_ask - prev["best_ask"])
        persistence = prev.get("persistence", 1)

        if volume_delta < self.cfg.MIN_VOLUME_DELTA:
            return None
        if price_move < self.cfg.MIN_PRICE_MOVE:
            return None
        if persistence < self.cfg.PERSISTENCE_CYCLES:
            return None
        if m.volume < self.cfg.MIN_VOLUME:
            return None
        if not (self.cfg.MIN_SPREAD <= m.spread <= self.cfg.MAX_SPREAD):
            return None

        return volume_delta * price_move * m.spread

    def run_once(self):
        live_markets = []

        for raw in self.fetch():
            m = self.parse(raw)
            if not m:
                continue

            score = self.is_live(m)
            self.state.update(m)

            if score:
                live_markets.append((score, m))

        self.state.save()

        if not live_markets:
            log.info("No live markets this cycle")
            return

        live_markets.sort(key=lambda x: x[0], reverse=True)
        selected = live_markets[: self.cfg.MAX_ALERTS_PER_CYCLE]

        for _, m in selected:
            link = self.generate_market_link(m)
            
            # Clean question text (remove any embedded URLs)
            clean_q = self.clean_question(m.question)
            
            # Add group item title if this is a nested market
            title = clean_q
            if m.group_item_title:
                title = f"{clean_q} - {m.group_item_title}"
            
            msg = (
                f"== LIVE SPREAD ALERT ==\n\n"
                f"{title}\n"
                f"Spread: {m.spread:.4f} ({m.spread*100:.1f}%)\n"
                f"Volume: ${m.volume:,.0f}\n\n"
                f" {link}"
            )
            self.notifier.send(msg)

    def run(self):
        log.info("Bot started")
        while True:
            try:
                self.run_once()
            except Exception:
                log.exception("Cycle error")
            time.sleep(self.cfg.CHECK_INTERVAL)


# ================= ENTRY =================

if __name__ == "__main__":
    LiveSpreadBot(load_config()).run()
