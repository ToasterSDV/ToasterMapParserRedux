"""
Calculates Warps between maps.
Reads TBIN, TMX, ContentPatcher, BusLocations, TrainStations, WarpNetwork
All methods called by setup.py, vanilla/generatevanilladata.py
Can be run separately, must run after content_patcher_setup.py, ftm_setup.py
Requires 64 bit python for included binary2strings module, although that can be
    omitted if no TBIN files are in use.
Creates mapwarps.json, vanilla/vanillamapwarps.json
Change mode at top of main call
"""
import copy
import os
import pprint
import re
import sys
import traceback

import builtins
from inspect import getframeinfo, stack

import binary2strings as b2s
import defusedxml.ElementTree as ET
import pyjson5

from tqdm import tqdm

sys.path.append("..")
from lib.bracketReplacer import bracketReplacer
from lib.parseCPatcherWhens import parseWhens


def addCPDefaultChanges(mapDict, mapChanges, fileToMap, mode, auxMaps, buildingDict, HasWarpNetwork, vanillaAuxMaps, vanillaAltMaps, legacyNames, errorlist):
    # returns [dict mapDict, list errorlist]
    # Adds in warpsOut created by contentpatcher
    # This only handles the default warps out, not the conditionals. We'll handle those elsewhere.
    for mC in tqdm(mapChanges, desc="Content Patcher Default Map Changes"):
        # ignoreMPs = ["Music", "contains", "AllowGrass", 'NPCWarp', "Light",
        #              "DayTiles", "NightTiles"]
        # wantedTypes = ["Door", "Warp", "MagicWarp", "LockedDoorWarp"]
        processed = []
        if not mC["HasConditions"] and "Update" not in mC:  # default change check
            # print("\n" + str(mC))
            if "Action" in mC and mC["Action"].lower() == "editmap":
                if "Target" in mC:
                    # begin location logic
                    if "," in mC["Target"]:  # workaround bad mod dev code, "Target": "Custom_GrandpasShedGreenhouse,Maps"
                        rawTarget = mC["Target"].rsplit(",", 1)[0]
                    else:
                        rawTarget = mC["Target"]
                    # mFile = mC["Target"].rsplit("/")[1]
                    locationdata = getTrueLocation(rawTarget, fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapDict, errorlist)
                    mapTarget = locationdata[0]
                    altMap = locationdata[1]
                    auxMap = locationdata[2]
                    errorlist = locationdata[3]
                    if mapTarget not in mapDict:
                        # possibly a submap?
                        mapLookup = getTrueLocation(mC["Target"], fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapDict, errorlist)
                        mapTarget = mapLookup[1]
                        errorlist = mapLookup[3]
                    if mapTarget is None:
                        # nonexistent map or spouse/warproom
                        continue
                    # end location logic
                    # begin processed list creation
                    if "AddWarps" in mC:
                        for aW in mC["AddWarps"]:
                            newWarp = generateDefaultWarps(aW, altMap, mapTarget, [], [], mC["Path"], auxMap, "modded", legacyNames, errorlist)
                            # pprint.pprint(newWarp)
                            errorlist = newWarp[2]
                            if newWarp[0]:
                                processed.append(newWarp[0])
                            # end AddWarps loop
                        # endif AddWarps
                    if "MapProperties" in mC:
                        for k, v in mC["MapProperties"].items():
                            if k == "Warp":
                                newWarp = generateDefaultWarps(v, altMap, mapTarget, [], [], mC["Path"], auxMap, "modded", legacyNames, errorlist)
                                errorlist = newWarp[2]
                                if newWarp[0]:
                                    processed.append(newWarp[0])
                                # print("MP " + mapTarget + " " + k + " " + str(processed[0]))
                                # endif Warp
                            # end MapProperties loop
                        # endif MapProperties
                    if "MapTiles" in mC:
                        for mT in mC["MapTiles"]:
                            if "SetProperties" in mT:
                                for propType, val in mT["SetProperties"].items():
                                    valParts = val.split(" ")
                                    actionWord = valParts[0]
                                    if actionWord == "WarpNetwork":
                                        parsedWarp = generateActionWarps(val, altMap, mapTarget, [], [], mC["Path"], auxMap, errorlist, mapDict, legacyNames)
                                        newData = parsedWarp[0]
                                        errorlist = parsedWarp[2]
                                        if newData:
                                            # print(newData)
                                            if HasWarpNetwork:
                                                processed.append(newData)
                                                wnOut = {"Conditions": "None", "Location": mapTarget, "Hours": "All", "Path": mC["Path"], "Type": "WarpNetwork"}
                                                if "WarpNetwork" not in mapDict:
                                                    mapDict["WarpNetwork"] = {"WarpsOut": []}
                                                mapDict["WarpNetwork"]["WarpsOut"].append(wnOut)
                                            # if it has a WarpNetwork inpoint and there's an Obelisk, that is also the Obelisk warpout point.
                                            obeliskSearch = list(filter(None, [value if (("ModName" in value and value["ModName"] in mC["Path"]) or ("ReplacedBy" in value and value["ReplacedBy"] in mC["Path"])) and "Obelisk" in key else '' for key, value in buildingDict.items()]))
                                            if obeliskSearch:
                                                obeliskConditions = {"saveBased": {"calculated": {"hasbuilding": [{"Negative": [], "Positive": [obeliskSearch[0]["Name"]]}]}}}
                                                obeliskOut = {"Conditions": obeliskConditions, "Location": mapTarget, "Hours": "All", "Path": mC["Path"], "Type": "Obelisk"}
                                                mapDict["Farm"]["ConditionalWarpsOut"].append(obeliskOut)
                                    elif propType == "Action" and ("Warp" in actionWord or "LoadMap" in actionWord):
                                        # adding action Warps
                                        if actionWord == "LockedDoorWarp" or actionWord == "MagicWarp" or actionWord == "Warp" or actionWord == "LoadMap":
                                            parsedWarp = generateActionWarps(val, altMap, mapTarget, [], [], mC["Path"], auxMap, errorlist, mapDict, legacyNames)
                                            newWarp = parsedWarp[0]
                                            errorlist = parsedWarp[2]
                                            if newWarp:
                                                processed.append(newWarp)
                                    elif propType == "Action" and actionWord == "Door":
                                        # adding door owner
                                        print("MTDO " + mapTarget + " " + propType + " " + + str(val))
                                    elif propType == "TouchAction" and ("Warp" in actionWord or "LoadMap" in actionWord):
                                        if actionWord == "Warp" or actionWord == "LoadMap":
                                            xCoord = mT["Position"]["X"]
                                            yCoord = mT["Position"]["Y"]
                                            warpParts = val.split(" ")
                                            warpString = str(xCoord) + " " + str(yCoord) + " " + " ".join(warpParts[1:])
                                            parsedWarp = generateDefaultWarps(warpString, altMap, mapTarget, [], [], mC["Path"], auxMap, "modded", legacyNames, errorlist)
                                            newWarp = parsedWarp[0]
                                            errorlist = parsedWarp[2]
                                            if newWarp:
                                                processed.append(newWarp)
                                            # print(mapTarget + " " + propType + " " + str(warplocations))
                                        # endif propType conditions
                                    # end SetProperties Loop
                                # endif SetProperties
                            # end MapTiles Loop
                        # end if MapTiles
                    if "ToArea" in mC and "FromFile" in mC:
                        # overlaying primary maps with auxmaps.
                        # Check if the auxmap has a warpout which isn't in the target map.
                        inboundMap = mC["FromFile"].rsplit("/", 1)[1].rsplit(".")[0]
                        if inboundMap in mapDict:
                            if mapTarget not in mapDict:
                                existingWarpsOut = []
                            elif "WarpsOut" in mapDict[mapTarget]:
                                existingWarpsOut = mapDict[mapTarget]["WarpsOut"]
                            else:
                                existingWarpsOut = []
                            if "WarpsOut" in inboundMap:
                                inboundWarpsOut = mapDict[inboundMap]["WarpsOut"]
                            else:
                                inboundWarpsOut = []
                            if not all(x in existingWarpsOut for x in inboundWarpsOut):
                                print(inboundMap + " has warps out not in " + mapTarget)
                            # endif inboundMap
                        # endif ToArea/FromFile
                    if "TextOperations" in mC:
                        for tO in mC["TextOperations"]:
                            if "Target" in tO:
                                if tO["Target"][1] == "Warp":
                                    newWarp = generateDefaultWarps(tO["Value"], altMap, mapTarget, [], [], mC["Path"], auxMap, "modded", legacyNames, errorlist)
                                    errorlist = newWarp[2]
                                    if newWarp[0]:
                                        processed.append(newWarp[0])
                                    # print("TO " + mapTarget + " " + tO["Target"][1] + " " + str(processed[0]))
                                    # endif Warp
                                # endif Target
                            # end TextOperations loop
                        # endif TextOperations
                    # end processed list creation
                    # endif Target
                # endif editmap
            # endif default change check
        if processed:
            # go through the processed list and actually add the changes to mapDict
            # print("Before: " + str(mapDict[mapTarget]["WarpsOut"]))
            for pr in processed:
                for woDict in pr:
                    if auxMap:
                        # outData[locationName]["AuxMaps"] = [auxMap]
                        # outData[locationName]["AuxedBy"] = [modName]
                        warpOutKey = "AuxWarpsOut"
                    else:
                        warpOutKey = "WarpsOut"
                    try:
                        if warpOutKey not in mapDict[mapTarget]:
                            mapDict[mapTarget][warpOutKey] = []
                        if woDict not in mapDict[mapTarget][warpOutKey]:
                            modName = mC["Path"].rsplit("/", 2)[1]
                            woDict["AppendedBy"] = modName
                            mapDict[mapTarget][warpOutKey].append(woDict)
                            # Devs will put innate Warps Out in TMX/TBIN and then block them via json
                            # with Warps Out that are one cell away in any direction.
                            # An example can be seen in East Scarp's Deep Woods map.
                            # We need to find these blocked innate exits and remove them.
                            if "X" in woDict and woDict["X"]:
                                xStripped = int(woDict['X'].replace("'", "").replace('"', ''))
                                yStripped = int(woDict['Y'].replace("'", "").replace('"', ''))
                                # walk through existing warps out (ewo) with coords to see if the appended exit blocks them
                                for ewo in mapDict[mapTarget][warpOutKey]:
                                    if "AppendedBy" not in ewo and "X" in ewo and ewo["X"]:
                                        ewoX = int(ewo['X'].replace("'", "").replace('"', ''))
                                        ewoY = int(ewo['Y'].replace("'", "").replace('"', ''))
                                        if (abs(xStripped - ewoX) <= 1 and abs(yStripped - ewoY) == 0) or (abs(xStripped - ewoX) == 0 and abs(yStripped - ewoY) <= 1):
                                            # remove the blocked exit
                                            mapDict[mapTarget][warpOutKey].remove(ewo)
                                # end blocked exit check
                        if auxMap:
                            if "AuxMaps" not in mapDict[mapTarget]:
                                mapDict[mapTarget]["AuxMaps"] = []
                            if auxMap not in mapDict[mapTarget]['AuxMaps']:
                                mapDict[mapTarget]["AuxMaps"].append(auxMap)
                            if "AuxedBy" not in mapDict[mapTarget]:
                                mapDict[mapTarget]["AuxedBy"] = []
                            if modName not in mapDict[mapTarget]["AuxedBy"]:
                                mapDict[mapTarget]["AuxedBy"].append(modName)
                            # endif auxMap
                    except KeyError:
                        errorlist.append("Mod Bug: The map named " + mC["Target"] + " is never loaded, skipping. (Mod: " + modName + ")")
                        pass
                    # end woDict loop
                # end processed loop
            # endif processed
            # print("After: " + str(mapDict[mapTarget]["WarpsOut"]))
        # end mapChanges loop
    return [mapDict, errorlist]


def buildMaps(mode, targetdir, errorlist, vmapstaticfile, maniList, blockers, decompileddir, vmapfile=None, mapChanges=None, moddedMapList=None, configData=None, dynos=None, events=None, buildings=None, festivalMaps=None):
    # return [dict mapData, list errorlist]
    mapData = {}
    auxMaps = {}
    replacedVanillaMaps = {}
    fileToMap = {}
    legacyNames = {}
    HasBusLocations = False
    HasTrainStations = False
    HasWarpNetwork = False
    vmsd = pyjson5.load(open(vmapstaticfile))
    vanillaAuxMaps = vmsd["vanillaAuxMaps"]  # dict
    vanillaAltMaps = vmsd["vanillaAltMaps"]  # dict
    vanillaBuildableMaps = vmsd["vanillaBuildableMaps"]  # list
    vanillaEventMaps = vmsd["vanillaEventMaps"]  # list
    vanillaFestivalMaps = vmsd["vanillaFestivalMaps"]  # dict
    if mode == "modded":
        vmapData = pyjson5.load(open(vmapfile),)
        for k, v in vmapData.items():
            v["WarpsIn"] = []
            v["AuxWarpsIn"] = []
            v["ConditionalWarpsIn"] = []
            mapData[k] = v
        # get all our lists
        print("==========================\nMaps\n==========================")
        mapFileData = makeFileList(mapChanges, moddedMapList, vmapData, configData, dynos, errorlist)
        mapFileList = mapFileData[0]
        replacedVanillaMaps = mapFileData[1]
        fileToMap = mapFileData[2]
        # spouseMaps = mapFileData[3]
        # warpRooms = mapFileData[4]
        auxMaps = mapFileData[5]
        conditionalChanges = mapFileData[6]
        warpNetworkNodes = mapFileData[7]
        legacyNames = mapFileData[8]
        errorlist = mapFileData[9]
        # pprint.pprint(conditionalChanges)
        # add vanilla auxmaps to auxmaps
        for k, v in vanillaAuxMaps.items():
            if k not in auxMaps:
                auxMaps[k] = v
        # determine if we have the optional map-affecting mods
        bl = list(filter(None, [value if value["ID"].lower() == "hootless.buslocations" else '' for value in maniList]))
        ts = list(filter(None, [value if value["ID"].lower() == "cherry.trainstation" else '' for value in maniList]))
        wn = list(filter(None, [value if value["ID"].lower() == "tlitookilakin.warpnetwork" else '' for value in maniList]))
        if len(bl) > 0:
            HasBusLocations = True
        if len(ts) > 0:
            HasTrainStations = True
        if len(wn) > 0:
            HasWarpNetwork = True
    if mode == "vanilla":
        mapFileList = findVanillaMapFiles(decompileddir)  # all TMX and TBIN files
        festivalMaps = vanillaFestivalMaps
    # read the map data from TMX/TBIN
    pmdOut = parseMapFiles(mapFileList, mode, fileToMap, auxMaps, replacedVanillaMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist)
    mapData = pmdOut[0]
    errorlist = pmdOut[1]

    if mode == "modded":
        pmdOut = addCPDefaultChanges(mapData, mapChanges, fileToMap, mode, auxMaps, buildings, HasWarpNetwork, vanillaAuxMaps, vanillaAltMaps, legacyNames, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]
    # fold AltMaps into their parents
    pmdOut = parseAltMaps(mapData, errorlist)
    mapData = pmdOut[0]
    errorlist = pmdOut[1]

    if mode == "modded":
        if conditionalChanges:
            pmdOut = parseConditionalWarps(mapData, conditionalChanges, auxMaps, fileToMap, mode, vanillaAuxMaps, vanillaAltMaps, festivalMaps, legacyNames, errorlist)
            mapData = pmdOut[0]
            errorlist = pmdOut[1]

        pmdOut = findBlockers(mapData, mapChanges, blockers, configData, dynos, auxMaps, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]

    # add the vanilla conditional warps
    pmdOut = parseVanillaConditionalWarps(mapData, replacedVanillaMaps, mode, errorlist)
    mapData = pmdOut[0]
    errorlist = pmdOut[1]

    if HasBusLocations:
        pmdOut = parseBusLocations(mapData, maniList, targetdir, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]

    if HasTrainStations:
        pmdOut = parseTrainStations(mapData, maniList, targetdir, configData, dynos, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]

    if HasWarpNetwork:
        pmdOut = parseWarpNetwork(mapData, warpNetworkNodes, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]

    # translate warps out to warps in
    pmdOut = parseWarpsIn(mapData, mode, errorlist)
    mapData = pmdOut[0]
    errorlist = pmdOut[1]

    # sort maps into Primary, Temp, Buildable.
    if mode == "vanilla":
        pmdOut = sortVanillaMaps(mapData, vanillaEventMaps, vanillaBuildableMaps, vanillaAltMaps, vanillaAuxMaps, festivalMaps, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]
    if mode == "modded":
        pmdOut = sortModdedMaps(mapData, moddedMapList, events, vmapData, vanillaBuildableMaps, festivalMaps, errorlist)
        mapData = pmdOut[0]
        festivalMaps = pmdOut[1]
        errorlist = pmdOut[2]
    # figure out which maps are accessible by default
    pmdOut = parseABD(mapData, errorlist)
    mapData = pmdOut[0]
    errorlist = pmdOut[1]

    if mode == "modded":
        # remove up any maps with no warps in or no warps out
        # mostly because devs forget to remove references to old maps
        pmdOut = purgeEmptyNodes(mapData, errorlist)
        mapData = pmdOut[0]
        errorlist = pmdOut[1]
        return [mapData, festivalMaps, errorlist]
    else:
        return [mapData, errorlist]
    # errorlist.append("For Dev: The following Spouse Maps were omitted: " + ", ".join(spouseMaps))
    # warpRooms = list(set(warpRooms))
    # warpRooms.remove("Destinations")
    # errorlist.append("For Dev: The following NPC Holding Rooms were omitted: " + ", ".join(warpRooms))


