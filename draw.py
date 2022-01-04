from colorsys import rgb_to_hls
import datetime as dt
from pytz import timezone

from matplotlib.colors import ListedColormap
import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plot_styles
from skyfield import almanac
from skyfield.api import N, W, wgs84, load


plt.style.use('blog')
plt.rcParams['font.sans-serif'] = ['Noway'] + plt.rcParams['font.sans-serif']

cmap = ListedColormap(['#021130', '#5e2c5b', '#b94c64', '#f68b53', '#fde050'])

# Figure out local midnight.
zone = timezone('Europe/London')

# Specify our location and lookups
eph = load('de421.bsp')
leith = wgs84.latlon(55.975464 * N, -3.1800574 * W)

f = almanac.dark_twilight_day(eph, leith)
ts = load.timescale()

dates = pd.date_range(
    start='2021/12/31 00:00:00', freq='1D', periods=370, tz='Europe/London'
)

all_records = []
for first_day, second_day in zip(dates, dates[1:]):
    t0 = ts.from_datetime(first_day)
    t1 = ts.from_datetime(second_day)
    times, events = almanac.find_discrete(t0, t1, f)

    for t, e in zip(times, events):
        all_records.append((t.astimezone(zone), almanac.TWILIGHTS[e], e))

all_stages = pd.DataFrame(all_records, columns=['StageStart', 'Stage', 'StageID'])
all_stages['DateTime'] = all_stages['StageStart'].dt.floor('1min')

all_minutes = all_stages.set_index('DateTime').resample('1min').ffill().reset_index()

all_minutes['Date'] = all_minutes['DateTime'].dt.date

# This is a bit of a bodge. 
all_minutes['Time'] = pd.to_datetime('2000-01-01 ' + all_minutes['DateTime'].dt.strftime('%H:%M:%S'))

# Filter down to just 2022
all_minutes = all_minutes[all_minutes['DateTime'].between('2022/01/01 00:00:00', '2022/12/31 23:59:59')]

# Get the last day's values for labelling purposes
last_day = all_minutes[all_minutes['Date'].eq(all_minutes['Date'].max())].copy()

last_day['Period'] = np.where(
    last_day['Stage'].eq('Day'), 
    'Day', last_day['Stage'] + '_' + last_day['DateTime'].dt.strftime('%p')
)

labels = last_day.groupby('Period', as_index=False)\
                 .agg({'Time': 'mean', 'Date': 'first', 'StageID': 'first'})

# Pivot table to use in our colourmesh
pivoted = all_minutes.pivot_table(index='Time', columns='Date', values='StageID')

fig, ax = plt.subplots(figsize=(15, 6))

fig.subplots_adjust(left=0.04, right=0.9, top=0.75, bottom=0.12)

ax.pcolormesh(
    pivoted.columns, pivoted.index,
    pivoted.values, # cmap='magma'
    cmap=cmap, vmin=0, vmax=4
)

# Make axis labels prettier
ax.yaxis.set_major_locator(mdates.HourLocator(byhour=range(1, 24, 2)))
ax.yaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
ax.yaxis.set_minor_locator(mdates.HourLocator(interval=1))

ax.xaxis.set_major_locator(mdates.DayLocator(1))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
ax.xaxis.set_minor_locator(mdates.WeekdayLocator(1))

for side in ('left', 'right', 'top', 'bottom'):
    ax.spines[side].set_visible(False)

# Set title
title = ax.set_title(
    'Sunshine on Leith', size=55, y=1.25, va='center', ha='center',
    weight='bold', color=cmap(4)
)

# Use the colourmap for a nice trailing effect
shadows = [
    pe.SimplePatchShadow(offset=(2.5*(4-x), -2.5*(4-x)), shadow_rgbFace=cmap(x), alpha=1)
    for x in range(4)
]

title.set_path_effects([
    *shadows,
    pe.Stroke(linewidth=2, foreground=plt.rcParams['figure.facecolor']),
    pe.Normal()
])

ax.annotate(
    'Sunrise and sunset times in Leith across 2022', size=14,
    xy=(0.5, 1.12), xycoords='axes fraction', ha='center', va='center'
)

# Label the stages
for _, row in labels.iterrows():
    current_colour = cmap(row['StageID'] / 4)
    lightness = rgb_to_hls(*current_colour[:-1])[1]
    outline = 'black' if lightness >= 0.2 else '#656565'
    stage_label = ax.annotate(
        row['Period'].split('_')[0],
        xy=(row['Date'], row['Time']),
        ha='left', va='center', xytext=(10, 0), textcoords='offset pixels', 
        size='medium', c=current_colour, weight='bold'
    )

    stage_label.set_path_effects([
        pe.Stroke(linewidth=2, foreground=outline, alpha=1), pe.Normal()
    ])

# Label summer and winter solstices (solstii? Who knows.)
datetimes, indices = almanac.find_discrete(
    ts.utc(2022, 1, 1), ts.utc(2022, 12, 31),
    almanac.seasons(eph)
)

for time, idx in zip(datetimes, indices):
    event = almanac.SEASON_EVENTS[idx]
    if 'solstice' in event.lower():
        dt = time.astimezone(zone)
        dt_string = dt.strftime('%d %B')
        ax.axvline(x=dt.date(), c=plt.rcParams['axes.edgecolor'], ls='--')
        ax.annotate(
            f'{event} ({dt_string})', xy=(dt.date(), 1), 
            xycoords=('data', 'axes fraction'),
            va='bottom', ha='center',
            xytext=(0, 5), textcoords='offset pixels',
            size='small'
        )

# Put the grid on!
ax.grid(axis='both', which='major', ls=':', alpha=0.5)

# Callback
ax.annotate(
    r'For more information visit ruszkow.ski/graphs/2022-01-04-sunshine-on-leith/',
    xy=(0, 0), xycoords='figure fraction', xytext=(10, 10), textcoords='offset pixels',
    size='x-small', alpha=0.75
)

plt.savefig('sunshine-on-leith.png')
