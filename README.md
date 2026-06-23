### YES I HAVE GOTTEN AI TO GENERATE AN ENTIRE README FILE but b4 tht for all my fellow humans that are not geeked out nerds:
deep chart cra**ed : Not the latest version (STILL HAS ALL MAJOR INDICATORS/FEATURES!)

Lemme explain;
basically the `bridge_mitm_proxy.py` file connects the data feed (makes your demo AMP / CQG guys) think this is the real version.

this file: `vol_hist_server.py` : fools deepcharts into thinking its actually connecting to its own server ( TO GET HISTORICAL DATA)

This file: `ipc_mitm.py` : ion even know bro i got ai to fix an error and it used this. I'm pretty sure i dont even run this while using deep charts.

This file `run_patched_deepchart.ps1` runs deepcharts and the bridge (data feed connector)


Now to connect to the data feed and make demo amp/cqg think its the real version we first need to intercept the connection.

We do this by adding that IP into our hosts file. (you can search more abt this if you want.)
Basically when we do that we can intercept the connection. Keep in mind if you use AMP/CQG on MW or QT, 
then it won't work. But ofc im a geeky mf I make mw studies and QT indicators, so i made this script which removes it from the hosts file. 

# Only rerun this file if you need to use Motivewave or quanttower using AMP/CQG demo accounts. (when you want to use deepcharts with amp cqg run this file again)
`toggle-proxy-hosts.bat` RUN THIS AS ADMIN. It will remove those IPs and allow you to use your other software *AS usual*.



`start_servers.ps1` - this basically runs the `bridge_mitm_proxy.py`, `vol_hist_server.py`, and `run_patched_deepchart.ps1` all 3 processes required to use deepcharts!
Run this file as ADMIN!

`toggle-proxy-hosts.bat` - adds/removes the IPs we need to the HOSTS file. Run this once at the start to setup hosts. Run again to toggle off (when you need MW/QT).


Okay step by step now my didlers:

## MODE 1: CQG / AMP Demo (Default)

1. Install python 3.14
2. Open powershell in the directory of wherever you've placed this entire FOLDER!
3. run `pip install -r requirements.txt` this will setup all the python requirements you need. so your bridge and vol servers will actually work LMFAO.
4. Right click `toggle-proxy-hosts.bat` and run as admin. Run it again (toggle on).
5. Set this env var so the bridge uses python 3.14 for CQG mode:
   ```
   $env:PYTHON_EXE = "python"
   ```
6. in the same command prompt type `start_servers.ps1`. This should get your deepcharts to run.
7. Go to connections, add a new one. From data feed select CQG, turn on `use demo credentials`. Enter your AMP CQG demo acc details.

## MODE 2: Rithmic Data (Free Trial — No Broker Needed)

Rithmic gives you a 14-day free paper trading account. No AMP/CQG broker required.

### Extra Requirements for Rithmic Mode:
- **Python 3.13** (Rithmic python library needs this specific version)
- **Rithmic trial account** from https://rithmic.com (click free trial, get username + password)

### Step by Step:

1. Install **Python 3.13** from https://www.python.org/downloads/release/python-3130/
2. Open powershell as admin in the project folder
3. `pip install -r requirements.txt`
4. Install the Rithmic library:
   ```
   pip install async_rithmic
   ```
5. Right click `toggle-proxy-hosts.bat` → Run as admin. Run it again (toggle on).
   This now also redirects `rituz00100.rithmic.com` to your machine.
6. Set these env vars BEFORE running start_servers:
   ```powershell
   $env:RITHMIC_MODE = "1"
   $env:RITHMIC_USER = "your_rithmic_trial_username"
   $env:RITHMIC_PASSWORD = "your_rithmic_trial_password"
   ```
   (Optional: `$env:RITHMIC_SYSTEM = "RithmicPaperTradingChicago"`)
7. Run `start_servers.ps1`
8. In Deepchart, add a CQG connection with your **Rithmic** credentials (Deepchart still speaks CQG protocol — the bridge translates it to Rithmic behind the scenes)

### How It Works:
The bridge detects `RITHMIC_MODE=1` and instead of forwarding your connection to CQG servers, it runs the Rithmic translator locally. Your Deepchart still thinks it's talking CQG — it gets symbol resolution, real-time ticks, and market data all translated from Rithmic Protocol API. No CQG demo account needed.

### Switching Back to CQG Mode:
```powershell
$env:RITHMIC_MODE = "0"
```
Or just don't set the env var.

## NOTE: WHENEVER YOU WANT TO USE MW OR QT WITH AMP/CQG DEMO CREDITNALS YOU HAVE TO RUN `toggle-proxy-hosts.bat` AS ADMIN!
### THIS WILL UNDO THE HOST FILE CHANGES!
### WHEN U WANT TO RUN DEEEPCHARTS AGAIN, RUN THE SAME FILE (`toggle-proxy-hosts.bat`) AS ADMIN AGAIN





# Deepchart CQG/Rithmic Proxy Toolkit

This tool lets you use **Deepchart** (a charting program) with either **CQG** (AMP demo account) or **Rithmic** (free trial — no broker needed).
It runs a "man-in-the-middle" proxy that sits between Deepchart and your data source so you can
inspect and modify the data flowing between them.

---

## What You Need

- **A Windows computer** (Deepchart only runs on Windows)
- **Python 3.10 or newer** installed (see below — 3.13 required for Rithmic)
- **Either:** CQG trading account (AMP demo) **OR** Rithmic free trial account
- **Deepchart** already installed
- **Administrator access** on your computer (to run the proxy)

