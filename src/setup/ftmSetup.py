"""
Parses FTM Data
Modules used in setup.py
Edits forage.json, artifacts.json, mapblockingobjects.json
"""
import copy
import os
import platform
import pprint
import sys
import traceback

import pyjson5
from tqdm import tqdm

import builtins
from inspect import getframeinfo, stack

sys.path.append("..")
from lib.parseCPatcherWhens import parseWhens
from lib.parsePreconditions import parsePreconditions
from lib.whenstripper import stripWhens


def buildFTM(targetdir, maniList, vmbos, vstrings, objids, dynamicTokens, configParams, secretNotes, mailIDs, vanillaids, gpreconditions, clothingDict, bcList, furnitureids, weaponDict, errorlist):
    # returns [ftmList, forage, artifacts, mbos, monsters, errorlist]
    hasFTM = False
    maniSearch = list(filter(lambda object: object["ID"] == 'Esca.FarmTypeManager', maniList))
    if maniSearch:
        hasFTM = True
    packSearch = [mk for mk, mv in enumerate(maniList) if mv["packFor"].lower() == "esca.farmtypemanager"]
    if packSearch:
        if not hasFTM:
            errorlist.append("Config Alert: You have packs for Farm Type Manager but do not have it installed.")
            return [[], forage, artifacts, vmbos, vmonsters, errorlist]
    else:
        if hasFTM:
            errorlist.append("Config Alert: You have Farm Type Manager installed but do not have any packs for it.")
            return [[], forage, artifacts, vmbos, vmonsters, errorlist]
    print("==========================\nFarm Type Manager\n==========================")
    # build a list of FTM files
    ftmList = ftmWalk(targetdir, maniList)
    # Devs play fast and loose with key cases, so let's work around that.
    # Generate lowercase key dicts for existing forage and artifacts
    lowervstrings = {}
    originalkeys = {}
    for key, val in vstrings.items():
        lowervstrings[key.lower()] = val

    # Uncomment this to test the Boarding House
    # ftmList = [["E:/Program Files/SteamLibrary/steamapps/common/Stardew Valley/Inactive Mods/[BH] Boarding House/[FTM] Boarding House/content.json", "E:/Program Files/SteamLibrary/steamapps/common/Stardew Valley/Inactive Mods/[BH] Boarding House", "Boarding House"]]

    # Parse the FTM Files
    mbos = parseFTM(ftmList, vmbos, lowervstrings, dynamicTokens, configParams, maniList, secretNotes, mailIDs, vanillaids, gpreconditions, originalkeys, objids, clothingDict, bcList, furnitureids, weaponDict, errorlist)
    return mbos


def ftmWalk(targetdir, maniList):
    # returns filelist
    filelist = []
    manisearch = list(filter(None, [value if value["packFor"].lower() == "esca.farmtypemanager" else '' for value in maniList]))
    if len(manisearch) > 0:
        for mod in manisearch:
            froot = targetdir + mod["ModFolder"]
            fpath = targetdir + mod["ModFolder"] + "/content.json"
            filelist.append([fpath, froot, mod["ModFolder"]])
    return filelist


