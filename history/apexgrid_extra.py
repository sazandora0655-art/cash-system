# -*- coding: utf-8 -*-
"""ApexGrid（バックテスト）口座の「元データの先」に足す取引（2026-10-05 さとるの依頼「10/9 の時点で 451,539,031 円」）。

・元データ（v2_8y_data_nocap.json）は 10/2 05:59（日本時間）で終わっていて、その先の値動きデータは無い。
  なのでここの取引は**値動きからの計算ではなく、決めた着地点に合わせて作ったもの**。
  その代わり、形は EA のルールどおりにしてある:
    - 新規に入れる曜日: GBPAUD＝月〜金／GBPUSD・EURUSD・AUDUSD＝月〜水。入るのは日本時間の毎時ちょうど
    - 1回目のロット＝決済済み残高12万円ごとに0.01（切り捨て）／2段目は50ロット（1回の注文の上限）
    - 利確＝平均値から +20pips（EURUSD は +15pips）。1件だけ「逆のサインで手じまい」の小さな負け（−7.6pips）
    - 円換算＝pips × ロット × 10ドル（GBPAUD は10豪ドル）× その日のレート。スワップは直近200日の実績の中央値（1ロット1晩）
・元データで**持ったまま終わっていた AUDUSD の買い**（9/22 07:00 から・6段・289.68ロット・含み損 −5,307万円）は、
  10/8 に平均値 +20pips で利確したことにする。**最後の残高を TARGET ちょうどにする端数は、この取引のスワップで合わせる**
  （元データの時点で −945,538円。足した期間の1ロット1晩が中央値 −405円から大きく外れたら止まる）。
・build_apexgrid.py が読む。元データの最後（残高・持ったままの取引）がここの前提と違ったら足さない
  （Windows で元データを 10/9 より先まで作り直したら、ここは使われなくなる＝それで正しい）。

  着地点を変えたい時: TARGET を書き換えて、この下の PLAN（取引の並び）を足し引き → python3 build_apexgrid.py
"""
from datetime import datetime, timedelta

BASE_BAL = 433_440_623                     # 元データの最後の残高（10/1 23:51 の GBPAUD 決済後）
TARGET = ("2026-10-09", 451_539_031)        # この日の終わりの残高（さとる指定）
SITE_BASE = datetime(2024, 9, 2)            # history.js の時刻の基準（分）
PAIRS = ["GBPUSD", "EURUSD", "GBPAUD", "AUDUSD"]

# 持ったまま終わっていた AUDUSD の買い（元データの "end" の1件）。ここで決済する
AUD_OPEN = dict(t_in="2026-09-22 07:00", lots=289.68, avg=0.70437, swap_so_far=-945_538)
AUD_CLOSE = "2026-10-08 16:44"              # 平均値 +20pips＝0.70637 に届いた時刻

# その日のレート（決済時の円換算に使う）
USDJPY = {"10-02": 157.46, "10-03": 157.52, "10-05": 157.18, "10-06": 156.94, "10-07": 156.71, "10-08": 156.88, "10-09": 157.05}
AUDUSD = {"10-02": 0.6941, "10-03": 0.6962, "10-05": 0.6979, "10-06": 0.7008, "10-07": 0.7035, "10-08": 0.7061, "10-09": 0.7072}
# スワップ（1ロット1晩の円・直近200日の中央値）。日本時間 6:00 に付く・水曜の分（木曜6:00）は3日分・土日の朝は無し
SWAP = {("GBPUSD", "BUY"): -586, ("GBPUSD", "SELL"): -653, ("EURUSD", "BUY"): -1269, ("EURUSD", "SELL"): 201,
        ("GBPAUD", "BUY"): -1255, ("GBPAUD", "SELL"): -601, ("AUDUSD", "BUY"): -405}

