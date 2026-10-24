import json, math, random, datetime as dt, sys
random.seed(7)
N = 365
end = dt.date(2026, 10, 26)
days = [end - dt.timedelta(days=N-1-i) for i in range(N)]
TODAY = N - 3  # 2026-10-24
def winter(d):
    return 0.5 + 0.5*math.cos(2*math.pi*(d.timetuple().tm_yday - 20)/365)
rain = []
for d in days:
    w = winter(d)
    p = 0.38 + 0.2*w
    r = random.expovariate(1/(3.0 + 3.5*w)) if random.random() < p else 0.0
    rain.append(round(r, 1))
over = {dt.date(2026,10,16):3.2, dt.date(2026,10,17):0, dt.date(2026,10,18):0.7, dt.date(2026,10,19):0.4,
        dt.date(2026,10,20):19.2, dt.date(2026,10,21):8.6, dt.date(2026,10,22):3.6, dt.date(2026,10,23):19.8,
        dt.date(2026,10,24):11.8, dt.date(2026,10,25):4.5, dt.date(2026,10,26):1.2, dt.date(2026,8,12):31.0}
for i, d in enumerate(days):
    if d in over: rain[i] = over[d]
    elif dt.date(2026,10,1) <= d <= dt.date(2026,10,15): rain[i] = round(min(rain[i], 1.0)*0.5, 1)
fast = 0.0; slow = 0.55; rows = []
for i, d in enumerate(days):
    R = rain[i]; w = winter(d)
    evap = 0.004 + 0.012*(1 - w)
    slow = max(0.05, slow*0.985 + 0.0105*R - evap)
    fast = fast*0.55 + 0.035*R
    stage = 1.05 + 0.75*slow + fast            # Osney, m on gauge (dummy)
    foul = 35.5 + (1.5 if d.weekday() < 5 else -1.0) + random.gauss(0, 0.8)
    infil = 6 + 48*max(0.0, slow - 0.45)
    rq = 1.6*R + 0.9*(rain[i-1] if i else 0) + 0.3*(rain[i-2] if i > 1 else 0)
    Q = foul + infil + rq
    rows.append(dict(d=d.isoformat(), rain=R, stage=round(stage, 3), gw=round(slow, 3),
                     foul=round(foul, 2), infil=round(infil, 2), rainq=round(rq, 2), Q=round(Q, 2)))
C = 92.0
for i, r in enumerate(rows):
    noisyQ = r['Q'] + random.gauss(0, 3)
    ex = noisyQ - C
    r['spill'] = 1 if ex > 0 and i <= TODAY else 0
    r['hours'] = round(min(24, 24*ex/(0.30*noisyQ)), 1) if r['spill'] else 0
    sig = lambda z: 1/(1+math.exp(-z))
    qh = r['Q'] + random.gauss(0, 4)
    r['p_bucket'] = round(sig((qh - C)/5.5), 3)
    r['p_gbm'] = round(min(0.99, max(0.01, sig((qh - C)/4.0) + random.gauss(0, 0.05))), 3)
    r['p_rain'] = 0.62 if r['rain'] > 12 else 0.09
    r['p_persist'] = (0.71 if rows[i-1].get('spill') else 0.04) if i else 0.04
# a couple of planted unexplained dry-day spills
for dd, h in [('2026-07-09', 3.5), ('2026-09-02', 6.0), ('2026-06-17', 2.0)]:
    for r in rows:
        if r['d'] == dd: r['spill'] = 1; r['hours'] = h; r['unexplained'] = 1
print('spill days', sum(r['spill'] for r in rows), 'hours', round(sum(r['hours'] for r in rows)),
      'C', C, 'Qmax', max(r['Q'] for r in rows), file=sys.stderr)
for m in range(1, 13):
    sub = [r for r in rows if int(r['d'][5:7]) == m]
    print(m, sum(r['spill'] for r in sub), round(sum(r['infil'] for r in sub)/len(sub), 1), round(max(r['stage'] for r in sub), 2), file=sys.stderr)
print('last 12', [(r['d'][5:], r['rain'], r['spill'], round(r['p_bucket'], 2), r['stage']) for r in rows[-12:]], file=sys.stderr)

sites = [
 dict(id='oxstw', name='Oxford STW (Sandford)', lat=51.7118, lon=-1.2258, gw=0.62, b=0.0, water='Pottery Stream'),
 dict(id='botley', name='West Way, Botley', lat=51.7522, lon=-1.2930, gw=0.35, b=-1.4, water='Seacourt Stream'),
 dict(id='willows', name='The Willows, N Hinksey', lat=51.7464, lon=-1.2832, gw=0.40, b=-1.2, water='Seacourt Stream'),
 dict(id='littlemore', name='Littlemore Low Level', lat=51.7206, lon=-1.2338, gw=0.55, b=-2.4, water='Thames'),
 dict(id='cassington', name='Cassington STW', lat=51.7930, lon=-1.3420, gw=0.45, b=-2.6, water='Thames (Port Meadow upstream)'),
 dict(id='islip', name='Islip STW', lat=51.8226, lon=-1.2380, gw=0.80, b=0.4, water='River Ray'),
 dict(id='wheatley', name='Wheatley STW', lat=51.7470, lon=-1.1380, gw=0.75, b=0.5, water='Wheatley Ditch'),
 dict(id='forest', name='Forest Hill STW', lat=51.7660, lon=-1.1520, gw=0.30, b=-1.8, water='Polecat End Ditch'),
 dict(id='horton', name='Horton-cum-Studley', lat=51.8030, lon=-1.1360, gw=0.55, b=-0.6, water='Danes Brook'),
 dict(id='beckley', name='Beckley STW', lat=51.7955, lon=-1.1880, gw=0.50, b=-1.6, water='Otmoor Lane Ditch'),
]
K = 32
for s in sites:
    ps = []
    for i in range(N-K, N):
        r3 = rows[i]['rain'] + 0.6*rows[i-1]['rain'] + 0.3*rows[i-2]['rain']
        z = (1-s['gw'])*(r3/9 - 1.6) + s['gw']*((rows[i]['gw']-0.6)*7) + s['b']
        p = 1/(1+math.exp(-2.2*z))
        ps.append(round(min(0.98, max(0.01, p + random.gauss(0, 0.015))), 3))
    s['p'] = ps
out = dict(rows=rows, C=C, today=TODAY, sites=sites, K=K)
json.dump(out, open(sys.argv[1], 'w'), separators=(',', ':'))
