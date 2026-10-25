"""Writes web/data/stats.json from data/interim/eval_predictions.pkl (run 5_evaluate.py first)."""
import pandas as pd, numpy as np, json
TE=pd.read_pickle('data/interim/eval_predictions.pkl'); out={}
for f,d in TE.groupby('fold'):
    br=lambda x,c: float(np.mean((x[c]-x.y)**2)); on=d[d.mid==0]
    m={c:dict(all=round(br(d,c),4),onset=round(br(on,c),4)) for c in ['clim','persistence','core_forecast','gbm_forecast','core_explain','gbm_explain']}
    cal=d.assign(b=pd.cut(d.core_forecast,[0,.02,.05,.1,.2,.4,.6,.8,1.01],right=False)).groupby('b').agg(n=('y','size'),p=('core_forecast','mean'),o=('y','mean'))
    out[f]=dict(sites=int(d.site.nunique()),days=int(len(d)),start=str(d.date.min().date()),end=str(d.date.max().date()),brier=m,
        cal=[[round(a,4),round(b,4),int(n)] for n,a,b in cal[['n','p','o']].values],obs_h=round(float(d.h.sum())),exp_h=round(float(d.core_hours.sum())))
json.dump(out,open('web/data/stats.json','w'))