def compareWarps(newWarps, existingWarps):
    # returns list of warps
    comped = []
    for nW in newWarps:
        matched = False
        # print(nW["Location"])
        for eW in existingWarps:
            if nW["Location"] == eW["Location"]:
                # print("warp to " + nW['Location'] + " already in existing map")
                matched = True
                break
        if matched:
            continue
        else:
            comped.append(nW)
    return comped


def findBlockers(mapDict, changeList, blockers, configData, dynos, auxMaps, errorlist):
    # returns [mapdict, errorlist]
    unlockers = []
    margin = 20  # approx max distance between a blocker and an exit using RSV Ridge to Ridge Forest as max
    doormargin = 2
    for mC in changeList:
        # go through changes and use hinting to find unlockers
        if "FromFile" in mC and (mC["FromFile"].endswith(".tmx") or mC["FromFile"].endswith(".tbin")) and "TargetWithoutPath" not in mC["FromFile"]:
            workingFile = bracketReplacer(mC["FromFile"], configData, dynos, {}, "filenames")
            ffMapPath = workingFile.rsplit("/", 1)[1]
            ffMapName = ffMapPath.split(".")[0]
            if "HighlandsCavernPrisonUnlocked" not in ffMapName:
                # Hardcode around SVE.
                # use mod dev hinting to figure out if it might be an unlocker map
                hinting = ["open", "unlock", "removerailroadboulder"]
                if "LogName" in mC:
                    if any(x in mC["LogName"].lower() for x in hinting):
                        ulList = [ffMapName, mC["LogName"]]
                        if ulList not in unlockers:
                            unlockers.append(ulList)
                # can also be in the filename
                if any(x in ffMapPath.lower() for x in hinting):
                    if "LogName" in mC:
                        logString = mC["LogName"]
                    else:
                        logString = ""
                    ulList = [ffMapName, logString]
                    if ulList not in unlockers:
                        unlockers.append(ulList)
                    if ffMapName in auxMaps:  # should not be there.
                        errorlist.append("For Dev: " + ffMapName + " is an unlocker but it's already in AuxMaps: " + auxMaps[ffMapName])

    # pprint.pprint(unlockers)
    # pprint.pprint(conditionalChanges)

    for ul in unlockers:
        # go through those unlockers and figure out which exits they match with
        ulParts = re.findall('[A-Z][^A-Z]+', ul[0])
        logParts = [x for x in ul[1].split(" ") if len(x) > 3]
        # print("Unlocker parts: " + str(ulParts))
        # print("Log Parts: " + str(logParts))
        # print(ul[0])
        # if there's an unlocker, maybe we can figure out what it's unlocking
        targetsearch = list(filter(None, [value if "FromFile" in value and ul[0] in value["FromFile"] else '' for value in changeList]))
        mapTarget = ""
        affectedArea = []
        thisWhen = {}
        found = False
        if len(targetsearch) > 0:
            for ts in targetsearch:
                # print("TargetSearch passed")
                targetName = ts["Target"].rsplit("/", 1)[1]
                if not mapTarget:
                    mapTarget = targetName
                elif mapTarget != targetName:
                    raise Exception("Unlocker targets multiple maps")
                    quit()
                if "ToArea" in ts:
                    startX = int(ts["ToArea"]["X"])
                    startY = int(ts["ToArea"]["Y"])
                    width = int(ts["ToArea"]["Width"])
                    height = int(ts["ToArea"]["Height"])
                    for xval in range(startX, startX + width):
                        for yval in range(startY, startY + height):
                            coords = [xval, yval]
                            if coords not in affectedArea:
                                affectedArea.append(coords)
                if "When" in ts:
                    thisWhen = ts["When"]
        # print("Target: " + mapTarget)
        if mapTarget and mapTarget in mapDict:
            # print("MapTarget passed")
            matchesFound = 0
            logMatchesFound = 0
            thisIdx = {}
            logIdx = {}
            ignore = False
            if "ConditionalWarpsOut" in mapDict[mapTarget] and mapDict[mapTarget]["ConditionalWarpsOut"]:
                for cwo in mapDict[mapTarget]["ConditionalWarpsOut"]:
                    if ul[0] in cwo["Path"]:
                        ignore = True
                        # print("Unlocker " + ul[0] + " is used in a conditional Warp Out, ignoring.")
            if ignore:
                continue
            for idx, wO in enumerate(mapDict[mapTarget]["WarpsOut"]):
                # print(str(idx) + ": " + str(wO["Location"]))
                if "X" in wO and wO["X"]:
                    warpcoords = [int(wO["X"]), int(wO["Y"])]
                    if warpcoords in affectedArea:
                        found = True
                        mapDict[mapTarget]["WarpsOut"][idx]["Blocker"] = "MapChange"
                        mapDict[mapTarget]["WarpsOut"][idx]["Conditions"] = thisWhen
                        # print("Found a blocked entrance via coords in " + mapTarget)
                        # pprint.pprint(mapDict[mapTarget])
                if any(x in wO["Location"] for x in ulParts):
                    # for action warps there are no coords but we can try
                    # to brute force it by comparing the name of the unlocker
                    # with the name of the warps
                    matches = [x for x in ulParts if x in wO["Location"]]
                    if len(matches) > matchesFound:
                        # print(matches)
                        matchesFound = len(matches)
                        if str(matchesFound) not in thisIdx:
                            thisIdx[str(matchesFound)] = []
                        thisIdx[str(matchesFound)].append(wO["Location"])
                if len(logParts) > 0 and any(x in wO["Location"] for x in logParts):
                    # we can also bruteforce against the log
                    logmatches = [x for x in logParts if x in wO["Location"]]
                    if len(logmatches) > logMatchesFound:
                        # print(logmatches)
                        logMatchesFound = len(logmatches)
                        if str(logMatchesFound) not in logIdx:
                            logIdx[str(logMatchesFound)] = []
                        logIdx[str(logMatchesFound)].append(wO["Location"])
            if matchesFound > 1 and matchesFound > logMatchesFound and not found:
                for idx, wO in enumerate(mapDict[mapTarget]["WarpsOut"]):
                    if wO["Location"] == thisIdx[str(matchesFound)][0]:
                        mapDict[mapTarget]["WarpsOut"][idx]["Blocker"] = "MapChange"
                        mapDict[mapTarget]["WarpsOut"][idx]["Conditions"] = thisWhen
                        # print("Found a blocked entrance via name comparison between " + ul[0] + " and " + mapDict[mapTarget]["WarpsOut"][idx]["Location"])
                        # pprint.pprint(mapDict[mapTarget]["WarpsOut"][idx])
            elif logMatchesFound > 1 and not found:
                for idx, wO in enumerate(mapDict[mapTarget]["WarpsOut"]):
                    if wO["Location"] == logIdx[str(logMatchesFound)][0]:
                        mapDict[mapTarget]["WarpsOut"][idx]["Blocker"] = "MapChange"
                        mapDict[mapTarget]["WarpsOut"][idx]["Conditions"] = thisWhen
                        # print("Found a blocked entrance via LOG comparison between " + ul[1] + " and " + mapDict[mapTarget]["WarpsOut"][idx]["Location"])
                        # pprint.pprint(mapDict[mapTarget]["WarpsOut"][idx])
            elif ul[0] == "RemoveRailroadBoulder":  # yet more SVE stupidity
                for idx, wO in enumerate(mapDict[mapTarget]["WarpsOut"]):
                    if wO["Location"] == "Summit":
                        mapDict[mapTarget]["WarpsOut"][idx]["Blocker"] = "MapChange"
                        mapDict[mapTarget]["WarpsOut"][idx]["Conditions"] = thisWhen
            # pprint.pprint(mapDict[mapTarget]["WarpsOut"])

    for k, v in mapDict.items():
        warpList = {}
        checkMap = None
        blocker = None
        if k in blockers:
            if "WarpsOut" in v:
                woIDX = []
                for wO in v["WarpsOut"]:
                    if "X" in wO and wO["X"]:
                        if wO["Location"] not in warpList:
                            warpList[wO["Location"]] = {"X": [], "Y": []}
                        warpList[wO["Location"]]["X"].append(wO["X"])
                        warpList[wO["Location"]]["Y"].append(wO["Y"])
                # print("WarpList: " + str(warpList))
                if not warpList:
                    if k == "Custom_GrandpasShedOutside":
                        # hardcoding for SVE yet again...
                        checkMap = "Custom_GrandpasShedRuins"
                        blocker = "Log"
                if warpList:
                    for blockingItem in blockers[k]:
                        # print(blockingItem)
                        blockX = blockingItem["X"][0]
                        blockY = blockingItem["Y"][0]
                        coordSum = int(blockX) + int(blockY)
                        lowestDiff = margin
                        # print("Blocker: " + str(blockX) + ", " + str(blockY) + " Sum: " + str(coordSum))
                        checkMap = None
                        for outMap, data in warpList.items():
                            for idx, coord in enumerate(data["X"]):
                                thiscoordSum = int(coord) + int(data["Y"][idx])
                                thiscoordDiff = abs(coordSum - thiscoordSum)
                                # print("Exit" + outMap + ": " + str(coord) + ", " + str(data["Y"][idx]) + " Sum: " + str(thiscoordSum) + " Diff: " + str(thiscoordDiff))
                                if thiscoordDiff < margin and thiscoordDiff < lowestDiff:
                                    lowestDiff = thiscoordDiff
                                    checkMap = outMap
                                    blocker = blockingItem["Blocker"]
                if checkMap is not None:
                    for idx, wO in enumerate(v["WarpsOut"]):
                        if wO["Location"] == checkMap:
                            woIDX.append(idx)
                    for woid in woIDX:
                        mapDict[k]["WarpsOut"][woid]["Blocker"] = blocker
        if "DoorCoords" in v:  # is an exit blocked by an NPC Door? e.g. Custom_AguarLab to Custom_AguarBasement in RSv
            # this only really works if there's a single Door owner.
            if "WarpsOut" in v:
                for wO in v["WarpsOut"]:
                    if "X" in wO and wO["X"] and ("Conditions" not in wO or wO["Conditions"] == "None"):
                        warpX = int(wO["X"])
                        warpY = int(wO["Y"])
                        for idx, dc in enumerate(v["DoorCoords"]):
                            if dc[0] - doormargin < warpX < dc[0] + doormargin and dc[1] - doormargin < warpY < dc[1] + doormargin:
                                doorOwner = v["DoorOwners"][idx]
                                warpConditions = {"saveBased": {"calculated": {"hearts": [{"Negative": [], "Positive": ["2"], "Target": doorOwner}]}}}
                                wO["Conditions"] = warpConditions
    return [mapDict, errorlist]


def findVanillaMapFiles(rootdir):
    # return list mapFiles
    mapFiles = []
    for root, dirs, files in os.walk(rootdir):
        for name in files:
            if name.endswith((".tmx")) or name.endswith((".tbin")):
                full_path = os.path.join(root, name).replace("\\", "/")
                mapFiles.append(full_path)
    return mapFiles


