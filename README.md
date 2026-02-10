# **Linua Updater**

Modern DLC management tool for The Sims 4  
© 2024–2025 l1ntol — All Rights Reserved

---

## **Overview**

**Linua Updater** is a lightweight Windows application that simplifies installation, management, and verification of DLC content for *The Sims 4*.  
The tool automates game folder detection, downloading, extraction, and validation while maintaining high reliability and clear, predictable behavior.

---

## **Features**

* **Automatic Sims 4 folder detection** via Windows Registry and path scanning
* **Auto-update checker** — Notifies when new versions are available
* **One-click DLC installation** with parallel download support
* **Export Logs** — Save installation logs for troubleshooting
* **Secure and verified download sources**
* **Real-time progress tracking** with detailed statistics
* **Smart network diagnostics** with proxy detection for RU/UA users
* **Download resume support** for interrupted downloads
* **Automatic 7-Zip detection** for multipart archives
* **Minimal dark interface** designed for comfort

---

## **System Requirements**

* Windows 10 or Windows 11 (64-bit)
* Installed copy of *The Sims 4*
* ~80 GB free disk space (for full DLC installation)
* Stable Internet connection
* Administrator privileges (for Program Files installations)

---

## **How to Use**

1. Download the latest **LinuaUpdater.exe** from the [Releases](https://github.com/l1ntol/linua-updater/releases) page
2. Run the application (no installation required)
3. Allow auto-update check on first launch
4. Select your Sims 4 folder (or use **Auto Detect**)
5. Choose the DLC you want to install
6. Press **Update** and wait for completion
7. **Important:** Run DLC Unlocker to activate installed DLC

---

## **Latest Updates**

**Current Version:** Check [Releases](https://github.com/l1ntol/linua-updater/releases) for the latest version and changelog.

**Recent Improvements:**
* Auto-update notifications on startup
* Export Logs functionality for bug reports
* Enhanced game detection through Windows Registry
* Simplified DLC selector interface
* Improved log readability and color coding
* Better network diagnostics for restricted regions

For detailed changelog, see individual release notes.

---

# ⚠️ **Important Notice (All Users)**

### **EP03 — City Living**
### **EP06 — Get Famous**

These two DLC **cannot be downloaded automatically by Linua Updater**.

This is a **global technical limitation**:

* The available mirrors do **not support direct programmatic downloads**
* Both DLC are distributed as **multipart archives (.7z.001 / .002)**
* They require **manual confirmation**, which prevents automated retrieval

Because of this, **EP03 and EP06 must be installed manually by all users**, regardless of region or VPN.

A complete manual installation guide is provided below.

---

# **Manual Installation (EP03 & EP06)**

### **1. Download the archives**

Official verified mirrors:

* **EP03 — City Living**  
  [https://gofile.io/d/7zzJA5](https://gofile.io/d/7zzJA5)

* **EP06 — Get Famous**  
  [https://gofile.io/d/PJ6wc4](https://gofile.io/d/PJ6wc4)

---

### **2. Extract both archives**

Each archive contains exactly two folders:

```
EP03 (or EP06)
_Installer
```

---

### **3. Place the folders into your Sims 4 directory**

Your game folder is usually located at:

```
C:\Program Files (x86)\Steam\steamapps\common\The Sims 4
```

Copy both folders into **The Sims 4** directory.

If Windows asks:  
**"Replace the files in the destination?"** → choose **Replace**.

Repeat for the second DLC.

---

### **Correct folder structure after installation**

```
The Sims 4
├── EP03
├── EP06
├── _Installer
├── Game
├── Data
└── ...
```

---

### **4. Continue installation through Linua Updater**

* Open **Linua Updater**
* Select any other DLC you need
* Press **Update**

---

## **Supported DLC**

### **Expansion Packs**

* EP01 — Get to Work
* EP02 — Get Together
* EP03 — City Living ⚠️ *Manual installation required*
* EP04 — Cats & Dogs
* EP05 — Seasons
* EP06 — Get Famous ⚠️ *Manual installation required*
* EP07 — Island Living
* EP08 — Discover University
* EP09 — Eco Lifestyle
* EP10 — Snowy Escape
* EP11 — Cottage Living
* EP12 — High School Years
* EP13 — Growing Together
* EP14 — Horse Ranch
* EP15 — For Rent
* EP16 — Lovestruck
* EP17 — Life and Death
* EP18 — Businesses and Hobbies
* EP19 — Enchanted by Nature
* EP20 — Adventure Awaits

---

### **Game Packs**

* GP01 — Outdoor Retreat
* GP02 — Spa Day
* GP03 — Dine Out
* GP04 — Vampires
* GP05 — Parenthood
* GP06 — Jungle Adventure
* GP07 — StrangerVille
* GP08 — Realm of Magic
* GP09 — Star Wars: Journey to Batuu
* GP10 — Dream Home Decorator
* GP11 — My Wedding Stories
* GP12 — Werewolves

---

### **Stuff Packs & Kits**

* SP01 — Luxury Party Stuff
* SP02 — Perfect Patio Stuff
* SP03 — Cool Kitchen Stuff
* SP04 — Spooky Stuff
* SP05 — Movie Hangout Stuff
* SP06 — Romantic Garden Stuff
* SP07 — Kids Room Stuff
* SP08 — Backyard Stuff
* SP09 — Vintage Glamour Stuff
* SP10 — Bowling Night Stuff
* SP11 — Fitness Stuff
* SP12 — Toddler Stuff
* SP13 — Laundry Day Stuff
* SP14 — My First Pet Stuff
* SP15 — Moschino Stuff
* SP16 — Tiny Living Stuff
* SP17 — Nifty Knitting
* SP18 — Paranormal Stuff
* SP20 — Throwback Fit Kit
* SP21 — Country Kitchen Kit
* SP22 — Bust the Dust Kit
* SP23 — Courtyard Oasis Kit
* SP24 — Fashion Street Kit
* SP25 — Industrial Loft Kit
* SP26 — Incheon Arrivals Kit
* SP28 — Modern Menswear Kit
* SP29 — Blooming Rooms Kit
* SP30 — Carnaval Streetwear Kit
* SP31 — Decor to the Max Kit
* SP32 — Moonlight Chic Kit
* SP33 — Little Campers Kit
* SP34 — First Fits Kit
* SP35 — Desert Luxe Kit
* SP36 — Pastel Pop Kit
* SP37 — Everyday Clutter Kit
* SP38 — Simtimates Collection Kit
* SP39 — Bathroom Clutter Kit
* SP40 — Greenhouse Haven Kit
* SP41 — Basement Treasures Kit
* SP42 — Grunge Revival Kit
* SP43 — Book Nook Kit
* SP44 — Poolside Splash Kit
* SP45 — Modern Luxe Kit
* SP46 — Home Chef Hustle Stuff Pack
* SP47 — Castle Estate Kit
* SP48 — Goth Galore Kit
* SP49 — Crystal Creations Stuff Pack
* SP50 — Urban Homage Kit
* SP51 — Party Essentials Kit
* SP52 — Riviera Retreat Kit
* SP53 — Cozy Bistro Kit
* SP54 — Artist Studio Kit
* SP55 — Storybook Nursery Kit
* SP56 — Sweet Slumber Party Kit
* SP57 — Cozy Kitsch Kit
* SP58 — Comfy Gamer Kit
* SP59 — Secret Sanctuary Kit
* SP60 — Casanova Cave Kit
* SP61 — Refined Living Room Kit
* SP62 — Business Chic Kit
* SP63 — Sleek Bathroom Kit
* SP64 — Sweet Allure Kit
* SP65 — Restoration Workshop Kit
* SP66 — Golden Years Kit
* SP67 — Kitchen Clutter Kit
* SP68 — Spongebob's House Kit
* SP69 — Autumn Apparel Kit
* SP70 — Spongebob Kid's Room Kit
* SP71 — Grange Mudroom Kit
* SP72 — Essential Glam Kit
* SP73 — Modern Retreat Kit
* SP74 — Garden to Table Kit
* SP81 — Prairie Dreams Kit

---

### **Free Packs**

* FP01 — Holiday Celebration Pack

---

## **Troubleshooting**

### **Game not detected**

* Use **Auto Detect** button (searches Windows Registry and common paths)
* Or select folder manually using **Browse**

### **Installation fails**

* Check Internet connection
* Ensure at least 80 GB free disk space
* Run as Administrator
* Disable antivirus temporarily if blocking downloads
* For Russia/Ukraine: Install VPN or Cloudflare WARP

### **DLC not showing in game**

* **Important:** Run DLC Unlocker to activate installed DLC
* Confirm the DLC folders exist in the game directory
* Restart the game

### **Multipart archive errors**

* Install **7-Zip** from [official website](https://www.7-zip.org/)

### **Update check fails**

* GitHub API has rate limits (60 requests/hour)
* Check your internet connection
* Try again later

### **Export Logs not working**

* Ensure you have write permissions to Desktop
* Logs are saved as: `LinuaUpdater_Log_YYYYMMDD_HHMMSS.txt`

---

# **Security Notice**

⚠ **This software is completely free. If you paid for it, you were scammed.**

The only legitimate sources are:

* **Official GitHub repository:** [github.com/l1ntol/lunia-dlc](https://github.com/l1ntol/linua-updater)
* **Official Releases page:** [Releases](https://github.com/l1ntol/linua-updater/releases)

Do **NOT** download this tool from any third-party websites or repacks.

### **About antivirus warnings**

False positives can occur in tools that manage archives and external downloads.  
This also affects:

* Anadius Unlocker
* ZloEmu
* Other community tools

This is expected behavior.

---

## **Original vs Fake**

### **Original**

* Transparent source code
* No hidden processes
* No background downloads
* Safe and predictable
* Auto-update notifications

### **Fake**

* Hidden scripts
* Modified EXE
* Suspicious background activity
* May contain malware
* No update checker

If your version behaves differently → you downloaded a **fake**.

---

## **For Developers**

### **Running from source**

```bash
# Clone repository
git clone https://github.com/l1ntol/lunia-dlc.git
cd lunia-dlc

# Install dependencies
pip install PyQt6 requests

# Run application
python LinuaUpdater_v4.2.py
```

### **Building executable**

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller --onefile --windowed --icon=icon.ico --name="LinuaUpdater" LinuaUpdater_v4.2.py

# Output: dist/LinuaUpdater.exe
```

### **Dependencies**

* PyQt6 >= 6.4.0
* requests >= 2.28.0

---

## **Technical Information**

* **Platform:** Windows (64-bit)
* **Architecture:** x64
* **Language:** Python 3.8+
* **GUI Framework:** PyQt6
* **No external dependencies** for .exe version

---

# **Copyright & Legal**

© 2024–2025 l1ntol — **All Rights Reserved**

You may:

* Use the program for personal purposes
* Review the source code for transparency
* Report bugs and suggest features

You may **NOT**:

* Modify, fork or redistribute the code
* Reupload the executable
* Publish this tool on third-party websites
* Create derivative works

Unauthorized distribution may result in a **DMCA takedown**.

This project is not affiliated with or endorsed by Electronic Arts or Maxis.  
*The Sims 4* is a trademark of Electronic Arts Inc.

---

## **Support**

* **Issues:** Use GitHub Issues for bug reports
* **Updates:** Check Releases page regularly
* **Auto-update:** Application will notify when new version is available

---

**Latest Release:** [Download Here](https://github.com/l1ntol/linua-updater/releases)
