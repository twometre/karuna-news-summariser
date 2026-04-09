import anthropic
import logging
from config import LOG_PATH, SUMMARY_MAX_WORDS
from db import get_setting

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def summarise_article(article):
    api_key = get_setting("anthropic_api_key") or __import__('config').ANTHROPIC_API_KEY
    if not api_key:
        logging.error("No Anthropic API key configured")
        return None
    max_words = int(get_setting("summary_max_words") or SUMMARY_MAX_WORDS)
    prompt = f"""Summarise the following news article in no more than {max_words} words in English.
Cover: Who, What, Where, When, How. Be factual and neutral. No preamble, no commentary.

Title: {article['title']}
Content: {article['summary'][:1500]}
Source URL: {article['url']}

Output format (plain text, no markdown):
[Summary text here]
Source: [URL]"""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        result_text = message.content[0].text.strip()
        logging.info(f"Summarised: {article['title'][:60]}")
        return {"title": article["title"], "url": article["url"],
                "category": article["category"], "summary": result_text}
    except Exception as e:
        logging.error(f"Summarise failed for {article['url']}: {e}")
        return None

def summarise_batch(articles):
    return [r for r in (summarise_article(a) for a in articles) if r]