def generateActionWarps(aW, altMap, locationName, existinglocations, warplocations, filepath, auxMap, errorlist, mapData, legacyNames, mode="normal"):
    # returns [warplocations, existinglocations, errorlist]
    printthis = False
    # if aW == "MagicWarp Custom_WizardBasement 14 18":
    #     printthis = True
    #     print(warplocations)
    warpHours = "All"
    warpConditions = "None"
    warpParts = aW.split(" ")
    # print(warpParts)
    warpType = warpParts[0]
    warpData = {"Type": warpType}
    toX = None
    toY = None
    if printthis:
        print(warpType)
    if warpType == "Theater_Exit":
        warpLocation = "Town"
    elif warpType == "BoatTicket":
        warpLocation = "BoatTunnel"
    elif warpType == "Warp_Sunroom_Door":
        warpLocation = "Sunroom"
        warpConditions = {"saveBased": {"calculated": {"hearts": [{"Negative": [], "Positive": ["2"], "Target": "Caroline"}]}}}
    elif warpType == "WarpNetwork":
        warpLocation = "WarpNetwork"
    elif len(warpParts) > 1:
        if not warpParts[1].isnumeric():
            warpLocation = warpParts[1]
            toX = warpParts[2]
            toY = warpParts[3]
        else:
            warpLocation = warpParts[3]
            toX = warpParts[1]
            toY = warpParts[2]
    else:
        warpLocation = warpType[4:]  # e.g. WarpBoatTunnel
    if printthis:
        print(warpLocation)
    warpLocation = translateWarpLocation(warpLocation, legacyNames)
    # if warpLocation not in primaryMaps and warpLocation not in auxMaps:
    #     errorstring = "AW Location " + warpLocation + " in " + filepath + " is not a map."
    #     if errorstring not in errorlist:
    #         errorlist.append(errorstring)
    if warpLocation == locationName:
        # discard circular warps
        # errorlist.append("Circular warp in " + filepath + " from " + warpLocation + " to " + locationName)
        return [False, existinglocations, errorlist]
    if warpLocation not in existinglocations:
        warpData["Location"] = warpLocation
        if len(warpParts) > 1 and not warpParts[1].isnumeric() and warpLocation != "WarpNetwork":
            warpData["Location"] = warpParts[1]
            existinglocations.append(warpParts[1])
        elif warpLocation == "WarpNetwork":
            warpData["Location"] = "WarpNetwork"
            existinglocations.append("WarpNetwork")
        elif warpType == "LockedDoorWarp":
            # there can be multiple locked doors from one location to another, e.g. Science House from Forest.
            # we have to record the X, Y coords of each door.
            # Note that these are not the X Y of the door itself, but rather the destination.
            # toX = warpParts[1]
            # toY = warpParts[2]
            existinglocations.append([toX, toY, warpLocation])
            # print(existinglocations)
            warpHours = warpParts[4] + ", " + warpParts[5]
            if len(warpParts) == 7:
                warpConditions = warpParts[6]
            elif len(warpParts) == 8:
                warpHearts = str(int(int(warpParts[7]) / 250))
                warpConditions = {"saveBased": {"calculated": {"hearts": [{"Negative": [], "Positive": [str(warpHearts)], "Target": warpParts[6]}]}}}
        elif warpType == "WarpWomensLocker":
            warpConditions = {"saveBased": {"player": {"isMale": False}}}
        elif warpType == "WarpMensLocker":
            warpConditions = {"saveBased": {"player": {"isMale": True}}}
        warpData["Hours"] = warpHours
        if warpConditions == 'None':
            warpConditions = parseWarpConditions(locationName, warpLocation, toX, toY)
        warpData["Conditions"] = warpConditions
        if warpData["Location"].isnumeric():
            errorlist.append("For Dev: generateActionWarps location is numeric: " + aW + "(File: " + filepath + ")")
        if mode == "vanilla":
            warpData["Path"] = "Vanilla"
        else:
            warpData["Path"] = filepath
        if auxMap:
            warpData["AuxMap"] = auxMap
        if mode == "conditional":
            # make sure the location is an actual map
            if warpData["Location"] not in mapData.keys():
                keyfound = False
                for key in mapData.keys():
                    if warpData["Location"].lower() == key.lower():
                        warpData["Location"] = key
                        keyfound = True
                        break
                if not keyfound:
                    errorlist.append(warpData["Location"] + " is not a map.")
                    errorlist.append(filepath)
                    return [False, existinglocations, errorlist]
        # try:
        if warpData not in warplocations:
            warplocations.append(warpData)
        # except TypeError:
        #     print(aW)
        #     print(warplocations)
        #     traceback.print_exc()
        #     quit()
        if printthis:
            print(warplocations)
    return [warplocations, existinglocations, errorlist]


def generateCompDict(newDict, existingDict, targetKey, newWhen, altMap, debug, errorlist):
    # compares conditional warps out with existing warps out
    # returns [dict existingDict (or False), errorlist]
    compKeys = ["Farm", "Casks", "Doors", "DoorOwners", "Greenhouse"]
    changed = False
    for k, v in newDict.items():
        if "WarpsOut" in v:
            if "WarpsOut" in existingDict:
                cwo = compareWarps(v["WarpsOut"], existingDict["WarpsOut"])
            else:
                cwo = v["WarpsOut"]
            if cwo:
                changed = True
                if "ConditionalWarpsOut" not in existingDict:
                    existingDict["ConditionalWarpsOut"] = []
                for cw in cwo:
                    if cw not in existingDict["ConditionalWarpsOut"]:
                        if debug:
                            errorlist.append(targetKey + " now has CWO from Load")
                        cw["Conditions"] = newWhen
                        if altMap:
                            cw["SubMap"] = altMap
                        existingDict["ConditionalWarpsOut"].append(cw)
        if "Shops" in v:
            if "Shops" in existingDict:
                if not all(x in existingDict["Shops"] for x in v["Shops"]):
                    changed = True
                    if "ConditionalShops" not in existingDict:
                        existingDict["ConditionalShops"] = []
                    for shop in v["Shops"]:
                        if shop not in existingDict["ConditionalShops"] and shop not in existingDict["Shops"]:
                            existingDict["ConditionalShops"].append(shop)
            else:
                changed = True
                if "ConditionalShops" not in existingDict:
                    existingDict["ConditionalShops"] = v["Shops"]
                else:
                    for shop in v["Shops"]:
                        if shop not in existingDict["ConditionalShops"]:
                            existingDict["ConditionalShops"].append(shop)
        for sK in compKeys:
            ccs = {}
            if sK in v and sK not in existingDict and v[sK]:
                ccs[sK] = v[sK]
            if sK in v and sK in existingDict and v[sK] != existingDict[sK]:
                ccs[sK] = v[sK]
            if len(ccs.keys()) > 0:
                changed = True
                if "ConditionalChanges" not in existingDict:
                    existingDict["ConditionalChanges"] = []
                ccs["Conditions"] = newWhen
                existingDict["ConditionalChanges"].append(ccs)
    if changed:
        if altMap:
            # only append the altmap if it changes the warps
            if "AltMaps" not in existingDict:
                existingDict["AltMaps"] = []
            if altMap not in existingDict["AltMaps"]:
                existingDict["AltMaps"].append(altMap)
        return [existingDict, errorlist]
    return [False, errorlist]


def generateDefaultWarps(warp, altMap, locationName, existinglocations, warplocations, filepath, auxMap, mode, legacyNames, errorlist):
    # returns [warpLocations, existinglocations, errorlist]
    warpParts = warp.split(" ")
    start = 0
    end = len(warpParts)
    step = 5
    printthis = False
    # if "Railroad.tbin" in filepath:
    #     printthis = True
    for i in range(start, end, step):
        x = i
        thisWarp = warpParts[x:x + step]
        if len(thisWarp) > 4:
            xCoord = thisWarp[0].replace("'", "").replace('"', '')
            yCoord = thisWarp[1].replace("'", "").replace('"', '')
            toX = thisWarp[3].replace("'", "").replace('"', '')
            toY = thisWarp[4].replace("'", "").replace('"', '')
            # if printthis:
            #     print(xCoord)
            #     print(yCoord)
            if int(xCoord) < -1 or int(yCoord) < -1:
                # SVE likes to place default warps at -30 or greater and then replace them with ActionWarps
                return [False, existinglocations, errorlist]
            if thisWarp[2] == "Warp":  # rare edge case bug in Stardew Aquarium MNF_ForestPatch.tmx
                rawLocation = thisWarp[3]
            else:
                rawLocation = thisWarp[2]
            if printthis:
                print(rawLocation)
            warpLocation = translateWarpLocation(rawLocation, legacyNames)
            if warpLocation.isnumeric():
                errorlist.append("generateDefaultWarp: location is numeric: " + warp)
                errorlist.append(filepath)
            # if warpLocation not in primaryMaps and warpLocation not in auxMaps:
            #     errorstring = "Warp Location " + warpLocation + " in " + filepath + " is not a map."
            #     if errorstring not in errorlist:
            #         errorlist.append(errorstring)
            if warpLocation == locationName:
                # discard circular warps
                # errorlist.append("Circular warp in " + filepath + " from " + warpLocation + " to " + locationName)
                return [False, existinglocations, errorlist]
            if warpLocation not in existinglocations:
                # print(warpLocation + " is not already in existinglocations")
                existinglocations.append([xCoord, yCoord, warpLocation])
                warpHours = "All"
                warpType = "Warp"
                if altMap:
                    warpConditions = parseWarpConditions(altMap, warpLocation, toX, toY)
                else:
                    warpConditions = parseWarpConditions(locationName, warpLocation, toX, toY)
                if mode == "vanilla":
                    path = "Vanilla"
                else:
                    path = filepath
                warpDict = {"Type": warpType, "Hours": warpHours, "Conditions": warpConditions, "Location": warpLocation, "X": xCoord, "Y": yCoord, "Path": path}
                if auxMap:
                    warpDict["AuxMap"] = auxMap
                if warpDict not in warplocations:
                    warplocations.append(warpDict)
                if printthis:
                    print(warpDict)
    return [warplocations, existinglocations, errorlist]


def getTrueLocation(filepath, fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapData, errorlist):
    # return [mapname (str), altMap (str), auxMap (str), errorlist (list)]
    if "/" in filepath:
        filename = filepath.rsplit("/", 1)[1]
    else:
        filename = filepath
    altMap = None
    auxMap = None
    # was the filename munged by the dev?
    if "," in filename:
        filename = filename.rsplit(",", 1)[0]
    auxSearch = filename.rsplit(".")[0]
    if mode == "vanilla":
        auxMaps = vanillaAuxMaps
    # is it an auxmap?
    if auxSearch in auxMaps:
        auxAssign = auxMaps[auxSearch]
        if auxAssign != auxSearch:
            auxMap = auxSearch
            mapname = auxAssign
        else:
            mapname = auxSearch
    if not auxMap:
        if mode == "vanilla":
            mapname = filename.split(".")[0]
        # ok maybe it's in filetomap
        if mode == "modded" and fileToMap:
            try:
                mapname = fileToMap[filename]
            except KeyError:
                mapname = filename.rsplit(".")[0]
        elif mode == "modded":
            mapname = filename.rsplit(".")[0]
        if mapname in vanillaAltMaps:
            altMap = vanillaAltMaps[mapname]
    # could be a case error.
    if mode == "modded":
        for key in mapData.keys():
            if mapname.lower() == key.lower():
                mapname = key
                break
    if not mapname:
        print("No Mapname found in " + filepath)
    return [mapname, altMap, auxMap, errorlist]


def makeFileList(changeList, moddedMapList, vmapData, configData, dynos, errorlist):
    # returns list [mapPaths, replacedVanillaMaps, fileToMap, spouseMaps, warpRooms, auxMaps, conditionalChanges, warpnetwork, legacyNames, errorlist]
    # generates all of the lists we'll need to create modded map data.
    mapPaths = []
    replacedVanillaMaps = {}
    fileToMap = {}
    auxMaps = {}
    spouseMaps = []
    warpRooms = []
    conditionalChanges = []
    warpNetwork = []
    legacyNames = {}
    for mm in moddedMapList:
        process = False
        isprimary = False
        if mm["ChangeType"] == "CustomLocation":
            if (mm["FromMapFile"].endswith(".tmx") or mm["FromMapFile"].endswith(".tbin")) and "TargetWithoutPath" not in mm["FromMapFile"]:
                process = True
                try:
                    mapname = mm["Name"]
                except KeyError:
                    mapname = mm["name"]
                # workingFile = mm["FromMapFile"].replace("{{TargetWithoutPath}}", mm["Target"].rsplit("/", 1)[1])
                workingFile = mm["FromMapFile"]
                workingFile = bracketReplacer(workingFile, configData, dynos, {}, "filenames")
                if "warp" in mapname.lower() and mapname not in warpRooms:
                    warpRooms.append(mapname)
                    process = False
            if "MigrateLegacyNames" in mm:
                for ln in mm["MigrateLegacyNames"]:
                    legacyNames[ln] = mapname
        elif mm["ChangeType"] == "Load":
            if (mm["FromFile"].endswith(".tmx") or mm["FromFile"].endswith(".tbin")) and "TargetWithoutPath" not in mm["FromFile"]:
                process = True
                mapname = mm["Target"].rsplit("/", 1)[1]
                printThis = False
                # if mm["FromFile"] == "Assets/maps/locations/Town.tbin":
                #     printThis = True
                workingFile = bracketReplacer(mm["FromFile"], configData, dynos, {}, "filenames")
                if printThis:
                    print(workingFile)
                mapfile = workingFile.rsplit("/", 1)[1].rsplit(".")[0]
                if printThis:
                    print(mapfile)
                if "Spouse" in workingFile and mapname not in spouseMaps:
                    isprimary = False
                    process = False
                    spouseMaps.append(mapname)
                elif "warp" in workingFile.lower() and mapname not in warpRooms:
                    warpRooms.append(mapname)
                    process = False
                elif "When" not in mm:
                    isprimary = True
                elif "When" in mm and mm["When"]:
                    if printThis:
                        print("Processing when")
                    if "ignore" in mm["When"] and mm["When"]["ignore"]:
                        process = True
                        isprimary = True
                    elif len(mm["WhenStrings"]) == 1:
                        # if the only when is a negative eventSeen, it's a primary map
                        if mm['WhenStrings'][0] == "saveBased|player|eventsSeen":
                            if printThis:
                                print("Passed")
                            isprimary = True
                            for eDict in mm["When"]["saveBased"]["player"]["eventsSeen"]:
                                if printThis:
                                    print(eDict)
                                if len(eDict["Negative"]) == 0 or len(eDict["Positive"]) > 0:
                                    conditionalChanges.append(mm)
                                    isprimary = False
                                    process = False
                                    break
                        else:
                            conditionalChanges.append(mm)
                            isprimary = False
                            process = False
                    elif len(mm["WhenStrings"]) > 1:
                        # more than one condition
                        conditionalChanges.append(mm)
                        isprimary = False
                        process = False
                if printThis:
                    print(isprimary)
                if not isprimary and process:
                    if mapfile not in auxMaps.keys():
                        auxMaps[mapfile] = mapname
        if process:
            mapFileName = workingFile.rsplit("/", 1)[1]
            fullMapPath = mm["Path"] + workingFile
            modName = mm["Path"].rsplit("/", 2)[1]
            if mapname in vmapData.keys():
                replacedVanillaMaps[mapname] = mm["ModName"]
            fileToMap[mapFileName] = mapname
            mapPaths.append([fullMapPath, modName])

    for mC in changeList:
        if "FromFile" in mC and (mC["FromFile"].endswith(".tmx") or mC["FromFile"].endswith(".tbin")) and "TargetWithoutPath" not in mC["FromFile"]:
            process = True
            isprimary = True
            workingFile = bracketReplacer(mC["FromFile"], configData, dynos, {}, "filenames")
            ffMapPath = workingFile.rsplit("/", 1)[1]
            ffMapName = ffMapPath.split(".")[0]
            changeTarget = mC["Target"].rsplit("/", 1)[1]
            if 'spouse' in ffMapPath.lower() and ffMapName not in spouseMaps:
                spouseMaps.append(ffMapName)
                process = False
                continue
            if "warp" in changeTarget.lower():
                warpRooms.append(changeTarget)
                process = False
                continue
            if ffMapName not in auxMaps.keys():
                if "When" not in mC:
                    process = True
                    isprimary = True
                    auxMaps[ffMapName] = changeTarget
                if "When" in mC and mC["When"]:
                    if "WhenStrings" not in mC:
                        pprint.pprint(mC)
                        quit()
                    if "ignore" in mC["When"] and mC["When"]["ignore"]:
                        process = True
                        isprimary = True
                    elif len(mC["WhenStrings"]) == 1:
                        # if the only when is a negative eventSeen, it's a primary map
                        if mC['WhenStrings'][0] == "saveBased|player|eventsSeen":
                            process = True
                            for eDict in mC["When"]["saveBased"]["player"]["eventsSeen"]:
                                if len(eDict["Negative"]) == 0 or len(eDict["Positive"]) > 0:
                                    conditionalChanges.append(mC)
                                    process = False
                                    break
                        else:
                            # some other when
                            conditionalChanges.append(mC)
                            process = False
                    elif len(mC["WhenStrings"]) > 1:
                        # more than one condition
                        conditionalChanges.append(mC)
                        process = False
            if process:
                if ffMapPath not in fileToMap:
                    fileToMap[ffMapPath] = changeTarget
                auxMaps[ffMapName] = changeTarget
                fullMapPath = mC["Path"] + workingFile
                modName = mC["Path"].rsplit("/", 2)[1]
                mapPaths.append([fullMapPath, modName])
        if "FromFile" not in mC:
            if mC["Method"] == "WarpNetwork":
                warpNetwork.append(mC)
            if "warp" in mC["Target"].lower():
                changeTarget = mC["Target"].rsplit("/", 1)[1]
                warpRooms.append(changeTarget)
                process = False
                continue
            if "HasConditions" in mC and mC["HasConditions"] == True:
                conditionalChanges.append(mC)
            elif "Update" in mC:
                conditionalChanges.append(mC)

    return [mapPaths, replacedVanillaMaps, fileToMap, spouseMaps, warpRooms, auxMaps, conditionalChanges, warpNetwork, legacyNames, errorlist]


