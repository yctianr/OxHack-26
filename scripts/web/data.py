import numpy as np, pandas as pd, json, pickle, math, warnings
from pyproj import Transformer
from collections import defaultdict, deque
warnings.filterwarnings('ignore')
U='data/'
t2ll=Transformer.from_crs(27700,4326,always_xy=True)
E=np.load('data/interim/web_elev.npy'); g=json.load(open('data/interim/web_grid.json')); W,S,Ee,N=g['bounds']; n=g['n']
def elev(lon,lat):
    px=(np.asarray(lon)-W)/(Ee-W)*(n-1); py=(N-np.asarray(lat))/(N-S)*(n-1)
    px=np.clip(px,0,n-1.001); py=np.clip(py,0,n-1.001); i,j=py.astype(int),px.astype(int); fx,fy=px-j,py-i
    return E[i,j]*(1-fx)*(1-fy)+E[i,j+1]*fx*(1-fy)+E[i+1,j]*(1-fx)*fy+E[i+1,j+1]*fx*fy
links=[l for l in pickle.load(open('data/interim/web_links.pkl','rb')) if l['form']!='lake']
# decimate + to lonlat
for k,l in enumerate(links):
    l['k']=k
    pts=l['pts']; keep=[pts[0]]
    for p in pts[1:-1]:
        if (p[0]-keep[-1][0])**2+(p[1]-keep[-1][1])**2>60**2: keep.append(p)
    keep.append(pts[-1]); l['bng']=keep
    lo,la=t2ll.transform([p[0] for p in keep],[p[1] for p in keep])
    l['ll']=list(zip(lo,la))
    l['z']=elev(lo,la)
flowing=[l for l in links if l['form']!='canal']
by_start=defaultdict(list)
for l in flowing: by_start[l['sn']].append(l['k'])
down={l['k']:list(by_start[l['en']]) for l in flowing}
starts=np.array([l['bng'][0] for l in flowing]); sk=[l['k'] for l in flowing]
fixed=0
for l in flowing:
    if not down[l['k']]:
        ex,ey=l['bng'][-1]; d=np.hypot(starts[:,0]-ex,starts[:,1]-ey)
        for j in np.argsort(d)[:3]:
            if d[j]<250 and sk[j]!=l['k']: down[l['k']]=[sk[j]]; fixed+=1; break
print('gap links bridged',fixed)
up=defaultdict(list)
for a,bs in down.items():
    for b in bs: up[b].append(a)
# upstream length (km) per link -> dilution proxy
uplen={}
for l in flowing:
    seen={l['k']}; q=deque([l['k']]); tot=0
    while q:
        x=q.popleft(); tot+=links[x]['len']
        for y in up[x]:
            if y not in seen: seen.add(y); q.append(y)
    uplen[l['k']]=tot/1000
# sites
s=pd.read_csv(U+'interim/sites61.csv'); cards=pd.read_csv(U+'interim/site_cards.csv').set_index('permit')
ar=pd.read_excel(U+'raw/annual_returns/tw_edm_2025.xlsx',sheet_name=0,header=5); ar.columns=[' '.join(str(c).split()) for c in ar.columns]
pc='EA Permit Reference (EA Consents Database)'; ar=ar.drop_duplicates(pc).set_index(pc)
TE=pd.read_pickle(U+'interim/eval_predictions.pkl'); B=TE[TE.fold=='B'].copy()
dates=sorted(B.date.unique()); D=len(dates); di={d:i for i,d in enumerate(dates)}
# size weight: TDV 2024 mean m3/d
tdv=pd.read_excel(U+'raw/tdv/tdv2024.xlsx',sheet_name=1,na_values='NaN',index_col=0)
tdvm={str(c).upper():pd.to_numeric(tdv[c],errors='coerce').mean() for c in tdv.columns}
def tdv_for(name):
    nm=name.upper().replace('-',' ').split(' (')[0].replace(' STW','').replace(' WORKS','')
    if nm=='OXFORD': return tdvm.get('OXFORD STW')
    for k,v in tdvm.items():
        kk=k.replace('-',' ')
        if kk.startswith(nm+' STW'): return v
    return None
xy=np.array([[np.mean([p[0] for p in l['bng']]),np.mean([p[1] for p in l['bng']])] for l in flowing])
def seg_dist(px,py,l):
    best=1e9
    P=l['bng']
    for (ax,ay),(bx,by) in zip(P[:-1],P[1:]):
        dx,dy=bx-ax,by-ay; t=0 if dx==dy==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
        best=min(best,math.hypot(ax+t*dx-px,ay+t*dy-py))
    return best
