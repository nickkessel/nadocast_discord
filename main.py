import pygrib
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.offsetbox import AnchoredText
#from mpl_toolkits.basemap import Basemap
#from mpl_toolkits.basemap import shiftgrid
from datetime import datetime, timezone, timedelta
from metpy.plots import USCOUNTIES
import requests
import numpy as np
from discord_webhook import DiscordWebhook, DiscordEmbed

#loading the .env file
from dotenv import load_dotenv
from pathlib import Path
import os
cwd = Path(os.getcwd())
env_path = cwd / '.env'
load_dotenv(env_path)
webhook_url = os.getenv('DISCORD_WEBHOOK')

#times when model runs become available
AVAILABLE_00Z = '03:30'
AVAILABLE_12Z = '15:35'
AVAILABLE_18Z = '21:05'


#DOMAINS
CONUS = ['CONUS', -127, -65, 25, 50]
CINCY = ['Cincinnati', -87.5, -82, 37.5, 41.5]
MW_GL = ['Midwest_Great_Lakes', -97.5, -79.5, 35, 48]
C_PLAINS = ['Central_Plains', -105.5, -93, 34.5, 44]
NE = ['Northeast_US', -80.5, -67.5, 39.5, 47.5]
MI = ['Michigan', -91, -82, 41.5, 47.5]

DATA_MIN = 0
DATA_MAX = 50
fixed_levels = np.arange(DATA_MIN, DATA_MAX, 0.25)

rgb_colors = []
with open('data/colortable.pal', 'r') as file:
    for line in file:
        if line.startswith('SolidColor:'):
            parts = line.split()
            
            # extract r, g, b columns and normalize
            r = float(parts[2]) / 255.0
            g = float(parts[3]) / 255.0
            b = float(parts[4]) / 255.0
            rgb_colors.append((r, g, b))

# create the custom colormap
custom_cmap = LinearSegmentedColormap.from_list('custom_dp', rgb_colors)

def current_utc_time():
    now = datetime.now(timezone.utc)
    
    date_no_day = now.strftime("%Y%m")
    date_formatted = now.strftime("%Y%m%d")
    time_formatted = now.strftime("%H:%M")
    print(date_formatted,time_formatted)
    return date_no_day, date_formatted, time_formatted

def get_latest_run(short_date, date, time):
    if time > AVAILABLE_18Z:
        model_run = '18'
        model_run2 = '18'
        fh = '01-17'
    elif time > AVAILABLE_12Z:
        model_run = '12'
        model_run2 = '12'
        fh = '01-23'
    elif time > AVAILABLE_00Z:
        model_run = '0'
        model_run2 = '00'
        fh = '12-35'
    else: #fallback to using the previous day's 18z run should the script be ran after 00z and before 0330z (when the 00z for the current day drops)
        print('are you running this before 0330z on the utc day? using previous UTC day run')
        now = datetime.now(timezone.utc)
        adj_date_time = now - timedelta(days=1)
        short_date = adj_date_time.strftime("%Y%m")
        date = adj_date_time.strftime("%Y%m%d")
        model_run = '18'
        model_run2 = '18'
        fh = '01-17'
        
        
    TOR_URL = f'http://data.nadocast.com/{short_date}/{date}/t{model_run}z/nadocast_2024_preliminary_models_conus_tornado_{date}_t{model_run2}z_f{fh}.grib2'
    print(f'Link to latest run: {TOR_URL}, downloading now')
    response = requests.get(TOR_URL)
    file_path = 'data/latest_run.grib2'
    if response.status_code == 200:
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print('file downloaded successfully')
    else:
        print('error downloading file')
    return model_run

