import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

data = [
    {"timestamp":1773764100000,"open":0.03686,"high":0.03696,"low":0.0368,"close":0.03696,"volume":86},
    {"timestamp":1773764700000,"open":0.03696,"high":0.03699,"low":0.03696,"close":0.03699,"volume":43},
    {"timestamp":1773765000000,"open":0.03699,"high":0.03701,"low":0.03701,"close":0.03701,"volume":12},
    {"timestamp":1773765300000,"open":0.03701,"high":0.03701,"low":0.03699,"close":0.03699,"volume":23},
    {"timestamp":1773765900000,"open":0.03699,"high":0.03705,"low":0.03699,"close":0.03705,"volume":63},
    {"timestamp":1773766200000,"open":0.03705,"high":0.03704,"low":0.03685,"close":0.03693,"volume":189},
    {"timestamp":1773768000000,"open":0.03693,"high":0.03702,"low":0.037,"close":0.03701,"volume":98},
    {"timestamp":1773768300000,"open":0.03701,"high":0.03697,"low":0.0368,"close":0.0368,"volume":238},
    {"timestamp":1773768900000,"open":0.0368,"high":0.03697,"low":0.03697,"close":0.03697,"volume":19},
    {"timestamp":1773769500000,"open":0.03697,"high":0.03692,"low":0.03677,"close":0.03677,"volume":116},
    {"timestamp":1773770100000,"open":0.03677,"high":0.03695,"low":0.03686,"close":0.03692,"volume":109},
    {"timestamp":1773771000000,"open":0.03692,"high":0.0369,"low":0.03674,"close":0.03674,"volume":257},
    {"timestamp":1773771300000,"open":0.03674,"high":0.03692,"low":0.03692,"close":0.03692,"volume":35},
    {"timestamp":1773771600000,"open":0.03692,"high":0.03691,"low":0.03661,"close":0.03661,"volume":319},
    {"timestamp":1773771900000,"open":0.03661,"high":0.03671,"low":0.03667,"close":0.03671,"volume":24},
    {"timestamp":1773772200000,"open":0.03671,"high":0.03681,"low":0.03671,"close":0.03681,"volume":324},
    {"timestamp":1773772500000,"open":0.03681,"high":0.03686,"low":0.03681,"close":0.03686,"volume":459},
    {"timestamp":1773772800000,"open":0.03686,"high":0.03703,"low":0.03686,"close":0.03703,"volume":288},
    {"timestamp":1773773100000,"open":0.03703,"high":0.03706,"low":0.03703,"close":0.03706,"volume":47},
    {"timestamp":1773773400000,"open":0.03706,"high":0.03706,"low":0.03705,"close":0.03705,"volume":25},
    {"timestamp":1773773700000,"open":0.03705,"high":0.03699,"low":0.03696,"close":0.03696,"volume":45},
    {"timestamp":1773774000000,"open":0.03696,"high":0.03703,"low":0.03702,"close":0.03702,"volume":58},
    {"timestamp":1773774300000,"open":0.03702,"high":0.03702,"low":0.03681,"close":0.03681,"volume":320},
    {"timestamp":1773774600000,"open":0.03681,"high":0.03681,"low":0.03671,"close":0.03681,"volume":432},
    {"timestamp":1773775200000,"open":0.03681,"high":0.03684,"low":0.03671,"close":0.03671,"volume":376},
    {"timestamp":1773775500000,"open":0.03671,"high":0.0367,"low":0.03652,"close":0.03667,"volume":1435},
    {"timestamp":1773775800000,"open":0.03667,"high":0.03664,"low":0.03664,"close":0.03664,"volume":7},
    {"timestamp":1773776100000,"open":0.03664,"high":0.03662,"low":0.0366,"close":0.0366,"volume":33},
    {"timestamp":1773776400000,"open":0.0366,"high":0.03666,"low":0.0365,"close":0.03654,"volume":192},
    {"timestamp":1773776700000,"open":0.03654,"high":0.03655,"low":0.03636,"close":0.03652,"volume":51},
    {"timestamp":1773777600000,"open":0.03652,"high":0.03656,"low":0.03652,"close":0.03656,"volume":240},
    {"timestamp":1773777900000,"open":0.03656,"high":0.03656,"low":0.03635,"close":0.0365,"volume":188},
    {"timestamp":1773778200000,"open":0.0365,"high":0.03657,"low":0.0365,"close":0.03657,"volume":226},
    {"timestamp":1773778500000,"open":0.03657,"high":0.03659,"low":0.03659,"close":0.03659,"volume":36},
    {"timestamp":1773778800000,"open":0.03659,"high":0.03659,"low":0.03659,"close":0.03659,"volume":24},
    {"timestamp":1773779100000,"open":0.03659,"high":0.03657,"low":0.03657,"close":0.03657,"volume":10},
    {"timestamp":1773779400000,"open":0.03657,"high":0.03672,"low":0.03659,"close":0.03672,"volume":358},
    {"timestamp":1773779700000,"open":0.03672,"high":0.03672,"low":0.03672,"close":0.03672,"volume":25},
    {"timestamp":1773780000000,"open":0.03672,"high":0.03676,"low":0.03672,"close":0.03676,"volume":178},
    {"timestamp":1773780300000,"open":0.03676,"high":0.03672,"low":0.03672,"close":0.03672,"volume":0},
    {"timestamp":1773780600000,"open":0.03672,"high":0.03679,"low":0.03657,"close":0.03657,"volume":354},
    {"timestamp":1773780900000,"open":0.03657,"high":0.03673,"low":0.03665,"close":0.03671,"volume":315},
    {"timestamp":1773781200000,"open":0.03671,"high":0.03667,"low":0.03667,"close":0.03667,"volume":10},
    {"timestamp":1773781800000,"open":0.03667,"high":0.03674,"low":0.03671,"close":0.03674,"volume":83},
    {"timestamp":1773783300000,"open":0.03674,"high":0.03673,"low":0.03673,"close":0.03673,"volume":24},
    {"timestamp":1773783600000,"open":0.03673,"high":0.03675,"low":0.03672,"close":0.03675,"volume":60},
    {"timestamp":1773784200000,"open":0.03675,"high":0.03669,"low":0.03668,"close":0.03668,"volume":36},
    {"timestamp":1773784500000,"open":0.03668,"high":0.03664,"low":0.03659,"close":0.03659,"volume":260},
    {"timestamp":1773784800000,"open":0.03659,"high":0.03668,"low":0.03655,"close":0.03655,"volume":381},
    {"timestamp":1773785400000,"open":0.03655,"high":0.03666,"low":0.03666,"close":0.03666,"volume":17},
]