def parseABD(mapDict, errorlist):
    # returns [dict mapDict, list errorlist]
    # determines initial accessibility at New Game start
    accessible = ['Farm']
    inaccessible = []
    uncheckedLocations = ["Farm"]
    while uncheckedLocations:
        mapName = uncheckedLocations.pop(0)
        if "WarpsOut" in mapDict[mapName]:
            outpoints = mapDict[mapName]["WarpsOut"]
            for waypoint in outpoints:
                if ("Conditions" not in waypoint
                        or ("Conditions" in waypoint and waypoint["Conditions"] == "None")
                        and "SubMap" not in waypoint
                        and ("Blocker" not in waypoint or not waypoint["Blocker"])):
                    if waypoint["Location"] not in accessible:
                        accessible.append(waypoint["Location"])
                        uncheckedLocations.append(waypoint["Location"])
                else:
                    inaccessible.append(waypoint["Location"])
        if "AuxWarpsOut" in mapDict[mapName] and mapDict[mapName]["AuxWarpsOut"]:
            auxoutpoints = mapDict[mapName]["AuxWarpsOut"]
            for waypoint in auxoutpoints:
                if ("Conditions" not in waypoint
                        or ("Conditions" in waypoint and waypoint["Conditions"] == "None")
                        and "SubMap" not in waypoint
                        and ("Blocker" not in waypoint or not waypoint["Blocker"])):
                    if waypoint["Location"] not in accessible:
                        accessible.append(waypoint["Location"])
                        uncheckedLocations.append(waypoint["Location"])
                else:
                    inaccessible.append(waypoint["Location"])
        if "ConditionalWarpsOut" in mapDict[mapName] and mapDict[mapName]["ConditionalWarpsOut"]:
            # some conditions ensure initial accessibility
            condoutpoints = mapDict[mapName]["ConditionalWarpsOut"]
            for waypoint in condoutpoints:
                # if the only conditions are eventsSeen Negative or mailReceived Negative, it's likely ABD.
                if isinstance(waypoint["Conditions"], dict):
                    try:
                        if len(waypoint["Conditions"].keys()) == 1 and "saveBased" in waypoint["Conditions"] and "player" in waypoint["Conditions"]["saveBased"] and len(waypoint["Conditions"]["saveBased"]["player"].keys()) == 1:
                            if "eventsSeen" in waypoint["Conditions"]["saveBased"]["player"] and len(waypoint["Conditions"]["saveBased"]["player"]["eventsSeen"]) == 1 and len(waypoint["Conditions"]["saveBased"]["player"]["eventsSeen"][0]["Negative"]) > 0 and len(waypoint["Conditions"]["saveBased"]["player"]["eventsSeen"][0]["Positive"]) == 0:
                                if waypoint["Location"] not in accessible:
                                    accessible.append(waypoint["Location"])
                                    uncheckedLocations.append(waypoint["Location"])
                            if "mailReceived" in waypoint["Conditions"]["saveBased"]["player"] and len(waypoint["Conditions"]["saveBased"]["player"]["mailReceived"]) == 1 and len(waypoint["Conditions"]["saveBased"]["player"]["mailReceived"][0]["Negative"]) > 0 and len(waypoint["Conditions"]["saveBased"]["player"]["mailReceived"][0]["Positive"]) == 0:
                                if waypoint["Location"] not in accessible:
                                    accessible.append(waypoint["Location"])
                                    uncheckedLocations.append(waypoint["Location"])
                    except AttributeError:
                        errorlist.append("parseABD error with waypoint: " + str(waypoint))
                        errorlist.append("Traceback: " + traceback.format_exc())
    for mapKey in accessible:
        mapDict[mapKey]["AccessibleByDefault"] = True
    for k, v in mapDict.items():
        if k not in accessible:
            mapDict[k]["AccessibleByDefault"] = False
    # pprint.pprint(accessible)
    return [mapDict, errorlist]


def parseAltMaps(mapDict, errorlist):
    # returns [mapDict, errorlist]
    altmapkeys = []
    toAdd = {}
    for k, v in mapDict.items():
        existinglocations = []
        # print(k)
        if "AltMapOf" in v and "WarpsOut" in v:
            # print(v["AltMapOf"])
            parentkey = v["AltMapOf"]
            toAdd[parentkey] = {"WarpsOut": []}
            if parentkey in mapDict:
                for pV in mapDict[parentkey]["WarpsOut"]:
                    existinglocations.append(pV["Location"])
            for locDict in v["WarpsOut"]:
                if locDict["Location"] not in existinglocations:
                    existinglocations.append(locDict["Location"])
                    if parentkey != "CommunityCenter":
                        locDict["SubMap"] = k
                    toAdd[parentkey]["WarpsOut"].append(locDict)
            altmapkeys.append(k)
            if "AltMaps" not in toAdd[parentkey]:
                toAdd[parentkey]["AltMaps"] = []
            if k not in toAdd[parentkey]["AltMaps"]:
                toAdd[parentkey]["AltMaps"].append(k)
    for k, v in toAdd.items():
        if k not in mapDict:
            mapDict[k] = {"WarpsOut": [], "Farm": False, "Greenhouse": False, "Casks": False, "AltMaps": []}
        mapDict[k]["WarpsOut"] += v["WarpsOut"]
        if "AltMaps" not in mapDict[k]:
            mapDict[k]["AltMaps"] = []
        for am in v["AltMaps"]:
            if am not in mapDict[k]["AltMaps"]:
                mapDict[k]['AltMaps'].append(am)
    for amk in altmapkeys:
        del mapDict[amk]

    return [mapDict, errorlist]


