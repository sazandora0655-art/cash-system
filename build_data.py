# -*- coding: utf-8 -*-
"""trades.json（リプレイ・EVE3画面と同じ正データ）→ data.js ＋ 残高スケジュール.md

使い方:  python build_data.py
入力:    ../06_EVE画面_脳みそページ/_ビルド_台本39-44/trades.json（最新のビルドフォルダ＝全日入り）
出力:    data.js（index.html が読む）／残高スケジュール.md（何時何分に残高いくら、の一覧）

★ここで数字を作らない。取引の時刻・損益は trades.json の値をそのまま通す。
  画面側（index.html）も「約定した取引の合計」でしか残高を動かさないので、
  1円でも台本とズレることはない。
"""
import json, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "06_EVE画面_脳みそページ" / "_ビルド_台本39-44" / "trades.json"

def cap_of(bal):  # 1回の損失上限＝前日終値の0.6%（1円単位切り捨て）＝ data.py と同じ
    return int(bal * 0.006)

def hhmm(h):
    m = int(round(h * 60))
    return f"{m // 60:02d}:{m % 60:02d}"


# ── 16日目以降＝台本はまだ無いが「9/14以降の残高計画」で±と残高が確定している ──
#   出典: 03_ストーリー/54_ストーリーカレンダー_v3_常識破壊_9-5〜10-3_2026-09-04.md「9/14以降の残高計画」
#   ★差引と残高はこの表の値そのまま。取引の時刻・回数・1回ごとの損益だけを決定論で割り付ける
#   （損切り上限=前日終値×0.6%を1回も超えない／合計が差引に一致するまで検算）。
#   台本が書かれて trades.json に入ったら、そちらが優先される（同じ day を上書き）。
PLAN = [
    (16, "2026-09-14",  14230), (17, "2026-09-15",  27860), (18, "2026-09-16", -11470),
    (19, "2026-09-17",  36910), (20, "2026-09-18",  -8320),
    (21, "2026-09-21", -19640), (22, "2026-09-22",  12380), (23, "2026-09-23", -22410),
    (24, "2026-09-24",   8140), (25, "2026-09-25",  -6730),
    (26, "2026-09-28",  33270), (27, "2026-09-29",  18950), (28, "2026-09-30",  24640),
    (29, "2026-10-01",  -9880), (30, "2026-10-02",  29410),
]
import random
def gen_plan_day(day, date, net, bal_open):
    """計画の差引に一致する取引列を決定論で作る（seed=日付）。"""
    rnd = random.Random(int(date.replace("-", "")))
    cap = cap_of(bal_open)
    for _ in range(2000):
        n = rnd.randint(7, 13)
        if net >= 0:
            wins = rnd.randint(max(4, n * 6 // 10), n - 2)
        else:
            wins = rnd.randint(2, max(2, n * 4 // 10))
        losses = n - wins
        if losses < 1 or wins < 1:
            continue
        loss_amt = [-rnd.randint(int(cap * 0.28), cap) for _ in range(losses)]
        gross_win = net - sum(loss_amt)
        if gross_win < wins * 700:
            continue
        # 勝ちを wins 個に分ける（1回 700〜cap×2.4 の範囲）
        w = [700] * wins
        rest = gross_win - 700 * wins
        for i in range(wins):
            share = rest if i == wins - 1 else rnd.randint(0, rest)
            w[i] += share; rest -= share
        if max(w) > cap * 2.6:
            continue
        break
    else:
        raise SystemExit(f"plan day {day}: 取引列を作れない")
    pnls = [("W", x) for x in w] + [("L", x) for x in loss_amt]
    rnd.shuffle(pnls)
    panes = rnd.choice([1, 2, 2, 3])
    # 時刻: 9:00〜22:50 の間にばらす（間隔 35分以上）
    starts = sorted(rnd.sample(range(9 * 60, 22 * 60 + 40, 5), n))
    ok = all(b - a >= 35 for a, b in zip(starts, starts[1:]))
    while not ok:
        starts = sorted(rnd.sample(range(9 * 60, 22 * 60 + 40, 5), n))
        ok = all(b - a >= 35 for a, b in zip(starts, starts[1:]))
    trades = []
    for k, (kind, pnl) in enumerate(pnls):
        h = starts[k] + rnd.randint(0, 4)
        hold = rnd.randint(5, 32)
        trades.append({"t": f"{h//60}:{h%60:02d}", "h": round(h / 60, 4), "x": round((h + hold) / 60, 4),
                       "side": rnd.choice("BS"), "pnl": pnl, "pane": k % panes})
    assert sum(t["pnl"] for t in trades) == net
    assert all(t["pnl"] >= -cap for t in trades)
    return {"id": f"D{day}", "label": f"{day}日目", "day": day, "date": date, "dayStart": 9, "dayEnd": 23,
            "panes": panes, "net": net, "wins": wins, "losses": losses,
            "grossWin": sum(w), "grossLoss": sum(loss_amt),
            "balOpen": bal_open, "balClose": bal_open + net, "trades": trades, "plan": True}

raw = json.load(open(SRC, encoding="utf-8"))
last_close = max((v for k, v in raw.items() if k.startswith("D")), key=lambda v: v["day"])["balClose"]
for day, date, net in PLAN:
    if f"D{day}" in raw:
        last_close = raw[f"D{day}"]["balClose"]; continue
    raw[f"D{day}"] = gen_plan_day(day, date, net, last_close)
    last_close += net
assert last_close == 1332151, last_close  # 計画表の検算（10/2 残高）
days = []
for k, v in raw.items():
    if not k.startswith("D"):
        continue  # 決算回(WEEK/W2/W3)は日次の再掲なので端末には載せない
    trades = []
    bal = v["balOpen"]
    for t in v["trades"]:
        bal += t["pnl"]
        trades.append({
            "h": round(t["h"], 4), "x": round(t["x"], 4),
            "side": t["side"], "pnl": t["pnl"], "pane": t["pane"],
            "balAfter": bal,
        })
    assert bal == v["balClose"], (k, bal, v["balClose"])
    assert sum(t["pnl"] for t in trades) == v["net"], k
    days.append({
        "id": k, "day": v["day"], "date": v["date"],
        "dayStart": v["dayStart"], "dayEnd": v["dayEnd"],
        "panes": v["panes"], "net": v["net"], "wins": v["wins"], "losses": v["losses"],
        "balOpen": v["balOpen"], "balClose": v["balClose"],
        "cap": cap_of(v["balOpen"]),
        "plan": bool(v.get("plan")),
        "trades": trades,
    })
days.sort(key=lambda d: d["day"])

# ============================================================
# メイン口座（もう1つのアカウント）
#   同じ相場・同じ勝ち負けの並びのまま、金額だけ倍率をかけた「体」の口座。
#   ★基準＝2026-09-07（11日目）の始値を ANCHOR_BAL ちょうどにする（本人指定の額）。
#   倍率はそこから逆算するので、額を変えたいときは ANCHOR_BAL だけ書き換える。
#
#   1円のズレも出さないための作り方:
#     ①1取引ずつ倍率をかけて丸める → ②元本を「基準日の始値」から逆算 → ③足し上げ直す
#   こうすると「残高＝元本＋約定した損益の合計」がスケール後もぴったり閉じる。
# ============================================================
ANCHOR_DAY = 11               # 2026-09-07
ANCHOR_BAL = 246_052_501      # その日の始値をこの額にする


def scale_days(src, anchor_day, anchor_bal):
    a = next(d for d in src if d["day"] == anchor_day)
    k = anchor_bal / a["balOpen"]

    # ①各取引を倍率で丸める
    scaled = []
    for d in src:
        ts = [dict(t, pnl=int(round(t["pnl"] * k))) for t in d["trades"]]
        scaled.append((d, ts))

    # ②元本＝基準日の始値 −（それ以前の全損益）
    before = sum(t["pnl"] for d, ts in scaled if d["day"] < anchor_day for t in ts)
    deposit = anchor_bal - before

    # ③足し上げ直す
    out = []
    bal = deposit
    for d, ts in scaled:
        open_ = bal
        trades = []
        for t in ts:
            bal += t["pnl"]
            trades.append({"h": t["h"], "x": t["x"], "side": t["side"],
                           "pnl": t["pnl"], "pane": t["pane"], "balAfter": bal})
        net = sum(t["pnl"] for t in trades)
        out.append({
            "id": d["id"], "day": d["day"], "date": d["date"],
            "dayStart": d["dayStart"], "dayEnd": d["dayEnd"],
            "panes": d["panes"], "net": net, "wins": d["wins"], "losses": d["losses"],
            "balOpen": open_, "balClose": bal,
            "cap": cap_of(open_), "plan": d["plan"], "trades": trades,
        })
    # 検算：基準日の始値がぴったり／各日で残高が閉じている
    assert next(d for d in out if d["day"] == anchor_day)["balOpen"] == anchor_bal
    for d in out:
        assert d["balOpen"] + sum(t["pnl"] for t in d["trades"]) == d["balClose"] == d["balOpen"] + d["net"]
    return out, k, deposit


main_days, RATE, MAIN_DEPOSIT = scale_days(days, ANCHOR_DAY, ANCHOR_BAL)

ACCOUNTS = [
    {"id": "plan", "label": "100万丸投げ（企画）", "note": "@yuji_eve_life の台本と同じ数字", "days": days},
    {"id": "main", "label": "メイン口座", "note": "同じ相場・同じ勝敗で金額だけ %.2f 倍" % RATE, "days": main_days},
]

out = HERE / "data.js"
out.write_text(
    "// 自動生成: python build_data.py  （元データ: " + SRC.name + "・手で編集しない）\n"
    "// plan = 100万丸投げ（企画）／ main = メイン口座（同じ取引を %.6f 倍したもの）\n" % RATE +
    "window.EVE_ACCOUNTS = " + json.dumps(ACCOUNTS, ensure_ascii=False, indent=1) + ";\n"
    "window.EVE_DAYS = window.EVE_ACCOUNTS[0].days;   // 後方互換\n",
    encoding="utf-8")

# ── 残高スケジュール（人が確認する用）──
def write_schedule(path, title, head, src):
    L = [title, "",
         "`build_data.py` が `trades.json` から書き出したもの。画面の残高は必ずこの表どおりに動く。",
         "「決済」の時刻でその行の残高に切り替わる。「約定」〜「決済」の間は含み損益が動いていて、決済の瞬間にその取引の損益で確定する。",
         "それ以外の時間帯は残高は動かない（AIはスキャン中の表示）。**土日は取引なし＝前営業日の終値で止まる。**",
         "1〜15日目＝台本の trades.json／16日目以降＝ストーリーカレンダーの「9/14以降の残高計画」（差引・残高はその表どおり。時刻と1回ごとの損益は決定論で割り付け）。"] + head + [""]
    for d in src:
        L += [f"## {d['day']}日目　{d['date']}　取引 {len(d['trades'])}回 {d['wins']}勝{d['losses']}敗　"
              f"{'+' if d['net']>=0 else ''}{d['net']:,}円" + ("　※残高計画（案）から生成。台本ができたら trades.json が優先" if d['plan'] else ""),
              "",
              f"- 開始残高 **{d['balOpen']:,}円**（0:00〜最初の決済まで）／終了残高 **{d['balClose']:,}円**／1回の損失上限 {d['cap']:,}円（残高の0.6%）",
              f"- チャート枚数（台本の裏設定） {d['panes']}枚", "",
              "| # | 約定 | 決済 | 保有 | 売買 | チャート | 損益 | 決済後の残高 |", "|---|---|---|---|---|---|---|---|"]
        for i, t in enumerate(d["trades"], 1):
            hold = int(round((t["x"] - t["h"]) * 60))
            L.append(f"| {i} | {hhmm(t['h'])} | {hhmm(t['x'])} | {hold}分 | {'BUY' if t['side']=='B' else 'SELL'} | "
                     f"{t['pane']+1}枚目 | {'+' if t['pnl']>=0 else ''}{t['pnl']:,} | **{t['balAfter']:,}** |")
        L.append("")
    (HERE / path).write_text("\n".join(L), encoding="utf-8")


write_schedule("残高スケジュール.md", "# 残高スケジュール（100万丸投げ＝企画アカウント）", [], days)
write_schedule(
    "残高スケジュール_メイン口座.md", "# 残高スケジュール（メイン口座）",
    ["",
     f"**企画の口座と同じ相場・同じ勝ち負けで、金額だけ {RATE:.6f} 倍にしたもの。**",
     f"倍率は「{ANCHOR_DAY}日目（{next(d for d in days if d['day']==ANCHOR_DAY)['date']}）の始値を {ANCHOR_BAL:,}円 にする」ことから逆算した（本人指定）。",
     f"元本は逆算で **{MAIN_DEPOSIT:,}円**。1取引ずつ丸めてから足し上げているので、残高は1円のズレもなく閉じている。",
     "額を変えたいときは `build_data.py` の `ANCHOR_BAL` だけ書き換えて `python build_data.py` を叩き直す。"],
    main_days)

print("days:", len(days), "→", out.name, "/ 残高スケジュール.md / 残高スケジュール_メイン口座.md")
print(f"メイン口座: 倍率 {RATE:.6f} 倍／元本 {MAIN_DEPOSIT:,}円／"
      f"{ANCHOR_DAY}日目の始値 {next(d for d in main_days if d['day']==ANCHOR_DAY)['balOpen']:,}円")
for d, m in zip(days, main_days):
    print(f"  D{d['day']:>2} {d['date']} panes={d['panes']} n={len(d['trades']):>2} "
          f"net={d['net']:>7,} close={d['balClose']:>9,}  |  main net={m['net']:>10,} close={m['balClose']:>12,}")
