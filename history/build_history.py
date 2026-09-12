# -*- coding: utf-8 -*-
"""取引履歴サイトのデータを書き出す（history.js）

使い方:  python build_history.py
入力:    ../data.js（既存のAIトレード画面が読んでいる正データ＝企画30日分・手で作らない）
出力:    history.js（取引履歴サイト index.html が読む）

★この画面は「2年分の履歴を遡って見る」ためのもの。数字の作り方は2つに分かれる。

  1) 2026-08-24 以降（企画の30日）＝ ../data.js の取引をそのまま通す。1円も動かさない。
     → AIトレード画面・リプレイ・台本と完全に一致する。

  2) 2026-08-21 まで（過去2年）＝ このスクリプトが決定論で生成する（seed固定・何度叩いても同じ）。
     終点が main 口座の元本 218,093,751円 ちょうどに着地するように作ってあるので、
     過去2年 → 企画30日 が残高で切れ目なく繋がる。

★本物のデータに差し替えるときは INPUT_CSV に MT4/MT5 の履歴CSVを置いて叩く（後述）か、
  サイトの ⚙ から CSV / JSON を読み込む。生成データは既定の見本でしかない。
"""
import json, sys, io, math, random, csv
from pathlib import Path
from datetime import date, datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
SRC_DATA = HERE.parent / "data.js"
OUT = HERE / "history.js"
INPUT_CSV = HERE / "取引履歴_入力.csv"     # 置いてあればこれを最優先で読む（本番データ用）

# ════════════════════════ ここだけ変えれば全部引き直る ════════════════════════
DEPOSIT     = 100_000_000        # 2年前に入れた額
START       = date(2024, 9, 2)   # 運用開始（月）
END         = date(2026, 8, 21)  # 生成の終点＝企画が始まる前の営業日（金）
ANCHOR_END  = 218_093_751        # ENDの終値。★main口座の元本と一致させる（build_data.py の逆算値）
RISK_PCT    = 0.006              # 企画口座の損切り上限＝残高の0.6%（AIトレード画面と同じ規律）
MAIN_RISK   = 0.0022             # メイン口座の損切り上限＝残高の0.22%。
                                 #   額がひと桁大きいぶん1回のリスクは薄く張る、という設定。
                                 #   ここを上げると勝率・PFが下がり、最大DDが深くなる
LOT_YEN     = 25_000             # 1ロットあたりのリスク額（ロット数の逆算用・表示だけに使う）
SEED        = 20260912
BASE_DT     = datetime(2024, 9, 2, 0, 0)   # 行の時刻はここからの「分」で持つ（ファイルを軽くするため）

HOLIDAYS = set()                 # 休場（年末年始・クリスマス）
for y in (2024, 2025, 2026):
    for md in ((12, 24), (12, 25), (12, 31), (1, 1), (1, 2)):
        HOLIDAYS.add(date(y, md[0], md[1]))


def bizdays(a, b):
    """平日だけ（土日と年末年始を抜く）"""
    out, d = [], a
    while d <= b:
        if d.weekday() < 5 and d not in HOLIDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out