def parseBusLocations(mapDict, manifests, rootdir, errorlist):
    # returns [mapDict, errorlist]
    busfiles = list(filter(None, [value if value["packFor"].lower() == "hootless.buslocations" and value["ID"] != "hootless.BLDesert" else '' for value in manifests]))
    for bf in busfiles:
        bfpath = rootdir + bf["ModFolder"] + "/content.json"
        bfdata = pyjson5.load(open(bfpath, encoding="utf-8"),)
        mapTarget = bfdata["mapname"]
        ticketPrice = bfdata["ticketPrice"]
        woDict = {"Conditions": {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccVault"], "Target": "hostPlayer"}]}}},
                  "Hours": "1000-1800",
                  "Location": mapTarget,
                  "Type": "BusWarp",
                  "Path": bfpath,
                  "TicketPrice": ticketPrice
                  }
        mapDict["BusStop"]["ConditionalWarpsOut"].append(woDict)
    return [mapDict, errorlist]


def parseConditionalWarps(mapDict, cChanges, auxMaps, fileToMap, mode, vanillaAuxMaps, vanillaAltMaps, festivalMaps, legacyNames, errorlist):
    # returns [dict mapDict, list errorlist]
    debug = False
    # We don't want everything, just stuff that affects productivity.
    ignoreProps = ["DayTiles", "NightTiles", "CustomCompanions", "Music", "Light", "NPCWarp", "ForceAllowTreePlanting"]
    ignoreActions = ["AdventureShop", "Arcade_Prairie", "Arcade_Minecart",
                     "BuyBackpack", "Billboard", "Blackjack", "Blacksmith", "Buy",
                     "BrokenBeachBridge", "Bus", "BusTicket", "BuyQiCoins",
                     "Carpenter", "ChangeIntoSwimsuit", "ChangeOutOfSwimsuit",
                     "ClubCards", "ClubComputer", "ClubSeller", "ClubShop",
                     "ClubSlots", "ColaMachine", "Concessions", "DesertBus",
                     "Dialogue", "DivorceBook", "ElliotBook", "ElliotPiano",
                     "Emote", "EvilShrineLeft", "EvilShrineCenter", "EvilShrineRight",
                     "FaceDirection", "FarmerFile", "Garbage", "Gunther", "HMGTF",
                     "IceCreamStand", "JojaShop", "Jukebox", "kitchen", "Letter",
                     "legendarySword", "LuauSoup", "MagicInk", "Mailbox",
                     "Material", "MessageOnce", "Message", "MessageSpeech",
                     "MineSign", "MinecartTransport", "MineElevator", "NextMineLevel",
                     "Notes", "NPCMessage", "playSound", "PoolEntrance", "QiCoins",
                     "Saloon", "SandDragon", "Shop", "Sleep", "Theater_BoxOffice",
                     "TownMailbox", "WizardBook", "WizardHatch",
                     "WizardShrine"]
    knownActions = ["Door", "EnterSewer", "LockedDoorWarp", "MagicWarp", "Shop", "Warp", "WarpCommunityCenter", "WarpGreenhouse"]
    keepProps = ["IsFarm", "IsGreenhouse", "CanCaskHere"]
    # shift any existing warpsout with conditions to conditional warps out
    for idx, change in enumerate(tqdm(cChanges, desc="Conditional Warps Out")):
        if debug:
            errorlist.append("Processing " + str(idx))
        processed = False
        changed = False
        # begin Location logic
        if "Target" in change:
            if "," in change["Target"]:  # workaround bad mod dev code, "Target": "Custom_GrandpasShedGreenhouse,Maps"
                rawTarget = change["Target"].rsplit(",", 1)[0]
            else:
                rawTarget = change["Target"]
            # mFile = mC["Target"].rsplit("/")[1]
            locationdata = getTrueLocation(rawTarget, fileToMap, "modded", auxMaps, vanillaAuxMaps, vanillaAltMaps, mapDict, errorlist)
            mapTarget = locationdata[0]
            altMap = locationdata[1]
            auxMap = locationdata[2]
            errorlist = locationdata[3]
            if mapTarget not in mapDict:
                # possibly a submap?
                mapLookup = getTrueLocation(change["Target"], fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapDict, errorlist)
                mapTarget = mapLookup[1]
            if mapTarget is None:
                if debug:
                    errorlist.append(change["Target"] + " is a Nonexistent map")
                processed = True
                continue
        # end Location logic
        if change["Action"] == "Load":
            loadedmapfile = False
            if "{{" in change["FromFile"]:
                if debug:
                    print("Ignoring " + change["FromFile"] + " as cosmetic")
                processed = True
                continue
            if change["FromFile"].endswith(".tbin"):
                filepath = [change["Path"] + change["FromFile"], change["ModName"]]
                parsedMap = parseTbin(filepath, "modded", fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapDict, legacyNames, errorlist)
                loadedmapfile = True
            elif change["FromFile"].endswith(".tmx"):
                filepath = [change["Path"] + change["FromFile"], change["ModName"]]
                parsedMap = parseTMX(filepath, "modded", fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapDict, legacyNames, errorlist)
                loadedmapfile = True
            if loadedmapfile:
                newData = parsedMap[0]
                errorlist = parsedMap[1]
                if not newData:
                    if debug:
                        errorlist.append("No new data in Loaded Map " + str(filepath))
                    processed = True
                    continue
                else:
                    if altMap:
                        thisTarget = altMap
                        altMapName = mapTarget
                    else:
                        thisTarget = mapTarget
                        altMapName = None
                    compDict = generateCompDict(newData, mapDict[thisTarget], thisTarget, change['When'], altMapName, debug, errorlist)
                    replaceDict = compDict[0]
                    errorlist = compDict[1]
                    if replaceDict:
                        mapDict[thisTarget] = replaceDict
                        changed = True
                        processed = True
                    else:
                        if debug:
                            print("No new Warps out in Loaded Map " + str(filepath))
                        processed = True
            # endif Load
        if change["Action"] == "EditMap":
            if "FromFile" in change:
                if "{{" in change["FromFile"]:
                    if debug:
                        print("Ignoring " + change["FromFile"] + " as cosmetic.")
                    processed = True
                    continue
            if "MapProperties" in change:
                # properties such as IsFarm, IsGreenhouse
                for propType, val in change["MapProperties"].items():
                    if propType in ignoreProps:
                        processed = True
                        if debug:
                            print("Ignoring cosmetic property MapProperties>> " + propType)
                    if propType in keepProps and val == "T":
                        if "ConditionalChanges" not in mapDict[mapTarget]:
                            mapDict[mapTarget]["ConditionalChanges"] = []
                        ccs = {}
                        if propType == "IsFarm":
                            ccs["Farm"] = True
                        if propType == "IsGreenhouse":
                            ccs["Greenhouse"] = True
                        if propType == "CanCaskHere":
                            ccs["Casks"] = True
                        ccs["Conditions"] = change["When"]
                        if ccs not in mapDict[mapTarget]["ConditionalChanges"]:
                            changed = True
                            processed = True
                            if debug:
                                print("Setting " + mapTarget + " as a Farm")
                            mapDict[mapTarget]["ConditionalChanges"].append(ccs)
                # endif MapProperties
            if "MapTiles" in change:
                for mT in change["MapTiles"]:
                    if "SetProperties" in mT:
                        cwos = []  # conditional warps out
                        for propType, val in mT["SetProperties"].items():
                            if isinstance(val, str):
                                valParts = val.split(" ")
                            actionWord = valParts[0]
                            if actionWord in ignoreActions:
                                processed = True
                                if debug:
                                    errorlist.append("Ignoring " + actionWord)
                                continue
                            if actionWord not in knownActions:
                                processed = True
                                if debug:
                                    print("Ignoring custom action: " + actionWord)
                            elif propType in ignoreProps:
                                processed = True
                                if debug:
                                    errorlist.append("Ignoring cosmetic property MapTiles >> SetProperties >> " + propType)
                                continue
                            elif propType == "Action" and ("Warp" in actionWord or "LoadMap" in actionWord):
                                # adding action Warps
                                if actionWord == "LockedDoorWarp" or actionWord == "MagicWarp" or actionWord == "Warp" or actionWord == "LoadMap":
                                    processed = True
                                    parsedWarp = generateActionWarps(val, altMap, mapTarget, [], [], change["Path"], auxMap, errorlist, mapDict, legacyNames, "conditional")
                                    newWarps = parsedWarp[0]
                                    errorlist = parsedWarp[2]
                                    if newWarps:
                                        cwos.append(newWarps)
                            elif propType == "Action" and actionWord == "Door":
                                # adding door owner
                                if "ConditionalDoorOwners" not in mapDict[mapTarget]:
                                    mapDict[mapTarget]["ConditionalDoorOwners"] = []
                                doorString = " ".join(valParts[1:])
                                cdo = {"NPC": doorString, "Conditions": change["When"]}
                                mapDict[mapTarget]["ConditionalDoorOwners"].append(cdo)
                                if debug:
                                    errorlist.append("New Conditional Door Owner")
                                processed = True
                                changed = True
                            elif propType == "TouchAction" and ("Warp" in actionWord or "LoadMap" in actionWord):
                                if actionWord == "Warp" or actionWord == "LoadMap":
                                    xCoord = mT["Position"]["X"]
                                    yCoord = mT["Position"]["Y"]
                                    warpParts = val.split(" ")
                                    warpString = "TouchWarp " + str(xCoord) + " " + str(yCoord) + " " + " ".join(warpParts[1:])
                                    # print(warpString)
                                    parsedWarp = generateActionWarps(warpString, altMap, mapTarget, [], [], change["Path"], auxMap, errorlist, mapDict, legacyNames, "conditional")
                                    newWarps = parsedWarp[0]
                                    errorlist = parsedWarp[2]
                                    # print(newWarps)
                                    if newWarps:
                                        cwos.append(newWarps)
                                    processed = True
                                if actionWord == "MagicWarp":
                                    processed = True
                                    parsedWarp = generateActionWarps(val, altMap, mapTarget, [], [], change["Path"], auxMap, errorlist, mapDict, legacyNames, "conditional")
                                    newWarps = parsedWarp[0]
                                    errorlist = parsedWarp[2]
                                    if newWarps:
                                        cwos.append(newWarps)
                                    # print(mapTarget + " " + propType + " " + str(warplocations))
                            elif propType == "Shop":
                                errorlist.append("For Dev: Cpatcher adding Shop Tile by MapTiles change in file " + change["File"])
                            # end SetProperties loop
                        if cwos:
                            # add the cwos to the mapDict
                            changed = True
                            if debug:
                                try:
                                    errorlist.append(mapTarget + " has CWO from EditMap > MapTiles > SetProperties")
                                except TypeError:
                                    print("No target for CWO: " + change["Target"])
                                    quit()
                            if "ConditionalWarpsOut" not in mapDict[mapTarget]:
                                mapDict[mapTarget]["ConditionalWarpsOut"] = []
                            for cw in cwos:
                                for woDict in cw:
                                    if "WhenString" in change and "instant|Time" in change["WhenString"]:
                                        hourData = change["When"]["instant"]["Time"]["Positive"]
                                        if hourData:
                                            woDict["Hours"] = hourData[8:]
                                            del change["When"]["instant"]["Time"]
                                    woDict["Conditions"] = change["When"]
                                    if woDict not in mapDict[mapTarget]["ConditionalWarpsOut"]:
                                        mapDict[mapTarget]["ConditionalWarpsOut"].append(woDict)
                                # end cwos loop
                            # endif cwos
                    if "SetTileSheet" in mT:
                        processed = True
                        if debug:
                            errorlist.append("Ignoring SetTileSheet as cosmetic")
                        continue
                    if "Remove" in mT:
                        # make sure what they're removing isn't a warp tile
                        if "Buildings" in mT["Layer"]:
                            xCoord = int(mT["Position"]["X"])
                            yCoord = int(mT["Position"]["Y"])
                        if "WarpsOut" in mapDict[mapTarget]:
                            for wO in mapDict[mapTarget]["WarpsOut"]:
                                if "X" in wO and wO["X"]:
                                    xStripped = int(wO["X"].replace("'", "").replace('"', ''))
                                    yStripped = int(wO["Y"].replace("'", "").replace('"', ''))
                                    if xCoord == xStripped and yCoord == yStripped:
                                        if "ConditionalDeletedWarps" not in mapDict[mapTarget]:
                                            mapDict[mapTarget]["ConditionalDeletedWarps"] = []
                                        condWO = copy.deepcopy(wO)
                                        condWO["Conditions"] = change["When"]
                                        if condWO not in mapDict[mapTarget]["ConditionalDeletedWarps"]:
                                            processed = True
                                            changed = True
                                            if debug:
                                                errorlist.append("Found deleted warps in " + mapTarget)
                                            mapDict[mapTarget]["ConditionalDeletedWarps"].append(condWO)
                            if not changed:
                                processed = True
                                if debug:
                                    errorlist.append("Removals did not delete any warps.")
                    # end MapTiles loop
                # endif MapTiles
            if "TextOperations" in change:
                for tO in change["TextOperations"]:
                    if "Target" in tO:
                        if tO["Target"][1] == "Warp":
                            processed = True
                            parsedWarp = generateDefaultWarps(tO["Value"], altMap, mapTarget, [], [], change["Path"], auxMap, "modded", legacyNames, errorlist)
                            newWarps = parsedWarp[0]
                            errorlist = parsedWarp[2]
                            if newWarps:
                                if "ConditionalWarpsOut" not in mapDict[mapTarget]:
                                    mapDict[mapTarget]["ConditionalWarpsOut"] = []
                                for wO in newWarps:
                                    wO["Conditions"] = change["When"]
                                    mapDict[mapTarget]["ConditionalWarpsOut"].append(wO)
                        if tO["Target"][1] in ignoreProps:
                            processed = True
                            if debug:
                                errorlist.append("Ignoring " + tO["Target"][1] + " as cosmetic")
                            continue
                    # end TextOperations loop
                # endif TextOperations
            if "ToArea" in change and "FromFile" in change:
                # map overlays and replacements
                modName = change["Path"].rsplit("/", 2)[1]
                filepath = [change["Path"] + change["FromFile"], modName]
                if change["FromFile"].endswith(".tmx"):
                    parsedMap = parseTMX(filepath, "modded", fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapDict, legacyNames, errorlist)
                    newData = parsedMap[0]
                    errorlist = parsedMap[1]
                if change["FromFile"].endswith(".tbin"):
                    parsedMap = parseTbin(filepath, "modded", fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapDict, legacyNames, errorlist)
                    newData = parsedMap[0]
                    errorlist = parsedMap[1]
                if not newData:
                    if debug:
                        errorlist.append("No new data in EditData TMX")
                    continue
                if altMap:
                    thisTarget = altMap
                    altMapName = mapTarget
                else:
                    thisTarget = mapTarget
                    altMapName = None
                compDict = generateCompDict(newData, mapDict[thisTarget], thisTarget, change['When'], altMapName, debug, errorlist)
                replaceDict = compDict[0]
                errorlist = compDict[1]
                if replaceDict:
                    mapDict[thisTarget] = replaceDict
                    processed = True
                    changed = True
                else:
                    processed = True
                    if debug:
                        errorlist.append("Empty replaceDict for " + mapTarget)
        if not changed and debug:
            errorlist.append("No Change Found")
        elif debug:
            if "ConditionalWarpsOut" in mapDict[mapTarget]:
                print(mapDict[mapTarget]["ConditionalWarpsOut"])
            if "ConditionalDeletedWarps" in mapDict[mapTarget]:
                print(mapDict[mapTarget]["ConditionalDeletedWarps"])
            if "ConditionalDoorOwners" in mapDict[mapTarget]:
                print(mapDict[mapTarget]["ConditionalDoorOwners"])
            if "ConditionalChanges" in mapDict[mapTarget]:
                print(mapDict[mapTarget]["ConditionalChanges"])
        if not processed and debug:
            errorlist.append("The following change was not processed: ")
            errorlist.append(change)
    return [mapDict, errorlist]


def parseMapFiles(mapFileList, mode, fileToMap, auxMaps, replacedVanillaMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist):
    # return list [mapData (dict), errorlist (list)]
    for mfl in tqdm(mapFileList, desc="Reading TMX and TBIN files"):
        if mode == "modded":
            mFile = mfl[0]
            modName = mfl[1]
        else:
            mFile = mfl
            mfl = [mFile, "Vanilla"]
            modName = "Vanilla"
        mData = {}
        if mFile.endswith(".tbin"):
            parsedMapData = parseTbin(mfl, mode, fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist)
        if mFile.endswith(".tmx"):
            parsedMapData = parseTMX(mfl, mode, fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist)
        mData = parsedMapData[0]
        errorlist = parsedMapData[1]
        if mData:
            k = list(mData.keys())[0]
            v = list(mData.values())[0]
            replacementkeys = ["WarpsOut", "doors", "doorowners"]
            listsToEmpty = ["WarpsIn", "WarpsOut", "AuxWarpsIn", "AuxWarpsOut", "ConditionalWarpsIn", "ConditionalWarpsOut"]
            # replaceMap = False
            if k in mapData:
                if mode == "modded" and k in replacedVanillaMaps and any(x in v for x in replacementkeys):
                    if "ReplacedBy" not in mapData[k]:
                        mapData[k]["ReplacedBy"] = []
                    if replacedVanillaMaps[k] not in mapData[k]["ReplacedBy"]:
                        mapData[k]["ReplacedBy"].append(replacedVanillaMaps[k])
                    # wipe the warps in, we'll have to recalculate them.
                    for eKey in listsToEmpty:
                        if eKey in mapData[k]:
                            mapData[k][eKey] = []
                    mapData[k]["AccessibleByDefault"] = False
                if mode == "modded" and "AuxWarpsOut" in v:
                    if "AuxedBy" not in mapData[k]:
                        mapData[k]["AuxedBy"] = []
                    for aB in v["AuxedBy"]:
                        if aB not in mapData[k]["AuxedBy"]:
                            mapData[k]["AuxedBy"].append(aB)
                if "WarpsOut" in v:
                    if "WarpsOut" not in mapData[k]:
                        mapData[k]["WarpsOut"] = []
                    for wo in v["WarpsOut"]:
                        if wo not in mapData[k]["WarpsOut"]:
                            mapData[k]["WarpsOut"].append(wo)
                if "Doors" in v:
                    mapData[k]["Doors"] = v["Doors"]
                if "Shops" in v:
                    mapData[k]["Shops"] = v["Shops"]
                if "DoorOwners" in v:
                    mapData[k]["DoorOwners"] = v["DoorOwners"]
                if "DoorCoords" in v:
                    mapData[k]["DoorCoords"] = v["DoorCoords"]
                if "Casks" in v:
                    mapData[k]["Casks"] = v["Casks"]
                if "Farm" in v:
                    mapData[k]["Farm"] = v["Farm"]
                if "Greenhouse" in v:
                    mapData[k]["Greenhouse"] = v["Greenhouse"]
                if "AuxMaps" in v:
                    if "AuxMaps" not in mapData[k]:
                        mapData[k]["AuxMaps"] = []
                    for aM in v["AuxMaps"]:
                        if aM not in mapData[k]["AuxMaps"]:
                            mapData[k]["AuxMaps"].append(aM)
                if "AuxWarpsOut" in v:
                    if "AuxWarpsOut" not in mapData[k]:
                        mapData[k]["AuxWarpsOut"] = []
                    for awo in v["AuxWarpsOut"]:
                        if awo not in mapData[k]["AuxWarpsOut"]:
                            mapData[k]["AuxWarpsOut"] += v["AuxWarpsOut"]
                if "FestMapOf" in v:
                    mapData[k]["FestMapOf"] = v["FestMapOf"]
            else:
                v["ModName"] = modName
                mapData[k] = v
    return [mapData, errorlist]


def parseTbin(mfl, mode, fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist):
    # returns [outData (dict), errorlist (list)]
    # binary parsing
    mFile = mfl[0]
    modName = mfl[1]
    # printthis = False
    # if mFile == "E:/Program Files/SteamLibrary/steamapps/common/Stardew Valley/Mods/Stardew Valley Expanded/[CP] Stardew Valley Expanded/assets/Maps/MapPatches/BearUnlocked.tbin":
    #     printthis = True
    avoidMaps = ["spousePatios", "Volcano_Well", "Volcano_SetPieces",
                 "VolcanoTemplate", "Spouse", "Island_Secret"]
    if any(x in mFile for x in avoidMaps):
        return False
    outData = {}
    warplocations = []
    existinglocations = []
    doorOwners = []
    locationdata = getTrueLocation(mFile, fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapData, errorlist)
    locationName = locationdata[0]
    outData[locationName] = {}
    altMap = locationdata[1]
    auxMap = locationdata[2]
    errorlist = locationdata[3]
    if locationName in festivalMaps:
        outData[locationName]["FestMapOf"] = festivalMaps[locationName]["Parent"]
    if altMap:
        outData[locationName]["AltMapOf"] = altMap
    if auxMap:
        outData[locationName]["AuxMaps"] = [auxMap]
        outData[locationName]["AuxedBy"] = [modName]
        warpOutKey = "AuxWarpsOut"
    else:
        warpOutKey = "WarpsOut"

    def gibberishStripper(inList):
        # returns list
        # binary2strings is not perfect, it leaves some nonsense in the strings.
        for idx, ele in enumerate(inList):
            # stripping = False
            # print("Before: " + repr(ele))
            if any(x == "\\" for x in repr(ele[-2:])):
                # stripping = True
                # print("slash found")
                eleParts = repr(ele).rsplit("\\", 1)
                ele = eleParts[0]
                # print("After strip: " + repr(ele))
            if any(x.isupper() for x in ele[-2:]):
                # print("Uppercase detected")
                # stripping = True
                eleParts = re.split(r"(?<=.)(?=[A-Z])", ele)
                # print(eleParts)
                if any(x.isupper() for x in eleParts[-2]) and len(eleParts[-2]) <= 2:
                    ele = "".join(eleParts[0:-2])
                elif (x.isupper() for x in eleParts[-1]) and len(eleParts[-1]) <= 2:
                    ele = "".join(eleParts[0:-1])
                # print("After strip: " + repr(ele))
            ele = ele.replace("'", "").replace('"', "")
            inList[idx] = ele
        return inList

    # outData = []
    tbinStrings = []
    with open(mFile, 'rb') as file:
        data = file.read()
        for (string, type, span, is_interesting) in b2s.extract_all_strings(data, only_interesting=True):
            tbinStrings.append(string)

    # print(mFile)
    # is it a farm?
    outData[locationName]["Farm"] = any(x for x in tbinStrings if "IsFarm" in x)

    # is it a Greenhouse?
    outData[locationName]["Greenhouse"] = any(x for x in tbinStrings if "IsGreenhouse" in x)

    # can you cask Here?
    outData[locationName]["Casks"] = any(x for x in tbinStrings if "CanCaskHere" in x)

    # find the warps, doors, door owners
    possibleWarps = []
    possibleDoors = []
    possibleDoorOwners = []
    possibleShops = []
    warps = []
    actionWarps = []
    doorCoords = []
    doorOwners = []
    shops = []
    for idx, tS in enumerate(tbinStrings):
        if tS == "Warp":
            possibleWarps.append(tbinStrings[idx + 1])
        elif "Warp" in tS and tS != "WarpTotemEntry":
            possibleWarps.append(tbinStrings[idx])
        elif "LoadMap" in tS or "BoatTicket" in tS:
            possibleWarps.append(tbinStrings[idx])
        if tS == "Doors":
            possibleDoors.append(tbinStrings[idx + 1])
        if tS.startswith("Door "):
            possibleDoorOwners.append(tbinStrings[idx])
        if tS == "Shop":
            possibleShops.append(tbinStrings[idx + 1])
    # remove gibberish
    possibleWarps = gibberishStripper(possibleWarps)
    possibleDoors = gibberishStripper(possibleDoors)
    possibleDoorOwners = gibberishStripper(possibleDoorOwners)
    possibleShops = gibberishStripper(possibleShops)
    # if possibleShops:
    #     print(possibleShops)
    # if "Railroad.tbin" in mFile:
    #     print(possibleWarps)
    for idx, pW in enumerate(possibleWarps):
        defaultRe = r"[-0-9]+ [-0-9]+ [A-Za-z_]+ [-0-9]+ [-0-9]+"
        if pW.startswith("Warp") or pW.startswith("MagicWarp") or pW.startswith("LockedDoorWarp") or pW.startswith("TouchWarp") or pW.startswith("LoadMap") or pW.startswith("BoatTicket"):
            actionWarps.append(pW)
        elif re.match(defaultRe, pW):
            warps.append(pW)
    for pd in possibleDoors:
        doorparts = pd.split(" ")
        start = 0
        end = len(doorparts)
        step = 4
        for i in range(start, end, step):
            x = i
            thisDoor = doorparts[x:x + step]
            doorX = int(thisDoor[0])
            doorY = int(thisDoor[1])
            doorCoords.append([doorX, doorY])
    for idx, pDO in enumerate(possibleDoorOwners):
        dS = pDO[5:]
        doorOwners.append(dS)
    for idx, pS in enumerate(possibleShops):
        if pS not in shops:
            shops.append(pS)
    # print(actionWarps)

    if doorOwners:
        outData[locationName]["Doors"] = len(doorOwners)
        outData[locationName]["DoorOwners"] = doorOwners
        outData[locationName]["DoorCoords"] = doorCoords
    if shops:
        outData[locationName]["Shops"] = shops
    for warp in warps:
        lastwarp = warp
        lastfile = mFile
        processedwarps = generateDefaultWarps(warp, altMap, locationName, existinglocations, warplocations, mFile, auxMap, "modded", legacyNames, errorlist)
        if processedwarps[0]:  # can return False with extreme negative coords
            warplocations = processedwarps[0]
        existinglocations = processedwarps[1]
        errorlist = processedwarps[2]
        if isinstance(warplocations, bool):
            print(lastwarp)
            print(lastfile)
    for aW in actionWarps:
        # print(aW)
        lastwarp = aW
        lastfile = mFile
        processedAWs = generateActionWarps(aW, altMap, locationName, existinglocations, warplocations, mFile, auxMap, errorlist, mapData, legacyNames)
        if processedAWs[0]:
            warplocations = processedAWs[0]
        existinglocations = processedAWs[1]
        errorlist = processedAWs[2]
        if isinstance(warplocations, bool):
            print(lastwarp)
            print(lastfile)
    outData[locationName][warpOutKey] = warplocations
    # if printthis:
    #     pprint.pprint(outData)
    # if "Railroad" in mFile:
    #     pprint.pprint(outData)
    return [outData, errorlist]


def parseTMX(mfl, mode, fileToMap, auxMaps, vanillaAuxMaps, vanillaAltMaps, festivalMaps, mapData, legacyNames, errorlist):
    # returns [outData (dict), errorlist (list)]
    # parses TMX files
    # if mode == "conditional":
    #     print("Hello")
    avoidMaps = ["spousePatios", "Volcano_Well", "Volcano_SetPieces",
                 "VolcanoTemplate", "Spouse", "Island_Secret"]
    mFile = mfl[0]
    modName = mfl[1]
    printthis = False
    # if mFile.endswith("RSVGathering.tmx"):
    #     printthis = True
    if mode == "vanilla" and any(x in mFile for x in avoidMaps):
        return [False, errorlist]
    outData = {}
    warplocations = []
    existinglocations = []
    doorCoords = []
    doors = 0
    doorOwners = []
    shops = []
    locationdata = getTrueLocation(mFile, fileToMap, mode, auxMaps, vanillaAuxMaps, vanillaAltMaps, mapData, errorlist)
    locationName = locationdata[0]
    outData[locationName] = {}
    altMap = locationdata[1]
    auxMap = locationdata[2]
    errorlist = locationdata[3]
    outData[locationName]["Farm"] = False
    outData[locationName]["Greenhouse"] = False
    outData[locationName]["Casks"] = False
    if locationName in festivalMaps:
        outData[locationName]["FestMapOf"] = festivalMaps[locationName]["Parent"]
    if altMap:
        outData[locationName]["AltMapOf"] = altMap
    if auxMap:
        outData[locationName]["AuxMaps"] = [auxMap]
        outData[locationName]["AuxedBy"] = [modName]
        warpOutKey = "AuxWarpsOut"
    else:
        warpOutKey = "WarpsOut"
    for _, elem in ET.iterparse(mFile, events=("end",)):
        if elem.tag == "properties":
            for child in elem:
                if child.tag == "property":
                    propType = child.get("name")
                    if propType == "IsFarm":
                        fV = child.get("value")
                        if fV == "T":
                            outData[locationName]["Farm"] = True
                    if propType == "IsGreenhouse":
                        fV = child.get("value")
                        if fV == "T":
                            outData[locationName]["Greenhouse"] = True
                    if propType == "CanCaskHere":
                        fV = child.get("value")
                        if fV == "T":
                            outData[locationName]["Casks"] = True
                    if propType == "Warp":
                        warp = child.get("value")
                        if printthis:
                            print(warp)
                        processedwarps = generateDefaultWarps(warp, altMap, locationName, existinglocations, warplocations, mFile, auxMap, mode, legacyNames, errorlist)
                        if processedwarps[0]:
                            warplocations = processedwarps[0]
                        existinglocations = processedwarps[1]
                        errorlist = processedwarps[2]
                    if propType == "Doors":
                        propVal = child.get("value")
                        doorparts = propVal.split(" ")
                        start = 0
                        end = len(doorparts)
                        step = 4
                        for i in range(start, end, step):
                            x = i
                            thisDoor = doorparts[x:x + step]
                            try:
                                doorX = int(thisDoor[0])
                                doorY = int(thisDoor[1])
                                doorCoords.append([doorX, doorY])
                            except IndexError:
                                errorlist.append("For Dev: parseTMX error reading doorparts: " + doorparts)
                                errorlist.append("For Dev: " + mFile)
                    if propType == "Action" or propType == "TouchAction":
                        propVal = child.get("value")
                        if propVal.startswith("Door "):
                            dOString = propVal
                            doorOwners.append(dOString[5:])
                        if "Warp" in propVal or "LoadMap" in propVal or "Theater_Exit" in propVal or "BoatTicket" in propVal:  # action warps
                            processedAWs = generateActionWarps(propVal, altMap, locationName, existinglocations, warplocations, mFile, auxMap, errorlist, mapData, legacyNames, mode)
                            if processedAWs[0]:
                                warplocations = processedAWs[0]
                            existinglocations = processedAWs[1]
                            errorlist = processedAWs[2]
                            if printthis:
                                pprint.pprint(warplocations)
                    if propType == "Shop":
                        propVal = child.get("value")
                        if propVal not in shops:
                            shops.append(propVal)
            elem.clear()
    if warplocations:
        outData[locationName][warpOutKey] = warplocations
    if doorOwners:
        outData[locationName]["Doors"] = len(doorOwners)
        outData[locationName]["DoorOwners"] = doorOwners
        outData[locationName]["DoorCoords"] = doorCoords
    if shops:
        outData[locationName]["Shops"] = shops
    if mode == "vanilla":
        # don't return empty areas for Vanilla
        # if printthis:
        #     pprint.pprint(outData)
        if warplocations or doorOwners or (doors > 0):
            # print(mFile)
            # pprint.pprint(outData)
            return [outData, errorlist]
        else:
            return [False, errorlist]
    elif mode == "modded":
        # return all areas from modded as they may get warpouts later
        return [outData, errorlist]
    else:
        return [False, errorlist]


def parseTrainStations(mapDict, manifests, rootdir, configParams, dynamicTokens, errorlist):
    # returns [mapDict, errorlist]
    trainfiles = list(filter(None, [value if value["packFor"].lower() == "cherry.trainstation" and value["ID"] != "hootless.BLDesert" else '' for value in manifests]))
    for tf in trainfiles:
        tfpath = rootdir + tf["ModFolder"] + "/TrainStops.json"
        tfdata = pyjson5.load(open(tfpath, encoding="utf-8"),)
        for k, v in tfdata.items():
            if k == "BoatStops":
                mapkey = "BoatTunnel"
                hours = "800-1700"
                warpType = "BoatWarp"
            elif k == "TrainStops":
                mapkey = "Railroad"
                hours = "All"
                warpType = "TrainWarp"
            for tstop in v:
                destination = tstop["TargetMapName"]
                ticketPrice = tstop["Cost"]
                if "Conditions" in tstop and tstop["Conditions"]:
                    tstop["When"] = tstop["Conditions"]
                    parentDir = rootdir + tf["ModFolder"]
                    parsedWhens = parseWhens(tstop, dynamicTokens, configParams, manifests, parentDir)
                    tstop["When"] = parsedWhens[0]
                    conditions = tstop["When"]
                elif mapkey == "BoatTunnel":
                    conditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["willyBoatFixed"], "Target": "hostPlayer"}]}}}
                    woKey = "ConditionalWarpsOut"
                else:
                    conditions = "None"
                    woKey = "WarpsOut"
                woDict = {"Conditions": conditions,
                          "Hours": hours,
                          "Location": destination,
                          "Type": warpType,
                          "Path": tfpath,
                          "TicketPrice": ticketPrice
                          }
            if woKey not in mapDict[mapkey]:
                mapDict[mapkey][woKey] = []
            mapDict[mapkey][woKey].append(woDict)
    return [mapDict, errorlist]


