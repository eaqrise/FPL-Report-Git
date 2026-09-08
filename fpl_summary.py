"""
FPL Summary Script

User Requirements Context:
- Summarize league standings (ORCA & CCC) only when the Gameweek is officially 100% complete.
- Display weekly points showing Gross Points, Net Points, and Transfer Hit deductions explicitly.
- Display overall points standings.
- Keep track of the last reported GW to prevent duplicate notifications.
- Send the final summary to LINE Notify using the LINE_TOKEN environment variable.
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

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def send_telegram_notify(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("No Telegram credentials found in environment. Skipping notification.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Text format adjusted for Telegram readability
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

def generate_league_summary(league_id, league_name):
    standings_url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    standings_data = fetch_json(standings_url)
    
    results = standings_data['standings']['results']
    teams = []
    
    for team in results:
        entry_id = team['entry']
        history_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
        history_data = fetch_json(history_url)
        
        if history_data['current']:
            latest_gw_data = history_data['current'][-1]
            gw = latest_gw_data['event']
            net_points = latest_gw_data['points']
            transfer_cost = latest_gw_data['event_transfers_cost']
            gross_points = net_points + transfer_cost
        else:
            gw = "N/A"
            net_points = 0
            transfer_cost = 0
            gross_points = 0
            
        teams.append({
            'name': team['entry_name'],
            'manager': team['player_name'],
            'gw': gw,
            'net_points': net_points,
            'gross_points': gross_points,
            'transfer_cost': transfer_cost,
            'total_points': team['total'],
            'rank': team['rank']
        })
    
    teams_by_net = sorted(teams, key=lambda x: x['net_points'], reverse=True)
    
    if not teams:
        return "No data available."
        
    gw = teams[0]['gw']
    
    # Text format adjusted slightly for LINE readability (less markdown, more plain text)
    summary = f"\n🏆 สรุปผลลีก {league_name} (GW {gw})\n\n"
    summary += "--- อันดับรายสัปดาห์ (GW Points) ---\n"
    for i, t in enumerate(teams_by_net, 1):
        summary += f"{i}. {t['name']} \n   -> {t['net_points']} แต้ม (ดิบ {t['gross_points']} | หัก -{t['transfer_cost']})\n"
    
    summary += "\n--- อันดับคะแนนรวม (Overall) ---\n"
    for t in teams:
        summary += f"{t['rank']}. {t['name']} = {t['total_points']} แต้ม\n"
        
    return summary

def main():
    try:
        gw_id, is_finished = check_gw_status()
    except Exception as e:
        print(f"Error checking GW status: {e}")
        return

    # FOR TESTING PURPOSES locally: uncomment the next line to force run even if GW is not finished
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
        
    # Send introductory message (optional, but good for context)
    header_msg = f"📊 สรุปผล FPL ประจำสัปดาห์ (สิ้นสุด GW {gw_id} เป็นทางการแล้ว!)"
    print(header_msg)
    send_telegram_notify(header_msg)
    
    for league in LEAGUES:
        try:
            summary = generate_league_summary(league['id'], league['name'])
            print(summary)
            # Send each league as a separate Telegram message
            send_telegram_notify(summary)
        except Exception as e:
            print(f"Error fetching data for {league['name']}: {e}\n")
            
    # Update state file
    with open(STATE_FILE, 'w') as f:
        f.write(str(gw_id))
        
    print("STATUS: REPORT_GENERATED")

if __name__ == '__main__':
    main()
