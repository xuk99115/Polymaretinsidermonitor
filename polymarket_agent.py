import requests
import pandas as pd
from datetime import datetime, timezone
import os
import time
import json
import hashlib
import re

# --- 配置区 ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = "5463485569"
MIN_BET_USD = 3000

DATA_API_URL = "https://data-api.polymarket.com"
GAMMA_API_URL = "https://gamma-api.polymarket.com"

# CSV 文件路径（历史记录）
CSV_FILE = "insider_alerts_history.csv"
# 已推送交易的记录文件（用于去重）
SENT_TRADES_FILE = "sent_trades.json"

# Google Sheets 配置（可选）
# 设置环境变量 GOOGLE_SHEETS_WEBHOOK 来启用
# 使用 Google Apps Script Web App 作为简单的写入接口
GOOGLE_SHEETS_WEBHOOK = os.getenv("GOOGLE_SHEETS_WEBHOOK")

# --- 市场分类关键词 ---
CATEGORY_KEYWORDS = {
    "政治": [
        # 基础政治词汇
        "president", "election", "democrat", "republican", "senate", "congress",
        "governor", "mayor", "vote", "ballot", "political", "nomination", "primary",
        "cabinet", "impeach", "政治", "选举", "总统", "white house", "supreme court",
        "midterms", "primaries", "mayoral", "courts", "regime",
        # 美国政治人物
        "trump", "biden", "vance", "jd vance", "newsom", "gavin newsom", "desantis",
        "harris", "kamala", "obama", "clinton", "pelosi", "mcconnell", "aoc",
        "alexandria ocasio-cortez", "bernie", "warren", "marco rubio", "rubio",
        "elon musk", "musk",
        # 美联储相关
        "fed chair", "fed decision", "kevin warsh", "warsh", "rick rieder", "rieder",
        "powell", "yellen", "federal reserve",
        # 国际政治 - 国家/地区
        "venezuela", "ukraine", "russia", "ceasefire", "gaza", "israel", "iran",
        "greenland", "portugal", "vietnam", "lebanon", "middle east", "geopolitics",
        # 国际政治人物
        "antonio jose seguro", "seguro", "joao cotrim figueiredo", "figueiredo",
        "andre ventura", "ventura", "to lam", "phan van giang",
        # 党派和组织
        "communist party", "liberal", "conservative", "independent", "ind",
        # 热门话题
        "epstein", "trade war", "us strikes", "us election", "global elections",
        "nyc mayor", "minnesota unrest", "presidential nominee", "nominee 2028"
    ],
    "Crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain", "token",
        "defi", "nft", "solana", "sol", "dogecoin", "doge", "xrp", "ripple",
        "binance", "coinbase", "sec", "etf", "halving", "mining", "wallet",
        "altcoin", "stablecoin", "usdt", "usdc", "airdrop", "memecoin"
    ],
    "体育": [
        # 联赛和赛事
        "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball", 
        "baseball", "hockey", "tennis", "golf", "ufc", "mma", "boxing",
        "olympics", "world cup", "super bowl", "championship", "playoff",
        "premier league", "epl", "la liga", "champions league", "ucl",
        "fifa", "ligue 1", "esports", "lol", "league of legends", "lck", "lpl",
        "nba finals", "nfl playoffs", "nba champion",
        # 球星
        "mvp", "lebron", "curry", "mahomes", "brady", "messi", "ronaldo",
        "体育", "比赛", "冠军", "espn", "sports",
        # NFL 球队 (32队)
        "bills", "dolphins", "patriots", "jets",
        "ravens", "bengals", "browns", "steelers",
        "texans", "colts", "jaguars", "titans",
        "broncos", "chiefs", "raiders", "chargers",
        "cowboys", "giants", "eagles", "commanders",
        "bears", "lions", "packers", "vikings",
        "falcons", "panthers", "saints", "buccaneers",
        "cardinals", "rams", "49ers", "seahawks",
        # NBA 球队 (30队)
        "celtics", "nets", "knicks", "76ers", "raptors",
        "bulls", "cavaliers", "pistons", "pacers", "bucks",
        "hawks", "hornets", "heat", "magic", "wizards",
        "nuggets", "timberwolves", "thunder", "trail blazers", "jazz",
        "warriors", "clippers", "lakers", "suns", "kings",
        "mavericks", "rockets", "grizzlies", "pelicans", "spurs",
        "oklahoma city", "boston", "golden state", "los angeles",
        # 英超球队 (Premier League)
        "arsenal", "aston villa", "bournemouth", "brentford", "brighton",
        "chelsea", "crystal palace", "everton", "fulham", "ipswich",
        "leicester", "liverpool", "manchester city", "manchester united",
        "newcastle", "nottingham forest", "southampton", "tottenham",
        "west ham", "wolves", "wolverhampton",
        # 西甲球队 (La Liga)
        "real madrid", "barcelona", "atletico madrid", "athletic bilbao",
        "real sociedad", "villarreal", "real betis", "sevilla", "valencia",
        "deportivo alaves", "getafe", "osasuna", "celta vigo", "mallorca",
        # 欧冠/意甲/法甲/德甲热门球队
        "bayern munich", "borussia dortmund", "psg", "paris saint-germain",
        "juventus", "inter milan", "ac milan", "napoli", "roma",
        "bologna", "fiorentina", "ajax", "benfica", "porto",
        # 法甲球队 (Polymarket 提到的)
        "stade rennais", "le havre", "rennes",
        # NHL 球队
        "lightning", "stars", "bruins", "maple leafs", "canadiens",
        "rangers", "islanders", "flyers", "penguins", "capitals",
        "hurricanes", "panthers", "red wings", "blackhawks", "avalanche",
        "oilers", "flames", "canucks", "kraken", "golden knights",
        # 电竞战队 (Esports)
        "t1", "drx", "jd gaming", "gen.g", "cloud9", "fnatic", "g2"
    ],
    "传统金融": [
        "fed", "interest rate", "inflation", "gdp", "unemployment", "stock",
        "s&p", "nasdaq", "dow jones", "bond", "treasury", "recession",
        "earnings", "ipo", "merger", "acquisition", "bank", "federal reserve",
        "cpi", "ppi", "fomc", "powell", "yellen", "wall street", "nyse",
        "金融", "股票", "利率", "经济"
    ]
}


