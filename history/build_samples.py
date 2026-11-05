"""Build explicitly labelled fictitious sample accounts. Never real client records."""
from datetime import date, datetime, timedelta
from pathlib import Path
import random, json

ROOT=Path(__file__).parent
BASE=datetime(2024,9,2)
PEOPLE=[
 dict(id='sample-y',name='Yさん',profile='38歳・専業主婦',start='2024-11-06',end='2026-11-05',total=8657391,period='2年間',seed=11051),
 dict(id='sample-k',name='Kさん',profile='45歳・長距離トラック運転手',start='2024-11-06',end='2026-11-05',total=12048367,period='2年間',seed=11052),
 dict(id='sample-l',name='Lさん',profile='48歳・農家',start='2026-04-01',end='2026-10-30',total=1754893,period='7ヶ月',seed=11053),
 dict(id='sample-41',name='41歳・シングルマザー',profile='パート勤務',start='2026-04-01',end='2026-10-30',total=1025647,period='7ヶ月',seed=11054,lastMonth=183719),
 dict(id='sample-61',name='61歳の利用者',profile='老後の蓄えづくり',start='2024-05-06',end='2026-11-05',total=20072183,period='約2年半',seed=11055),
]

def split(total,weights):
 scale=total/sum(weights)
 out=[round(x*scale) for x in weights]
 out[-1]+=total-sum(out)
 return out

accounts=[]
for person_index,p in enumerate(PEOPLE,1):
 rng=random.Random(p['seed'])
 start=date.fromisoformat(p['start']); end=date.fromisoformat(p['end'])
 days=[start+timedelta(days=i) for i in range((end-start).days+1) if (start+timedelta(days=i)).weekday()<5]
 bymonth={}
 for day in days:bymonth.setdefault(day.strftime('%Y-%m'),[]).append(day)
 monthkeys=list(bymonth)
 weights=[rng.uniform(.65,1.45)*(1+.45*i/max(1,len(monthkeys)-1))*len(bymonth[k])/22 for i,k in enumerate(monthkeys)]
 if len(monthkeys)>12:
  for i in range(len(weights)):
   if i%8==6:weights[i]*=-.85
   elif i%7==3:weights[i]*=.12
 else:
  weights[2]*=-.35
  weights[4]*=.18
 if p.get('lastMonth'):
  totals=split(p['total']-p['lastMonth'],weights[:-1])+[p['lastMonth']]
 else:totals=split(p['total'],weights)
 rows=[]; balance=0
 for mi,(key,ds) in enumerate(bymonth.items()):
  # Synthetic drawdowns and varied returns are only for the labelled sample.
  ws=[rng.uniform(.6,2.2)*(-rng.uniform(.4,1.2) if rng.random()<.29 else 1) for _ in ds]
  ws[0]=abs(ws[0])+2
  if sum(ws)<3:ws=[x+1 for x in ws]
  amounts=split(totals[mi],ws)
  for day,daily in zip(ds,amounts):
   n=rng.randint(4,9)
   ts=sorted(rng.sample(range(8*60,21*60),n))
   tw=[rng.uniform(.5,1.6)*(-.65 if rng.random()<.35 else 1) for _ in ts]
   if sum(tw)<1:tw=[abs(v) for v in tw]
   parts=split(daily,tw)
   for t,pnl in zip(ts,parts):
    close=datetime.combine(day,datetime.min.time())+timedelta(minutes=t)
    hold=rng.randint(4,78)
    balance+=pnl
    rows.append([int((close-timedelta(minutes=hold)-BASE).total_seconds()/60),int((close-BASE).total_seconds()/60),rng.randrange(3),rng.randrange(2),round(rng.uniform(.01,.16),2),pnl,balance])
 assert balance==p['total']
 accounts.append(dict(id=p['id'],label='追加口座'+str(person_index)+'（シミュレーション）',sample=True,profitOnly=True,deposit=0,lotDp=2,period=p['period'],badge='シミュレーション',caption='架空の取引データによる表示サンプルです。実在する利用者の取引実績ではありません。',note='Synthetic sample; seed='+str(p['seed']),rows=rows))

payload={'base':'2024-09-02T00:00','accounts':accounts}
(ROOT/'samples.js').write_text('// 架空の表示サンプル。実在する利用者の取引実績ではありません。\nwindow.CASH_SAMPLES = '+json.dumps(payload,ensure_ascii=False,separators=(',',':'))+';\n')
(ROOT/'samples-validation.json').write_text(json.dumps([dict(id=a['id'],total=a['rows'][-1][6],rows=len(a['rows']),losingTrades=sum(r[5]<0 for r in a['rows'])) for a in accounts],ensure_ascii=False,indent=2))
print((ROOT/'samples-validation.json').read_text())
