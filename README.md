# GearSwap Doctor 2.7.0

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
| **Healing** | every healing set of a file - cure, Curaga, cure on yourself, being cured, fast cast, Cursna, Regen, Waltz: what it heals now and what's wasted over a cap (cure potency 50 %, potency II 30 %, casting time 80 %), which sets are missing, and **the best set from your own gear** for the spell you pick, day / weather, keeping your weapons or not, with the enmity, damage taken, Conserve MP or interruption it must have. Put it in the set, or add it as a new one |
| **Add features** | adds things your GearSwap may not do yet, with all their options and your own gear in the lists: Doom / Curse gear, sleep gear, Echo Drops when silenced, cancel shadows / Sneak / Stoneskin before a recast, movement speed gear when you run, refresh gear at low MP, a DT key, a DT set at low HP, reraise gear, weapon lock, Treasure Hunter (Tag / Always), Hachirin-no-Obi / Orpheus's Sash, Moonshade swap at high TP, Warp / Dim. / experience ring commands, low ammo warning, a small window with the modes. ★ = suggested for that job and your gear. One click writes them into the file (backed up and checked first); your own rules stay as they are. In game: `//gs c gsd help` |
| **Overview** | every GearSwap file of a character: loads?, sets, problems, wsdist upgrades, best gain |
| **Problems** | files that don't load, sets used but never made, misspelled item names (fixable with a click), items in the wrong slot / for the wrong job, items you don't own or left in storage |
| **Upgrades (wsdist)** | better weapon skill sets **and TP (engaged) sets** from your own gear: your set and the better one side by side, swaps in green. TP sets are judged by time to a weapon skill (or damage per round) and keep the damage taken they have now |
| **Sets** | every set in every file in the game's equipment grid, problems marked |
| **Build a set** | pick a weapon skill or TP set, **the weapon (main / sub)** and **how much damage taken, physical damage taken and magic damage taken it must have**; wsdist builds the best set from your own gear that has them (a few seconds). A quick **Buffs** list picks what's up while it's judged. Put it in that set or save it as a new set. The numbers are remembered per set and the check-ups use them |
| **My gear** | what the character owns, by bag, with a search |
| **Backups** | every change is backed up first; put any backup back |
| **Settings** | TP / enemy / **buffs** for the check-ups (None, Solo, Typical party or your own ticks: Haste, songs, rolls, bubbles, food, Aftermath), TP sets on/off and how they're judged, sub job per job, the daily check, folders |

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