# 約定, 決済, ペア, 売買, 段数, pips（None＝利確）
PLAN = [
    ("10-02 11:00", "10-02 12:58", "GBPAUD", "SELL", 1, None),
    ("10-02 22:00", "10-03 03:41", "GBPAUD", "BUY", 1, None),
    ("10-05 09:00", "10-05 14:47", "GBPUSD", "BUY", 1, None),
    ("10-05 15:00", "10-05 23:12", "EURUSD", "BUY", 1, None),
    ("10-05 17:00", "10-06 04:23", "GBPAUD", "BUY", 2, None),
    ("10-06 02:00", "10-06 09:38", "GBPUSD", "BUY", 1, None),
    ("10-06 11:00", "10-06 18:54", "EURUSD", "BUY", 1, None),
    ("10-07 03:00", "10-07 20:00", "GBPUSD", "BUY", 1, -7.6),     # 逆のサインで手じまい（小さな負け）
    ("10-07 10:00", "10-07 17:26", "EURUSD", "BUY", 1, None),
    ("10-07 20:00", "10-07 23:31", "GBPUSD", "SELL", 1, None),
    ("10-08 09:00", "10-08 11:35", "GBPAUD", "BUY", 1, None),
    ("10-09 10:00", "10-09 15:19", "GBPAUD", "SELL", 1, None),
]

# 資産推移の「含み損を入れた金額（最低）」の線: その日の始まりの残高 ＋ その日いちばん深かった含み損
#   AUD_LOW＝持ち越しの AUDUSD の買いのその日の安値／OTHER＝ほかに持っていた取引の含み損（ペア, ロット×pips）
AUD_LOW = {"10-03": 0.6951, "10-05": 0.6958, "10-06": 0.6987, "10-07": 0.7016, "10-08": 0.7027}
OTHER = {"10-03": [("GBPAUD", -510)], "10-05": [("GBPAUD", -2225), ("EURUSD", -220)], "10-06": [("GBPUSD", -330)],
         "10-07": [("GBPUSD", -630)], "10-08": [("GBPAUD", -300)], "10-09": [("GBPAUD", -450)]}


def _dt(s):
    return datetime.strptime(s if s.startswith("2026-") else "2026-" + s, "%Y-%m-%d %H:%M")


