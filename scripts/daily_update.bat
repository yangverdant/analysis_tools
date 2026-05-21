@echo off
REM 足球数据每日自动更新任务
REM 使用Windows任务计划程序设置每天运行

cd /d d:\football_tools
python scripts\update_football_data.py --all

echo 更新完成: %date% %time%
