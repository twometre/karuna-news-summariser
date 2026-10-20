import re
import logging
import anthropic
from config import LOG_PATH, SUMMARY_MAX_WORDS
from db import get_setting

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

MODEL = "claude-haiku-4-5"

def _get_key():
    return get_setting("anthropic_api_key") or __import__('config').ANTHROPIC_API_KEY

def _parse_batch(text, n):
    """Extract numbered summaries: '### 1\\nsummary...' blocks. Returns list aligned to input count."""
    parts = re.split(r"^###\s*(\d+)\s*$", text, flags=re.M)
    # parts = [preamble, '1', body1, '2', body2, ...]
    found = {}
    for i in range(1, len(parts) - 1, 2):
        try:
            idx = int(parts[i])
        except ValueError:
            continue
        body = parts[i + 1].strip()
        if 1 <= idx <= n and body:
            found[idx] = body
    return [found.get(i) for i in range(1, n + 1)]

def summarise_batch(articles):
    if not articles:
        return []
    api_key = _get_key()
    if not api_key:
        logging.error("No Anthropic API key configured")
        return []
    max_words = int(get_setting("summary_max_words") or SUMMARY_MAX_WORDS)
    client = anthropic.Anthropic(api_key=api_key)

    blocks = []
    for i, a in enumerate(articles, 1):
        blocks.append(f"### {i}\nTitle: {a['title']}\nContent: {a['summary'][:1200]}")
    prompt = f"""Summarise each news article below in no more than {max_words} words each, in English.
Cover: Who, What, Where, When, How. Be factual and neutral. No preamble, no commentary.

Reply with EXACTLY one block per article, in this format (plain text, no markdown):
### 1
[summary of article 1]
### 2
[summary of article 2]
...and so on for all {len(articles)} articles. Do not skip or merge numbers.

{chr(10).join(blocks)}"""

    summaries = None
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=250 * len(articles) + 100,
            messages=[{"role": "user", "content": prompt}])
        summaries = _parse_batch(message.content[0].text.strip(), len(articles))
        got = sum(1 for s in summaries if s)
        logging.info(f"Batch summarised {got}/{len(articles)} articles in one call")
    except Exception as e:
        logging.error(f"Batch summarise failed: {e}")

    results = []
    for i, article in enumerate(articles):
        text = summaries[i] if summaries else None
        if not text:
            # Fallback: retry this one article on its own.
            text = _summarise_single(client, article, max_words)
        if not text:
            continue
        results.append({"title": article["title"], "url": article["url"],
                        "category": article["category"], "summary": text})
    return results

def _summarise_single(client, article, max_words):
    prompt = f"""Summarise the following news article in no more than {max_words} words in English.
Cover: Who, What, Where, When, How. Be factual and neutral. No preamble, no commentary.

Title: {article['title']}
Content: {article['summary'][:1500]}"""
    try:
        message = client.messages.create(
            model=MODEL, max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        logging.info(f"Fallback summarised: {article['title'][:60]}")
        return message.content[0].text.strip()
    except Exception as e:
        logging.error(f"Summarise failed for {article['url']}: {e}")
        return None