times = [datetime.fromtimestamp(d['timestamp']/1000) for d in data]
opens = [d['open'] for d in data]
highs = [d['high'] for d in data]
lows = [d['low'] for d in data]
closes = [d['close'] for d in data]
volumes = [d['volume'] for d in data]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                gridspec_kw={'height_ratios': [3, 1]},
                                facecolor='#1e1e2e')
ax1.set_facecolor('#1e1e2e')
ax2.set_facecolor('#1e1e2e')

times_num = mdates.date2num(times)
candle_width = 3.5 * 60 / (24 * 3600)

for t, o, h, l, c in zip(times_num, opens, highs, lows, closes):
    color = '#26a69a' if c >= o else '#ef5350'
    ax1.plot([t, t], [l, h], color=color, linewidth=0.8, zorder=2)
    body_bottom = min(o, c)
    body_height = max(abs(c - o), 0.000001)
    rect = plt.Rectangle((t - candle_width/2, body_bottom), candle_width, body_height,
                          facecolor=color, edgecolor=color, linewidth=0.5, zorder=3)
    ax1.add_patch(rect)

ax1.set_xlim(times_num[0] - candle_width, times_num[-1] + candle_width)
ax1.set_ylim(min(lows) * 0.9998, max(highs) * 1.0002)
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax1.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
ax1.tick_params(colors='#aaaaaa', labelsize=8)
ax1.yaxis.tick_right()
ax1.set_ylabel('Price (USD)', color='#aaaaaa', fontsize=9)
ax1.yaxis.set_label_position('right')
ax1.grid(True, alpha=0.15, color='#aaaaaa', linestyle='--', linewidth=0.5)
for spine in ax1.spines.values():
    spine.set_edgecolor('#444444')

vol_colors = ['#26a69a' if c >= o else '#ef5350' for o, c in zip(opens, closes)]
ax2.bar(times_num, volumes, width=candle_width, color=vol_colors, alpha=0.8)
ax2.set_xlim(times_num[0] - candle_width, times_num[-1] + candle_width)
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax2.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30]))
ax2.tick_params(colors='#aaaaaa', labelsize=8)
ax2.yaxis.tick_right()
ax2.set_ylabel('Volume', color='#aaaaaa', fontsize=9)
ax2.yaxis.set_label_position('right')
ax2.grid(True, alpha=0.15, color='#aaaaaa', linestyle='--', linewidth=0.5)
for spine in ax2.spines.values():
    spine.set_edgecolor('#444444')

fig.suptitle('DIME/USD  —  5m Chart (Last 6 Hours)', color='white',
             fontsize=13, fontweight='bold', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.97])

output = '/Users/RobTerpilowski/Code/PythonProjects/news-trader/dime_usd_5m.png'
plt.savefig(output, dpi=150, bbox_inches='tight', facecolor='#1e1e2e')
print(f"Saved: {output}")