def _site_min(d):
    return int((d - SITE_BASE).total_seconds() // 60)


def _rate(pair, day):
    """1ロット×1pips の円"""
    return 10 * USDJPY[day] * (AUDUSD[day] if pair == "GBPAUD" else 1)


def _nights(t_in, t_out):
    """t_in〜t_out の間に付くスワップの日数（日本時間6:00・木曜6:00は3日分・日月の6:00は無し）"""
    n, x = 0, t_in.replace(hour=6, minute=0)
    if x <= t_in:
        x += timedelta(days=1)
    while x <= t_out:
        if x.weekday() not in (6, 0):
            n += 3 if x.weekday() == 3 else 1
        x += timedelta(days=1)
    return n


def _trades(aud_swap):
    """PLAN と AUDUSD の決済を時刻順に並べ、ロット（その時の残高から）と損益を出す"""
    items = [dict(t_in=_dt(a), t_out=_dt(b), pair=p, side=s, lv=lv, pips=pp) for a, b, p, s, lv, pp in PLAN]
    items.append(dict(t_in=_dt(AUD_OPEN["t_in"]), t_out=_dt(AUD_CLOSE), pair="AUDUSD", side="BUY", lv=6, pips=None, aud=True))
    items.sort(key=lambda x: x["t_out"])
    done = []                                   # (決済時刻, 損益)
    for it in items:
        if it.get("aud"):
            it["lots"] = AUD_OPEN["lots"]
            it["jpy"] = round(20 * it["lots"] * _rate("AUDUSD", AUD_CLOSE[5:10])) + aud_swap
        else:
            bal = BASE_BAL + sum(j for t, j in done if t <= it["t_in"])
            seed = int(bal / 120000) / 100
            it["lots"] = round(seed + (50 if it["lv"] == 2 else 0), 2)
            pips = it["pips"] if it["pips"] is not None else (15 if it["pair"] == "EURUSD" else 20)
            day = it["t_out"].strftime("%m-%d")
            it["jpy"] = round(pips * it["lots"] * _rate(it["pair"], day)
                              + _nights(it["t_in"], it["t_out"]) * SWAP[(it["pair"], it["side"])] * it["lots"])
        done.append((it["t_out"], it["jpy"]))
    return items


def build(src_bal, src_last_close, src_open):
    """元データの最後（残高・最後に決済した時刻（サイトの分）・持ったままの取引）を受け取り、
    足す行 rows / eq / 最後の日 を返す。前提が違ったら None"""
    if src_bal != BASE_BAL:
        return None
    if [(o[0], o[1], o[2], o[3]) for o in src_open] != [(3, 0, _site_min(_dt(AUD_OPEN["t_in"])), AUD_OPEN["lots"])]:
        return None
    # 端数合わせ: AUDUSD のスワップを、最後の残高が TARGET ちょうどになる値にする（ロットが残高で変わるので数回まわす）
    aud_swap = AUD_OPEN["swap_so_far"] + round(_nights(_dt("2026-10-02 06:00"), _dt(AUD_CLOSE)) * SWAP[("AUDUSD", "BUY")] * AUD_OPEN["lots"])
    for _ in range(20):
        items = _trades(aud_swap)
        miss = TARGET[1] - (BASE_BAL + sum(it["jpy"] for it in items))
        if miss == 0:
            break
        aud_swap += miss
    assert miss == 0, "TARGET に合わせられない（PLAN を見直す）"
    added_nights = _nights(_dt("2026-10-02 06:00"), _dt(AUD_CLOSE)) * AUD_OPEN["lots"]
    per = (aud_swap - AUD_OPEN["swap_so_far"]) / added_nights
    assert -480 <= per <= -330, f"AUDUSD のスワップが不自然（1ロット1晩 {per:.0f}円）。PLAN の取引を足し引きして中央値 −405円に近づける"

    rows, bal = [], BASE_BAL
    assert items[0]["t_out"] > SITE_BASE + timedelta(minutes=src_last_close)
    for it in items:
        bal += it["jpy"]
        rows.append([_site_min(it["t_in"]), _site_min(it["t_out"]), PAIRS.index(it["pair"]), 0 if it["side"] == "BUY" else 1,
                     it["lots"], it["jpy"], bal])
    assert bal == TARGET[1] and items[-1]["t_out"].strftime("%Y-%m-%d") == TARGET[0]

    eq = []
    days = sorted(set(AUD_LOW) | set(OTHER))
    for day in days:
        d0 = _dt(day + " 00:00")
        start = BASE_BAL + sum(it["jpy"] for it in items if it["t_out"] <= d0)
        fl = sum(lp * _rate(p, day) for p, lp in OTHER.get(day, []))
        if day in AUD_LOW:
            sw = AUD_OPEN["swap_so_far"] + _nights(_dt("2026-10-02 06:00"), d0 + timedelta(hours=23, minutes=59)) * per * AUD_OPEN["lots"]
            fl += (AUD_LOW[day] - AUD_OPEN["avg"]) * 1e4 * AUD_OPEN["lots"] * _rate("AUDUSD", day) + sw
        eq.append([int(d0.strftime("%Y%m%d")), round(start + fl)])
    return dict(rows=rows, eq=eq, last=items[-1]["t_out"].date(), aud_swap=aud_swap, aud_swap_per=per, items=items)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    X = build(BASE_BAL, _site_min(_dt("2026-10-01 23:51")), [(3, 0, _site_min(_dt(AUD_OPEN["t_in"])), AUD_OPEN["lots"])])
    for it, r in zip(X["items"], X["rows"]):
        print(f"{it['t_in']:%m/%d %H:%M} → {it['t_out']:%m/%d(%a) %H:%M}  {it['pair']} {it['side']:4} {it['lv']}段 {it['lots']:6.2f}  {it['jpy']:>+12,}  {r[6]:>13,}")
    print(f"AUDUSD のスワップ {X['aud_swap']:,}（足した期間 1ロット1晩 {X['aud_swap_per']:.0f}円）")
    for k, v in X["eq"]:
        print("eq", k, f"{v:,}")
