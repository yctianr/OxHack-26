import numpy as np, math, io, urllib.request, json, os, rasterio
from PIL import Image
from pyproj import Transformer
from concurrent.futures import ThreadPoolExecutor
t2ll=Transformer.from_crs(27700,4326,always_xy=True); ll2b=Transformer.from_crs(4326,27700,always_xy=True)
X0,Y0,RX,RY=452000,206000,29000,28000
cx=[X0-RX,X0+RX,X0-RX,X0+RX]; cy=[Y0-RY,Y0-RY,Y0+RY,Y0+RY]
lo,la=t2ll.transform(cx,cy)
W,S,E,N=min(lo),min(la),max(lo),max(la)
print('bounds',W,S,E,N)
Z=12
def tx(lon): return (lon+180)/360*2**Z
def ty(lat): r=math.radians(lat); return (1-math.log(math.tan(r)+1/math.cos(r))/math.pi)/2*2**Z
x0,x1=int(tx(W)),int(tx(E)); y0,y1=int(ty(N)),int(ty(S))
def get(xy):
    x,y=xy; f=f'data/raw/terrarium/{Z}_{x}_{y}.png'
    if not os.path.exists(f):
        os.makedirs('data/raw/terrarium',exist_ok=True)
        urllib.request.urlretrieve(f'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png',f)
    a=np.asarray(Image.open(f).convert('RGB')).astype(np.float64)
    return xy,a[...,0]*256+a[...,1]+a[...,2]/256-32768
tiles=[(x,y) for x in range(x0,x1+1) for y in range(y0,y1+1)]
with ThreadPoolExecutor(16) as ex: res=dict(ex.map(get,tiles))
M=np.zeros(((y1-y0+1)*256,(x1-x0+1)*256))
for (x,y),a in res.items(): M[(y-y0)*256:(y-y0+1)*256,(x-x0)*256:(x-x0+1)*256]=a
print('mosaic',M.shape,M.min(),M.max())
def bil(A,px,py):
    px=np.clip(px,0,A.shape[1]-1.001); py=np.clip(py,0,A.shape[0]-1.001)
    i,j=py.astype(int),px.astype(int); fy,fx=py-i,px-j
    return A[i,j]*(1-fx)*(1-fy)+A[i,j+1]*fx*(1-fy)+A[i+1,j]*(1-fx)*fy+A[i+1,j+1]*fx*fy
def elev_grid(n):
    lons=np.linspace(W,E,n); lats=np.linspace(N,S,n)
    LON,LAT=np.meshgrid(lons,lats)
    px=(tx(LON)-x0)*256; 
    r=np.radians(LAT); py=((1-np.log(np.tan(r)+1/np.cos(r))/np.pi)/2*2**Z-y0)*256
    e=bil(M,px,py)
    # LIDAR 20 m blend
    R=rasterio.open('data/raw/oxford_dtm_20m.tif'); L=R.read(1).astype(float); L[L<-1000]=np.nan
    bx,by=ll2b.transform(LON,LAT)
    col=(bx-R.bounds.left)/20-0.5; row=(R.bounds.top-by)/20-0.5
    inside=(col>=0)&(col<L.shape[1]-1)&(row>=0)&(row<L.shape[0]-1)
    Lf=np.nan_to_num(L,nan=0); lv=bil(Lf,col,row)
    # feather 1.5 km at edges
    d=np.minimum.reduce([col,L.shape[1]-1-col,row,L.shape[0]-1-row])*20
    w=np.clip(d/1500,0,1)*inside
    off=np.nanmedian((lv-e)[w>0.99])
    print('lidar-terrarium median offset',off)
    return LON,LAT,e*(1-w)+lv*w, (bx,by)
n=1024
LON,LAT,E1,_=elev_grid(n)
np.save('data/interim/web_elev.npy',E1)
json.dump(dict(bounds=[W,S,E,N],n=n),open('data/interim/web_grid.json','w'))
# Terrarium encode
v=E1+32768; r=np.floor(v/256); g=np.floor(v-r*256); b=np.floor((v-r*256-g)*256)
Image.fromarray(np.dstack([r,g,b]).astype(np.uint8)).save('web/data/elevation.png',optimize=True)
print('elev range',E1.min(),E1.max())