# ════════════════════════ 1. 月ごとの成績を決める ════════════════════════
def month_returns(months, target_mult, rnd, dd_max=0.065):
    """月次リターンを引いて、掛け合わせが target_mult ちょうどになるまで寄せる。

    ・平均は月+3%台、たまに負け月（年に2〜3回）。連続で勝ち続けない。
    ・1ヶ月で+15%や-10%は出さない（AIに丸投げの口座として不自然になる）。
    ・負け月が固まって資産が大きく凹む並びは捨てる（月次で見た下落は dd_max まで）。
      ここを大きくすると「一度どかんと減ってから戻す」曲線になる。
    """
    goal = math.log(target_mult)

    def normalize(rs):
        for _ in range(400):
            cur = sum(math.log(1 + r) for r in rs)
            gap = goal - cur
            if abs(gap) < 1e-12:
                break
            step = gap / months
            rs = [max(-0.072, min(0.125, math.exp(math.log(1 + r) + step) - 1)) for r in rs]
        return rs

    def drawdown(rs):
        b = peak = 1.0
        dd = 0.0
        for r in rs:
            b *= (1 + r)
            peak = max(peak, b)
            dd = max(dd, (peak - b) / peak)
        return dd

    best, best_dd = None, 9.0
    for _ in range(240):
        rs = []
        for i in range(months):
            r = rnd.gauss(0.036, 0.040)
            if rnd.random() < 0.13:          # 12ヶ月に1〜2回は はっきりした負け月
                r = -abs(rnd.gauss(0.034, 0.018))
            rs.append(max(-0.072, min(0.125, r)))
        rs = normalize(rs)
        dd = drawdown(rs)
        if dd <= dd_max:
            return rs
        if dd < best_dd:
            best_dd, best = dd, rs
    return best


def split_days(n, up_ratio, rnd):
    """1ヶ月ぶんの日次の重み。勝ち日と負け日を混ぜ、連勝・連敗の波を作る"""
    w, streak, sign = [], 0, 1
    for i in range(n):
        if streak <= 0:                      # 連続する長さを引き直す
            sign = 1 if rnd.random() < up_ratio else -1
            streak = rnd.randint(1, 4) if sign > 0 else rnd.randint(1, 3)
        streak -= 1
        mag = abs(rnd.gauss(0.45, 0.30)) + 0.06
        if rnd.random() < 0.10:
            mag *= rnd.uniform(1.8, 3.0)     # たまに大きく動く日
        w.append(sign * mag)
    return w


def _shuffle_blocks(vals, rnd):
    """連勝・連敗のかたまりは保ったまま、月の中での位置を入れ替える。

    そのまま並べると波が毎月おなじ位置に来て、曜日ごとの成績に嘘くさい偏りが出る
    （月・火だけ稼げない、など）。合計は変わらない。
    """
    blocks, cur = [], [vals[0]]
    for v in vals[1:]:
        if (v >= 0) == (cur[-1] >= 0):
            cur.append(v)
        else:
            blocks.append(cur)
            cur = [v]
    blocks.append(cur)
    rnd.shuffle(blocks)
    return [v for b in blocks for v in b]


def day_pnls(days, bal0, bal1, rnd):
    """その月の日次損益（円）。合計が bal1-bal0 にぴったり一致する"""
    total = bal1 - bal0
    n = len(days)
    up = 0.66 if total >= 0 else 0.42
    for _ in range(300):
        w = split_days(n, up, rnd)
        pos, neg = sum(x for x in w if x > 0), -sum(x for x in w if x < 0)
        if pos < 1e-6 or neg < 1e-6:
            continue
        # 勝ち日合計 G、負け日合計 L を決める（G - L = total、G/L は 1.3〜2.6 倍）
        scale = abs(total) / max(bal0, 1)
        ratio = rnd.uniform(1.35, 2.6) if total >= 0 else rnd.uniform(0.42, 0.78)
        # G = ratio*L かつ G-L = total
        if abs(ratio - 1) < 0.05:
            continue
        L = total / (ratio - 1)
        G = ratio * L
        if L < 0 or G < 0:
            continue
        # 1日の振れが大きすぎたらやり直し（勝ち日+4%／負け日-2.5%まで）
        vals = []
        ok = True
        for x in w:
            v = (G * x / pos) if x > 0 else (L * x / neg)
            lim = bal0 * (0.030 if v > 0 else 0.019)
            if abs(v) > lim:
                ok = False
                break
            vals.append(v)
        if not ok or scale > 0.18:
            continue
        out = [int(round(v)) for v in vals]
        out[-1] += total - sum(out)          # 端数は最終営業日で吸収
        if abs(out[-1]) > bal0 * 0.034:
            continue
        return _shuffle_blocks(out, rnd)
    # どうしても決まらないときは均等割り（保険）
    out = [int(total / n)] * n
    out[-1] += total - sum(out)
    return out


