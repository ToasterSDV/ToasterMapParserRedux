# SDV Map Parser by OnionNinja
Parses Warps from Modded Stardew Maps (modularized from Toaster 0.0.2)

# Instructions

1. Set up `src/config.ini` to your satisfaction.
2. Ensure you have all requirements installed.
3. Run `src/setup.py`.

Most output should appear in the top level of the json directory. One file will be written to saves and one file will be written to notes. Some reference files (file lists, etc) will be written to json/refs.

# Dev Notes on the Cut

This is a heavily cut down version of the full setup for the forthcoming Toaster as of v0.0.2 internal (10 Aug 2023). It's gutted down to just what's needed to make the mapwarps.json file.

I tested it with my current loadout and it worked just fine.

If you want to test with a Stardrop Mod Profile you can point mod_directory in config.ini to the absolute version of `%appdata%/Stardrop/Data/SelectedMods/` instead of to your actual mods folder.

I gutted it down as far as I could. One of the things that was sacrificed was the logging. If you need more output on what it's doing, feel free to stick in whatever you like. This is your copy to use.

Installing binary2strings can be a little buggy on some python configs. It isn't my library, and I'm sorry. If you have questions [here is the repo](https://github.com/glmcdona/binary2strings)

# AuxMaps vs AltMaps

* Aux Maps are full or partial permanent replacements of vanilla maps, e.g. adding shortcuts to backwoods/mountain. An AuxMap will have some if not all of the same Warps as the map it replaces.
* Alt Maps are temporary, e.g. Town-Christmas, Beach-NightMarket. They are folded into their parents in the mapSetup process.

# WarpsOut vs. ConditionalWarpsOut vs. AuxWarpsOut

* WarpsOut are there from the start and persist regardless of patches.
* ConditionalWarpsOut are added to the basemaps procedurally by contentpatcher editmaps if the edit has a non-trivial "When" parameter. (e.g., Mail/Flag, Event Seen, HasItem, Weather)
* AuxWarpsOut are added by Map Patches (TMX/TBIN)

# What is not included

* In general, cosmetic changes are ignored as Toaster is not interested in the graphics, only getting from Map A to Map B.
* X, Y coordinates on WarpsOut are the location of the warp out in the specified location, not the warp in to the next location.