sites=[]
TYPE={'Storm tank at WwTW':'works','Storm tank at WwTW - with treatment':'works','Inlet SO at WwTW':'works','Inlet SO at WwTW - with treatment':'works','Storm discharge at pumping station':'pumping','SO on sewer network':'network'}
for i,r in s.iterrows():
    p=r.permitNumber; a=ar.loc[p] if p in ar.index else None
    t=TYPE.get(a['Storm Discharge Asset Type'],'works') if a is not None else ('works' if r.locationName in ('Little Milton','Tetsworth','Weston-On-The-Green STW') else 'unknown')
    rw=str(a['Receiving Water / Environment (common name) (EA Consents Database)']).title() if a is not None else ''
    nm=str(a['Site Name (WaSC operational) [optional]']) if a is not None else r.locationName
    if p=='TEMP.3002': nm='Weston-on-the-Green STW (2)'
    # snap
    cand=np.argsort(np.hypot(xy[:,0]-r.x,xy[:,1]-r.y))[:25]
    dd=[(seg_dist(r.x,r.y,flowing[c]),flowing[c]['k']) for c in cand]; dbest,kbest=min(dd)
    # downstream set
    seen=[kbest]; S_=set(seen); q=deque([kbest])
    while q:
        x=q.popleft()
        for y in down.get(x,[]):
            if y not in S_: S_.add(y); seen.append(y); q.append(y)
    # trip path along first-branch chain
    chain=[]; x=kbest; vis=set()
    while x is not None and x not in vis and len(chain)<400:
        vis.add(x); chain.append(x); nx=down.get(x,[]); x=nx[0] if nx else None
    path=[]; 
    # start from snap point roughly: whole first link
    for c in chain:
        for (lo,la),z in zip(links[c]['ll'],links[c]['z']):
            if not path or (abs(path[-1][0]-lo)+abs(path[-1][1]-la))>1e-7: path.append([lo,la,float(z)])
    # timestamps (s) at 0.4 m/s, trimmed at 25 km
    ts=[0.0]; 
    for a_,b_ in zip(path[:-1],path[1:]):
        dxm=(b_[0]-a_[0])*111320*math.cos(math.radians(51.75)); dym=(b_[1]-a_[1])*110540
        ts.append(ts[-1]+math.hypot(dxm,dym)/0.4)
    k=[j for j,t_ in enumerate(ts) if t_<=25000/0.4]
    path=path[:k[-1]+1]; ts=ts[:k[-1]+1]
    lon,lat=t2ll.transform(r.x,r.y)
    sz=tdv_for(r.locationName) if t=='works' else None
    c=cards.loc[p] if p in cards.index else None
    rec=dict(id=p,name=nm.replace(' STW',' STW').replace('XX (Bucknell) SPS','Bucknell SPS'),place=r.locationName,type=t,water=rw,lon=round(lon,5),lat=round(lat,5),z=round(float(elev(lon,lat)),1),
             snap_m=round(dbest),downstream=seen,size=None if sz is None or np.isnan(sz) else round(float(sz)),
             trip=[[round(a_,5),round(b_,5),round(z_,1)] for a_,b_,z_ in path],ts=[round(t_) for t_ in ts])
    if c is not None:
        ft=float(c.flow_trigger_m3s)
        rec['card']=dict(tau=int(c.tau_h),flow_trigger=None if not np.isfinite(ft) or ft>70.5 else round(ft,1),rain_trigger=round(float(c.rain_trigger_mm),1),
                         hours_yr=round(float(c.spill_h_per_yr)),wet_share=round(float(c.wet_share),2),gw_tag=int(c.gw_tag),long_share=round(float(c.long_episode_share),2))
    b=B[B.site==p]
    if len(b):
        arr=lambda col,f=3: [None]*D if False else None
        def A(col,nd=3):
            v=[None]*D
            for d_,x_ in zip(b.date,b[col]): v[di[d_]]=round(float(x_),nd)
            return v
        rec['obs']=A('y',0); rec['hours']=A('h',1); rec['pe']=A('core_explain'); rec['pf']=A('core_forecast'); rec['eh']=A('core_hours',1)
    sites.append(rec)
print('snap dist', sorted([(x['snap_m'],x['place']) for x in sites])[-8:])
print('with preds',sum('pe' in x for x in sites),'sizes',sum(x['size'] is not None for x in sites))
# upstream site lists per link
upsites=defaultdict(list)
for si,x in enumerate(sites):
    for k_ in x['downstream']: upsites[k_].append(si)
main={'River Thames','River Thame','River Cherwell','River Evenlode','River Windrush','River Ock','River Ray','River Glyme'}
rv=[]
for l in links:
    rv.append(dict(k=l['k'],n=(l['name'] or '').replace('River ',''),m=int(l['name'] in main),c=int(l['form']=='canal'),
                   p=[[round(a,5),round(b,5),round(float(z),1)] for (a,b),z in zip(l['ll'],l['z'])],
                   u=upsites.get(l['k'],[]),L=round(uplen.get(l['k'],0),1)))
json.dump(dict(dates=[pd.Timestamp(d).strftime('%Y-%m-%d') for d in dates],sites=sites),open('web/data/outfalls.json','w'),separators=(',',':'))
json.dump(rv,open('web/data/rivers.json','w'),separators=(',',':'))
print('links',len(rv),'with upstream sites',sum(1 for r in rv if r['u']))
