"""推送渠道 — Server酱(微信)、邮件、日志

渠道:
1. 日志 — 始终启用
2. Server酱(SCT) — 微信推送, 配置 push.serverchan_sendkey
3. 邮件 — SMTP推送, 配置 push.email_* 字段
"""
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / 'config' / 'api_keys.yaml'


def _load_push_config() -> dict:
    """加载推送配置"""
    try:
        import yaml
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        push = data.get('push', {})
        return push
    except Exception:
        return {}


def send_serverchan(title: str, content: str) -> bool:
    """发送Server酱推送(微信消息)

    Args:
        title: 消息标题(最长256)
        content: Markdown格式内容

    Returns:
        True if sent successfully
    """
    config = _load_push_config()
    sendkey = config.get('serverchan_sendkey', '')
    if not sendkey:
        logger.info('Server酱未配置, 跳过推送')
        return False

    try:
        import requests
        url = f'https://sctapi.ftqq.com/{sendkey}.send'
        resp = requests.post(url, data={'title': title[:256], 'desp': content}, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('code') == 0 or result.get('errno') == 0:
                logger.info('Server酱推送成功')
                return True
            logger.warning('Server酱返回错误: %s', result.get('message', result))
            return False
        logger.warning('Server酱HTTP错误: %d', resp.status_code)
        return False
    except Exception as e:
        logger.warning('Server酱推送失败: %s', e)
        return False


def format_daily_push(date: str, mode: str, predictions: list,
                      top3: list, stop_loss: dict, roi_summary: dict) -> str:
    """格式化日推送内容(Server酱Markdown格式)"""
    lines = []
    lines.append(f'## {date} 分析师日报')
    lines.append(f'模式: {mode} | 今日{len(predictions)}场比赛')
    lines.append('')

    # 止损
    if stop_loss.get('active'):
        lines.append(f'> **止损模式**: 近7天ROI {stop_loss.get("roi", 0)}%, Kelly减半, 只推TOP1')
        lines.append('')

    # 全部比赛6项预测
    if predictions:
        lines.append('### 全部赛事预测')
        lines.append('')
        for pred in predictions:
            home = pred.get('home_team_cn', '主')
            away = pred.get('away_team_cn', '客')
            league = pred.get('league_name_cn', '')
            pp = pred.get('play_predictions', {})

            # 胜平负
            spf = pp.get('spf', {})
            spf_dir = spf.get('direction_cn', spf.get('direction', '?'))
            spf_probs = spf.get('probabilities', {})

            line = f'**{league} {home} vs {away}**'
            if spf_dir:
                line += f' — {spf_dir}'
            lines.append(line)

            # 详细概率
            if spf_probs:
                lines.append(f'  胜平负: 主{spf_probs.get("3", 0):.0%} 平{spf_probs.get("1", 0):.0%} 客{spf_probs.get("0", 0):.0%}')

            # TOP3比分
            top3_scores = pp.get('top3_scores', [])
            if top3_scores:
                score_str = '  '.join(f'{s["score"]}({s["probability"]:.0%})' for s in top3_scores)
                lines.append(f'  比分: {score_str}')

            # 让球胜平负
            rqspf = pp.get('rqspf', {})
            if rqspf and rqspf.get('direction'):
                rq_dir = rqspf.get('direction_cn', rqspf.get('direction', '?'))
                rq_hc = rqspf.get('handicap', 0)
                rq_probs = rqspf.get('probabilities', {})
                if rq_probs:
                    lines.append(f'  让球(让{rq_hc:+.1f}): {rq_dir} 主{rq_probs.get("3", 0):.0%} 平{rq_probs.get("1", 0):.0%} 客{rq_probs.get("0", 0):.0%}')

            # 大小球
            ou = pp.get('over_under', {})
            if ou and ou.get('recommendation'):
                lines.append(f'  大小球: {ou.get("recommendation", "?")} (大2.5={ou.get("over_2_5", 0):.0%})')

            # 半全场
            bqc = pp.get('bqc', {})
            if bqc and bqc.get('recommendation'):
                lines.append(f'  半全场: {bqc.get("recommendation_cn", bqc.get("recommendation", "?"))}')

            lines.append('')

    # TOP3价值投注
    if top3:
        lines.append('### 推荐投注 TOP3')
        for i, bet in enumerate(top3, 1):
            home = bet.get('home', '主')
            away = bet.get('away', '客')
            league = bet.get('league', '')
            selection_map = {'3': '主胜', '1': '平局', '0': '客胜'}
            selection = selection_map.get(bet.get('selection', ''), bet.get('selection', ''))
            edge = bet.get('edge', 0)
            reason = bet.get('reason', '模型推荐')
            lines.append(f'**{i}. {league} {home} vs {away}**')
            lines.append(f'   → {selection} | 优势+{edge:.0%}')
            lines.append(f'   {reason}')
            lines.append('')
    else:
        lines.append('### 今日无价值投注')
        lines.append('')

    # ROI
    if roi_summary:
        lines.append('### 近期ROI')
        for period, info in roi_summary.items():
            lines.append(f'- {period}: {info.get("roi", "-")} ({info.get("wins", 0)}/{info.get("matches", 0)}正确)')
        lines.append('')

    return '\n'.join(lines)


def send_email(title: str, content: str) -> bool:
    """发送邮件推送

    配置(config/api_keys.yaml):
      push:
        email_smtp_host: smtp.qq.com
        email_smtp_port: 465
        email_user: your@qq.com
        email_password: authorization_code
        email_to: recipient@example.com
    """
    config = _load_push_config()
    host = config.get('email_smtp_host', '')
    user = config.get('email_user', '')
    password = config.get('email_password', '')
    to = config.get('email_to', '')

    if not all([host, user, password, to]):
        logger.info('邮件推送未配置, 跳过')
        return False

    port = int(config.get('email_smtp_port', 465))

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = title
        msg['From'] = user
        msg['To'] = to

        # Plain text fallback
        plain = content.replace('##', '').replace('**', '').replace('###', '').replace('> ', '')
        msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        # HTML version (simple: wrap markdown in <pre>)
        html = f'<html><body><pre style="font-family:monospace;font-size:14px">{content}</pre></body></html>'
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()

        server.login(user, password)
        server.sendmail(user, to.split(','), msg.as_string())
        server.quit()
        logger.info('邮件推送成功: %s', to)
        return True
    except Exception as e:
        logger.warning('邮件推送失败: %s', e)
        return False


def push_to_all_channels(title: str, content: str) -> Dict:
    """推送到所有已配置的渠道"""
    results = {}

    # 1. 日志(始终)
    logger.info('推送内容: %s', title)
    results['log'] = True

    # 2. Server酱
    results['serverchan'] = send_serverchan(title, content)

    # 3. 邮件
    results['email'] = send_email(title, content)

    return results