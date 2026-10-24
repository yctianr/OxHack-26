"""Render a hillshade PNG (with a rough Thames-level water tint) from the 20 m Oxford DTM.
Usage: python scripts/terrain/hillshade.py data/raw/oxford_dtm_20m.tif docs/img/oxford_relief.png
The water tint is a linear interpolation of river level by northing - illustrative only."""
import os, sys, math, zlib, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readtif import read
w, h, v, _ = read(sys.argv[1])
E0, N1 = 440000, 216000   # top-left (subset E 440000-462000, N 198000-216000), 20 m cells
cs = 20.0
def z(x, y):
    x = min(max(x, 0), w-1); y = min(max(y, 0), h-1)
    return v[y*w+x]
az, alt = math.radians(315), math.radians(40)
px = bytearray()
for y in range(h):
    px.append(0)
    N = N1 - (y+0.5)*cs
    # approximate Thames water level falling from Godstow (~58.1 mAOD, north) to Sandford (~53.7, south)
    wl = 53.7 + (N-201000)/(213000-201000)*(58.1-53.7)
    for x in range(w):
        e = z(x, y)
        dzdx = ((z(x+1,y-1)+2*z(x+1,y)+z(x+1,y+1)) - (z(x-1,y-1)+2*z(x-1,y)+z(x-1,y+1))) / (8*cs)
        dzdy = ((z(x-1,y+1)+2*z(x,y+1)+z(x+1,y+1)) - (z(x-1,y-1)+2*z(x,y-1)+z(x+1,y-1))) / (8*cs)
        slope = math.atan(3*math.hypot(dzdx, dzdy))
        aspect = math.atan2(dzdy, -dzdx)
        hs = max(0.0, math.cos(alt)*math.cos(slope) + math.sin(alt)*math.sin(slope)*math.cos(az - aspect))
        t = min(1, max(0, (e-52)/110))
        base = (int(232-70*t), int(236-60*t), int(222-80*t))
        if e < wl + 1.0:
            k = 0.85 if e < wl + 0.3 else 0.55
            base = tuple(int(b*(1-k) + c*k) for b, c in zip(base, (58, 135, 229)))
        sh = 0.45 + 0.55*hs
        px.extend(bytes(min(255, int(c*sh)) for c in base))
def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t+d) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(px), 9)) + chunk(b'IEND', b'')
open(sys.argv[2], 'wb').write(png)
print('ok', w, h)
