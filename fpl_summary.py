"""
FPL Summary Script
"""
import urllib.request
import urllib.parse
import json
import os

LEAGUES = [
    {"id": 294735, "name": "ORCA Fantasy"},
    {"id": 2178239, "name": "CCC Season III"}
]

STATE_FILE = "last_reported_gw.txt"

# คู่มือ Override กรณีเงื่อนไขกำกวม: 
# { GW_ID: {'debt': {entry_id: 100, entry_id2: 50, entry_id3: 50}} }
ORCA_MANUAL_OVERRIDES = {}

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def send_telegram_notify(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("No Telegram credentials found. Skipping notification.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req) as response:
            print("Telegram Notify sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram Notify: {e}")

def check_gw_status():
    bootstrap_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    data = fetch_json(bootstrap_url)
    
    current_event = None
    for event in data['events']:
        if event['is_current']:
            current_event = event
            break
            
    if not current_event:
        return None, False
        
    gw_id = current_event['id']
    is_finished = current_event['finished'] and current_event['data_checked']
    return gw_id, is_finished

def calc_orca_debt(g0, g1, g2):
    debt = {}
    n0, n1, n2 = len(g0), len(g1), len(g2)
    if n0 >= 3:
        pay = 70 if n0 == 3 else (50 if n0 == 4 else (40 if n0 == 5 else int(200/n0)))
        for t in g0: debt[t] = pay
        return debt
    if n0 == 2:
        if n1 == 1:
            for t in g0: debt[t] = 75
            for t in g1: debt[t] = 50
            return debt
        elif n1 == 2:
            for t in g0: debt[t] = 75
            for t in g1: debt[t] = 25
            return debt
        elif n1 > 2:
            for t in g0: debt[t] = 75
            for t in g1: debt[t] = int(50/n1)
            return debt
    if n0 == 1:
        debt[g0[0]] = 100
        if n1 == 1:
            debt[g1[0]] = 50
            if n2 == 1:
                debt[g2[0]] = 50
                return debt
            elif n2 > 1:
                for t in g2: debt[t] = int(50/n2)
                return debt
        elif n1 == 2:
            for t in g1: debt[t] = 50
            return debt
        elif n1 > 2:
            for t in g1: debt[t] = int(100/n1)
            return debt
    return None

def generate_league_summary(league_id, league_name):
    standings_url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    standings_data = fetch_json(standings_url)
    
    start_event = standings_data['league']['start_event']
    results = standings_data['standings']['results']
    teams = []
    
    for team in results:
        entry_id = team['entry']
        history_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
        history_data = fetch_json(history_url)
        
        gw_history = {}
        for gw_data in history_data['current']:
            gw_event = gw_data['event']
            if gw_event >= start_event:
                net_pts = gw_data['points'] - gw_data['event_transfers_cost']
                gross_pts = gw_data['points']
                gw_history[gw_event] = {'net': net_pts, 'gross': gross_pts}
        
        if history_data['current']:
            latest_gw_data = history_data['current'][-1]
            gw = latest_gw_data['event']
            net_points = latest_gw_data['points'] - latest_gw_data['event_transfers_cost']
            transfer_cost = latest_gw_data['event_transfers_cost']
            gross_points = latest_gw_data['points']
        else:
            gw = "N/A"
            net_points = 0
            transfer_cost = 0
            gross_points = 0
            
        teams.append({
            'entry_id': entry_id,
            'name': team['entry_name'],
            'manager': team['player_name'],
            'gw': gw,
            'net_points': net_points,
            'gross_points': gross_points,
            'transfer_cost': transfer_cost,
            'total_points': team['total'],
            'rank': team['rank'],
            'gw_history': gw_history,
            'losses': 0,
            'orca_wins': 0,
            'orca_losses': 0,
            'orca_debt': 0
        })

    orca_weekly_losers_str = ""
    orca_weekly_winners_str = ""
    
    if teams and teams[0]['gw'] != "N/A":
        max_gw = teams[0]['gw']
        
        if league_id == 2178239:
            for gw_idx in range(start_event, max_gw + 1):
                gw_scores = [t['gw_history'][gw_idx]['net'] for t in teams if gw_idx in t['gw_history']]
                if gw_scores:
                    min_score = min(gw_scores)
                    for t in teams:
                        if gw_idx in t['gw_history'] and t['gw_history'][gw_idx]['net'] == min_score:
                            t['losses'] += 1
                            
        if league_id == 294735:
            for gw_idx in range(start_event, max_gw + 1):
                teams_this_gw = [t for t in teams if gw_idx in t['gw_history']]
                if not teams_this_gw:
                    continue
                    
                max_score = max(t['gw_history'][gw_idx]['gross'] for t in teams_this_gw)
                winners_this_gw = []
                for t in teams_this_gw:
                    if t['gw_history'][gw_idx]['gross'] == max_score:
                        t['orca_wins'] += 1
                        winners_this_gw.append(t['name'])
                        
                if gw_idx == max_gw:
                    orca_weekly_winners_str = ", ".join(winners_this_gw)
                    
                if gw_idx in ORCA_MANUAL_OVERRIDES and 'debt' in ORCA_MANUAL_OVERRIDES[gw_idx]:
                    manual_debt = ORCA_MANUAL_OVERRIDES[gw_idx]['debt']
                    for t in teams:
                        if t['entry_id'] in manual_debt:
                            t['orca_debt'] += manual_debt[t['entry_id']]
                    if gw_idx == max_gw:
                        orca_weekly_losers_str = "MANUAL OVERRIDE"
                    continue
                
                scores = sorted(list(set(t['gw_history'][gw_idx]['gross'] for t in teams_this_gw)))
                g0 = [t['entry_id'] for t in teams_this_gw if t['gw_history'][gw_idx]['gross'] == scores[0]] if len(scores) > 0 else []
                g1 = [t['entry_id'] for t in teams_this_gw if t['gw_history'][gw_idx]['gross'] == scores[1]] if len(scores) > 1 else []
                g2 = [t['entry_id'] for t in teams_this_gw if t['gw_history'][gw_idx]['gross'] == scores[2]] if len(scores) > 2 else []
                
                gw_debt = calc_orca_debt(g0, g1, g2)
                
                if gw_debt is None:
                    if gw_idx == max_gw:
                        orca_weekly_losers_str = "เงื่อนไขกำกวม (รอกำหนด Manual)"
                else:
                    for t in teams:
                        if t['entry_id'] in gw_debt:
                            t['orca_debt'] += gw_debt[t['entry_id']]
                            t['orca_losses'] += 1
                    
                    if gw_idx == max_gw:
                        losers_list = []
                        for t in teams:
                            if t['entry_id'] in gw_debt:
                                losers_list.append(f"{t['name']}(เสีย {gw_debt[t['entry_id']]})")
                        orca_weekly_losers_str = ", ".join(losers_list)
    
    teams_by_net = sorted(teams, key=lambda x: x['net_points'], reverse=True)
    teams_by_gross = sorted(teams, key=lambda x: x['gross_points'], reverse=True)
    
    if not teams:
        return "No data available."
        
    gw = teams[0]['gw']
    
    summary = f"\n🏆 สรุปผลลีก {league_name} (GW {gw})\n\n"
    
    if league_id == 294735:
        summary += f"🌟 แชมป์สัปดาห์นี้: {orca_weekly_winners_str}\n"
        summary += f"💸 คนเสียตังค์สัปดาห์นี้: {orca_weekly_losers_str}\n\n"
    
    anyone_took_hit = any(t['transfer_cost'] > 0 for t in teams)
    
    if anyone_took_hit:
        summary += "--- อันดับรายสัปดาห์ (คะแนนดิบ ไม่หักลบ) ---\n"
        for i, t in enumerate(teams_by_gross, 1):
            summary += f"{i}. {t['name']} = {t['gross_points']} แต้ม\n"
            
        summary += "\n--- อันดับรายสัปดาห์ (คะแนนสุทธิ หักลบแล้ว) ---\n"
        for i, t in enumerate(teams_by_net, 1):
            if t['transfer_cost'] > 0:
                summary += f"{i}. {t['name']} = {t['net_points']} แต้ม (หัก -{t['transfer_cost']})\n"
            else:
                summary += f"{i}. {t['name']} = {t['net_points']} แต้ม\n"
    else:
        summary += "--- อันดับรายสัปดาห์ (GW Points) ---\n"
        for i, t in enumerate(teams_by_net, 1):
            summary += f"{i}. {t['name']} = {t['net_points']} แต้ม\n"
    
    summary += "\n--- อันดับคะแนนรวม (Overall) ---\n"
    for t in teams:
        summary += f"{t['rank']}. {t['name']} = {t['total_points']} แต้ม\n"
        
    if league_id == 2178239:
        summary += "\n--- 🚨 สถิติคนแพ้ (บ๊วยรายสัปดาห์) ---\n"
        teams_by_losses = sorted(teams, key=lambda x: x['losses'], reverse=True)
        for t in teams_by_losses:
            summary += f"💀 {t['name']} = แพ้ {t['losses']} ครั้ง\n"
            
    if league_id == 294735:
        summary += "\n--- 📊 สถิติสะสม (Win/Loss & ยอดเสียเงิน) ---\n"
        teams_by_stats = sorted(teams, key=lambda x: (x['orca_debt'], -x['orca_wins']), reverse=True)
        for t in teams_by_stats:
            if t['orca_wins'] > 0 or t['orca_losses'] > 0:
                icon = "💀" if t['orca_debt'] > 0 else "👑"
                debt_str = f" | ยอดสะสม -{t['orca_debt']} บาท" if t['orca_debt'] > 0 else ""
                summary += f"{icon} {t['name']} = Win {t['orca_wins']} Loss {t['orca_losses']}{debt_str}\n"
            
    return summary

def main():
    try:
        gw_id, is_finished = check_gw_status()
    except Exception as e:
        print(f"Error checking GW status: {e}")
        return

    # is_finished = True 

    if not is_finished:
        print(f"Gameweek {gw_id} is still ongoing. No final report generated.")
        return

    last_reported = -1
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            content = f.read().strip()
            if content.isdigit():
                last_reported = int(content)
                
    if gw_id == last_reported:
        print(f"Gameweek {gw_id} already reported. Waiting for next Gameweek.")
        return
        
    header_msg = f"📊 สรุปผล FPL ประจำสัปดาห์ (สิ้นสุด GW {gw_id} เป็นทางการแล้ว!)"
    print(header_msg)
    send_telegram_notify(header_msg)
    
    for league in LEAGUES:
        try:
            summary = generate_league_summary(league['id'], league['name'])
            print(summary)
            send_telegram_notify(summary)
        except Exception as e:
            print(f"Error fetching data for {league['name']}: {e}\n")
            
    with open(STATE_FILE, 'w') as f:
        f.write(str(gw_id))
        
    print("STATUS: REPORT_GENERATED")

if __name__ == '__main__':
    main()
