import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def test_365scores():
    from app.data_sources.scores365_source import Scores365Source

    source = Scores365Source()

    # 获取所有比赛
    games = await source.get_games()

    print(f'365Scores返回比赛数: {len(games)}')

    # 查找已结束的比赛
    ended = [g for g in games if g.get('statusText') == 'Ended']
    print(f'已结束比赛数: {len(ended)}')

    # 显示最近5场已结束比赛
    print('\n最近已结束比赛:')
    for game in ended[:5]:
        home = game.get('homeCompetitor', {})
        away = game.get('awayCompetitor', {})
        print(f'  {game.get("startTime", "")[:10]} | {home.get("name")} {home.get("score")} - {away.get("score")} {away.get("name")}')

    # 查找瑞典联赛
    swedish = [g for g in games if 'Djurgarden' in str(g) or 'Sirius' in str(g) or 'Allsvenskan' in str(g)]
    print(f'\n瑞典联赛相关比赛: {len(swedish)}')
    for g in swedish[:3]:
        print(f'  {g}')

    await source.close()

asyncio.run(test_365scores())