def parseVanillaConditionalWarps(mapDict, replacedVanillaMaps, mode, errorlist):
    # returns [dict mapDict, list errorlist]
    # move any WarpsOut with conditions to ConditionalWarpsOut
    for k, v in mapDict.items():
        toDelete = []
        if "WarpsOut" in v:
            for wO in v["WarpsOut"]:
                if isinstance(wO["Conditions"], dict):
                    if "ConditionalWarpsOut" not in mapDict[k]:
                        mapDict[k]["ConditionalWarpsOut"] = []
                    toDelete.append(wO)
                    mapDict[k]["ConditionalWarpsOut"].append(wO)
                if mode == "vanilla" and k == "Forest" and wO["Location"] == "Woods":
                    wO["Blocker"] = "Log"
            for delDict in toDelete:
                mapDict[k]["WarpsOut"].remove(delDict)

    sewerConditions = {"saveBased": {"hasRustyKey": True}}
    minecartConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccBoilerRoom"], "Target": "hostPlayer"}]}}}
    quarryMinecartConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccBoilerRoom", "ccCraftsRoom"], "Target": "hostPlayer"}]}}}

    # Desert
    desertConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccVault"], "Target": "hostPlayer"}]}}}
    skullConditions = {"saveBased": {"hasSkullKey": True}}
    if mode == "vanilla":
        mapDict["BusStop"]["ConditionalWarpsOut"] = []
        mapDict["SkullCave"]["ConditionalWarpsOut"] = []
        mapDict["Farm"]["ConditionalWarpsOut"] = []
        mapDict["FarmHouse"]["AuxWarpsOut"] = []
        mapDict["Cabin"]["AuxWarpsOut"] = []
        mapDict["WizardHouse"]["ConditionalWarpsOut"] = []
        mapDict["BoatTunnel"]["ConditionalWarpsOut"] = []
        mapDict["Island_W"]["ConditionalWarpsOut"] = []
        mapDict["Mine"]["ConditionalWarpsOut"] = []
        mapDict["77377"] = {"ModName": "Vanilla"}
        mapDict["SkullMines"] = {"ModName": "Vanilla"}
        # Volcano
        mapDict["VolcanoDungeon0"] = {"ModName": "Vanilla"}
        mapDict["VolcanoDungeon9"] = {"ModName": "Vanilla"}
        mapDict["VolcanoDungeon5"] = {"ModName": "Vanilla"}
        mapDict["VolcanoDungeon0"]["WarpsOut"] = [{"Conditions": "None", "Location": "Island_N", "Hours": "All"},
                                                  {"Conditions": "None", "Location": "VolcanoDungeon1", "Hours": "All"}]
        mapDict["VolcanoDungeon9"]["WarpsOut"] = [{"Conditions": "None", "Location": "Island_N", "Hours": "All"},
                                                  {"Conditions": "None", "Location": "VolcanoDungeon1", "Hours": "All"},
                                                  {"Conditions": "None", "Location": "Caldera", "Hours": "All"}]
        mapDict["VolcanoDungeon5"]["WarpsOut"] = [{"Conditions": "None", "Location": "VolcanoDungeon4", "Hours": "All"},
                                                  {"Conditions": "None", "Location": "VolcanoDungeon6", "Hours": "All"}]
        calderaConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["caldera"], "Target": "hostPlayer"}]}}}
        mapDict["VolcanoDungeon0"]["ConditionalWarpsOut"] = [{"Conditions": calderaConditions, "Location": "Caldera", "Hours": "All"}]
        mapDict["VolcanoDungeon0"]["WarpsIn"] = [{"Conditions": "None", "Location": "VolcanoDungeon1", "Hours": "All"}]
        # Quarry Cave
        mapDict["77377"]["WarpsOut"] = [{"Conditions": "None", "Location": "Mine", "Hours": "All"}]
        mapDict["77377"]["_Notes"] = "Quarry Cave"

    if mode == "vanilla" or "Desert" in replacedVanillaMaps.keys():
        mapDict["Desert"]["WarpsOut"].append({"Conditions": "None", "Location": "BusStop", "Hours": "All", "Type": "BusWarp"})
    if mode == "vanilla" or "BusStop" in replacedVanillaMaps.keys():
        mapDict["BusStop"]["ConditionalWarpsOut"].append({"Conditions": desertConditions, "Location": "Desert", "Hours": "1000-1700", "Type": "BusWarp", "TicketPrice": 500})
        mapDict["BusStop"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "Mine", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["BusStop"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "Town", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["BusStop"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "Mountain", "Hours": "All", "Type": "MinecartWarp"})
    if mode == "vanilla" or "SkullCave" in replacedVanillaMaps.keys():
        mapDict["SkullCave"]["ConditionalWarpsOut"].append({"Conditions": skullConditions, "Location": "SkullMines", "Hours": "All"})

    # Farm
    if mode == "vanilla" or "Farm" in replacedVanillaMaps.keys():
        ghConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccPantry"], "Target": "hostPlayer"}]}}}
        mapDict["Farm"]["ConditionalWarpsOut"].append({"Conditions": ghConditions, "Location": "Greenhouse", "Hours": "All"})
        defaultObelisks = [["Earth Obelisk", "Mountain"], ["Water Obelisk", "Beach"], ["Desert Obelisk", "Desert"], ["Island Obelisk", "Island_W"]]
        for dO in defaultObelisks:
            obeliskConditions = {"saveBased": {"calculated": {"hasbuilding": [{"Negative": [], "Positive": [dO[0]]}]}}}
            mapDict["Farm"]["ConditionalWarpsOut"].append({"Conditions": obeliskConditions, "Location": dO[1], "Hours": "All", "WarpType": "Obelisk"})

    # FarmHouse and Cabins
    cellarConditions = {"saveBased": {"calculated": {"farmhouseupgrade": 3}}}
    cabinCellarConditions = {"saveBased": {"calculated": {"cellarAssignments": "farmhand"}}}
    if mode == "vanilla" or "FarmHouse" in replacedVanillaMaps.keys():
        mapDict["FarmHouse"]["AuxWarpsOut"].append({"Conditions": cellarConditions, "Location": "Cellar", "Hours": "All", "AuxMap": "FarmHouse2"})
    if mode == "vanilla" or "Cabin" in replacedVanillaMaps.keys():
        mapDict["Cabin"]["AuxWarpsOut"].append({"Conditions": cabinCellarConditions, "Location": "Cellar", "Hours": "All", "AuxMap": "Cabin2"})
    if mode == "vanilla" or "Cellar" in replacedVanillaMaps.keys():
        mapDict["Cellar"]["WarpsOut"].append({"Conditions": "None", "Location": "Cabin", "Hours": "All"})

    # FishShop
    if mode == "vanilla" or "FishShop" in replacedVanillaMaps.keys():
        boatConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["willyHours"], "Target": "hostPlayer"}]}}}
        mapDict["Beach"]["ConditionalWarpsOut"].append({"Conditions": boatConditions, "Location": "FishShop", "Hours": "800-1700"})

    # Forest
    if mode == "vanilla" or "Forest" in replacedVanillaMaps.keys():
        mapDict["Forest"]["ConditionalWarpsOut"].append({"Conditions": sewerConditions, "Location": "Sewer", "Hours": "All"})
    if mode == "vanilla" or ("WizardHouse" in replacedVanillaMaps.keys() and "Custom_WizardBasement" not in mapDict):  # SVE workaround number 967...
        wizBasementConditions = {"saveBased": {"calculated": {"hearts": [{"Negative": [], "Positive": ["4"], "Target": "Wizard"}]}}}
        mapDict["WizardHouse"]["ConditionalWarpsOut"].append({"Conditions": wizBasementConditions, "Location": "WizardHouseBasement", "Hours": "All"})
    if mode == "modded" and "Custom_WizardHouse" in mapDict:
        del mapDict["WizardHouseBasement"]["WarpsOut"]
        del mapDict["WizardHouseBasement"]["ConditionalWarpsIn"]

    # Ginger Island
    if mode == "vanilla" or "BoatTunnel" in replacedVanillaMaps.keys():
        islandConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["willyBoatFixed"], "Target": "hostPlayer"}]}}}
        mapDict["BoatTunnel"]["ConditionalWarpsOut"].append({"Conditions": islandConditions, "Location": "Island_S", "Hours": "800-1700", "Type": "BoatWarp", "TicketPrice": 1000})
    if mode == "vanilla" or "Island_W" in replacedVanillaMaps.keys():
        nutRoomConditions = {"saveBased": {"goldenWalnutsFound": 100}}
        mapDict["Island_W"]["ConditionalWarpsOut"].append({"Conditions": nutRoomConditions, "Location": "QiNutRoom", "Hours": "All"})

    # Mine and Quarry
    if mode == "vanilla" or "Mine" in replacedVanillaMaps.keys():
        quarryConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccCraftsRoom"], "Target": "hostPlayer"}]}}}
        mapDict["Mine"]["ConditionalWarpsOut"].append({"Conditions": quarryConditions, "Location": "77377", "Hours": "All"})
        mapDict["Mine"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "BusStop", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Mine"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "Town", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Mine"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "Mountain", "Hours": "All", "Type": "MinecartWarp"})

    # Mountain
    if mode == "vanilla" or "Mountain" in replacedVanillaMaps.keys():
        thConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["leoMoved"], "Target": "hostPlayer"}]}}}
        mapDict["Mountain"]["ConditionalWarpsOut"].append({"Conditions": thConditions, "Location": "LeoTreeHouse", "Hours": "All"})
        mapDict["Mountain"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "Mine", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Mountain"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "BusStop", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Mountain"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "Town", "Hours": "All", "Type": "MinecartWarp"})

    # Railroad
    if mode == "vanilla":
        summitConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["Farm_Eternal"], "Target": "hostPlayer"}]}}}
        mapDict["Railroad"]["ConditionalWarpsOut"].append({"Conditions": summitConditions, "Location": "Summit", "Hours": "All"})

    # Town
    if mode == "vanilla" or "Town" in replacedVanillaMaps.keys():
        ajmConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": ["ccMovieTheater"], "Positive": ["abandonedJojaMartAccessible"]}]}}}
        cinemaConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccMovieTheater"]}]}}}
        jojaConditions = {"saveBased": {"player": {"mailReceived": [{"Negative": ["ccIsComplete"], "Positive": [], "Target": "hostPlayer"}]}}}
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": ajmConditions, "Location": "AbandonedJojaMart", "Hours": "All"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": cinemaConditions, "Location": "MovieTheater", "Hours": "900-2100"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": sewerConditions, "Location": "Sewer", "Hours": "All"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": jojaConditions, "Location": "JojaMart", "Hours": "900-2300"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "Mine", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": minecartConditions, "Location": "BusStop", "Hours": "All", "Type": "MinecartWarp"})
        mapDict["Town"]["ConditionalWarpsOut"].append({"Conditions": quarryMinecartConditions, "Location": "Mountain", "Hours": "All", "Type": "MinecartWarp"})
    # for some reason there's no default exit to the Town from the Sewer
    if mode == "vanilla" or "Sewer" in replacedVanillaMaps.keys():
        mapDict["Sewer"]["WarpsOut"].append({"Conditions": "None", "Location": "Town", "Hours": "All", "X": 16, "Y": 10, "WarpType": "TouchWarp"})

    # Shops
    if mode == "vanilla":
        mapDict["AdventureGuild"]["Shops"] = ["MarlonRecovery", "MarlonShop"]
        mapDict["AnimalShop"]["Shops"] = ["AnimalShop"]
        mapDict["ArchaeologyHouse"]["Shops"] = ["Museum"]
        mapDict["Blacksmith"]["Shops"] = ["BlacksmithUpgrade", "ClintShop"]
        mapDict["Club"]["Shops"] = ["QiShop"]
        mapDict["Desert"]["Shops"] = ["DesertTrade"]
        mapDict["FishShop"]["Shops"] = ["WillyShop"]
        mapDict["Forest"]["Shops"] = ["HatMouse", "TravellingMerchant"]
        mapDict["Hospital"]["Shops"] = ["HarveyShop"]
        mapDict["Island_FieldOffice"]["Shops"] = ["IslandFieldOffice"]
        mapDict["Island_N"]["Shops"] = ["IslandTrade"]
        mapDict["Island_S"]["Shops"] = ["IslandResort"]
        mapDict["JojaMart"]["Shops"] = ["JojaCD", "JojaMart"]
        mapDict["Mine"]["Shops"] = ["Dwarf"]
        mapDict["MovieTheater"]["Shops"] = ["Concessions", "CraneGame"]
        mapDict["QiNutRoom"]["Shops"] = ["WalnutRoom"]
        mapDict["Saloon"]["Shops"] = ["ColaMachine", "GusShop"]
        mapDict["SandyHouse"]["Shops"] = ["SandyShop"]
        mapDict["ScienceHouse"]["Shops"] = ["CarpenterMenu", "RobinShop"]
        mapDict["SeedShop"]["Shops"] = ["PierreBackpackShop", "PierreShop"]
        mapDict["Sewer"]["Shops"] = ["DogStatue", "KrobusShop"]
        mapDict["Town"]["Shops"] = ["IceCreamStand", "Theater_BoxOffice"]
        mapDict["VolcanoDungeon5"]["Shops"] = ["VolcanoShop"]
        mapDict["WizardHouse"]["Shops"] = ["CarpenterMenuMagical"]
        mapDict["WizardHouseBasement"]["Shops"] = ["WizardShrine"]
        mapDict["Woods"]["Shops"] = ["CannoliStatue"]
        mapDict["Town-EggFestival"]["Shops"] = ["EggFest"]
        mapDict["Forest-FlowerFestival"]["Shops"] = ["FlowerDance"]
        mapDict["Forest-IceFestival"]["Shops"] = ["IceFestival"]
        mapDict["Beach-Jellies"]["Shops"] = ["Jellies"]
        mapDict["Beach-Luau"]["Shops"] = ["Luau"]
        mapDict["Beach-NightMarket"]["Shops"] = ["BlueBoat", "MagicBoat", "Lupini", "TravellingMerchantNightMarket"]
        mapDict["Town-Halloween"]["Shops"] = ["SpiritsEve"]
        mapDict["Town-Fair"]["Shops"] = ["StardewFair"]
        mapDict["Town-Christmas"]["Shops"] = ["WinterStar"]

    # Claim the Community Center for Vanilla since we created the map from an amalgam of submaps
    if mode == "vanilla":
        mapDict["CommunityCenter"]["ModName"] = "Vanilla"

    return [mapDict, errorlist]


