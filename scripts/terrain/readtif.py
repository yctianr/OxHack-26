import struct, sys
def read(path):
    b = open(path,'rb').read()
    e = '>' if b[:2]==b'MM' else '<'
    off = struct.unpack(e+'I', b[4:8])[0]
    n = struct.unpack(e+'H', b[off:off+2])[0]
    tags = {}
    for i in range(n):
        t, typ, cnt, val = struct.unpack(e+'HHI4s', b[off+2+12*i: off+14+12*i])
        size = {1:1,2:1,3:2,4:4,5:8,11:4,12:8,16:8}.get(typ,1)*cnt
        raw = val if size<=4 else b[struct.unpack(e+'I',val)[0]: struct.unpack(e+'I',val)[0]+size]
        fmt = {3:'H',4:'I',11:'f',12:'d',16:'Q'}.get(typ)
        tags[t] = struct.unpack(e+fmt*cnt, raw[:size]) if fmt else raw
    w, h = tags[256][0], tags[257][0]
    if 273 in tags:
        data = b''.join(b[o:o+c] for o, c in zip(tags[273], tags[279]))
        vals = list(struct.unpack(e+'f'*(w*h), data[:4*w*h]))
    else:
        tw, th = tags[322][0], tags[323][0]
        tx = (w + tw - 1)//tw
        vals = [0.0]*(w*h)
        for k,(o,c) in enumerate(zip(tags[324], tags[325])):
            ty_, tx_ = divmod(k, tx)
            tile = struct.unpack(e+'f'*(tw*th), b[o:o+4*tw*th])
            for r in range(th):
                y = ty_*th + r
                if y >= h: break
                for q in range(tw):
                    x = tx_*tw + q
                    if x < w: vals[y*w+x] = tile[r*tw+q]
    return w, h, vals, tags
if __name__ == '__main__':
    w,h,v,t = read(sys.argv[1])
    good=[x for x in v if x>-1000]
    print(w,h,'min',min(good),'max',max(good),'nodata',len(v)-len(good), 'tiepoint', t.get(33922), 'scale', t.get(33550))