def parse_timestamp(time_str):
    """解析时间戳，支持多种格式"""
    if not time_str:
        return None
    
    try:
        if isinstance(time_str, (int, float)):
            if time_str > 1e10:
                return datetime.fromtimestamp(time_str / 1000, tz=timezone.utc)
            else:
                return datetime.fromtimestamp(time_str, tz=timezone.utc)
        elif isinstance(time_str, str):
            if time_str.endswith('Z'):
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(time_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception as e:
        print(f"⚠️ DEBUG - 时间解析失败: {e}, 原始值: {time_str}")
    return None


def categorize_market(market_title):
    """根据市场标题分类"""
    if not market_title:
        return "其他"
    
    title_lower = market_title.lower()
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in title_lower:
                return category
    
    return "其他"


def generate_trade_id(trade):
    """生成交易唯一ID用于去重"""
    # 使用交易的关键字段生成唯一哈希
    unique_str = f"{trade.get('proxyWallet', '')}-{trade.get('transactionHash', '')}-{trade.get('timestamp', '')}-{trade.get('usdcSize', '')}"
    return hashlib.md5(unique_str.encode()).hexdigest()


def load_sent_trades():
    """加载已发送的交易记录"""
    try:
        if os.path.exists(SENT_TRADES_FILE):
            with open(SENT_TRADES_FILE, 'r') as f:
                data = json.load(f)
                # 只保留最近7天的记录，避免文件过大
                cutoff = datetime.now(timezone.utc).timestamp() - (7 * 24 * 60 * 60)
                return {k: v for k, v in data.items() if v > cutoff}
    except Exception as e:
        print(f"⚠️ 加载已发送交易记录失败: {e}")
    return {}


def save_sent_trades(sent_trades):
    """保存已发送的交易记录"""
    try:
        with open(SENT_TRADES_FILE, 'w') as f:
            json.dump(sent_trades, f)
    except Exception as e:
        print(f"⚠️ 保存已发送交易记录失败: {e}")


def is_trade_sent(trade_id, sent_trades):
    """检查交易是否已发送"""
    return trade_id in sent_trades


def mark_trade_sent(trade_id, sent_trades):
    """标记交易为已发送"""
    sent_trades[trade_id] = datetime.now(timezone.utc).timestamp()


def save_to_csv(alert_data):
    """保存警报到CSV文件"""
    try:
        # 准备数据
        new_row = pd.DataFrame([alert_data])
        
        # 如果文件存在，追加；否则创建新文件
        if os.path.exists(CSV_FILE):
            existing_df = pd.read_csv(CSV_FILE)
            df = pd.concat([existing_df, new_row], ignore_index=True)
        else:
            df = new_row
        
        # 保存到CSV
        df.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        print(f"✅ 已保存到CSV: {CSV_FILE}")
        return True
    except Exception as e:
        print(f"❌ 保存CSV失败: {e}")
        return False


def save_to_google_sheets(alert_data):
    """保存警报到 Google Sheets（通过 Apps Script Web App）"""
    if not GOOGLE_SHEETS_WEBHOOK:
        print("⚠️ Google Sheets: 未配置 GOOGLE_SHEETS_WEBHOOK")
        return False
    
    try:
        print(f"📤 正在发送数据到 Google Sheets...")
        print(f"   URL: {GOOGLE_SHEETS_WEBHOOK[:50]}...")
        
        response = requests.post(
            GOOGLE_SHEETS_WEBHOOK,
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:200]}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("status") == "success":
                    print(f"✅ 已保存到 Google Sheets")
                    return True
                else:
                    print(f"⚠️ Google Sheets 返回错误: {result.get('message', 'unknown')}")
                    return False
            except:
                # 即使无法解析 JSON，状态码 200 也算成功
                print(f"✅ 已保存到 Google Sheets (状态码 200)")
                return True
        else:
            print(f"⚠️ Google Sheets 保存失败: HTTP {response.status_code}")
            print(f"   响应内容: {response.text[:500]}")
            return False
    except requests.exceptions.Timeout:
        print(f"⚠️ Google Sheets 请求超时")
        return False
    except Exception as e:
        print(f"⚠️ Google Sheets 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_user_profile(address):
    """获取显示名称和创建时间（通过第一笔交易时间估算）"""
    try:
        res = requests.get(f"{DATA_API_URL}/activity?user={address}&limit=1000", timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0:
                earliest_trade = None
                earliest_time = None
                
                for trade in data:
                    time_str = (trade.get('timestamp') or 
                               trade.get('time') or 
                               trade.get('createdAt') or
                               trade.get('created_at') or
                               trade.get('date') or
                               trade.get('blockTimestamp'))
                    
                    if time_str:
                        dt = parse_timestamp(time_str)
                        if dt:
                            if earliest_time is None or dt < earliest_time:
                                earliest_time = dt
                                earliest_trade = trade
                
                if earliest_trade and earliest_time:
                    print(f"✅ DEBUG - 找到最早交易时间: {earliest_time}")
                    display_name = (earliest_trade.get('user') or 
                                   earliest_trade.get('username') or 
                                   earliest_trade.get('displayName') or 
                                   address)
                    return {"name": display_name, "created_at": earliest_time}
        
        print(f"⚠️ DEBUG - activity API 无数据，尝试从 trades API 获取...")
        res2 = requests.get(f"{DATA_API_URL}/trades?user={address}&limit=1000", timeout=10)
        if res2.status_code == 200:
            trades = res2.json()
            if trades and len(trades) > 0:
                earliest_trade = None
                earliest_time = None
                
                for trade in trades:
                    time_str = (trade.get('timestamp') or 
                               trade.get('time') or 
                               trade.get('createdAt') or
                               trade.get('created_at') or
                               trade.get('blockTimestamp'))
                    
                    if time_str:
                        dt = parse_timestamp(time_str)
                        if dt:
                            if earliest_time is None or dt < earliest_time:
                                earliest_time = dt
                                earliest_trade = trade
                
                if earliest_time:
                    print(f"✅ DEBUG - 从第一笔交易获取创建时间: {earliest_time}")
                    return {"name": address, "created_at": earliest_time}
        
    except Exception as e:
        print(f"⚠️ 获取用户 Profile 失败 ({address}): {e}")
        import traceback
        traceback.print_exc()
    
    print(f"⚠️ DEBUG - 无法获取账号创建时间，使用默认值")
    return {"name": address, "created_at": None}


def get_user_trade_count(address):
    """获取用户历史交易总数"""
    try:
        # 尝试从 profile API 获取交易次数
        profile_url = f"https://polymarket.com/api/profile/{address}"
        res = requests.get(profile_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # 尝试从 profile 数据中获取交易数
            if isinstance(data, dict):
                # 可能的字段名
                trade_count = (data.get('tradesCount') or 
                              data.get('trades_count') or 
                              data.get('totalTrades') or
                              data.get('numTrades') or
                              data.get('positionsCount') or
                              data.get('positions_count'))
                if trade_count is not None:
                    print(f"✅ DEBUG - 从 profile API 获取交易次数: {trade_count}")
                    return int(trade_count)
        
        # 备用方案：查询多页交易数据来估算
        total_count = 0
        cursor = None
        max_pages = 10  # 最多查询10页，避免超时
        
        for page in range(max_pages):
            url = f"{DATA_API_URL}/activity?user={address}&limit=500"
            if cursor:
                url += f"&cursor={cursor}"
            
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                break
                
            data = res.json()
            if not data or len(data) == 0:
                break
            
            total_count += len(data)
            
            # 如果返回的数据少于 limit，说明已经到最后一页
            if len(data) < 500:
                break
            
            # 获取下一页的 cursor（如果 API 支持）
            # 通常是最后一条记录的某个字段
            if isinstance(data, list) and len(data) > 0:
                last_item = data[-1]
                cursor = last_item.get('id') or last_item.get('cursor')
                if not cursor:
                    # 如果没有 cursor，使用偏移量
                    break
        
        if total_count > 0:
            print(f"✅ DEBUG - 从 activity API 统计交易次数: {total_count}+")
            return total_count
        
        # 最后备用：从 trades API 获取
        res = requests.get(f"{DATA_API_URL}/trades?user={address}&limit=500", timeout=10)
        if res.status_code == 200:
            trades = res.json()
            if trades:
                print(f"✅ DEBUG - 从 trades API 统计交易次数: {len(trades)}+")
                return len(trades)
                
    except Exception as e:
        print(f"⚠️ DEBUG - 获取交易次数失败: {e}")
        return 99  # 报错则返回较大值，避免误报
    return 0


def send_instant_alert(trade_info, profile, bet_count, category):
    """发送即时报警"""
    if not TELEGRAM_TOKEN:
        print("❌ 错误: 未设置 TELEGRAM_TOKEN 环境变量")
        return False

    age_str = "未知"
    if profile['created_at']:
        days = (datetime.now(timezone.utc) - profile['created_at']).days
        age_str = f"{days} 天"

    # 根据类别选择emoji
    category_emoji = {
        "政治": "🏛️",
        "Crypto": "₿",
        "体育": "⚽",
        "传统金融": "📈",
        "其他": "❓"
    }
    
    emoji = category_emoji.get(category, "❓")

    # 格式化概率显示
    price_str = f"{trade_info.get('price_percent')}%" if trade_info.get('price_percent') is not None else "未知"
    
    msg = (
        f"🚨 *疑似内幕交易警报* 🚨\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 投注金额: `${trade_info['bet_size']}` USDC\n"
        f"👤 用户: `{profile['name']}`\n"
        f"📅 账号年龄: `{age_str}`\n"
        f"📊 历史笔数: `{bet_count}` 次\n"
        f"🎯 预测结果: *{trade_info['outcome']}*\n"
        f"↕️ 方向: *{trade_info.get('side', '未知')}*\n"
        f"📈 买入概率: `{price_str}`\n"
        f"🏟️ 市场: {trade_info['market']}\n"
        f"🎲 市场类型: *{trade_info.get('market_type', '未知')}*\n"
        f"{emoji} 类别: *{category}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔍 *特征*: 疑似新账号/低频账号大额交易"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    if r.status_code != 200:
        print(f"❌ Telegram 发送失败: {r.text}")
        return False
    else:
        print(f"✅ 成功推送交易: {profile['name']}")
        return True


def send_hourly_summary(category_counts, total_count):
    """发送每小时汇总报告"""
    if not TELEGRAM_TOKEN or total_count == 0:
        return
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:00 UTC")
    
    summary_lines = []
    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            emoji = {"政治": "🏛️", "Crypto": "₿", "体育": "⚽", "传统金融": "📈", "其他": "❓"}.get(category, "❓")
            summary_lines.append(f"{emoji} {category}: {count} 笔")
    
    msg = (
        f"📊 *每小时内幕交易汇总* 📊\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕐 时间: {now}\n"
        f"📈 总计: *{total_count}* 笔可疑交易\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*分类统计:*\n" + "\n".join(summary_lines)
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    if r.status_code != 200:
        print(f"❌ 汇总消息发送失败: {r.text}")
    else:
        print(f"✅ 成功发送每小时汇总")


def run_task():
    print(f"开始扫描 (阈值: ${MIN_BET_USD})...")
    params = {"limit": 100, "filterType": "CASH", "filterAmount": MIN_BET_USD, "takerOnly": "true"}
    
    # 加载已发送的交易记录（用于去重）
    sent_trades = load_sent_trades()
    
    # 用于统计分类
    category_counts = {"政治": 0, "Crypto": 0, "体育": 0, "传统金融": 0, "其他": 0}
    alerts_this_run = []
    
    try:
        response = requests.get(f"{DATA_API_URL}/trades", params=params, timeout=15)
        trades = response.json()
        
        if not trades:
            print("当前无符合条件的交易。")
            return

        for t in trades:
            # 生成交易ID并检查是否已发送
            trade_id = generate_trade_id(t)
            if is_trade_sent(trade_id, sent_trades):
                print(f"⏭️ 跳过已推送的交易: {trade_id[:8]}...")
                continue
            
            raw_amt = t.get('usdcSize') or t.get('amount') or t.get('cash')
            if raw_amt is None:
                try:
                    raw_amt = float(t.get('price', 0)) * float(t.get('size', 0))
                except:
                    raw_amt = 0
                    
            amt = float(raw_amt)
            
            if amt < MIN_BET_USD:
                continue
                
            address = t.get('proxyWallet')
            if not address:
                continue
            
            print(f"检查交易: 用户 {address[:10]}... 金额: ${amt}")
            
            profile = get_user_profile(address)
            bet_count = get_user_trade_count(address)
            
            # 判定逻辑：年龄 <= 10天 OR 交易笔数 < 10
            is_suspicious = False
            days_old = None
            if profile['created_at']:
                days_old = (datetime.now(timezone.utc) - profile['created_at']).days
                if days_old <= 10:
                    is_suspicious = True
            
            if bet_count < 10:
                is_suspicious = True
            
            if is_suspicious:
                market_title = t.get('title') or "未知市场"
                category = categorize_market(market_title)
                
                # 提取交易方向 (BUY/SELL)
                side = t.get('side', '').upper()
                if side == 'BUY':
                    side_display = "买入 (Buy)"
                elif side == 'SELL':
                    side_display = "卖出 (Sell)"
                else:
                    side_display = side or "未知"
                
                # 提取买入概率 (price 是 0-1 之间的值)
                price = t.get('price')
                if price is not None:
                    try:
                        price_percent = round(float(price) * 100, 1)
                    except:
                        price_percent = None
                else:
                    price_percent = None
                
                # 判断市场类型：Yes/No 是二元市场，其他是多选市场
                outcome = t.get('outcome', '')
                if outcome and outcome.lower() in ['yes', 'no']:
                    market_type = "Yes/No 二元"
                else:
                    market_type = "多可能性"
                
                trade_data = {
                    "bet_size": round(amt, 2),
                    "outcome": outcome,
                    "market": market_title,
                    "side": side_display,
                    "price_percent": price_percent,
                    "market_type": market_type
                }
                
                # 只推送政治类别到 Telegram
                should_send_telegram = (category == "政治")
                telegram_sent = False
                
                if should_send_telegram:
                    telegram_sent = send_instant_alert(trade_data, profile, bet_count, category)
                else:
                    print(f"⏭️ 跳过非政治类别的 TG 推送: {category}")
                    telegram_sent = True  # 标记为"处理完成"以继续保存到 CSV/Sheets
                
                if telegram_sent:
                    # 标记为已发送
                    mark_trade_sent(trade_id, sent_trades)
                    
                    # 更新分类统计
                    category_counts[category] = category_counts.get(category, 0) + 1
                    
                    # 保存到CSV
                    csv_data = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "user_address": address,
                        "user_name": profile['name'],
                        "bet_size_usdc": round(amt, 2),
                        "outcome": outcome,
                        "side": side_display,
                        "price_percent": price_percent if price_percent is not None else "未知",
                        "market_type": market_type,
                        "market": market_title,
                        "category": category,
                        "account_age_days": days_old if days_old is not None else "未知",
                        "trade_count": bet_count,
                        "transaction_hash": t.get('transactionHash', ''),
                        "trade_id": trade_id
                    }
                    save_to_csv(csv_data)
                    save_to_google_sheets(csv_data)
                    alerts_this_run.append(csv_data)
                
                time.sleep(1)
        
        # 保存已发送交易记录
        save_sent_trades(sent_trades)
        
        # 发送每小时汇总
        total_alerts = sum(category_counts.values())
        if total_alerts > 0:
            send_hourly_summary(category_counts, total_alerts)
        
        print(f"\n📊 本次扫描完成: {total_alerts} 笔可疑交易")

    except Exception as e:
        print(f"运行时错误: {e}")
        import traceback
        traceback.print_exc()


def test_user_profile(address=None):
    """测试函数：验证用户 Profile API 响应"""
    print("=" * 60)
    print("🧪 开始测试用户 Profile API")
    print("=" * 60)
    
    if not address:
        print("\n📥 从实际交易中获取测试地址...")
        try:
            params = {"limit": 1, "filterType": "CASH", "filterAmount": MIN_BET_USD, "takerOnly": "true"}
            response = requests.get(f"{DATA_API_URL}/trades", params=params, timeout=15)
            trades = response.json()
            if trades and len(trades) > 0:
                address = trades[0].get('proxyWallet')
                print(f"✅ 找到测试地址: {address}")
            else:
                address = "0x075ed056bac4e1b9f123a98983268ab891a81521"
                print(f"⚠️ 未找到交易，使用示例地址: {address}")
        except Exception as e:
            print(f"❌ 获取交易失败: {e}")
            address = "0x075ed056bac4e1b9f123a98983268ab891a81521"
            print(f"使用示例地址: {address}")
    
    print(f"\n🔍 测试地址: {address}")
    profile = get_user_profile(address)
    print(f"\n📊 解析结果:")
    print(f"  名称: {profile['name']}")
    print(f"  创建时间: {profile['created_at']}")
    if profile['created_at']:
        days = (datetime.now(timezone.utc) - profile['created_at']).days
        print(f"  账号年龄: {days} 天")
    else:
        print(f"  账号年龄: 未知")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_address = sys.argv[2] if len(sys.argv) > 2 else None
        test_user_profile(test_address)
    else:
        run_task()
