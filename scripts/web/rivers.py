import sqlite3, struct, json, numpy as np, pickle
from pyproj import Transformer
G='data/raw/os_open_rivers/oprvrs_gb.gpkg'
c=sqlite3.connect(G)
X0,Y0=452000,206000; RX,RY=29000,28000
rows=c.execute("""select w.id,w.geometry,w.flow_direction,w.form,w.watercourse_name,w.start_node,w.end_node,w.length from watercourse_link w join rtree_watercourse_link_geometry r on w.fid=r.id
 where r.maxx>? and r.minx<? and r.maxy>? and r.miny<?""",(X0-RX,X0+RX,Y0-RY,Y0+RY)).fetchall()
def parse(b):
    flags=b[3]; env=(flags>>1)&7; off=8+[0,32,48,48,64][env]
    w=b[off:]; bo='<' if w[0]==1 else '>'
    t=struct.unpack(bo+'I',w[1:5])[0]
    if t in (1002,3002): dim=3
    else: dim=2
    n=struct.unpack(bo+'I',w[5:9])[0]
    sz=8*dim
    return [struct.unpack(bo+'dd',w[9+sz*i:9+sz*i+16]) for i in range(n)]
links=[]
for lid,g,fd,form,name,sn,en,L in rows:
    pts=parse(g)
    if fd=='in opposite direction': pts=pts[::-1]; sn,en=en,sn
    links.append(dict(id=lid,pts=pts,form=form,name=name,sn=sn,en=en,len=L))
from collections import Counter
print(len(links),Counter(l['form'] for l in links), Counter(r[2] for r in rows))
pickle.dump(links,open('data/interim/web_links.pkl','wb'))
