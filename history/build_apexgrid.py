# -*- coding: utf-8 -*-
"""取引履歴サイトの「3つ目の口座」＝ApexGrid（バックテスト）のデータ apexgrid.js を書き出す。

・中身は有料版EA ApexGrid_v2 を 25万円・追加入金なしで 2018-01-02 から動かした場合のバックテスト
  （過去の値動きでの計算。実際の口座の成績ではない）。画面にも「バックテスト」と必ず出す。
・元データ: システム関連/20_ApexGrid（有料版）/さらなる最強EA_2026-09-20/参考資料…/ツール/v2_8y_data_nocap.json
  （同じフォルダの v2_8y_run.py --lot-cap 1000 → v2_8y_page.py --data-out v2_8y_data_nocap.json が作る。作り方はそこの README.md）
  2026-10-03 から「1回目のロットの上限なし・安全装置なし」の計算（さとるの依頼。9/25 時点で 4億7,979万円になる計算）。
  それより前は「上限1.00・安全装置45%」の v2_8y_data.json だった（引数にそのファイルを渡せば作れる）。
・history.js とは別のファイルにしてあるので、build_history.py を叩き直しても消えない。
  index.html が history.js のあとに apexgrid.js を読み、window.EVE_HISTORY.accounts に1口座足す。
・企画口座・メイン口座の数字には一切さわらない。

  python build_apexgrid.py [v2_8y_data.json の場所]
"""
import json, sys, io
from pathlib import Path
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
OUT = HERE / "apexgrid.js"
DEFAULT_SRC = (HERE.parents[4] / "システム関連" / "20_ApexGrid（有料版）" / "さらなる最強EA_2026-09-20"
               / "参考資料（検証の詳細・普段は見なくてよい）" / "ツール" / "v2_8y_data_nocap.json")
SITE_BASE = date(2024, 9, 2)        # history.js の base（時刻はここからの分）
DATA_BASE = date(2018, 1, 1)        # v2_8y_data.json の base（日本時間）
OFF = (SITE_BASE - DATA_BASE).days * 1440


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    D = json.loads(src.read_text(encoding="utf-8"))
    S, M = D["sum"], D["meta"]
    rows = []
    for t in D["T"]:
        pair, side, t_in, t_out, levels, lots, pips, jpy, swap, reason, bal = t[:11]
        if D["reasons"][reason] == "end":      # まだ決済していない取引は載せない（残高に入っていない）
            continue
        rows.append([t_in - OFF, t_out - OFF, pair, side, lots, jpy, bal])
    rows.sort(key=lambda r: r[1])
    assert rows[-1][6] == S["bal"] and rows[0][6] - rows[0][5] == S["cap"]
    b = S["cap"]
    for r in rows:
        b += r[5]; assert b == r[6]            # 残高＝元本＋損益の積み上げ（1円もズレない）
    eq = []
    for d in D["D"]:
        dt = DATA_BASE + timedelta(days=d[0])
        eq.append([dt.year * 10000 + dt.month * 100 + dt.day, min(d[7], d[6])])   # その日の「含み損を入れた金額」の最低
    wins = [r[5] for r in rows if r[5] > 0]; loss = [r[5] for r in rows if r[5] < 0]
    first = DATA_BASE + timedelta(minutes=S["first_t"]); last = DATA_BASE + timedelta(minutes=S["last_t"])
    d_from = DATA_BASE + timedelta(days=S["first_t"] // 1440); d_to = DATA_BASE + timedelta(days=(S["last_t"] - 1) // 1440)
    g = M.get("guard_pct", 0)
    nocap = M.get("lot_cap", 1.0) > 1.0
    acct = dict(
        id="apex", label="ApexGrid（バックテスト）", kind="backtest", badge="バックテスト", deposit=S["cap"],
        note="有料版EA ApexGrid_v2 のバックテスト（過去の値動きでの計算）。実際の口座の成績ではない。",
        caption=("ApexGrid（EA）のバックテスト＝過去の値動きでの計算です。実際の口座の成績ではありません。"
                 f"{S['cap'] // 10000}万円・追加入金なしで {d_from.year}年{d_from.month}月{d_from.day}日から {d_to.year}年{d_to.month}月{d_to.day}日まで動かした場合。"
                 + (f"最初の注文のロットは残高{M['ref'] // 10000}万円ごとに0.01で、上限を付けずに増やした計算。" if nocap else "")
                 + (f"安全装置（含み損が残高の{g:g}%で全部決済）は{S['guard_n']}回。" if g else "安全装置（含み損で全部決済）は使っていない計算。")
                 + "これからの成績を約束するものではありません。"),
        chLabels=D["pairs"], chWord="ペア", lotDp=2, hours24=True,
        summary=dict(n=len(rows), win=len(wins), loss=len(loss), net=rows[-1][6] - S["cap"], bal=rows[-1][6],
                     pf=round(sum(wins) / abs(sum(loss)), 3), maxdd_pct=S["dd"], low=S["low"], made=M["made"]),
    )
    head = json.dumps(acct, ensure_ascii=False, separators=(", ", ": "))[:-1]
    js = ("// 自動生成: python build_apexgrid.py （手で編集しない）\n"
          "// ApexGrid（有料版EA）のバックテスト。過去の値動きでの計算で、実際の口座の成績ではない。\n"
          f"// {S['cap']:,}円・追加入金なし・{d_from} 〜 {d_to}（日本時間）。元データ: システム関連/20_ApexGrid…/ツール/{src.name}（作成 {M['made']}）\n"
          f"// 1回目のロット: 残高{M['ref']:,}円ごとに0.01・{'上限なし' if nocap else '上限 %.2f' % M.get('lot_cap', 1.0)}。安全装置: {('含み損が残高の%g%%で全部決済' % g) if g else 'なし'}\n"
          "// rows: [約定, 決済, ペア, 売買(0=BUY 1=SELL), ロット, 損益, 決済後の残高]  時刻は history.js と同じ 2024-09-02 00:00 からの分（昔の取引は負の数）\n"
          "// eq:   [日付(yyyymmdd), その日の「含み損を入れた金額」の最低]\n"
          "(function(){\n"
          "  var H = window.EVE_HISTORY; if(!H || !H.accounts) return;\n"
          "  if(H.accounts.some(function(a){ return a.id === 'apex'; })) return;\n"
          "  H.accounts.push(" + head + ",\n"
          '    "eq": ' + json.dumps(eq, separators=(",", ":")) + ",\n"
          '    "rows": [\n' + ",\n".join("      " + json.dumps(r, separators=(",", ":")) for r in rows) + "\n    ]\n  });\n})();\n")
    OUT.write_bytes(js.encode("utf-8"))        # 改行は LF（Mac と Windows で差分が出ないように）
    print("→ %s  (%.0f KB)" % (OUT.name, OUT.stat().st_size / 1024))
    print("  apex  %s 〜 %s  %d件  元本 %s → 残高 %s  勝率 %.1f%%  PF %.2f  最大の落ち込み（含み損込み） %.1f%%  いちばん減った時 %s"
          % (first.isoformat(), last.isoformat(), len(rows), "{:,}".format(S["cap"]), "{:,}".format(rows[-1][6]),
             100 * len(wins) / len(rows), acct["summary"]["pf"], S["dd"], "{:,}".format(S["low"])))


if __name__ == "__main__":
    main()