def parseWarpConditions(map, outWarp, toX=None, toY=None):
    # returns string
    outString = "None"
    if map == "Mountain" and outWarp == "Mine":
        if toX.isnumeric() and int(toX) == 67 and toY.isnumeric() and int(toY) == 16:  # quarry cave, we hope
            outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccCraftsRoom"], "Target": "hostPlayer"}]}}}
        else:
            outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["landslideDone"], "Target": "hostPlayer"}]}}}
    if map == "Mountain" and outWarp == "Railroad":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["JojaRockslideNotice"], "Target": "hostPlayer"}]}}}
    if map == "Town" and outWarp.startswith("CommunityCenter"):
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccDoorUnlock"], "Target": "hostPlayer"}]}}}
    if map == "Forest" and outWarp == "WizardHouse":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["wizardJunimoNote"], "Target": "hostPlayer"}]}}}
    if map == "Railroad" and outWarp == "WitchWarpCave":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["witchStatueGone"], "Target": "hostPlayer"}]}}}
    if map == "WitchSwamp" and outWarp == "WitchHut":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["henchmanGone"], "Target": "hostPlayer"}]}}}
    if map == "Mountain" and outWarp == "AdventureGuild":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["guildQuest"], "Target": "hostPlayer"}]}}}
    if map == "FishShop" and outWarp == "BoatTunnel":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["willyBackRoomInvitation"], "Target": "hostPlayer"}]}}}
    if map == "Sewer" and outWarp == "BugLand":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["krobusUnseal"], "Target": "hostPlayer"}]}}}
    if map == "Island_S" and outWarp == "Island_W":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["Island_Turtle"], "Target": "hostPlayer"}]}}}
    if map == "Island_S" and outWarp == "Island_N":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ISLAND_NORTH_DIGSITE_LOAD"], "Target": "hostPlayer"}]}}}
    if map == "Island_S" and outWarp == "Island_SE":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["Island_Resort"], "Target": "hostPlayer"}]}}}
    if map == "Island_N" and outWarp in ["IslandNorthCave1", "Island_FieldOffice"]:
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["safariGuyIntro"], "Target": "hostPlayer"}]}}}
    if map == "Island_W" and outWarp == "IslandFarmHouse":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["Island_UpgradeHouse"], "Target": "hostPlayer"}]}}}
    if map == "Island_W" and outWarp == "QiNutRoom":
        outString = {"saveBased": {"goldenWalnutsFound": 100}}
    if map == "Town" and outWarp == "AbandonedJojaMart":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["abandonedJojaMartAccessible"], "Target": "hostPlayer"}]}}}
    if map == "Town" and outWarp == "MovieTheater":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["ccMovieTheater"], "Target": "hostPlayer"}]}}}
    if map == "Mountain" and outWarp == "LeoTreeHouse":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["leoMoved"], "Target": "hostPlayer"}]}}}
    if map == "Town" and outWarp == "Trailer_big":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["pamHouseUpgrade"], "Target": "hostPlayer"}]}}}
    if (map == "Town" or map == "Forest") and outWarp == "Sewer":
        outString = {"saveBased": {"calculated": {"haswalletitem": [{"Negative": [], "Positive": ["RustyKey"], "Target": ""}]}}}
    if map == "SandyHouse" and outWarp == "Club":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": [], "Positive": ["TH_LumberPile"], "Target": "hostPlayer"}]}}}
    if map == "Hospital" and outWarp == "HarveyRoom":
        outString = {"saveBased": {"calculated": {"hearts": [{"Negative": [], "Positive": ["2"], "Target": "Harvey"}]}}}
    if map == "Town" and outWarp == "JojaMart":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": ["ccIsComplete"], "Positive": [], "Target": "hostPlayer"}]}}}
    if outWarp == "BathHouse_MensLocker":
        outString = {"saveBased": {"player": {"isMale": True}}}
    if outWarp == "BathHouse_WomensLocker":
        outString = {"saveBased": {"player": {"isMale": False}}}
    if map == "Beach" and outWarp == "FishShop":
        outString = {"saveBased": {"player": {"mailReceived": [{"Negative": ["willyHours"], "Positive": [], "Target": "hostPlayer"}]}}}
    return outString


def parseWarpNetwork(mapDict, wnList, errorlist):
    # returns [mapDict, errorlist]
    if "WarpNetwork" not in mapDict:
        mapDict["WarpNetwork"] = {"WarpsOut": [], "ModName": "WarpNetwork"}
    for wn in wnList:
        destinations = wn["Entries"]
        conditions = "None"
        if wn["HasConditions"]:
            conditions = wn["When"]
            woKey = "ConditionalWarpsOut"
        if conditions == "None":
            woKey = "WarpsOut"
        for k, v in destinations.items():
            mapKey = v["location"]
            cnDict = {"Conditions": conditions, "Location": "WarpNetwork", "Hours": "All", "Path": wn["Path"], "Type": "WarpNetwork"}
            outDict = {"Conditions": conditions, "Location": mapKey, "Hours": "All", "Path": wn["Path"], "Type": "WarpNetwork"}
            if mapKey not in mapDict:
                mapDict[mapKey] = {}
            if woKey not in mapDict[mapKey]:
                mapDict[mapKey][woKey] = []
            mapDict[mapKey][woKey].append(cnDict)
            mapDict["WarpNetwork"]["WarpsOut"].append(outDict)

    defaultMaps = ["Farm", "Beach", "Mountain", "Desert", "Island_W"]
    defaultWN = {"Conditions": "None", "Location": "WarpNetwork", "Hours": "All", "Path": "WarpNetwork", "Type": "WarpNetwork"}
    for dM in defaultMaps:
        defaultWO = {"Conditions": "None", "Location": dM, "Hours": "All", "Path": "WarpNetwork", "Type": "WarpNetwork"}
        mapDict[dM]["WarpsOut"].append(defaultWN)
        mapDict["WarpNetwork"]["WarpsOut"].append(defaultWO)
    return [mapDict, errorlist]