def ftmWhen(area, dynamicTokens, configParams, maniList, parentDir, secretNotes, mailIDs, vanillaids, gpreconditions):
    locationWhen = "Default"
    locationSpec = area["UniqueAreaID"]
    whenDict = {"static": {},
                "saveBased": {"calculated": {}, "locations": {},
                              "player": {"mailReceived": [], "friendshipData": {}}
                              },
                "instant": {},
                "dynamic": {},
                "config": {},
                "extant": {"config": [],
                           "saveBased": [],
                           "instant": [],
                           "dynamic": [],
                           "smapi": []
                           },
                "query": {"config": [],
                          "saveBased": [],
                          "instant": [],
                          "dynamic": [],
                          "smapi": [],
                          "misc": [],
                          "static": []
                          },
                "skip": False,
                "unknownkeys": []
                }  # if we have whens, we'll fill this up and replace locationWhen with it.
    replaceWhen = False
    if "SpawnTiming" in area:
        # A lot of devs will set spawn times to start at 600 and end at 600 for "once per day."
        # We call this default behavior
        if "StartTime" in area["SpawnTiming"] and area["SpawnTiming"]["StartTime"] != 600:
            whenDict["instant"]["StartTime"] = area["SpawnTiming"]["StartTime"]
            replaceWhen = True
        if "EndTime" in area["SpawnTiming"] and area["SpawnTiming"]["EndTime"] != 600:
            whenDict["instant"]["EndTime"] = area["SpawnTiming"]["EndTime"]
            replaceWhen = True
        if "OnlySpawnifAPlayerIsPresent" in area["SpawnTiming"]:
            whenDict["instant"]["PlayerIsPresent"] = area["SpawnTiming"]["OnlySpawnifAPlayerIsPresent"]
            replaceWhen = True
    if "ExtraConditions" in area:
        ec = area["ExtraConditions"]
        # it can be null
        if "LimitedNumberOfSpawns" in ec and ec["LimitedNumberOfSpawns"]:
            # if it only spawns a few times, skip it. It's a special item, not forage.
            # print("Area " + locationName + " UniqueAreaID "
            #       + locationSpec + " has limited spawns, skipping.")
            return False
        if "Years" in ec and ec["Years"]:
            outYears = []
            for year in ec["Years"]:
                # format can be #, #-# or #+
                if "-" in year:
                    yearrangeParts = year.split("-")
                    for ryear in range(int(yearrangeParts[0]), int(yearrangeParts[1])):
                        outYears.append(ryear)
                else:
                    outYears.append(year)
            whenDict["saveBased"]["year"] = {
                "Positive": outYears}
            replaceWhen = True
        if "Seasons" in ec and ec["Seasons"]:
            whenDict["saveBased"]["currentSeason"] = {
                "Positive": ec["Seasons"]}
            replaceWhen = True
        if "Days" in ec and ec["Days"]:
            outDays = []
            for day in ec["Days"]:
                # format can be #, #-# or #+
                if day.endswith("+"):
                    dayrangestart = day[-1]
                    for rday in range(dayrangestart, 28):
                        outDays.append(rday)
                elif "-" in day:
                    dayrangeParts = day.split("-")
                    for rday in range(int(dayrangeParts[0]), int(dayrangeParts[1])):
                        outDays.append(rday)
                else:
                    outDays.append(int(day))
            whenDict["saveBased"]["dayOfMonth"] = {
                "Positive": outDays}
            replaceWhen = True
            # endif Days
        if "WeatherYesterday" in ec and ec["WeatherYesterday"]:
            whenDict["saveBased"]["FTMWeatherYesterday"] = {
                "Positive": ec["WeatherYesterday"]}
            replaceWhen = True
        if "WeatherToday" in ec and ec["WeatherToday"]:
            whenDict["saveBased"]["locationWeather"] = {
                "Positive": ec["WeatherToday"]}
            replaceWhen = True
        if "WeatherTomorrow" in ec and ec["WeatherTomorrow"]:
            whenDict["saveBased"]["weatherForTomorrow"] = {
                "Positive": ec["WeatherTomorrow"]}
            replaceWhen = True
        if "CPConditions" in ec and ec["CPConditions"]:
            ec["When"] = ec["CPConditions"]
            parsedWhens = parseWhens(ec, dynamicTokens, configParams, maniList, parentDir)
            extraPCs = parsedWhens[0]
            if extraPCs["ignore"]:
                extraPCs = {}
            else:
                for k, v in extraPCs.items():
                    if isinstance(v, dict):
                        for sk, sv in v.items():
                            if sk not in whenDict[k]:
                                whenDict[k][sk] = sv
                            elif isinstance(sv, dict):
                                for ssk, ssv in sv.items():
                                    if ssk not in whenDict[k][sk]:
                                        whenDict[k][sk][ssk] = ssv
                                    elif isinstance(ssv, dict):  # player > mailReceived, player > friendshipData
                                        for sssk, sssv in ssv.items():
                                            if sssk not in whenDict[k][sk][ssk]:
                                                whenDict[k][sk][ssk][sssk] = sssv
                replaceWhen = True
        if "EPUPreconditions" in ec and ec["EPUPreconditions"]:
            whenDict["preconditions"] = []
            for ecItem in ec["EPUPreconditions"]:
                pcs = ecItem.split("/")
                pcList = []
                for pc in pcs:
                    pcList.append(parsePreconditions(
                        pc, locationSpec, secretNotes, mailIDs, vanillaids, gpreconditions))
                whenDict["preconditions"].append(pcList)
            replaceWhen = True
        # endif ExtraConditions
    if replaceWhen:
        strippedWhens = stripWhens(whenDict)
        locationWhen = strippedWhens[0]
    return locationWhen


