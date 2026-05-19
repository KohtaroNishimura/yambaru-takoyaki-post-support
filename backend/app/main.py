import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import cnlunar
import httpx
from dotenv import load_dotenv
from astral import moon
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()

JST = ZoneInfo("Asia/Tokyo")
NAGO_LAT = 26.5881
NAGO_LON = 127.9761

WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]

STYLE_HINT = "朝営業告知。元気で親しみやすく、あちこーこー感を強める。"


class EventItem(BaseModel):
    name: str
    category: str
    origin: str
    priority_score: int


class ProduceItem(BaseModel):
    name: str
    description: str
    pairing_with_takoyaki: str


class PostStrategy(BaseModel):
    primary_hashtag: str
    suggested_copy: str


class GenerateRequest(BaseModel):
    pass


class TodayInfo(BaseModel):
    date: str
    weekday: str
    weather: str
    temperature_c: float
    sunrise: str
    sunset: str
    old_calendar: str
    rokuyo: str
    sekki24: str
    okinawa_event: str
    tide: str
    location: str
    business_hours: str
    events: list[EventItem]
    seasonal_produce: list[ProduceItem]
    post_strategy: PostStrategy


class GenerateResponse(BaseModel):
    post: str
    info: TodayInfo


app = FastAPI(title="Yambaru Takoyaki Post Support API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def weather_code_to_ja(code: int) -> str:
    mapping = {
        0: "快晴",
        1: "晴れ",
        2: "晴れ時々くもり",
        3: "くもり",
        45: "霧",
        48: "霧",
        51: "小雨",
        53: "雨",
        55: "強い雨",
        61: "小雨",
        63: "雨",
        65: "強い雨",
        71: "雪",
        80: "にわか雨",
        81: "雨",
        82: "強いにわか雨",
        95: "雷雨",
    }
    return mapping.get(code, "天気情報あり")


SEKKI_JA_MAP = {
    "小寒": "小寒",
    "大寒": "大寒",
    "立春": "立春",
    "雨水": "雨水",
    "惊蛰": "啓蟄",
    "春分": "春分",
    "清明": "清明",
    "谷雨": "穀雨",
    "立夏": "立夏",
    "小满": "小満",
    "芒种": "芒種",
    "夏至": "夏至",
    "小暑": "小暑",
    "大暑": "大暑",
    "立秋": "立秋",
    "处暑": "処暑",
    "白露": "白露",
    "秋分": "秋分",
    "寒露": "寒露",
    "霜降": "霜降",
    "立冬": "立冬",
    "小雪": "小雪",
    "大雪": "大雪",
    "冬至": "冬至",
}


OKINAWA_EVENTS = [
    ((1, 1), "元日", "新年のはじまり。あたたかいものを囲んでゆるりと過ごす日。"),
    ((1, 2), "初売り", "買い物客が多い時期。食べ歩きのおやつ需要が高まりやすい日。"),
    ((1, 17), "ジュリ馬", "名護の伝統行事。地域のにぎわいが高まる節目の日。"),
    ((2, 3), "節分", "季節の変わり目。福を呼び込む願いを込める日。"),
    ((3, 3), "浜下り", "海辺で無病息災を願う沖縄の行事。春の海風を感じる頃。"),
    ((4, 3), "清明祭（シーミー）", "先祖を敬い家族で集う沖縄の大切な時期。"),
    ((5, 4), "ユッカヌヒー（ハーリー）", "海の安全と豊漁を願う、港がにぎわう伝統行事。"),
    ((7, 13), "旧盆（ウンケー）", "ご先祖を迎える日。家族で過ごす時間を大切にする頃。"),
    ((7, 14), "旧盆（ナカビ）", "旧盆の中日。親族の行き来が増える時期。"),
    ((7, 15), "旧盆（ウークイ）", "ご先祖を見送る日。夜のにぎわいが生まれやすい頃。"),
    ((8, 10), "十五夜", "月を眺めて実りに感謝する頃。"),
    ((9, 7), "重陽の節句（菊酒）", "長寿や健康を願う節目の日。"),
    ((12, 8), "事始め", "年末年始の準備を始める頃。"),
    ((12, 24), "ムーチー", "家族の健康を願って鬼餅を作る、沖縄の冬の行事。"),
]

EVENTS_MASTER_PATH = Path(__file__).resolve().parents[2] / "data" / "okinawa_events_master.json"

FIXED_EVENTS = [
    {"month": 3, "day": 5, "name": "サンゴの日", "category": "local_okinawa", "origin": "沖縄県", "priority": 68},
    {"month": 3, "day": 6, "name": "島らっきょうの日", "category": "agriculture", "origin": "伊江村", "priority": 95},
    {"month": 4, "day": 8, "name": "島やさいの日", "category": "agriculture", "origin": "JAおきなわ", "priority": 92},
    {"month": 5, "day": 7, "name": "粉の日（コナモンの日）", "category": "takoyaki", "origin": "日本コナモン協会", "priority": 98},
    {"month": 5, "day": 8, "name": "ゴーヤーの日", "category": "agriculture", "origin": "沖縄県", "priority": 90},
    {"month": 7, "day": 15, "name": "マンゴーの日", "category": "agriculture", "origin": "沖縄県", "priority": 88},
    {"month": 8, "day": 8, "name": "たこ焼の日", "category": "takoyaki", "origin": "日本記念日協会", "priority": 100},
    {"month": 9, "day": 22, "name": "シークヮーサーの日", "category": "agriculture", "origin": "沖縄県", "priority": 93},
    {"month": 10, "day": 16, "name": "国消国産の日", "category": "ja_agri", "origin": "JA全中", "priority": 96},
    {"month": 10, "day": 17, "name": "沖縄そばの日", "category": "local_okinawa", "origin": "沖縄県", "priority": 84},
]

# Fallback national observances used only when no Okinawa/fixed/recurring events are available.
NATIONAL_DAY_FALLBACKS = {
    (5, 19): {"name": "ボクシングの日", "origin": "日本プロボクシング協会"},
}

SEASONAL_PRODUCE_BY_MONTH = {
    1: [
        {"name": "タンカン", "description": "冬に旬を迎える沖縄柑橘。甘みと香りが強い。", "pairing": "食後のデザート提案"},
        {"name": "島にんじん", "description": "甘みがあり火を入れると風味が立つ冬野菜。", "pairing": "細切りを軽く炒めてトッピング"},
    ],
    2: [
        {"name": "島にんじん", "description": "冬の終わりまで楽しめる島野菜。", "pairing": "刻んで生地に混ぜて香り付け"},
        {"name": "葉ニンニク", "description": "辛みが穏やかで香りの良い沖縄の冬野菜。", "pairing": "ガーリック風味だれに活用"},
    ],
    3: [
        {"name": "島らっきょう", "description": "香りが良くシャキッとした食感が特徴。", "pairing": "ネギ代わりに刻みトッピング"},
        {"name": "パッションフルーツ", "description": "春から初夏に出回る芳醇なトロピカル果実。", "pairing": "食後ドリンク提案"},
    ],
    4: [
        {"name": "シブイ（冬瓜）", "description": "水分が多くさっぱりした味わい。", "pairing": "和風だしだれとの相性を訴求"},
        {"name": "島やさい各種", "description": "ハンダマやンジャナなど個性豊かな葉野菜。", "pairing": "日替わりトッピング企画"},
    ],
    5: [
        {"name": "ゴーヤー", "description": "苦味が特徴の沖縄を代表する夏野菜。", "pairing": "薄切りを副菜提案"},
        {"name": "アセローラ", "description": "ビタミンCが豊富な沖縄果実。", "pairing": "食後ドリンク提案"},
    ],
    6: [
        {"name": "マンゴー", "description": "夏の主役果実。濃厚な甘みが魅力。", "pairing": "食後デザート提案"},
        {"name": "パイナップル", "description": "酸味と甘みのバランスが良い旬果実。", "pairing": "シークヮーサー塩とのセット提案"},
    ],
    7: [
        {"name": "マンゴー", "description": "最盛期を迎える沖縄果実。", "pairing": "食後デザート提案"},
        {"name": "オクラ", "description": "夏に旬を迎える粘りのある野菜。", "pairing": "刻みオクラを和風たれに"},
    ],
    8: [
        {"name": "パイナップル", "description": "沖縄北部で親しまれる夏果実。", "pairing": "冷たいドリンク提案"},
        {"name": "パパイヤ", "description": "青果・完熟ともに使える沖縄食材。", "pairing": "副菜の提案"},
    ],
    9: [
        {"name": "シークヮーサー", "description": "青切りの爽やかな酸味が特徴。", "pairing": "ポン酢だれの香り付け"},
        {"name": "島かぼちゃ", "description": "甘みがあり煮崩れしにくい。", "pairing": "季節限定トッピング"},
    ],
    10: [
        {"name": "カーブチー", "description": "やんばるで親しまれる在来柑橘。", "pairing": "柑橘塩だれ提案"},
        {"name": "紅いも", "description": "秋に向けて存在感が増す沖縄素材。", "pairing": "甘じょっぱ系の限定商品提案"},
    ],
    11: [
        {"name": "紅いも", "description": "秋から冬に甘みが増す沖縄食材。", "pairing": "限定メニュー告知"},
        {"name": "スターフルーツ", "description": "冬に向けて出回るトロピカル果実。", "pairing": "食後デザート提案"},
    ],
    12: [
        {"name": "島にんじん", "description": "冬の食卓を彩る沖縄野菜。", "pairing": "細切りトッピング提案"},
        {"name": "ローゼル", "description": "鮮やかな赤色のハーブ。", "pairing": "温冷ドリンク提案"},
    ],
}


def is_nth_weekday(dt: datetime, weekday: int, nth: int) -> bool:
    if dt.weekday() != weekday:
        return False
    return ((dt.day - 1) // 7) + 1 == nth


def build_daily_events(dt: datetime, okinawa_event: str) -> list[EventItem]:
    events: list[EventItem] = []

    if okinawa_event != "該当する沖縄行事はありません。":
        events.append(
            EventItem(
                name=okinawa_event.split("。")[0],
                category="local_okinawa",
                origin="沖縄県",
                priority_score=94,
            )
        )

    for event in FIXED_EVENTS:
        if dt.month == event["month"] and dt.day == event["day"]:
            events.append(
                EventItem(
                    name=event["name"],
                    category=event["category"],
                    origin=event["origin"],
                    priority_score=int(event["priority"]),
                )
            )

    # Monthly recurring synergy day: 3rd Saturday
    if is_nth_weekday(dt, weekday=5, nth=3):
        events.append(
            EventItem(
                name="オコパー・タコパーの日",
                category="takoyaki",
                origin="日清製粉グループ",
                priority_score=100,
            )
        )
        events.append(
            EventItem(
                name="おきなわ食材の日",
                category="ja_agri",
                origin="沖縄県地産地消推進県民会議",
                priority_score=97,
            )
        )

    if not events:
        fallback = NATIONAL_DAY_FALLBACKS.get((dt.month, dt.day))
        if fallback:
            events.append(
                EventItem(
                    name=fallback["name"],
                    category="national_memorial_day",
                    origin=fallback["origin"],
                    priority_score=60,
                )
            )

    events.sort(key=lambda e: e.priority_score, reverse=True)
    return events[:3]


def build_seasonal_produce(dt: datetime) -> list[ProduceItem]:
    rows = SEASONAL_PRODUCE_BY_MONTH.get(dt.month, [])
    return [
        ProduceItem(
            name=row["name"],
            description=row["description"],
            pairing_with_takoyaki=row["pairing"],
        )
        for row in rows[:2]
    ]


def build_post_strategy(events: list[EventItem], produce: list[ProduceItem], location: str) -> PostStrategy:
    produce_text = produce[0].name if produce else "旬の島野菜"
    suggested = f"{produce_text}の季節感も一緒に楽しめる一日に。"
    primary = events[0].name if events else "記念日"
    return PostStrategy(primary_hashtag=f"#{primary}", suggested_copy=suggested)


def load_events_master() -> dict[str, Any]:
    try:
        with EVENTS_MASTER_PATH.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
    except Exception:
        pass
    return {}


def format_old_calendar_info(dt: datetime) -> tuple[str, str]:
    lunar = cnlunar.Lunar(dt.replace(tzinfo=None))
    leap = "閏" if lunar.isLunarLeapMonth else ""
    old_calendar = f"{leap}{lunar.lunarMonthCn}{lunar.lunarDayCn}"
    if lunar.todaySolarTerms != "无":
        sekki = SEKKI_JA_MAP.get(lunar.todaySolarTerms, lunar.todaySolarTerms)
    else:
        term = SEKKI_JA_MAP.get(lunar.nextSolarTerm, lunar.nextSolarTerm)
        sekki = term
    return old_calendar, sekki


def calc_rokuyo(dt: datetime) -> str:
    lunar = cnlunar.Lunar(dt.replace(tzinfo=None))
    month = lunar.lunarMonth
    day = lunar.lunarDay
    start_index = (month - 1) % 6
    names = ["先勝", "友引", "先負", "仏滅", "大安", "赤口"]
    return names[(start_index + day - 1) % 6]


def calc_tide_from_moon_age(dt: datetime) -> str:
    age = moon.phase(dt.date())
    if age < 1.8 or age >= 27.7:
        return "大潮"
    if age < 4.6:
        return "中潮"
    if age < 7.4:
        return "小潮"
    if age < 9.3:
        return "長潮"
    if age < 11.1:
        return "若潮"
    if age < 13.9:
        return "中潮"
    if age < 16.7:
        return "大潮"
    if age < 19.5:
        return "中潮"
    if age < 22.3:
        return "小潮"
    if age < 24.2:
        return "長潮"
    if age < 26.0:
        return "若潮"
    return "中潮"


def pick_okinawa_event(dt: datetime) -> str:
    master = load_events_master()
    lunar = cnlunar.Lunar(dt.replace(tzinfo=None))
    lunar_key = (lunar.lunarMonth, lunar.lunarDay)

    for event in master.get("lunar_events", []):
        month = int(event.get("lunar_month", -1))
        day = int(event.get("lunar_day", -1))
        if (month, day) == lunar_key:
            name = str(event.get("name", ""))
            detail = str(event.get("description", ""))
            if name and detail:
                return f"{name}。{detail}"

    for event in master.get("seasonal_events", []):
        if str(event.get("solar_term", "")) == SEKKI_JA_MAP.get(lunar.todaySolarTerms, lunar.todaySolarTerms):
            name = str(event.get("name", ""))
            detail = str(event.get("description", ""))
            if name and detail:
                return f"{name}。{detail}"

    # OKINAWA_EVENTS is defined with fixed (solar) month/day tuples.
    key = (dt.month, dt.day)
    for event_key, name, detail in OKINAWA_EVENTS:
        if event_key == key:
            return f"{name}。{detail}"
    return "該当する沖縄行事はありません。"


async def get_today_info() -> TodayInfo:
    now = datetime.now(JST)
    weekday = WEEKDAYS_JA[now.weekday()]

    weather_url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={NAGO_LAT}&longitude={NAGO_LON}"
        "&daily=weather_code,temperature_2m_max,sunrise,sunset"
        "&timezone=Asia%2FTokyo&forecast_days=1"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(weather_url)
            res.raise_for_status()
            data = res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"天気情報の取得に失敗: {exc}")

    daily = data.get("daily", {})
    weather_code = int(daily.get("weather_code", [0])[0])
    temp_max = float(daily.get("temperature_2m_max", [28.0])[0])
    sunrise = str(daily.get("sunrise", [""])[0])[-5:]
    sunset = str(daily.get("sunset", [""])[0])[-5:]

    old_calendar, sekki24 = format_old_calendar_info(now)
    okinawa_event = pick_okinawa_event(now)
    events = build_daily_events(now, okinawa_event)
    seasonal_produce = build_seasonal_produce(now)
    post_strategy = build_post_strategy(
        events=events,
        produce=seasonal_produce,
        location="JAファーマーズ前",
    )

    return TodayInfo(
        date=now.strftime("%Y-%m-%d"),
        weekday=weekday,
        weather=weather_code_to_ja(weather_code),
        temperature_c=temp_max,
        sunrise=sunrise,
        sunset=sunset,
        old_calendar=old_calendar,
        rokuyo=calc_rokuyo(now),
        sekki24=sekki24,
        okinawa_event=okinawa_event,
        tide=calc_tide_from_moon_age(now),
        location="JAファーマーズ前",
        business_hours="12:00〜17:30",
        events=events,
        seasonal_produce=seasonal_produce,
        post_strategy=post_strategy,
    )


def build_local_post(info: TodayInfo) -> str:
    if info.events:
        day_tag = info.events[0].name
    else:
        day_tag = "記念日"
    season_line = f"今日は #{day_tag} ですね。"

    return (
        "はいさい☀️\n"
        f"{season_line}\n"
        f"やんばるは{info.weather}、最高気温{info.temperature_c:.0f}℃予報です。\n"
        f"{info.post_strategy.suggested_copy}\n"
        f"{info.location}で、あちこーこーのたこ焼きを焼いてお待ちしています🐙🔥\n\n"
        "【営業時間】\n"
        f"{info.business_hours}\n"
        "（売り切れ次第終了の場合があります）\n\n"
        "御来店お待ちしております。\n\n"
        "#やんばる #たこ焼き #あちこーこー #沖縄 #名護"
    )


def build_prompt(info: TodayInfo) -> str:
    return f"""
あなたは「やんばる あちこーこー たこ焼き」のSNS担当です。

目的:
- X向け営業投稿を作る
- 地域密着・焼きたて感・親しみを自然に伝える

条件:
- 日本語
- 読みやすい改行
- 220文字前後
- 営業情報は必ず入れる
- 沖縄らしいやわらかい言い回しを入れる
- ハッシュタグは最後に3〜5個
- 2行目付近で「今日は #〇〇の日」を自然に入れる
- 沖縄行事がなければ、全国の記念日（eventsの最上位）を #〇〇の日 として使う
- 「【営業時間】」の見出しを入れる
- 旧暦・二十四節気は内部参照のみ。本文には無理に入れない

投稿スタイル:
{STYLE_HINT}

今日の情報:
- 日付: {info.date}（{info.weekday}）
- 天気: {info.weather}
- 気温: {info.temperature_c:.1f}℃
- 日の出/日の入: {info.sunrise}/{info.sunset}
- 旧暦: {info.old_calendar}
- 六曜: {info.rokuyo}
- 二十四節気: {info.sekki24}
- 沖縄行事: {info.okinawa_event}
- 潮汐: {info.tide}
- 今日の主要イベント: {[e.model_dump() for e in info.events]}
- 旬の農産物: {[p.model_dump() for p in info.seasonal_produce]}
- 投稿戦略: {info.post_strategy.model_dump()}
- 出店場所: {info.location}
- 営業時間: {info.business_hours}
""".strip()


def try_openai_post(prompt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key or OpenAI is None:
        return None

    try:
        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model=model,
            input=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        text = (resp.output_text or "").strip()
        return text if text else None
    except Exception:
        return None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/today", response_model=TodayInfo)
async def today() -> TodayInfo:
    return await get_today_info()


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    info = await get_today_info()
    prompt = build_prompt(info)
    post = try_openai_post(prompt) or build_local_post(info)
    return GenerateResponse(post=post, info=info)
