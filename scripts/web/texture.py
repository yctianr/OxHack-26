import numpy as np, json, pickle
from PIL import Image, ImageDraw, ImageFilter
from pyproj import Transformer
t2ll=Transformer.from_crs(27700,4326,always_xy=True)
E=np.clip(np.load('data/interim/web_elev.npy'),35,None); np.save('data/interim/web_elev.npy',E)
g=json.load(open('data/interim/web_grid.json')); W,S,Ee,N=g['bounds']
# re-encode clipped elevation
v=E+32768; r=np.floor(v/256); gg=np.floor(v-r*256); b=np.floor((v-r*256-gg)*256)
Image.fromarray(np.dstack([r,gg,b]).astype(np.uint8)).save('web/data/elevation.png',optimize=True)
T=2048
Eu=np.asarray(Image.fromarray(E.astype(np.float32)).resize((T,T),Image.BICUBIC))
dx=(Ee-W)/T*111320*np.cos(np.radians(51.75)); dy=(N-S)/T*110540
gy,gx=np.gradient(Eu,dy,dx)
ex=3.0
slope=np.arctan(ex*np.hypot(gx,gy)); asp=np.arctan2(-gy,gx)
az,alt=np.radians(315),np.radians(35)
hs=np.sin(alt)*np.cos(slope)+np.cos(alt)*np.sin(slope)*np.cos(az-asp)
hs=np.clip(hs,0,1)
t=np.clip((Eu-45)/(200-45),0,1)[...,None]
lo=np.array([14,26,30]); mid=np.array([34,44,40]); hi=np.array([66,64,56])
col=np.where(t<0.4, lo+(mid-lo)*(t/0.4), mid+(hi-mid)*((t-0.4)/0.6))
shade=(0.45+0.85*hs)[...,None]
img=np.clip(col*shade,0,255).astype(np.uint8)
im=Image.fromarray(img,'RGB')
# faint streams
links=pickle.load(open('data/interim/web_links.pkl','rb'))
d=ImageDraw.Draw(im,'RGBA')
for l in links:
    if l['form']=='lake': continue
    lo_,la_=t2ll.transform([p[0] for p in l['pts']],[p[1] for p in l['pts']])
    xy=[((a-W)/(Ee-W)*T,(N-c)/(N-S)*T) for a,c in zip(lo_,la_)]
    d.line(xy,fill=(70,140,160,70),width=1)
im.save('web/data/terrain.jpg',quality=86)
print('ok')