def parseFTM(ftmList, vmbos, lowervstrings, dynamicTokens, configParams, maniList, secretNotes, mailIDs, vanillaids, gpreconditions, originalkeys, objids, clothingDict, bcList, furnitureids, weaponDict, errorlist):
    # return [forageids, artiids, largeObjectDict, monsters, objids]
    largeObjectDict = vmbos  # vanilla map blocking objects
    for ff in tqdm(ftmList, desc="Reading FTM Files"):
        filepath = ff[0]
        try:
            data = pyjson5.load(open(filepath, encoding="utf-8"),)
            if "LargeObjectSpawnEnabled" in data and data["LargeObjectSpawnEnabled"] == True:
                # find large removable objects that only spawn once. They probably do so to block a map exit.
                # map_warpcheck will need this data.
                loSettings = data["Large_Object_Spawn_Settings"]
                loAreas = loSettings["Areas"]
                for area in loAreas:
                    if "ExtraConditions" in area and area["ExtraConditions"]["LimitedNumberOfSpawns"] == len(area["IncludeCoordinates"]):
                        if "ObjectTypes" in area and area["ObjectTypes"]:
                            if area["MapName"] not in largeObjectDict:
                                largeObjectDict[area["MapName"]] = []
                            for idx, object in enumerate(area["ObjectTypes"]):
                                coordList = area["IncludeCoordinates"]
                                for coordStr in coordList:
                                    blockDict = {"X": [], "Y": [], "Blocker": object}
                                    # print(coordStr)
                                    blockCoords = []
                                    if ";" in coordStr:
                                        blockCoords = coordStr.split(";")
                                    if "/" in coordStr:
                                        blockCoords = coordStr.split("/")
                                    # print(blockCoords)
                                    for coordPair in blockCoords:
                                        coordList = coordPair.split(",")
                                        blockDict["X"].append(int(coordList[0]))
                                        blockDict["Y"].append(int(coordList[1]))
                                    largeObjectDict[area["MapName"]].append(blockDict)
        except Exception:
            errorlist.append('For Dev: Error encountered with: ' + filepath)
            errorlist.append("Traceback: " + traceback.format_exc())
    return largeObjectDict


# def print_wrap(*args, **kwargs):
#     caller = getframeinfo(stack()[1][0])
#     original_print("FN:", caller.filename, "Line:", caller.lineno, "Func:", caller.function, ":::", *args, **kwargs)


if __name__ == "__main__":
    # original_print = print
    # builtins.print = print_wrap
    import configparser
    from cls.data import Data as jsonData
    from lib.utils import writeJson, errorsOut
    config = configparser.ConfigParser()
    config.read("../config.ini")
    targetdir = config["PATHS"]["mod_directory"]
    jsonpath = config["PATHS"]["project_root"] + "json/"
    logpath = config["PATHS"]["log_path"]
    output_method = config["OUTPUT"]["output_method"]
    errorlist = []

    artifacts = jsonData(jsonpath, "artifacts").data
    bcList = jsonData(jsonpath, "bigobjects-rebase-postmfm").data
    clothingDict = jsonData(jsonpath, "apparel-rebase-postmfm").data
    forage = jsonData(jsonpath, "forage").data
    furnitureids = jsonData(jsonpath, "furniture-rebase-postmfm").data
    mail = jsonData(jsonpath, "mail").data
    maniList = jsonData(jsonpath, "manifests").data
    objids = jsonData(jsonpath, "objects-rebase-postmfm").data
    secretNotes = jsonData(jsonpath, "secretNotes").data
    weaponDict = jsonData(jsonpath, "weapons-rebase-postmfm").data

    configParams = jsonData(jsonpath, "configparams", "refs").data
    dynamicTokens = jsonData(jsonpath, "dynamictokens", "refs").data
    gpreconditions = jsonData(jsonpath, "preconditions", "refs").data
    vmbos = jsonData(jsonpath, "vanillamapblockingobjects", "refs").data
    vorelocations = jsonData(jsonpath, "vanillaorenodes", "refs").data
    vstrings = jsonData(jsonpath, "vanillastrings", "refs").data

    vanillaids = jsonData(jsonpath, "vanillaids", "vanilla").data
    vmonsters = jsonData(jsonpath, "vanillamonsters", "vanilla").data

    mbos = buildFTM(targetdir, maniList, forage, artifacts, vmbos, vstrings, objids, dynamicTokens, configParams, secretNotes, mail, vanillaids, gpreconditions, vmonsters, vorelocations, clothingDict, bcList, furnitureids, weaponDict, errorlist)

    # pprint.pprint(weaponDict["9"])
    # writeJson(artifacts, "artifacts-temp", jsonpath)
    # writeJson(forage, "forage-temp", jsonpath)
    # writeJson(ftmFiles, "ftmfiles", jsonpath, "refs")
    # writeJson(mbos, "mapblockingobjects", jsonpath)
    # writeJson(monsters, "monsters", jsonpath)
    # writeJson(objids, "objects-rebase-afterftm", jsonpath)

    if errorlist:
        errorsOut(errorlist, output_method, logpath)