def parseWarpsIn(mapDict, mode, errorlist):
    # returns [dict mapDict, list errorlist]
    # Add Warps In based on Warps Out
    newAreas = {}
    for k, v in tqdm(mapDict.items(), desc="Parsing Warps In"):
        if "WarpsOut" in v:
            for wO in v["WarpsOut"]:
                targetKey = wO["Location"]
                if "SubMap" in wO and targetKey != "CommunityCenter":
                    outDict = {"Location": wO["SubMap"], "Conditions": wO["Conditions"], "Hours": wO["Hours"]}
                elif targetKey == "BeachNightMarket":
                    targetKey = "Beach"
                    outDict = {"Location": k, "Conditions": "Beach-NightMarket", "Hours": "All"}
                else:
                    outDict = {"Location": k, "Conditions": wO["Conditions"], "Hours": wO["Hours"]}
                if mode == "vanilla" and targetKey not in mapDict:
                    newAreas[targetKey] = {"WarpsIn": []}
                    newAreas[targetKey]["WarpsIn"].append(outDict)
                elif mode == "modded" and targetKey not in mapDict:
                    customTargetKey = "Custom_" + targetKey
                    if customTargetKey not in mapDict:
                        newAreas[targetKey] = {"WarpsIn": []}
                        newAreas[targetKey]["WarpsIn"].append(outDict)
                    else:
                        if "WarpsIn" not in mapDict[customTargetKey]:
                            mapDict[customTargetKey]["WarpsIn"] = []
                        if outDict not in mapDict[customTargetKey]["WarpsIn"]:
                            mapDict[customTargetKey]["WarpsIn"].append(outDict)
                else:
                    if "WarpsIn" not in mapDict[targetKey]:
                        mapDict[targetKey]["WarpsIn"] = []
                    if outDict not in mapDict[targetKey]["WarpsIn"]:
                        mapDict[targetKey]["WarpsIn"].append(outDict)
            if "AuxWarpsOut" in v:
                for xO in v["AuxWarpsOut"]:
                    targetKey = xO["Location"]
                    if "SubMap" in xO and targetKey != "CommunityCenter":
                        outDict = {"Location": xO["SubMap"], "Conditions": xO["Conditions"], "Hours": xO["Hours"], "AuxMap": xO["AuxMap"]}
                    elif targetKey == "BeachNightMarket":
                        targetKey = "Beach"
                        outDict = {"Location": k, "Conditions": "Beach-NightMarket", "Hours": "All", "AuxMap": xO["AuxMap"]}
                    else:
                        outDict = {"Location": k, "Conditions": xO["Conditions"], "Hours": xO["Hours"], "AuxMap": xO["AuxMap"]}
                    if mode == "modded" and targetKey not in mapDict:
                        customTargetKey = "Custom_" + targetKey
                        if customTargetKey not in mapDict:
                            newAreas[targetKey] = {"AuxWarpsIn": []}
                            newAreas[targetKey]["AuxWarpsIn"].append(outDict)
                        else:
                            if "AuxWarpsIn" not in mapDict[customTargetKey]:
                                mapDict[customTargetKey]["AuxWarpsIn"] = []
                            if outDict not in mapDict[customTargetKey]["AuxWarpsIn"]:
                                mapDict[customTargetKey]["AuxWarpsIn"].append(outDict)
                    else:
                        if "AuxWarpsIn" not in mapDict[targetKey]:
                            mapDict[targetKey]["AuxWarpsIn"] = []
                        if outDict not in mapDict[targetKey]["AuxWarpsIn"]:
                            mapDict[targetKey]["AuxWarpsIn"].append(outDict)
            if "ConditionalWarpsOut" in v:
                for cO in v["ConditionalWarpsOut"]:
                    targetKey = cO["Location"]
                    printthis = False
                    # if targetKey == "Custom_ESJacobBarn":
                    #     printthis = True
                    if printthis:
                        print(cO)
                    if "SubMap" in cO and targetKey != "CommunityCenter":
                        outDict = {"Location": cO["SubMap"], "Conditions": cO["Conditions"], "Hours": xO["Hours"]}
                    elif targetKey == "BeachNightMarket":
                        targetKey = "Beach"
                        cO["Conditions"]["Submap"] = "Beach-NightMarket"
                        outDict = {"Location": k, "Conditions": cO["Conditions"], "Hours": "All"}
                    else:
                        outDict = {"Location": k, "Conditions": cO["Conditions"], "Hours": cO["Hours"]}
                    if printthis:
                        print(outDict)
                    if mode == "modded" and targetKey not in mapDict:
                        customTargetKey = "Custom_" + targetKey
                        if customTargetKey not in mapDict:
                            newAreas[targetKey] = {"AuxWarpsIn": []}
                            newAreas[targetKey]["AuxWarpsIn"].append(outDict)
                        else:
                            if "ConditionalWarpsIn" not in mapDict[customTargetKey]:
                                mapDict[customTargetKey]["ConditionalWarpsIn"] = []
                            if outDict not in mapDict[customTargetKey]["ConditionalWarpsIn"]:
                                mapDict[customTargetKey]["ConditionalWarpsIn"].append(outDict)
                    else:
                        if "ConditionalWarpsIn" not in mapDict[targetKey]:
                            mapDict[targetKey]["ConditionalWarpsIn"] = []
                        if outDict not in mapDict[targetKey]["ConditionalWarpsIn"]:
                            mapDict[targetKey]["ConditionalWarpsIn"].append(outDict)
    if newAreas:
        for k, v in newAreas.items():
            mapDict[k] = v

    return [mapDict, errorlist]


def purgeEmptyNodes(mapDict, errorlist):
    # returns mapDict
    toPurge = []
    for k, v in mapDict.items():
        inRoads = ["WarpsIn", "AuxWarpsIn", "ConditionalWarpsIn"]
        outRoads = ["WarpsOut", "AuxWarpsOut", "ConditionalWarpsOut"]
        shops = ["Shops", "ConditionalShops"]
        wayIn = False
        wayOut = False
        shop = False
        for ir in inRoads:
            if ir in v and isinstance(v[ir], list) and len(v[ir]) > 0:
                wayIn = True
                break
        for outR in outRoads:
            if outR in v and isinstance(v[outR], list) and len(v[outR]) > 0:
                wayOut = True
                break
        for shopKey in shops:
            if shopKey in v and isinstance(v[shopKey], list) and v[shopKey]:
                shop = True
                break
        if not shop and (not wayIn or not wayOut):
            toPurge.append(k)
    # pprint.pprint(toPurge)
    for purgeMe in toPurge:
        del mapDict[purgeMe]
    # errorlist.append("The following maps were purged as completely inaccessible: " + ", ".join(toPurge))
    return [mapDict, errorlist]


def sortModdedMaps(mapDict, moddedMapList, eventDict, vmapData, vBuildables, festivalMaps, errorlist):
    # returns [mapDict, errorlist]
    primaryMaps = []
    eventMaps = []

    # internals
    eventStarters = []
    eventMoves = []
    unsorted = []

    # merge festival maps into parents
    for festmap, festData in festivalMaps.items():
        # merge festival maps into their parents
        if festmap in mapDict:  # vanilla festival maps are already gone
            if "FestMapOf" in mapDict[festmap]:
                parentMap = mapDict[festmap]["FestMapOf"]
                if "AltMaps" not in mapDict[parentMap]:
                    mapDict[parentMap]["AltMaps"] = []
                if festmap not in mapDict[parentMap]["AltMaps"]:
                    mapDict[parentMap]["AltMaps"].append(festmap)
                if "Shops" in mapDict[festmap]:
                    if "ConditionalShops" not in mapDict[parentMap]:
                        mapDict[parentMap]["ConditionalShops"] = []
                    if "Shops" not in festData:
                        festData["Shops"] = []
                    for festShop in mapDict[festmap]["Shops"]:
                        if festShop not in mapDict[parentMap]["ConditionalShops"]:
                            mapDict[parentMap]["ConditionalShops"].append(festShop)
                        if festShop not in festData["Shops"]:
                            festData["Shops"].append(festShop)
            del mapDict[festmap]
    # go through the events and sort starting locations from event-only locations
    for k, v in eventDict.items():
        if isinstance(v, dict) and "Location" in v:
            eventStarters.append(v["Location"])
            if "OtherLocations" in v:
                for oL in v["OtherLocations"]:
                    if oL not in eventMoves:
                        eventMoves.append(oL)
    for eS in eventStarters:
        if eS in eventMoves:
            eventMoves.remove(eS)

    for k, v in mapDict.items():
        if ("WarpsIn" not in v or not v["WarpsIn"]) and ("AuxWarpsIn" not in v or not v["AuxWarpsIn"]) and ("ConditionalWarpsIn" not in v or not v["ConditionalWarpsIn"]):
            # there is no bloody way into this map
            if k in eventMoves and k not in vmapData.keys():
                eventMaps.append(k)
                # print(k + " is probably an event map")
            elif k in vmapData.keys():
                primaryMaps.append(k)
                # print(k + " is a Vanilla Map")
            elif k in vBuildables:
                primaryMaps.append(k)
            else:
                unsorted.append(k)
        else:
            primaryMaps.append(k)

    for k in unsorted:
        # maps unreachable for any reason: holidays, temp maps, warp rooms,
        # spouse patios, excluded by weird hasmod checks, etc.
        del mapDict[k]

    for k in primaryMaps:
        mapDict[k]["MapType"] = "Primary"
    for k in eventMaps:
        mapDict[k]["MapType"] = "Temp"
    for k in vBuildables:
        mapDict[k]["MapType"] = "Buildable"
    return [mapDict, festivalMaps, errorlist]


def sortVanillaMaps(mapDict, vanillaEvents, vanillaBuildables, vanillaAltMaps, vanillaAuxMaps, festivalMaps, errorlist):
    # returns [dict mapDict, list errorlist]
    for k in mapDict.keys():
        if k in vanillaEvents:
            mapDict[k]["MapType"] = "Temp"
        elif k in vanillaBuildables:
            mapDict[k]["MapType"] = "Buildable"
        else:
            mapDict[k]["MapType"] = "Primary"

    for festmap, festData in festivalMaps.items():
        # merge festival maps into their parents
        if "FestMapOf" in mapDict[festmap]:
            parentMap = mapDict[festmap]["FestMapOf"]
            if "AltMaps" not in mapDict[parentMap]:
                mapDict[parentMap]["AltMaps"] = []
            if festmap not in mapDict[parentMap]["AltMaps"]:
                mapDict[parentMap]["AltMaps"].append(festmap)
            if "Shops" in mapDict[festmap]:
                if "ConditionalShops" not in mapDict[parentMap]:
                    mapDict[parentMap]["ConditionalShops"] = []
                if "Shops" not in festData:
                    festData["Shops"] = []
                for festShop in mapDict[festmap]["Shops"]:
                    if festShop not in mapDict[parentMap]["ConditionalShops"]:
                        mapDict[parentMap]["ConditionalShops"].append(festShop)
                    if festShop not in festData["Shops"]:
                        festData["Shops"].append(festShop)
        del mapDict[festmap]

    for altmap, mapkey in vanillaAltMaps.items():
        if "AltMaps" not in mapDict[mapkey]:
            mapDict[mapkey]["AltMaps"] = []
        if altmap not in mapDict[mapkey]["AltMaps"]:
            mapDict[mapkey]["AltMaps"].append(altmap)

    for auxmap, mapkey in vanillaAuxMaps.items():
        if mapkey in vanillaAltMaps:
            mapkey = vanillaAltMaps[mapkey]
        if "AuxMaps" not in mapDict[mapkey]:
            mapDict[mapkey]["AuxMaps"] = []
            mapDict[mapkey]["AuxedBy"] = ["Vanilla"]
        if auxmap not in mapDict[mapkey]["AuxMaps"]:
            try:
                mapDict[mapkey]["AuxMaps"].append(auxmap)
            except KeyError:
                errorlist.append("For Dev: sortVanillaMaps error: " + mapkey + " " + auxmap)
                errorlist.append("Traceback: " + traceback.format_exc())

    return [mapDict, festivalMaps, errorlist]


def translateWarpLocation(inString, legacyNames):
    # returns string
    # unifies location names
    outString = inString
    if inString == "VolcanoEntrance":
        outString = "VolcanoDungeon0"
    if inString == "Island_Resort":
        outString = "Island_S"
    if inString == "IslandEast":
        outString = "Island_E"
    if inString == "IslandFarmCave":
        outString = "Island_FarmCave"
    if inString == "IslandFieldOffice":
        outString = "Island_FieldOffice"
    if inString == "IslandHut":
        outString = "Island_Hut"
    if inString == "IslandNorth":
        outString = "Island_N"
    if inString == "IslandShrine":
        outString = "Island_Shrine"
    if inString == "IslandSouth":
        outString = "Island_S"
    if inString == "IslandSouthEast":
        outString = "Island_SE"
    if inString == "IslandWest":
        outString = "Island_W"
    if inString == "Island_Resort":
        outString = "Island_S"
    if inString == "CaptainRoom":
        outString = "Island_CaptainRoom"
    if inString in legacyNames:
        outString = legacyNames[inString]
    return outString


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
    jsonpath = config["PATHS"]["project_root"] + "json/"
    logpath = config["PATHS"]["log_path"]
    output_method = config["OUTPUT"]["output_method"]

    # for vanilla
    localMode = "vanilla"
    localerrorlist = []
    localmaniList = []
    localtargetDir = config["PATHS"]["mod_directory"]
    localvmapstaticfile = jsonpath + "refs/vanillamapstatic.json"
    localblockers = jsonData(jsonpath, "vanillamapblockingobjects", "refs").data
    localdecompdir = config["PATHS"]["decompiled_stardew"]

    # uncomment for modded
    localMode = "modded"
    localblockers = jsonData(jsonpath, "mapblockingobjects").data
    localbuildings = jsonData(jsonpath, "buildings").data
    localconfigdata = jsonData(config["PATHS"]["project_root"] + "saves/", "configparams").data
    localdynos = jsonData(jsonpath, "dynamictokens", "refs").data
    localevents = jsonData(jsonpath, "events").data
    localfestivalMaps = jsonData(jsonpath, "festivalmaps", "refs").data
    localmaniList = jsonData(jsonpath, "manifests").data
    localmapchanges = jsonData(jsonpath, "mapchanges", "refs").data
    localmaplist = jsonData(jsonpath, "moddedmaps", "refs").data
    localvmapfile = "../../json/vanilla/vanillamapwarps.json"

    if localMode == "vanilla":
        pmdOut = buildMaps(localMode, localtargetDir, localerrorlist, localvmapstaticfile, localmaniList, localblockers, localdecompdir, {})
    else:
        pmdOut = buildMaps(localMode, localtargetDir, localerrorlist, localvmapstaticfile,
                           localmaniList, localblockers, localdecompdir, localvmapfile,
                           localmapchanges, localmaplist, localconfigdata, localdynos,
                           localevents, localbuildings, localfestivalMaps)
    mapData = pmdOut[0]
    festivalMaps = pmdOut[1]
    errorlist = pmdOut[2]
    # pprint.pprint(festivalMaps)
    writeJson(mapData, "mapwarps", jsonpath)
    if errorlist:
        errorsOut(errorlist, output_method, logpath)
