"""
GearSwap Doctor: weapons wsdist (Kastra's simulator) doesn't list, added on top of its gear list when it loads.

His report 2026-11-07: MyAlt's Kaja Katana didn't come up in Build a set's Main weapon list - wsdist only has the
upgraded Ambuscade weapons (Gokotai, Tauret, Shining One), not the Kaja ones, and the Doctor only offers weapons wsdist
can work out. Stats from BG Wiki (Kaja_Katana, Kaja_Knife, Kaja_Lance), written the way gear.py writes the upgrades.
Their weapon skill bonus (the same as the upgrade's) is in updater.FIXES (weapon_bonus.py).
"""

EXTRA = [
    {"Name": "Kaja Katana", "Name2": "Kaja Katana", "Skill Type": "Katana", "Type": "Weapon", "DMG": 148, "Delay": 227,
     "Katana Skill": 242, "Magic Accuracy Skill": 242, "Magic Damage": 217, "DEX": 10, "AGI": 10, "INT": 10,
     "Accuracy": 35, "Attack": 25, "Ranged Accuracy": 35, "Magic Accuracy": 35, "Magic Attack": 13, "Jobs": ["nin"]},
    {"Name": "Kaja Knife", "Name2": "Kaja Knife", "Skill Type": "Dagger", "Type": "Weapon", "DMG": 117, "Delay": 180,
     "Dagger Skill": 242, "Magic Accuracy Skill": 242, "Magic Damage": 217, "DEX": 10, "MND": 10, "INT": 10,
     "Accuracy": 35, "Attack": 25, "Magic Accuracy": 35, "Magic Attack": 13,
     "Jobs": ["rdm", "thf", "bst", "brd", "rng", "nin", "cor", "pup", "dnc"]},
    {"Name": "Kaja Lance", "Name2": "Kaja Lance", "Skill Type": "Polearm", "Type": "Weapon", "DMG": 313, "Delay": 480,
     "DEX": 15, "INT": 15, "MND": 15, "Accuracy": 35, "Attack": 25, "Magic Accuracy": 35, "Magic Attack": 18,
     "Magic Damage": 226, "Polearm Skill": 242, "Magic Accuracy Skill": 242, "Jobs": ["sam", "drg", "war", "pld"]},
]
# one-handed: they can go in the sub slot too (dual wield)
SUB = ("Kaja Katana", "Kaja Knife")


def add_to(gear):
    """Put ours in wsdist's gear module (an item it has itself stays as it is). Returns the names added."""
    added = []
    for e in EXTRA:
        if e["Name2"] in gear.all_gear:
            continue
        gear.all_gear[e["Name2"]] = e
        gear.mains.append(e)
        if e["Name"] in SUB:
            gear.subs.append(e)
        added.append(e["Name"])
    return added
