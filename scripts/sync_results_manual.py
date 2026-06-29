"""Sync results for specific dates"""
import sys
import os
sys.path.insert(0, '/opt/football_tools')

from backend.app.lottery.services.sync_service import LotterySyncService

DB_PATH = "/opt/football_tools/data/football_v2.db"
service = LotterySyncService(DB_PATH)

# 同步 6 月 11 日 -12 日 的结果
for d in ["2026-06-11", "2026-06-12"]:
    print(f'=== Syncing results for {d} ===')
    result = service.sync_results(d)
    print('Success:', result.get('success'))
    print('Saved:', result.get('saved'))
    if result.get('errors'):
        print('Errors:', result['errors'][:3])

service.close()