---

## Step 1 — Install Python

### For CQG mode (easy):
1. Go to https://www.python.org/downloads/
2. Download Python **3.14**
3. Check **"Add Python to PATH"** during install

### For Rithmic mode:
You need **Python 3.13 specifically** — the Rithmic python library only works on 3.13.
1. Download from https://www.python.org/downloads/release/python-3130/
2. Install normally, **do NOT** add to PATH (to avoid conflict with 3.14)
3. Note the install path: `C:\Users\YourName\AppData\Local\Programs\Python\Python313\python.exe`

---

## Step 2 — Download These Files

Place all the files from this project into a folder on your computer, for example:
`C:\Users\YourName\deepchart-proxy`

---

## Step 3 — Install the Required Packages

Open **PowerShell as Administrator** (right-click Start → "Terminal (Admin)").

Navigate to your folder:

```
cd C:\Users\YourName\deepchart-proxy
```

Then run:

```
pip install -r requirements.txt
```

Wait for it to finish.

---

## Step 4 — Redirect Traffic to Your Computer

This step tells Windows to send CQG/Rithmic traffic to your computer instead of the real
servers, so the proxy can intercept it.

**Run `toggle-proxy-hosts.bat` as Administrator.** Run it once to add the entries.
Run it again to remove them (when you need MotiveWave/QuantTower with AMP/CQG).

The hosts file will redirect:
- `demoapi.cqg.com` → your machine
- `api.cqg.com` → your machine  
- `depth-it.historical.deepcharts.com` → your machine
- `data-b.historical.deepcharts.com` → your machine
- `rituz00100.rithmic.com` → your machine (needed for Rithmic mode)

> ⚠️ **If your computer restarts or changes networks**, your IP might change.
> Re-run `toggle-proxy-hosts.bat` to fix it.

---

## Step 5 — Install the Security Certificate (One-Time)

The proxy creates its own security certificate so it can decrypt traffic.
You need to tell Windows to trust it.

1. Open your folder
2. Open the folder called `mitm_ca`
3. **Right-click** the file `ca.pem` → **Install Certificate**
4. Choose **Local Machine** → click Next
5. Choose **Place all certificates in the following store** → click Browse
6. Select **Trusted Root Certification Authorities** → OK → Next → Finish
7. Click Yes if Windows asks

**Don't see `mitm_ca` folder?** Run the proxy once (Step 6), it will create the
folder and certificates automatically. Then come back to this step.

---

## Step 6 — Run Everything (One Command)

```powershell
start_servers.ps1
```

Run this **as Administrator**. It will:
1. Kill old python/Deepchart processes
2. Start the historical data server
3. Start the bridge MITM proxy
4. Launch VolumetricaBridge (Deepchart's bridge)
5. Launch Deepchart

### For Rithmic mode, set env vars first:
```powershell
$env:RITHMIC_MODE = "1"
$env:RITHMIC_USER = "your_rithmic_username"
$env:RITHMIC_PASSWORD = "your_rithmic_password"
start_servers.ps1
```

The script auto-detects Rithmic mode and uses Python 3.13.

---

## Step 7 — Connect in Deepchart

Go to **Connections → Add New → Data Feed: CQG**
- **CQG mode:** Check "Use demo credentials", enter your AMP CQG demo username/password
- **Rithmic mode:** Enter your Rithmic trial username/password (Deepchart thinks it's CQG, the bridge translates)

---

## What Each File Does

| File | What it's for |
|------|--------------|
| `bridge_mitm_proxy.py` | The main proxy — CQG mode forwards to AMP, Rithmic mode translates locally |
| `rithmic_translator.py` | CQG↔Rithmic protocol translator (only used in RITHMIC_MODE) |
| `vol_hist_server.py` | Handles historical chart data (so charts don't hang) |
| `ipc_mitm.py` | (Optional) Monitors communication between Deepchart and its bridge |
| `run_patched_deepchart.ps1` | Launches Deepchart with required patches |
| `mitm_ca/` | Folder with security certificates (auto-created) |
| `cqg_test/` | CQG protobuf definitions the proxy uses to understand CQG's data format |
| `logs/` | Folder where log files are saved (auto-created) |
| `requirements.txt` | List of packages to install |
| `toggle-proxy-hosts.bat` | Toggles hosts file on/off (run as admin) |
| `toggle-proxy-hosts.ps1` | PowerShell version of the hosts toggle |
| `start_servers.ps1` | Starts everything (run as admin) |

---

## Troubleshooting

### "Permission denied" or "Can't bind to port 443"
Run PowerShell **as Administrator**.

### "Python is not recognized"
You didn't check "Add Python to PATH" during installation.

### "No module named..."
You forgot to run `pip install -r requirements.txt`.

### Bridge starts but Rithmic translator fails
Check that:
- Python 3.13 is installed
- `pip install async_rithmic` was run under Python 3.13
- `RITHMIC_USER` and `RITHMIC_PASSWORD` env vars are set

### Deepchart connects but no data shows
Your hosts file might have the wrong IP address. Re-run `toggle-proxy-hosts.bat`.

### The proxy starts but Deepchart won't connect
Try closing everything and starting fresh:
```powershell
Get-Process -Name python,Deepchart,Volumetrica* -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## Credits

This is for **educational purposes only**. Use with your own accounts.
Rithmic 14-day free trial: https://rithmic.com
