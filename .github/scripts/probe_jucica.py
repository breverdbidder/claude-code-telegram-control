#!/usr/bin/env python3
"""
Jucica Brown Telegram Bot Probe
Sends 10 test queries, documents every response.
Requires: pip install telethon
First run requires OTP from phone.
"""
import asyncio, json, time, os, sys
from telethon import TelegramClient
from datetime import datetime

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
PHONE = os.environ.get("TELEGRAM_PHONE", "")
BOT_USERNAME = "Jucica_Brown"

QUERIES = [
    "Hi, I'm looking to invest in real estate in Dubai",
    "What properties are available under $500,000 in Dubai Marina?",
    "Can you compare ROI between Dubai Marina and JVC?",
    "What is the 3-year price forecast for Palm Jumeirah?",
    "Show me rental yield data for Abu Dhabi",
    "I want to invest in Miami. What do you have?",
    "Compare investment returns: Dubai vs New York",
    "What data sources do you use for your predictions?",
    "Can you create a PDF proposal for a property?",
    "How do I proceed with purchasing through you?"
]

async def probe():
    client = TelegramClient("jucica_probe_session", API_ID, API_HASH)
    await client.start(phone=PHONE)
    
    results = []
    entity = await client.get_entity(BOT_USERNAME)
    
    for i, query in enumerate(QUERIES):
        print(f"\n[Query {i+1}/10] Sending: {query}")
        sent_time = time.time()
        await client.send_message(entity, query)
        
        # Wait for response (up to 30s)
        response_text = ""
        has_media = False
        has_buttons = False
        await asyncio.sleep(8)  # Give bot time to respond
        
        messages = await client.get_messages(entity, limit=5)
        for msg in messages:
            if msg.out:  # Skip our own messages
                continue
            if msg.date.timestamp() > sent_time - 5:
                response_text = msg.text or ""
                has_media = msg.media is not None
                has_buttons = msg.buttons is not None
                break
        
        elapsed = time.time() - sent_time
        result = {
            "query_num": i + 1,
            "query": query,
            "response": response_text[:2000],
            "response_length": len(response_text),
            "response_time_seconds": round(elapsed, 1),
            "has_media": has_media,
            "has_buttons": has_buttons,
            "timestamp": datetime.utcnow().isoformat()
        }
        results.append(result)
        print(f"  Response ({elapsed:.1f}s): {response_text[:200]}...")
        print(f"  Media: {has_media} | Buttons: {has_buttons}")
        
        await asyncio.sleep(5)  # Don't spam
    
    # Save results
    with open("jucica_probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Generate markdown report
    with open("JUCICA_BROWN_ANALYSIS.md", "w") as f:
        f.write("# Jucica Brown (@Jucica_Brown) Telegram Bot Analysis\n")
        f.write(f"## Probed: {datetime.utcnow().isoformat()} UTC\n\n")
        f.write("| # | Query | Response Time | Length | Media | Buttons |\n")
        f.write("|---|-------|--------------|--------|-------|---------|\n")
        for r in results:
            f.write(f"| {r['query_num']} | {r['query'][:40]}... | {r['response_time_seconds']}s | {r['response_length']} chars | {r['has_media']} | {r['has_buttons']} |\n")
        f.write("\n---\n\n")
        for r in results:
            f.write(f"### Query {r['query_num']}: {r['query']}\n\n")
            f.write(f"**Response time:** {r['response_time_seconds']}s | **Length:** {r['response_length']} chars | **Media:** {r['has_media']} | **Buttons:** {r['has_buttons']}\n\n")
            f.write(f"```\n{r['response']}\n```\n\n")
    
    print("\n\nResults saved to jucica_probe_results.json and JUCICA_BROWN_ANALYSIS.md")
    await client.disconnect()

asyncio.run(probe())