def generate_map(domain, model_run):
    fig, ax = plt.subplots(figsize=(12, 8), subplot_kw={'projection': ccrs.PlateCarree()})

    filepath = 'data/latest_run.grib2'
    grbs = pygrib.open(filepath)
    grb = grbs.select(name = 'Tornado probability')[0]
    data = grb.values
    lats, lons = grb.latlons()
    print("Processed grib data")

    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS, linestyle=":")
    ax.add_feature(cfeature.STATES, linestyle = "-", linewidth = 1)
    ax.add_feature(USCOUNTIES, linewidth = 0.3)
    print("Added basemap features")
    trans = ccrs.PlateCarree()._as_mpl_transform(ax)

    mesh = ax.contourf(lons, lats, data, levels = fixed_levels, cmap = custom_cmap, transform = trans, vmin = DATA_MIN, vmax = DATA_MAX)
    domain = domain
    ax.set_extent([domain[1], domain[2], domain[3], domain[4]], crs = ccrs.PlateCarree())
    mask = (lons >= domain[1]) & (lons <= domain[2]) & (lats >= domain[3]) & (lats <= domain[4])
    visible_data = np.where(mask, data, -np.inf)
    max_val = np.round(np.max(visible_data), 3)
    print(max_val)
    max_idx = np.unravel_index(np.argmax(visible_data), visible_data.shape)
    max_lat = lats[max_idx]
    max_lon = lons[max_idx]
    print(max_lat, max_lon)
    ax.plot(max_lon, max_lat, marker = '.', color = 'black', markeredgecolor = 'white', markersize = 7, transform = ccrs.PlateCarree())
    max_box = AnchoredText(        
        f'Max prob: {max_val}%',
        loc = 'upper left',
        prop = dict(fontsize=12, fontweight = 'bold'),
        frameon=True,
        borderpad=0.5
    )

    max_box.patch.set_facecolor('white')
    max_box.patch.set_alpha(0.8)
    max_box.patch.set_edgecolor('black')
    ax.add_artist(max_box)
    
    domain_box = AnchoredText(        
        f'{domain[0]} domain',
        loc = 'upper right',
        prop = dict(fontsize=10, fontweight = 'bold'),
        frameon=True,
        borderpad=0.5
    )

    domain_box.patch.set_facecolor('white')
    domain_box.patch.set_alpha(0.8)
    domain_box.patch.set_edgecolor('black')
    ax.add_artist(domain_box)
    
    #ax.text(0.01, 0.97, f'Max prob: {max_val}%', transform = ax.transAxes, ha = 'left', va = 'top', fontweight = 'bold', bbox=dict(facecolor='white', alpha = 0.8, edgecolor='black'))
    #ax.annotate(f'Max prob: {max_val}%', xy = (0.01,0.95), xytext = (0,0), fontsize = 10, xycoords = 'axes fraction', textcoords= 'offset points', 
     #           bbox = dict(facecolor='white', alpha = 0.8))
    divider = make_axes_locatable(ax)
    cax = divider.append_axes('bottom', size = '5%', pad = 0.05, axes_class= plt.Axes)
    print('generated annotations')

    plt.colorbar(mesh, cax=cax, orientation = 'horizontal', label = f'Chance of a tornado w/in 25mi of a point ({grb.units})')
    plt.title(f'Nadocast {grb.name} - {grb.validDate} - {model_run}z run')
    grbs.close
    save_path = f'output/fcst_{current_date}_{model_run}z_run_TOR_{domain[0]}.png' #a known bug is that for the current_date, this uses the 'uncorrected' value, so if it is really the NEXT utc day, and the script is ran before 0330z, then the value for the date on the plot is actually a day ahead. probably not a hard fix but not bothered to do it rn
    plt.savefig(save_path, bbox_inches = 'tight', pad_inches = 0.2, dpi = 300)
    print(f"Saved to {save_path}")
    plt.close()
    now = datetime.now(timezone.utc)
    product_text = f'Nadocast 2024 Model - Tor Prob ({domain[0]}) - {current_date}_{model_run}z run\nMax probability is {max_val}%, at {max_lat:.2f},{max_lon:.2f}\nMap generated at {now.strftime("%Y/%m/%d, %H:%M:%Sz")}'
    return product_text, save_path

def send_to_discord(webhooks, text, img='data/test.jpg'): 
    """send text and images to a set of webhooks

    Args:
        webhooks (list): list of webhooks to send to
        text (str): the text to be sent
        img (str, optional): the filepath to the image. defaults to no image. Defaults to ''.
    """    
    for hook in webhooks:
        webhook = DiscordWebhook(url = hook, content = text)
        with open(img, 'rb') as f:
            webhook.add_file(file=f.read(), filename='forecast_map.png')
        try:
            response = webhook.execute()
            print(f'successfully sent to webhook {webhooks.index(hook) + 1} of {len(webhooks)}!')
        except Exception as e:
            print(f'Error!!! : {e}')
os.makedirs('output', exist_ok= 'True')
date_no_day, current_date, current_time = current_utc_time()
run_hour = get_latest_run(date_no_day,current_date,current_time)
domains_list = [CONUS, MW_GL, C_PLAINS, NE, CINCY, MI]
for domain in domains_list:
    caption, img_save_path = generate_map(domain, run_hour)
    send_to_discord([webhook_url], caption, img_save_path)