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
# physics water balance (main model) vs the statistical backup, on the same held-out works and days (run 9_wb_fit.py first)
from sklearn.metrics import roc_auc_score
WB=pd.read_pickle('data/interim/wb_predictions.pkl')
M=TE.merge(WB[['site','fold','date','wb1_p','wb1_hours']],on=['site','fold','date'])
phys={}
for f,d in M.groupby('fold'):
    br=lambda c: float(np.mean((d[c]-d.y)**2)); clim=br('clim')
    auc=lambda c: float(d.groupby('site').filter(lambda g: g.y.sum()>=5 and (1-g.y).sum()>=5).groupby('site').apply(lambda g: roc_auc_score(g.y,g[c])).median())
    rows={c:dict(brier=round(br(c),4),skill=round(1-br(c)/clim,2),auc=round(auc(c),3) if c!='clim' else None) for c in ['wb1_p','core_explain','core_forecast','persistence','clim']}
    cal=d.assign(b=pd.cut(d.wb1_p,[0,.02,.05,.1,.2,.4,.6,.8,1.01],right=False)).groupby('b').agg(n=('y','size'),p=('wb1_p','mean'),o=('y','mean')).dropna()
    phys[f]=dict(sites=int(d.site.nunique()),days=int(len(d)),start=str(d.date.min().date()),end=str(d.date.max().date()),rows=rows,
        cal=[[round(a,4),round(b,4),int(n)] for n,a,b in cal[['n','p','o']].values],obs_h=round(float(d.h.sum())),phys_h=round(float(d.wb1_hours.sum())),stat_h=round(float(d.core_hours.sum())))
out['phys']=phys
json.dump(out,open('web/data/stats.json','w'))
