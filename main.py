#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import hashlib, os, subprocess, time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

# ============================================================
GITHUB_USERNAME, GITHUB_REPO = "jasdovica-glitch", "achmin-live"
# PUT YOUR GITHUB TOKEN HERE
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
APP_NAME = "ACHMIN LIVE"
# ============================================================

SIIIR_URL = "https://www.siiiiir.tv/"
ATKORAT_URL = "https://atkorat.net/"

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class DualScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        })

    def fetch_html(self, url: str) -> Optional[str]:
        try:
            r = self.session.get(url, timeout=20)
            r.encoding = 'utf-8'
            return r.text if r.ok else None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def normalize_name(self, text: str) -> str:
        t = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه')
        t = t.replace('ال', '').replace(' ', '')
        return t

    def parse_matches(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        matches = []
        for el in soup.find_all('div', class_='AY_Match'):
            try:
                classes = el.get('class', [])
                m = {
                    'home': '', 'away': '', 'home_logo': '', 'away_logo': '',
                    'time': '', 'status': 'upcoming', 'status_text': 'لم تبدأ بعد',
                    'home_score': None, 'away_score': None, 'has_score': False,
                    'is_live': False, 'is_soon': False, 'is_finished': False,
                    'priority': 3, 'tournament': '', 'match_url': '',
                    'stream_id': None, 'stream_url': '', 'has_stream': False
                }

                if 'live' in classes or 'gools' in classes or 'started' in classes:
                    m['status']='live'; m['status_text']='جارية الآن'; m['priority']=1; m['is_live']=True
                elif 'comming-soon' in classes:
                    m['status']='soon'; m['status_text']='بعد قليل'; m['priority']=2; m['is_soon']=True
                elif 'finished' in classes:
                    m['status']='finished'; m['status_text']='انتهت'; m['priority']=4; m['is_finished']=True

                tm1 = el.find('div', class_='TM1')
                if tm1:
                    nm = tm1.find('div', class_='TM_Name')
                    lg = tm1.find('img')
                    m['home'] = nm.text.strip() if nm else '---'
                    m['home_logo'] = lg.get('data-src') or lg.get('src', '') if lg else ''

                tm2 = el.find('div', class_='TM2')
                if tm2:
                    nm = tm2.find('div', class_='TM_Name')
                    lg = tm2.find('img')
                    m['away'] = nm.text.strip() if nm else '---'
                    m['away_logo'] = lg.get('data-src') or lg.get('src', '') if lg else ''

                time_el = el.find('span', class_='MT_Time')
                if time_el:
                    m['time'] = time_el.text.strip()

                if m['is_live'] or m['is_finished']:
                    gs = el.find_all('span', class_='RS-goals')
                    if len(gs) >= 2:
                        m['home_score'] = gs[0].text.strip()
                        m['away_score'] = gs[1].text.strip()
                        m['has_score'] = True

                link = el.find('a', href=True)
                if link:
                    m['match_url'] = link['href']
                    title_attr = link.get('title', '')
                    if 'في دوري ' in title_attr:
                        m['tournament'] = title_attr.split('في دوري ')[-1].strip()
                    elif 'في كأس ' in title_attr:
                        m['tournament'] = title_attr.split('في كأس ')[-1].strip()
                    elif 'في ' in title_attr:
                        m['tournament'] = title_attr.split('في ')[-1].strip()

                if m['home'] and m['away']:
                    matches.append(m)
            except Exception as e:
                continue
                
        matches.sort(key=lambda x: x['priority'])
        return matches

    def get_iframe_src(self, url: str) -> str:
        try:
            r = self.session.get(url, timeout=15)
            if r.ok:
                soup = BeautifulSoup(r.text, 'html.parser')
                iframe = soup.find('iframe')
                if iframe and iframe.get('src'):
                    return iframe.get('src')
        except: pass
        return ""

    def run_scraping(self):
        logger.info("Fetching Siiir TV data...")
        siiir_html = self.fetch_html(SIIIR_URL)
        if not siiir_html: return None
            
        matches = self.parse_matches(siiir_html)
        live_or_soon = [m for m in matches if m['is_live'] or m['is_soon']]
        
        if live_or_soon:
            logger.info("Fetching Atkorat stream links...")
            atkorat_html = self.fetch_html(ATKORAT_URL)
            if atkorat_html:
                at_matches = self.parse_matches(atkorat_html)
                at_map = {}
                for am in at_matches:
                    key1 = self.normalize_name(am['home']) + "-" + self.normalize_name(am['away'])
                    key2 = self.normalize_name(am['away']) + "-" + self.normalize_name(am['home'])
                    at_map[key1] = am['match_url']
                    at_map[key2] = am['match_url']

                for m in live_or_soon:
                    k = self.normalize_name(m['home']) + "-" + self.normalize_name(m['away'])
                    target_url = at_map.get(k)
                    if target_url:
                        iframe = self.get_iframe_src(target_url)
                        if iframe:
                            m['stream_url'] = iframe
                            m['has_stream'] = True
                            m['stream_id'] = hashlib.md5(iframe.encode()).hexdigest()[:8]
        return matches

class HTMLBuilder:
    # Futuristic SVGs for Matches
    icon_live_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" style="filter: drop-shadow(0px 0px 4px rgba(239,68,68,0.8));"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3"/><circle cx="12" cy="12" r="2" fill="currentColor"/></svg>'
    icon_soon_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="miter" style="filter: drop-shadow(0px 0px 4px rgba(245,158,11,0.8));"><polygon points="12 2 22 7 22 17 12 22 2 17 2 7 12 2"/><path d="M12 7v5l3 3"/></svg>'
    icon_upcoming_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="miter" style="filter: drop-shadow(0px 0px 4px rgba(16,185,129,0.8));"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/></svg>'
    icon_finished_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="miter" style="filter: drop-shadow(0px 0px 4px rgba(59,130,246,0.8));"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M8 12l3 3 5-5"/></svg>'

    def generate_fixtures(self, matches: List[Dict]) -> str:
        groups = {}
        for m in matches: groups.setdefault(m.get('tournament', 'مباريات أخرى'), []).append(m)
        live_m = [m for m in matches if m['is_live']]; soon_m = [m for m in matches if m['is_soon']]
        upcoming_m = [m for m in matches if not m['is_live'] and not m['is_soon'] and not m['is_finished']]
        finished_m = [m for m in matches if m['is_finished']]
        cards_html = ''
        for tname, tmatches in groups.items():
            cards = ''.join(self._match_card(m) for m in tmatches)
            cards_html += f'''<section class="tournament-section"><div class="section-header"><h2>🏆 {tname}</h2><span class="section-badge">{len(tmatches)} مباريات</span></div><div class="cards-grid">{cards}</div></section>'''
        return self._app_template(cards_html, len(live_m), len(soon_m), len(upcoming_m), len(finished_m))

    def _match_card(self, m):
        cc = {'live':'card-live','soon':'card-soon','finished':'card-finished'}.get(m['status'],'')
        bc = {'live':'badge-live','soon':'badge-soon','finished':'badge-finished'}.get(m['status'],'badge-upcoming')
        status_icons = {'live': f'<span class="status-icon-svg">{self.icon_live_svg}</span>', 'soon': f'<span class="status-icon-svg">{self.icon_soon_svg}</span>', 'upcoming': f'<span class="status-icon-svg">{self.icon_upcoming_svg}</span>', 'finished': f'<span class="status-icon-svg">{self.icon_finished_svg}</span>'}
        icon = status_icons.get(m['status'], status_icons['upcoming'])
        sc = f'<div class="score-display"><span class="score-value">{m["home_score"]}</span><span class="score-sep">-</span><span class="score-value">{m["away_score"]}</span></div>' if m['has_score'] and m['home_score'] is not None else '<div class="score-vs">VS</div>'
        stream_url = f"streams/{m['stream_id']}.html" if m['has_stream'] and m['stream_id'] else ''
        btn = f'<a href="{stream_url}" class="watch-btn" onclick="return showNotice(event, this)">مشاهدة البث</a>' if stream_url else ''
        return f'<div class="match-card {cc}"><div class="card-body"><div class="match-row"><div class="team-box team-left"><div class="team-logo-wrap"><img src="{m["home_logo"]}" class="team-logo-img" onerror="this.style.visibility=\'hidden\'" loading="lazy"></div><span class="team-label">{m["home"]}</span></div><div class="match-center"><div class="status-row"><span class="status-badge {bc}">{icon} {m["status_text"]}</span></div><div class="time-row">🕐 {m["time"]}</div>{sc}</div><div class="team-box team-right"><div class="team-logo-wrap"><img src="{m["away_logo"]}" class="team-logo-img" onerror="this.style.visibility=\'hidden\'" loading="lazy"></div><span class="team-label">{m["away"]}</span></div></div><div class="tournament-label">{m.get("tournament","")}</div><div class="action-row">{btn}</div></div></div>'

    def generate_stream_page(self, match):
        url = match.get('stream_url', '')
        sc = f'{match["home_score"]} - {match["away_score"]}' if match['has_score'] and match['home_score'] else 'VS'
        lb = '<span class="live-badge">🔴 LIVE</span>' if match['is_live'] else ''
        return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{match['home']} {sc} {match['away']} | {APP_NAME}</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet"><style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Tajawal',sans-serif;background:#0f172a;color:#f8fafc;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px}}.sc{{width:100%;max-width:960px;background:#1e293b;border-radius:12px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.5);border:1px solid #334155}}.sh2{{background:#0f172a;padding:22px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid #334155}}.mi{{display:flex;align-items:center;gap:20px}}.tm{{display:flex;flex-direction:column;align-items:center;gap:8px}}.tlg{{width:56px;height:56px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.05);padding:5px}}.tmn{{font-size:15px;font-weight:700;text-align:center}}.scd{{font-size:34px;font-weight:900;font-family:monospace;min-width:110px;text-align:center}}.svs{{font-size:16px;font-weight:700;color:#94a3b8}}.live-badge{{background:#ef4444;color:#fff;padding:8px 20px;border-radius:6px;font-size:13px;font-weight:800;display:inline-block;margin-bottom:6px;letter-spacing:.5px;box-shadow:0 0 8px rgba(239,68,68,0.4)}}.bbtn{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.05);color:#e2e8f0;text-decoration:none;padding:10px 22px;border-radius:6px;font-size:13px;font-weight:700;border:1px solid #334155}}.pw{{position:relative;width:100%;background:#000}}iframe{{display:block;width:100%;height:520px;border:none}}.sf{{padding:14px 24px;text-align:center;font-size:11px;color:#64748b;border-top:1px solid #334155}}@media(max-width:600px){{.sh2{{padding:14px 16px;gap:10px}}.tlg{{width:40px;height:40px}}.scd{{font-size:26px;min-width:80px}}iframe{{height:300px}}.tmn{{font-size:13px}}}}</style></head><body><div class="sc"><div class="sh2"><div class="mi"><div class="tm"><img src="{match['home_logo']}" class="tlg" onerror="this.style.display='none'"><span class="tmn">{match['home']}</span></div><div class="scd">{lb}<div class="svs">{sc}</div></div><div class="tm"><img src="{match['away_logo']}" class="tlg" onerror="this.style.display='none'"><span class="tmn">{match['away']}</span></div></div><a href="../fixtures.html" class="bbtn"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg> العودة للجدول</a></div><div class="pw"><iframe src="{url}" allowfullscreen allow="autoplay;fullscreen;picture-in-picture" sandbox="allow-scripts allow-same-origin allow-presentation" referrerpolicy="no-referrer"></iframe></div><div class="sf">{APP_NAME}</div></div></body></html>'''

    def _common_css(self):
        return '''/* Futuristic Pro Slate Theme - ZERO ANIMATIONS */
:root{--bg:#0f172a;--card:#1e293b;--text:#f8fafc;--text2:#94a3b8;--border:#334155;--accent:#3b82f6;--red:#ef4444;--green:#10b981;--gold:#f59e0b;--blue:#3b82f6;--radius:12px;--stat-bg:rgba(255,255,255,0.03);--pill-bg:rgba(239,68,68,0.15);--pill-border:rgba(239,68,68,0.3);--pill-color:#fca5a5;--badge-live-bg:rgba(239,68,68,0.15);--badge-live-color:#fca5a5;--badge-soon-bg:rgba(245,158,11,0.15);--badge-soon-color:#fcd34d;--badge-up-bg:rgba(16,185,129,0.15);--badge-up-color:#6ee7b7;--badge-fin-bg:rgba(59,130,246,0.15);--badge-fin-color:#93c5fd;--logo-bg:rgba(255,255,255,0.03);--vs-bg:rgba(255,255,255,0.03)} body.light-mode {--bg:#f8fafc;--card:#ffffff;--text:#0f172a;--text2:#475569;--border:#e2e8f0;--accent:#2563eb;--red:#dc2626;--green:#059669;--gold:#d97706;--blue:#2563eb;--stat-bg:rgba(0,0,0,0.03);--pill-bg:rgba(220,38,38,0.1);--pill-border:rgba(220,38,38,0.2);--pill-color:#dc2626;--badge-live-bg:rgba(220,38,38,0.1);--badge-live-color:#dc2626;--badge-soon-bg:rgba(217,119,6,0.1);--badge-soon-color:#d97706;--badge-up-bg:rgba(5,150,105,0.1);--badge-up-color:#059669;--badge-fin-bg:rgba(37,99,235,0.1);--badge-fin-color:#2563eb;--logo-bg:rgba(0,0,0,0.03);--vs-bg:rgba(0,0,0,0.03)} *{margin:0;padding:0;box-sizing:border-box} body{font-family:'Tajawal',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6;font-size:15px;-webkit-font-smoothing:antialiased;} a{text-decoration:none;color:inherit} .header{background:var(--bg);border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100;} .header-inner{max-width:1300px;margin:0 auto;padding:0 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap} .brand h1{font-size:26px;font-weight:900;letter-spacing:-1px;color:var(--accent);text-transform:uppercase;} .brand span{font-size:11px;color:var(--text2);font-weight:500;letter-spacing:1px} .header-actions{display:flex;align-items:center;gap:12px} .live-pill{display:flex;align-items:center;gap:8px;background:var(--pill-bg);border:1px solid var(--pill-border);padding:7px 16px;border-radius:20px;font-size:12px;font-weight:700;color:var(--pill-color);letter-spacing:.5px;} .live-dot{width:8px;height:8px;background:var(--red);border-radius:50%;box-shadow:0 0 6px var(--red);} .theme-btn{width:40px;height:40px;border-radius:50%;border:1px solid var(--border);background:var(--stat-bg);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;color:var(--text2);} .main-content{max-width:1300px;margin:0 auto;padding:32px 28px} .stats-row{display:flex;gap:12px;margin-bottom:32px;flex-wrap:wrap} .stat-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;display:flex;align-items:center;gap:14px;flex:1;min-width:130px;box-shadow:0 4px 6px rgba(0,0,0,0.05);} .stat-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:var(--stat-bg);} .stat-icon svg{width:22px;height:22px;} .stat-icon-live { color: var(--red); } .stat-icon-soon { color: var(--gold); } .stat-icon-up { color: var(--green); } .stat-icon-fin { color: var(--blue); } .stat-value{font-size:26px;font-weight:900;line-height:1} .stat-label{font-size:11px;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:1px} .tournament-section{margin-bottom:40px} .section-header{margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px} .section-header::before{content:'';width:4px;height:20px;background:var(--accent);border-radius:2px;} .section-header h2{font-size:19px;font-weight:800;color:var(--text);} .section-badge{font-size:11px;color:var(--text2);background:var(--stat-bg);padding:3px 10px;border-radius:6px;font-weight:600;border:1px solid var(--border);} .cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px} .match-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:0 2px 4px rgba(0,0,0,0.1);} .card-live{border-left:4px solid var(--red);} .card-soon{border-left:4px solid var(--gold);} .card-body{padding:18px} .match-row{display:flex;align-items:center;justify-content:space-between;gap:12px} .team-box{display:flex;flex-direction:column;align-items:center;gap:10px;flex:1;min-width:0} .team-logo-wrap{width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:var(--logo-bg);border-radius:50%;padding:8px;border:1px solid var(--border);} .team-logo-img{width:100%;height:100%;object-fit:contain;} .team-label{font-size:14px;font-weight:700;text-align:center;line-height:1.3;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)} .match-center{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:120px} .status-badge{display:flex;align-items:center;gap:6px;padding:6px 14px;border-radius:8px;font-size:11px;font-weight:800;white-space:nowrap;letter-spacing:.5px;border:1px solid var(--border);} .badge-live{background:var(--badge-live-bg);color:var(--badge-live-color);border-color:var(--pill-border);} .badge-soon{background:var(--badge-soon-bg);color:var(--badge-soon-color);} .badge-upcoming{background:var(--badge-up-bg);color:var(--badge-up-color);} .badge-finished{background:var(--badge-fin-bg);color:var(--badge-fin-color);} .status-icon-svg{display:flex;align-items:center;justify-content:center;width:14px;height:14px;color:inherit;} .time-row{font-size:13px;color:var(--text2);font-weight:600;font-family:monospace} .score-display{display:flex;align-items:center;gap:10px;font-size:32px;font-weight:900;color:var(--text)} .score-value{min-width:30px;text-align:center} .score-sep{color:var(--text2);font-weight:300} .score-vs{font-size:13px;font-weight:700;color:var(--text2);background:var(--vs-bg);padding:6px 16px;border-radius:8px;border:1px solid var(--border)} .tournament-label{text-align:center;margin-top:12px;font-size:11px;color:var(--text2);font-weight:600;opacity:.8;letter-spacing:.5px} .action-row{text-align:center;margin-top:16px} .watch-btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:12px 32px;border-radius:8px;font-size:13px;font-weight:800;font-family:inherit;letter-spacing:.5px;box-shadow:0 4px 10px rgba(59,130,246,0.3);} .footer{text-align:center;padding:20px;color:var(--text2);font-size:12px;border-top:1px solid var(--border);margin-top:40px;letter-spacing:.5px} .modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.9);z-index:999;display:flex;align-items:center;justify-content:center;padding:20px} .modal-overlay.hidden{display:none} .modal-box{background:var(--card);border-radius:16px;padding:32px;max-width:440px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.8);border:1px solid var(--border);} .modal-icon{margin-bottom:12px;display:flex;justify-content:center;} .modal-title{font-size:20px;font-weight:800;margin-bottom:8px;color:var(--text);} .modal-text{font-size:14px;color:var(--text2);line-height:1.6;margin-bottom:20px} .modal-countdown{font-size:28px;font-weight:900;color:var(--accent);margin:8px 0} .modal-btn{background:var(--accent);color:#fff;border:none;padding:12px 36px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;} .modal-btn:disabled{opacity:.4;cursor:not-allowed} .modal-checkbox{margin-top:16px;font-size:12px;color:var(--text2);display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer} .modal-checkbox input{width:16px;height:16px;cursor:pointer;accent-color:var(--accent)} @media(max-width:900px){.cards-grid{grid-template-columns:1fr}.header-inner{flex-direction:column;align-items:flex-start}} @media(max-width:500px){.main-content{padding:20px 14px}.card-body{padding:16px}.team-logo-wrap{width:54px;height:54px}.score-display{font-size:28px}.team-label{font-size:13px}.watch-btn{padding:10px 24px;font-size:12px}.cards-grid{gap:12px}.stat-card{padding:16px;gap:12px}.stat-value{font-size:24px}.modal-box{padding:24px 18px}}'''

    def _common_js(self):
        return '''document.addEventListener('DOMContentLoaded', function() { var s = localStorage.getItem('ft-theme'); var darkIcon = document.querySelector('.theme-icon-dark'); var lightIcon = document.querySelector('.theme-icon-light'); if (s === 'light') { document.body.classList.add('light-mode'); } else { document.body.classList.remove('light-mode'); } if (darkIcon && lightIcon) { if (s === 'light') { darkIcon.style.display = 'none'; lightIcon.style.display = 'flex'; } else { darkIcon.style.display = 'flex'; lightIcon.style.display = 'none'; } } }); function toggleTheme() { var b = document.body; var d = document.querySelector('.theme-icon-dark'); var l = document.querySelector('.theme-icon-light'); if (!d || !l) return; if (b.classList.contains('light-mode')) { b.classList.remove('light-mode'); localStorage.setItem('ft-theme', 'dark'); d.style.display = 'flex'; l.style.display = 'none'; } else { b.classList.add('light-mode'); localStorage.setItem('ft-theme', 'light'); d.style.display = 'none'; l.style.display = 'flex'; } } var streamUrl = null; var countdownTimer = null; function showNotice(event, link) { if (localStorage.getItem('ft-hide-notice') === 'true') return true; event.preventDefault(); streamUrl = link.href; var m = document.getElementById('streamModal'); var c = document.getElementById('modalCountdown'); var b = document.getElementById('modalOkBtn'); if (!m || !c || !b) return false; m.classList.remove('hidden'); b.disabled = true; var s = 3; c.textContent = s; clearInterval(countdownTimer); countdownTimer = setInterval(function() { s--; c.textContent = s; if (s <= 0) { clearInterval(countdownTimer); b.disabled = false; c.textContent = ''; } }, 1000); return false; } document.getElementById('modalOkBtn').addEventListener('click', function() { document.getElementById('streamModal').classList.add('hidden'); clearInterval(countdownTimer); if (streamUrl) window.location.href = streamUrl; }); function dontShowAgain(checked) { if (checked) localStorage.setItem('ft-hide-notice', 'true'); else localStorage.removeItem('ft-hide-notice'); } window.addEventListener('pageshow', function(e) { if (e.persisted || (performance.getEntriesByType("navigation")[0]?.type === 'back_forward')) { location.reload(); } });'''

    def _app_template(self, cards, l, s, u, f):
        # NEW SVGs to replace Emojis
        svg_mobile = '<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 4px 6px rgba(59,130,246,0.3));"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>'
        svg_tv = '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/></svg>'
        svg_moon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
        svg_sun = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>'
        
        return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{APP_NAME} | جدول المباريات</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet"><style>{self._common_css()}</style></head><body><div id="appBlock" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:var(--bg);z-index:9999;align-items:center;justify-content:center;font-family:'Tajawal',sans-serif;text-align:center;padding:20px;"><div><div style="margin-bottom:16px;">{svg_mobile}</div><div style="font-size:22px;font-weight:900;color:var(--text);margin-bottom:8px;">التطبيق مطلوب</div><div style="font-size:14px;color:var(--text2);line-height:1.6;">يرجى تحميل تطبيق {APP_NAME} للمشاهدة.</div></div></div><div class="modal-overlay hidden" id="streamModal"><div class="modal-box"><div class="modal-icon">{svg_tv}</div><div class="modal-title">تنبيه مهم</div><div class="modal-text">إذا لم يشتغل البث، يرجى الرجوع وتحديث الصفحة ثم المحاولة مرة أخرى.</div><div class="modal-countdown" id="modalCountdown">3</div><button class="modal-btn" id="modalOkBtn" disabled>حسناً</button><label class="modal-checkbox"><input type="checkbox" id="modalDontShow" onchange="dontShowAgain(this.checked)">لا تظهر هذه الرسالة مرة أخرى</label></div></div><header class="header"><div class="header-inner"><div class="brand"><h1>{APP_NAME}</h1><span>جدول المباريات | بث مباشر</span></div><div class="header-actions"><div class="live-pill"><div class="live-dot"></div><span>{l} LIVE</span></div><button class="theme-btn" onclick="toggleTheme()" title="تغيير المظهر"><span class="theme-icon-dark" style="display:flex;align-items:center;justify-content:center;">{svg_moon}</span><span class="theme-icon-light" style="display:none;align-items:center;justify-content:center;">{svg_sun}</span></button></div></div></header><main class="main-content"><div class="stats-row"><div class="stat-card"><div class="stat-icon stat-icon-live">{self.icon_live_svg}</div><div><div class="stat-value">{l}</div><div class="stat-label">جارية الآن</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-soon">{self.icon_soon_svg}</div><div><div class="stat-value">{s}</div><div class="stat-label">بعد قليل</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-up">{self.icon_upcoming_svg}</div><div><div class="stat-value">{u}</div><div class="stat-label">لم تبدأ بعد</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-fin">{self.icon_finished_svg}</div><div><div class="stat-value">{f}</div><div class="stat-label">انتهت</div></div></div></div>{cards}</main><footer class="footer"><p>© {datetime.now().year} {APP_NAME}</p></footer><script>(function(){{var ua=navigator.userAgent.toLowerCase();var isApp=ua.includes('wv')||ua.includes('webview')||document.referrer.includes('appcreator')||window.location.href.includes('from=app');var urlParams = new URLSearchParams(window.location.search);if(!isApp && urlParams.get('from') !== 'app'){{var b=document.getElementById('appBlock');b.style.display='flex';document.querySelector('.header').style.display='none';document.querySelector('.main-content').style.display='none';document.querySelector('.footer').style.display='none'}}}})();{self._common_js()}</script></body></html>'''

class Deployer:
    def deploy(self):
        if not GITHUB_TOKEN or GITHUB_TOKEN == "YOUR_GITHUB_TOKEN":
            logger.warning("GITHUB_TOKEN is missing. Skipping deployment.")
            return

        logger.info("Deploying to GitHub Pages...")
        try:
            remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GIT_ASKPASS"] = "echo"
            cwd = str(OUTPUT_DIR.absolute())

            if not (OUTPUT_DIR / ".git").exists():
                subprocess.run(["git", "init"], cwd=cwd, check=False, capture_output=True)
                subprocess.run(["git", "checkout", "-b", "gh-pages"], cwd=cwd, check=False, capture_output=True)

            subprocess.run(["git", "config", "user.email", "jasdovica@gmail.com"], cwd=cwd, check=False)
            subprocess.run(["git", "config", "user.name", "jasdovica-glitch"], cwd=cwd, check=False)
            subprocess.run(["git", "add", "."], cwd=cwd, check=False)
            subprocess.run(["git", "commit", "-m", f"update {datetime.now():%H:%M:%S}"], cwd=cwd, capture_output=True)
            
            res = subprocess.run(["git", "push", "--force", remote_url, "HEAD:gh-pages"], 
                                 cwd=cwd, env=env, capture_output=True, text=True)

            if res.returncode == 0:
                logger.info("Deployed successfully!")
            else:
                logger.error(f"Deploy failed details:\n{res.stderr.strip()}")
        except Exception as e: 
            logger.error(f"Deploy error: {e}")

def main():
    logger.info(f"🚀 {APP_NAME} - Local Server Mode Started")
    scraper, builder, gh_deployer, count = DualScraper(), HTMLBuilder(), Deployer(), 0
    
    while True:
        count += 1
        logger.info(f"--- Cycle #{count} | {datetime.now():%H:%M:%S} ---")
        try:
            matches = scraper.run_scraping()
            if matches is not None:
                logger.info(f"Matches: {len(matches)} | Live: {sum(1 for m in matches if m['is_live'])}")
                
                (OUTPUT_DIR / "fixtures.html").write_text(builder.generate_fixtures(matches), encoding='utf-8')
                stream_dir = OUTPUT_DIR / "streams"
                stream_dir.mkdir(exist_ok=True)
                
                for m in matches:
                    if m['has_stream'] and m['stream_id']:
                        (stream_dir / f"{m['stream_id']}.html").write_text(builder.generate_stream_page(m), encoding='utf-8')
                
                gh_deployer.deploy()
                logger.info("✅ Update completed")
            else:
                logger.warning("Fetch failed (0 Matches)")
        except Exception as e:
            logger.error(f"Error: {e}")
            
        time.sleep(60)

if __name__ == "__main__":
    main()