# ════════════════════════ 2. 1日ぶんの取引に割る ════════════════════════
def gen_day_trades(d, net, bal, rnd):
    """その日の損益 net にぴったり一致する取引列を作る。

    ・1回の負けは 損切り上限（残高×0.6%）を絶対に超えない
    ・勝ちは 0.25R〜2.4R（Rは損切り上限）。負けより勝ちが大きい形にする
    ・時刻は9:00〜23:00。保有は数分〜1時間半。負けの方が短い（早く切る）
    """
    cap = int(bal * MAIN_RISK)
    need_n = int(abs(net) / max(1, cap * 1.5)) + 1       # 大きく動いた日は回数が増える
    lo, hi = max(6, need_n), max(12, need_n + 4)
    for _ in range(6000):
        n = rnd.randint(lo, min(28, hi))
        if net >= 0:
            wins = rnd.randint(max(3, n * 60 // 100), max(4, n * 84 // 100))
        else:
            wins = rnd.randint(max(2, n * 34 // 100), max(3, n * 56 // 100))
        losses = n - wins
        if wins < 1 or losses < 1:
            continue
        loss = [-rnd.randint(int(cap * 0.18), int(cap * 0.73)) for _ in range(losses)]
        need = net - sum(loss)                       # 勝ちで作るべき合計
        if need < wins * int(cap * 0.17) or need > wins * int(cap * 2.7):
            continue
        # 勝ちを wins 個に分ける
        base = int(cap * 0.17)
        rest = need - base * wins
        cuts = sorted(rnd.random() for _ in range(wins - 1))
        parts, prev = [], 0.0
        for c in list(cuts) + [1.0]:
            parts.append(c - prev)
            prev = c
        win = [base + int(rest * p) for p in parts]
        win[-1] += need - sum(win)
        if any(w <= 0 or w > cap * 3.1 for w in win):
            continue

        pnls = [(w, True) for w in win] + [(l, False) for l in loss]
        rnd.shuffle(pnls)

        # 時刻を割る（9:00〜23:00を n 個に散らす）
        slots = sorted(rnd.uniform(9.0, 22.4) for _ in range(n))
        rows, b = [], bal
        for i, (p, is_win) in enumerate(pnls):
            hold = rnd.uniform(0.18, 1.5) if is_win else rnd.uniform(0.07, 0.6)
            t_in = slots[i]
            t_out = min(22.9, t_in + hold)
            b += p
            rows.append({
                "in": t_in, "out": t_out,
                "ch": rnd.randint(0, 2),
                "side": rnd.randint(0, 1),                    # 0=BUY 1=SELL
                "lots": round(max(0.1, cap / LOT_YEN) * rnd.uniform(0.78, 1.14), 1),
                "pnl": p, "bal": b,
            })
        return _lay_out(rows, bal, rnd)
    return _fallback(net, bal, rnd)


def _destreak(rows, rnd, maxrun=4):
    """勝ちだけ・負けだけが延々と続く並びをほどく（勝ち負けの中身は変えない）。

    決済が早いのは損切り側なので、放っておくと負けが日の後半に固まり、
    日をまたいで「24連敗」のような、勝率と釣り合わない数字が出てしまう。
    決済の時刻はそのまま、損益の並び順だけを組み直す。
    """
    W = [r["pnl"] for r in rows if r["pnl"] >= 0]
    L = [r["pnl"] for r in rows if r["pnl"] < 0]
    if not W or not L:
        return rows
    out, last, run = [], 0, 0
    while W or L:
        okW = W and not (last == 1 and run >= maxrun)
        okL = L and not (last == -1 and run >= maxrun)
        if okW and okL:
            pick = 1 if rnd.random() < len(W) / float(len(W) + len(L)) else -1
        elif okW:
            pick = 1
        elif okL:
            pick = -1
        else:
            pick = 1 if W else -1
        out.append(W.pop(0) if pick == 1 else L.pop(0))
        run = run + 1 if pick == last else 1
        last = pick
    for r, v in zip(rows, out):
        r["pnl"] = v
    return rows


def _lay_out(rows, bal, rnd=None):
    """決済の順に並べ直して、残高を振り直す"""
    rows.sort(key=lambda r: r["out"])
    if rnd is not None:
        _destreak(rows, rnd)
    b = bal
    for r in rows:
        b += r["pnl"]
        r["bal"] = b
    return rows


FALLBACK_DAYS = []


def _fallback(net, bal, rnd):
    """上の条件では組めなかった日。★ここで必ず作る（作れないと残高がズレる）。

    勝ちは必ず正・負けは必ず負になるように、先に「勝ちの合計」を決めてから
    残りを負けに回す。逆順で作ると、荒れた日に全敗の日ができてしまう。
    """
    cap = max(1, int(bal * MAIN_RISK))
    if net >= 0:
        wins = max(3, min(20, int(net / (cap * 0.8)) + 3))
        losses = max(2, int(wins * 0.55))
        gross_l = -max(1, int(cap * 0.45)) * losses
        need = net - gross_l
    else:
        losses = max(3, min(22, int(-net / (cap * 0.7)) + 3))
        wins = max(2, int(losses * 0.5))
        need = max(wins, int(cap * 0.35) * wins)
        gross_l = net - need
    loss = [gross_l // losses] * losses
    loss[-1] += gross_l - sum(loss)
    win = [max(1, need // wins)] * wins
    win[-1] += need - sum(win)
    if win[-1] <= 0:                       # 端数で最後の1本が潰れたら均す
        win = [max(1, need // wins)] * wins
        win[-1] = need - sum(win[:-1])
    n = wins + losses
    FALLBACK_DAYS.append(n)

    pnls = [(w, True) for w in win] + [(l, False) for l in loss]
    rnd.shuffle(pnls)
    slots = sorted(rnd.uniform(9.0, 22.4) for _ in range(n))
    rows = []
    for i, (p, is_win) in enumerate(pnls):
        hold = rnd.uniform(0.18, 1.5) if is_win else rnd.uniform(0.07, 0.6)
        rows.append({"in": slots[i], "out": min(22.9, slots[i] + hold),
                     "ch": rnd.randint(0, 2), "side": rnd.randint(0, 1),
                     "lots": round(max(0.1, cap / LOT_YEN) * rnd.uniform(0.78, 1.14), 1),
                     "pnl": p, "bal": 0})
    return _lay_out(rows, bal, rnd)


# ════════════════════════ 3. 2年分を生成 ════════════════════════
def generate():
    rnd = random.Random(SEED)
    days = bizdays(START, END)
    # 月ごとに区切る
    months, cur, key = [], [], None
    for d in days:
        k = (d.year, d.month)
        if k != key:
            if cur:
                months.append(cur)
            cur, key = [], k
        cur.append(d)
    months.append(cur)

    mr = month_returns(len(months), ANCHOR_END / DEPOSIT, rnd)
    bal = DEPOSIT
    out = []
    for mi, md in enumerate(months):
        b1 = int(round(bal * (1 + mr[mi]))) if mi < len(months) - 1 else ANCHOR_END
        pnls = day_pnls(md, bal, b1, rnd)
        for d, net in zip(md, pnls):
            rows = gen_day_trades(d, net, bal, rnd)
            if not rows:                      # 作れなかった日は取引なしにして翌日へ送る
                continue
            bal = rows[-1]["bal"]
            out.append((d, rows))
        # 月末に必ず合わせる（1円でもズレたら、そのぶん過去2年と企画30日が繋がらなくなる）
        if out and bal != b1:
            gap = b1 - bal
            trs = out[-1][1]
            share = gap // len(trs)
            for t in trs:
                t["pnl"] += share
            trs[-1]["pnl"] += gap - share * len(trs)
            _lay_out(trs, trs[0]["bal"] - trs[0]["pnl"])
            bal = trs[-1]["bal"]
    return out


# ════════════════════════ 4. 企画30日（../data.js）を繋ぐ ════════════════════════
def load_plan_days():
    s = SRC_DATA.read_text(encoding="utf-8")
    i, j = s.index("["), s.index("];")
    return json.loads(s[i:j + 1])


def minutes(d, h):
    """日付＋小数時 → BASE_DT からの分"""
    dt = datetime(d.year, d.month, d.day) + timedelta(hours=h)
    return int(round((dt - BASE_DT).total_seconds() / 60))


def rows_from_generated(gen):
    rows = []
    for d, trs in gen:
        for t in trs:
            rows.append([minutes(d, t["in"]), minutes(d, t["out"]), t["ch"], t["side"],
                         t["lots"], t["pnl"], t["bal"]])
    return rows


def rows_from_account(acct):
    """data.js の1口座（企画30日）→ 履歴の行。数字はそのまま通す"""
    rows = []
    for day in sorted(acct["days"], key=lambda x: x["day"]):
        d = datetime.strptime(day["date"], "%Y-%m-%d").date()
        cap = day.get("cap") or int(day["balOpen"] * RISK_PCT)
        rnd = random.Random(int(day["date"].replace("-", "")))
        for t in day["trades"]:
            rows.append([minutes(d, t["h"]), minutes(d, t["x"]), t["pane"],
                         0 if t["side"] == "B" else 1,
                         round(max(0.1, cap / LOT_YEN) * rnd.uniform(0.78, 1.12), 1),
                         t["pnl"], t["balAfter"]])
    return rows


# ════════════════════════ 5. CSV入力（本番データ用） ════════════════════════
def rows_from_csv(path):
    """MT4/MT5の履歴CSVを読む。列名はゆるく見る。

    必要なのは 決済時刻 と 損益 だけ。あれば約定時刻・売買・ロット・銘柄も拾う。
    """
    rows, bal = [], None
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        for r in rd:
            g = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            def pick(*names):
                for n in names:
                    if n in g and g[n] != "":
                        return g[n]
                return ""
            pnl = pick("profit", "pnl", "損益", "利益")
            if not pnl:
                continue
            pnl = int(round(float(pnl.replace(",", "").replace("円", ""))))
            ot = pick("open time", "opentime", "約定時刻", "時間")
            ct = pick("close time", "closetime", "決済時刻", "決済時間") or ot
            def parse(s):
                for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
                    try:
                        return datetime.strptime(s, fmt)
                    except ValueError:
                        pass
                return None
            a, b = parse(ot), parse(ct)
            if b is None:
                continue
            if a is None:
                a = b
            side = 0 if pick("type", "種別", "売買").lower().startswith(("buy", "買")) else 1
            lots = pick("size", "lots", "volume", "数量") or "0"
            try:
                lots = round(float(lots.replace(",", "")), 2)
            except ValueError:
                lots = 0
            bal = (bal or 0) + pnl
            rows.append([int((a - BASE_DT).total_seconds() / 60),
                         int((b - BASE_DT).total_seconds() / 60),
                         0, side, lots, pnl, bal])
    rows.sort(key=lambda r: r[1])
    return rows


# ════════════════════════ 6. 書き出し ════════════════════════
def summarize(rows, deposit):
    if not rows:
        return {}
    wins = [r[5] for r in rows if r[5] > 0]
    loss = [r[5] for r in rows if r[5] < 0]
    peak, dd = deposit, 0
    for r in rows:
        peak = max(peak, r[6])
        dd = max(dd, peak - r[6])
    return {
        "n": len(rows), "win": len(wins), "loss": len(loss),
        "net": rows[-1][6] - deposit, "bal": rows[-1][6],
        "pf": round(sum(wins) / abs(sum(loss)), 3) if loss else 0,
        "maxdd": dd,
    }


def main():
    accounts = []

    if INPUT_CSV.exists():
        rows = rows_from_csv(INPUT_CSV)
        dep = 0
        accounts.append({"id": "csv", "label": "読み込んだ口座", "deposit": dep,
                         "note": INPUT_CSV.name, "rows": rows})
        print("CSVから %d件 読み込みました" % len(rows))
    else:
        gen = generate()
        hist = rows_from_generated(gen)
        data = load_plan_days()
        by = {a["id"]: a for a in data}

        # ★表示名は「口座1 / 口座2」だけにする（本人指示 2026-09-12）。
        #   口座1＝100万丸投げ（企画・@yuji_eve_life）／口座2＝メイン口座
        accounts.append({
            "id": "plan", "label": "口座1", "deposit": 1_000_000,
            "note": "2026年8月24日 預託（100万丸投げ）",
            "rows": rows_from_account(by["plan"]),
        })
        accounts.append({
            "id": "main", "label": "口座2", "deposit": DEPOSIT,
            "note": "%s 運用開始（メイン）" % START.strftime("%Y年%-m月"),
            "rows": hist + rows_from_account(by["main"]),
        })

    js = (
        "// 自動生成: python build_history.py （手で編集しない）\n"
        "// 2026-08-24以降は ../data.js の取引そのもの＝AIトレード画面・台本と1円も違わない。\n"
        "// それ以前の2年は build_history.py が決定論で生成（seed=%d・何度叩いても同じ）。\n"
        "// fmt: [約定, 決済, 板, 売買(0=BUY 1=SELL), ロット, 損益, 決済後の残高]  時刻は %s からの分\n"
        % (SEED, BASE_DT.strftime("%Y-%m-%d %H:%M")) +
        "window.EVE_HISTORY = {\n"
        '  "base": "%s",\n' % BASE_DT.strftime("%Y-%m-%dT%H:%M") +
        '  "fmt": ["in","out","ch","side","lots","pnl","bal"],\n'
        '  "riskPct": %s,\n' % RISK_PCT +
        '  "accounts": [\n'
    )
    parts = []
    for a in accounts:
        s = summarize(a["rows"], a["deposit"])
        body = ",\n".join("      " + json.dumps(r, separators=(",", ":")) for r in a["rows"])
        parts.append(
            '    {\n'
            '      "id": %s, "label": %s, "note": %s, "deposit": %d,\n'
            '      "summary": %s,\n'
            '      "rows": [\n%s\n      ]\n'
            '    }' % (json.dumps(a["id"], ensure_ascii=False),
                       json.dumps(a["label"], ensure_ascii=False),
                       json.dumps(a["note"], ensure_ascii=False),
                       a["deposit"], json.dumps(s, ensure_ascii=False), body)
        )
    js += ",\n".join(parts) + "\n  ]\n};\n"
    OUT.write_text(js, encoding="utf-8")

    print("→ %s  (%.0f KB)   ならし直した日 %d日" % (OUT.name, OUT.stat().st_size / 1024, len(FALLBACK_DAYS)))
    for a in accounts:
        s = summarize(a["rows"], a["deposit"])
        if not s:
            continue
        first = BASE_DT + timedelta(minutes=a["rows"][0][1])
        last = BASE_DT + timedelta(minutes=a["rows"][-1][1])
        print("  %-5s %s 〜 %s  %d件  元本 %s → 残高 %s  勝率 %.1f%%  PF %.2f  最大DD %s"
              % (a["id"], first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d"), s["n"],
                 "{:,}".format(a["deposit"]), "{:,}".format(s["bal"]),
                 100 * s["win"] / s["n"], s["pf"], "{:,}".format(s["maxdd"])))


if __name__ == "__main__":
    main()
