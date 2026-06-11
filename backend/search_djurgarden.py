import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def search_djurgarden():
    from app.data_sources.scores365_source import Scores365Source

    source = Scores365Source()
    games = await source.get_games()

    # 搜索Djurgarden
    for g in games:
        home = g.get('homeCompetitor', {}).get('name', '')
        away = g.get('awayCompetitor', {}).get('name', '')
        if 'Djurgarden' in home or 'Djurgarden' in away or 'Sirius' in home or 'Sirius' in away:
            print(f'{g.get("startTime", "")[:10]} | {home} vs {away} | status: {g.get("statusText")} | score: {g.get("homeCompetitor", {}).get("score")}-{g.get("awayCompetitor", {}).get("score")}')

    await source.close()

asyncio.run(search_djurgarden())