#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import hashlib
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

APP_NAME = "ACHMIN LIVE"
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

                # Fix Score Issue: Only extract score if match is actually live or finished
                if m['is_live'] or m['is_finished']:
                    gs = el.find_all('span', class_='RS-goals')
                    if len(gs) >= 2:
                        m['home_score'] = gs[0].text.strip()
                        m['away_score'] = gs[1].text.strip()
                        m['has_score'] = True

                # Fix Tournament Issue: Extract from Title attribute
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
    icon_live_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 9l1.5-1.5C6.5 6.5 9 5 12 5s5.5 1.5 6.5 2.5L20 9M7 12l1.5-1.5C9.5 9.5 10.7 9 12 9s2.5.5 3.5 1.5L17 12M12 15h.01"/></svg>'
    icon_soon_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
    icon_upcoming_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
    icon_finished_svg = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94.63 1.5 1.98 2.63 3.61 2.96V19H7v2h10v-2h-4v-3.1c1.63-.33 2.98-1.46 3.61-2.96C19.08 12.63 21 10.55 21 8V7c0-1.1-.9-2-2-2zM7 10.82C5.84 10.4 5 9.3 5 8V7h2v3.82zM19 8c0 1.3-.84 2.4-2 2.82V7h2v1z"/></svg>'

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
        return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{match['home']} {sc} {match['away']} | {APP_NAME}</title><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet"><style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Tajawal',sans-serif;background:#000;color:#fff;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px}}.sc{{width:100%;max-width:960px;background:#0c0c0c;border-radius:6px;overflow:hidden;box-shadow:0 4px 30px rgba(229,9,20,.15);border:1px solid rgba(229,9,20,.2)}}.sh2{{background:#141414;padding:22px 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;border-bottom:1px solid rgba(229,9,20,.15)}}.mi{{display:flex;align-items:center;gap:20px}}.tm{{display:flex;flex-direction:column;align-items:center;gap:8px}}.tlg{{width:56px;height:56px;border-radius:50%;object-fit:contain;background:rgba(255,255,255,.03);padding:5px}}.tmn{{font-size:15px;font-weight:700;text-align:center}}.scd{{font-size:34px;font-weight:900;font-family:monospace;min-width:110px;text-align:center}}.svs{{font-size:16px;font-weight:700;color:#999}}.live-badge{{background:#e50914;color:#fff;padding:8px 20px;border-radius:4px;font-size:13px;font-weight:800;animation:pulse 2s infinite;display:inline-block;margin-bottom:6px;letter-spacing:.5px}}@keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(229,9,20,.4)}}50%{{box-shadow:0 0 0 12px rgba(229,9,20,0)}}}}.bbtn{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.05);color:#e5e5e5;text-decoration:none;padding:10px 22px;border-radius:4px;font-size:13px;font-weight:700;transition:all .2s;border:1px solid rgba(255,255,255,.1)}}.bbtn:hover{{background:rgba(229,9,20,.15);border-color:#e50914;color:#fff}}.pw{{position:relative;width:100%;background:#000}}iframe{{display:block;width:100%;height:520px;border:none}}.sf{{padding:14px 24px;text-align:center;font-size:11px;color:#777;border-top:1px solid rgba(229,9,20,.1)}}@media(max-width:600px){{.sh2{{padding:14px 16px;gap:10px}}.tlg{{width:40px;height:40px}}.scd{{font-size:26px;min-width:80px}}iframe{{height:300px}}.tmn{{font-size:13px}}}}</style></head><body><div class="sc"><div class="sh2"><div class="mi"><div class="tm"><img src="{match['home_logo']}" class="tlg" onerror="this.style.display='none'"><span class="tmn">{match['home']}</span></div><div class="scd">{lb}<div class="svs">{sc}</div></div><div class="tm"><img src="{match['away_logo']}" class="tlg" onerror="this.style.display='none'"><span class="tmn">{match['away']}</span></div></div><a href="../fixtures.html" class="bbtn"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg> العودة للجدول</a></div><div class="pw"><iframe src="{url}" allowfullscreen allow="autoplay;fullscreen;picture-in-picture" sandbox="allow-scripts allow-same-origin allow-presentation" referrerpolicy="no-referrer"></iframe></div><div class="sf">{APP_NAME}</div></div></body></html>'''

    def _common_css(self):
        return ''':root{--bg:#0a0a0a;--card:#111;--text:#fff;--text2:#aaa;--border:rgba(255,255,255,0.08);--accent:#e50914;--red:#e50914;--green:#2ecc71;--gold:#e5a00d;--blue:#3498db;--radius:8px;--stat-bg:rgba(255,255,255,0.04);--pill-bg:rgba(229,9,20,0.12);--pill-border:rgba(229,9,20,0.25);--pill-color:#ff6b6b;--badge-live-bg:rgba(229,9,20,0.15);--badge-live-color:#ff6b6b;--badge-soon-bg:rgba(229,160,13,0.15);--badge-soon-color:#e5a00d;--badge-up-bg:rgba(46,204,113,0.15);--badge-up-color:#2ecc71;--badge-fin-bg:rgba(52,152,219,0.15);--badge-fin-color:#3498db;--logo-bg:rgba(255,255,255,0.03);--vs-bg:rgba(255,255,255,0.04)} body.light-mode {--bg:#f5f5f5;--card:#ffffff;--text:#111111;--text2:#555555;--border:rgba(0,0,0,0.08);--accent:#d10000;--red:#d10000;--green:#00a854;--gold:#b8860b;--blue:#1a6fe6;--stat-bg:rgba(0,0,0,0.03);--pill-bg:rgba(209,0,0,0.1);--pill-border:rgba(209,0,0,0.25);--pill-color:#d10000;--badge-live-bg:rgba(209,0,0,0.1);--badge-live-color:#d10000;--badge-soon-bg:rgba(184,134,11,0.1);--badge-soon-color:#b8860b;--badge-up-bg:rgba(0,168,84,0.1);--badge-up-color:#00a854;--badge-fin-bg:rgba(26,111,230,0.1);--badge-fin-color:#1a6fe6;--logo-bg:rgba(0,0,0,0.03);--vs-bg:rgba(0,0,0,0.03)} *{margin:0;padding:0;box-sizing:border-box} body{font-family:'Tajawal',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6;font-size:15px;transition:background 0.3s, color 0.3s;-webkit-font-smoothing:antialiased;} a{text-decoration:none;color:inherit} .header{background:var(--bg);border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:100;} .header-inner{max-width:1300px;margin:0 auto;padding:0 28px;display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap} .brand h1{font-size:26px;font-weight:900;letter-spacing:-1px;color:var(--accent);text-transform:uppercase;} .brand span{font-size:11px;color:var(--text2);font-weight:500;letter-spacing:1px} .header-actions{display:flex;align-items:center;gap:12px} .live-pill{display:flex;align-items:center;gap:8px;background:var(--pill-bg);border:1px solid var(--pill-border);padding:7px 16px;border-radius:20px;font-size:12px;font-weight:700;color:var(--pill-color);letter-spacing:.5px;} .live-dot{width:7px;height:7px;background:var(--red);border-radius:50%;animation:dotPulse 1.5s infinite;} @keyframes dotPulse{0%,100%{opacity:1;}50%{opacity:0.4;}} .theme-btn{width:40px;height:40px;border-radius:50%;border:1px solid var(--border);background:var(--stat-bg);cursor:pointer;font-size:18px;display:flex;align-items:center;justify-content:center;transition:all .2s;color:var(--text2);} .theme-btn:hover{border-color:var(--accent);color:var(--text);} .main-content{max-width:1300px;margin:0 auto;padding:32px 28px} .stats-row{display:flex;gap:12px;margin-bottom:32px;flex-wrap:wrap} .stat-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px 24px;display:flex;align-items:center;gap:14px;flex:1;min-width:130px;transition:transform 0.2s;} .stat-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:var(--stat-bg);} .stat-icon svg{width:22px;height:22px;} .stat-icon-live { color: var(--red); } .stat-icon-soon { color: var(--gold); } .stat-icon-up { color: var(--green); } .stat-icon-fin { color: var(--blue); } .stat-value{font-size:26px;font-weight:900;line-height:1} .stat-label{font-size:11px;color:var(--text2);font-weight:600;text-transform:uppercase;letter-spacing:1px} .tournament-section{margin-bottom:40px} .section-header{margin-bottom:20px;padding-bottom:10px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px} .section-header::before{content:'';width:3px;height:20px;background:var(--accent);border-radius:2px;} .section-header h2{font-size:19px;font-weight:800;color:var(--gold);} .section-badge{font-size:11px;color:var(--text2);background:var(--stat-bg);padding:3px 10px;border-radius:4px;font-weight:600;border:1px solid var(--border);} .cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px} .match-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border-color 0.2s;} .match-card:hover{border-color:rgba(229,9,20,0.3);} .card-live{border-left:3px solid var(--accent);} .card-soon{border-left:3px solid var(--gold);} .card-body{padding:18px} .match-row{display:flex;align-items:center;justify-content:space-between;gap:12px} .team-box{display:flex;flex-direction:column;align-items:center;gap:10px;flex:1;min-width:0} .team-logo-wrap{width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:var(--logo-bg);border-radius:50%;padding:6px;} .team-logo-img{width:100%;height:100%;object-fit:contain;} .team-label{font-size:14px;font-weight:700;text-align:center;line-height:1.3;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)} .match-center{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:120px} .status-badge{display:flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;font-size:10px;font-weight:700;white-space:nowrap;letter-spacing:.5px;background:rgba(255,255,255,0.05);} .badge-live{background:var(--badge-live-bg);color:var(--badge-live-color);} .badge-soon{background:var(--badge-soon-bg);color:var(--badge-soon-color);} .badge-upcoming{background:var(--badge-up-bg);color:var(--badge-up-color);} .badge-finished{background:var(--badge-fin-bg);color:var(--badge-fin-color);} .status-icon-svg{display:flex;align-items:center;justify-content:center;width:14px;height:14px;color:inherit;} .time-row{font-size:12px;color:var(--text2);font-weight:500;font-family:monospace} .score-display{display:flex;align-items:center;gap:10px;font-size:32px;font-weight:900;color:var(--text)} .score-value{min-width:30px;text-align:center} .score-sep{color:var(--text2);font-weight:300} .score-vs{font-size:13px;font-weight:700;color:var(--text2);background:var(--vs-bg);padding:5px 16px;border-radius:20px;border:1px solid var(--border)} .tournament-label{text-align:center;margin-top:8px;font-size:10px;color:var(--text2);font-weight:500;opacity:.7;text-transform:uppercase;letter-spacing:.5px} .action-row{text-align:center;margin-top:12px} .watch-btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;padding:10px 28px;border-radius:30px;font-size:13px;font-weight:700;transition:background 0.2s;font-family:inherit;letter-spacing:.3px;} .watch-btn:hover{background:#ff0a16;} .footer{text-align:center;padding:20px;color:var(--text2);font-size:11px;border-top:1px solid var(--border);margin-top:40px;letter-spacing:.5px} .modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.9);z-index:999;display:flex;align-items:center;justify-content:center;padding:20px} .modal-overlay.hidden{display:none} .modal-box{background:var(--card);border-radius:16px;padding:32px;max-width:440px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.8);border:1px solid var(--border);} .modal-icon{font-size:48px;margin-bottom:12px} .modal-title{font-size:20px;font-weight:800;margin-bottom:8px;} .modal-text{font-size:14px;color:var(--text2);line-height:1.6;margin-bottom:20px} .modal-countdown{font-size:28px;font-weight:900;color:var(--accent);margin:8px 0} .modal-btn{background:var(--accent);color:#fff;border:none;padding:12px 36px;border-radius:30px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit;transition:background 0.2s} .modal-btn:disabled{opacity:.4;cursor:not-allowed} .modal-btn:not(:disabled):hover{background:#ff0a16} .modal-checkbox{margin-top:16px;font-size:12px;color:var(--text2);display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer} .modal-checkbox input{width:16px;height:16px;cursor:pointer;accent-color:var(--accent)} @media(max-width:900px){.cards-grid{grid-template-columns:1fr}.header-inner{flex-direction:column;align-items:flex-start}} @media(max-width:500px){.main-content{padding:20px 14px}.card-body{padding:14px}.team-logo-wrap{width:50px;height:50px}.score-display{font-size:26px}.team-label{font-size:12px}.watch-btn{padding:9px 22px;font-size:12px}.cards-grid{gap:10px}.stat-card{padding:14px 16px;gap:10px}.stat-value{font-size:22px}.modal-box{padding:24px 18px}}'''

    def _common_js(self):
        return '''document.addEventListener('DOMContentLoaded', function() { var s = localStorage.getItem('ft-theme'); var darkIcon = document.querySelector('.theme-icon-dark'); var lightIcon = document.querySelector('.theme-icon-light'); if (s === 'light') { document.body.classList.add('light-mode'); } else { document.body.classList.remove('light-mode'); } if (darkIcon && lightIcon) { if (s === 'light') { darkIcon.style.display = 'none'; lightIcon.style.display = ''; } else { darkIcon.style.display = ''; lightIcon.style.display = 'none'; } } }); function toggleTheme() { var b = document.body; var d = document.querySelector('.theme-icon-dark'); var l = document.querySelector('.theme-icon-light'); if (!d || !l) return; if (b.classList.contains('light-mode')) { b.classList.remove('light-mode'); localStorage.setItem('ft-theme', 'dark'); d.style.display = ''; l.style.display = 'none'; } else { b.classList.add('light-mode'); localStorage.setItem('ft-theme', 'light'); d.style.display = 'none'; l.style.display = ''; } } var streamUrl = null; var countdownTimer = null; function showNotice(event, link) { if (localStorage.getItem('ft-hide-notice') === 'true') return true; event.preventDefault(); streamUrl = link.href; var m = document.getElementById('streamModal'); var c = document.getElementById('modalCountdown'); var b = document.getElementById('modalOkBtn'); if (!m || !c || !b) return false; m.classList.remove('hidden'); b.disabled = true; var s = 3; c.textContent = s; clearInterval(countdownTimer); countdownTimer = setInterval(function() { s--; c.textContent = s; if (s <= 0) { clearInterval(countdownTimer); b.disabled = false; c.textContent = ''; } }, 1000); return false; } document.getElementById('modalOkBtn').addEventListener('click', function() { document.getElementById('streamModal').classList.add('hidden'); clearInterval(countdownTimer); if (streamUrl) window.location.href = streamUrl; }); function dontShowAgain(checked) { if (checked) localStorage.setItem('ft-hide-notice', 'true'); else localStorage.removeItem('ft-hide-notice'); } window.addEventListener('pageshow', function(e) { if (e.persisted || (performance.getEntriesByType("navigation")[0]?.type === 'back_forward')) { location.reload(); } });'''

    def _app_template(self, cards, l, s, u, f):
        return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{APP_NAME} | جدول المباريات</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&display=swap" rel="stylesheet"><style>{self._common_css()}</style></head><body><div id="appBlock" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:var(--bg);z-index:9999;align-items:center;justify-content:center;font-family:'Tajawal',sans-serif;text-align:center;padding:20px;"><div><div style="font-size:64px;margin-bottom:16px;">📱</div><div style="font-size:22px;font-weight:900;color:var(--text);margin-bottom:8px;">التطبيق مطلوب</div><div style="font-size:14px;color:var(--text2);line-height:1.6;">يرجى تحميل تطبيق {APP_NAME} للمشاهدة.</div></div></div><div class="modal-overlay hidden" id="streamModal"><div class="modal-box"><div class="modal-icon">📺</div><div class="modal-title">تنبيه مهم</div><div class="modal-text">إذا لم يشتغل البث، يرجى الرجوع وتحديث الصفحة ثم المحاولة مرة أخرى.</div><div class="modal-countdown" id="modalCountdown">3</div><button class="modal-btn" id="modalOkBtn" disabled>حسناً</button><label class="modal-checkbox"><input type="checkbox" id="modalDontShow" onchange="dontShowAgain(this.checked)">لا تظهر هذه الرسالة مرة أخرى</label></div></div><header class="header"><div class="header-inner"><div class="brand"><h1>{APP_NAME}</h1><span>جدول المباريات | بث مباشر</span></div><div class="header-actions"><div class="live-pill"><div class="live-dot"></div><span>{l} LIVE</span></div><button class="theme-btn" onclick="toggleTheme()" title="تغيير المظهر"><span class="theme-icon-dark">🌙</span><span class="theme-icon-light" style="display:none">☀️</span></button></div></div></header><main class="main-content"><div class="stats-row"><div class="stat-card"><div class="stat-icon stat-icon-live">{self.icon_live_svg}</div><div><div class="stat-value">{l}</div><div class="stat-label">جارية الآن</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-soon">{self.icon_soon_svg}</div><div><div class="stat-value">{s}</div><div class="stat-label">بعد قليل</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-up">{self.icon_upcoming_svg}</div><div><div class="stat-value">{u}</div><div class="stat-label">لم تبدأ بعد</div></div></div><div class="stat-card"><div class="stat-icon stat-icon-fin">{self.icon_finished_svg}</div><div><div class="stat-value">{f}</div><div class="stat-label">انتهت</div></div></div></div>{cards}</main><footer class="footer"><p>© {datetime.now().year} {APP_NAME}</p></footer><script>(function(){{var ua=navigator.userAgent.toLowerCase();var isApp=ua.includes('wv')||ua.includes('webview')||document.referrer.includes('appcreator')||window.location.href.includes('from=app');if(!isApp){{var b=document.getElementById('appBlock');b.style.display='flex';document.querySelector('.header').style.display='none';document.querySelector('.main-content').style.display='none';document.querySelector('.footer').style.display='none'}}}})();{self._common_js()}</script></body></html>'''

def main():
    logger.info(f"Starting {APP_NAME} - Actions Mode")
    scraper, builder = DualScraper(), HTMLBuilder()
    
    matches = scraper.run_scraping()
    if matches is not None:
        logger.info(f"Matches parsed: {len(matches)}")
        (OUTPUT_DIR / "fixtures.html").write_text(builder.generate_fixtures(matches), encoding='utf-8')
        stream_dir = OUTPUT_DIR / "streams"
        stream_dir.mkdir(exist_ok=True)
        for m in matches:
            if m['has_stream'] and m['stream_id']:
                (stream_dir / f"{m['stream_id']}.html").write_text(builder.generate_stream_page(m), encoding='utf-8')
        logger.info("HTML files generated successfully.")
    else:
        logger.warning("No matches found or fetch failed.")

if __name__ == "__main__":
    main()