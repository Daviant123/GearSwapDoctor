# GearSwap Doctor 2.2.0

A free tool for Final Fantasy XI players who use **Windower 4 + GearSwap**. It checks your GearSwap files, fixes what
can be fixed, and finds better weapon skill sets **from the gear you own**, using **wsdist** (Kastra's FFXI damage
simulator).

**Download:** click `GearSwap Doctor.exe` above, then **Download raw file** (or the download button). Double-click it:
nothing to install. Windows may say "Windows protected your PC" the first time (the exe isn't signed): click
**More info > Run anyway**.

## What it does

| Tab | |
|---|---|
| **Jobs** | click a job (or All jobs): its misspelled names, upgrades from your own gear and the things to look at, each ticked or not - **Do everything for that job** at once, or one part at a time (Fix ticked names / Apply ticked upgrades). All jobs: the to-do list, most important first |
| **Overview** | every GearSwap file of a character: loads?, sets, problems, wsdist upgrades, best gain |
| **Problems** | files that don't load, sets used but never made, misspelled item names (fixable with a click), items in the wrong slot / for the wrong job, items you don't own or left in storage |
| **Upgrades (wsdist)** | better weapon skill sets from your own gear: your set and the better one side by side, swaps in green |
| **Sets** | every set in every file in the game's equipment grid, problems marked |
| **Simulate** | wsdist on one weapon skill set: its damage, or the best set from your gear (sub job, enemy, TP) |
| **My gear** | what the character owns, by bag, with a search |
| **Backups** | every change is backed up first; put any backup back |
| **Settings** | TP / enemy for the check-ups, sub job per job, the daily check, folders |

Nothing in your GearSwap files changes until you click **Apply**. Every change is backed up first, and a change that
would stop the file loading is refused. In game, `//gs reload` to use the new sets.

## What it needs

- **Windower 4** with GearSwap (it finds the folder, or asks once).
- **Your bags**: from the **findAll** addon (`//lua load findall` once and log in each character - most players
  already have it) or from Steward. Without them it still checks the files, but can't say what you own.
- **wsdist** is downloaded the first time you start it, straight from Kastra's GitHub page
  (github.com/IzaKastra/wsdist_beta). It isn't included here: wsdist is Kastra's work.

Its own files (settings, reports, backups, wsdist) go to `%APPDATA%\GearSwap Doctor`.

## Free

GearSwap Doctor is free and always will be: no ads, no paid features, no donations.

## Source

The Python source is in `source\` (`gsd_app.py` is the window). To run it from source: Python 3.10+,
`pip install lupa numpy`, then `python source\gsd_app.py`.
