"""
Parses Content Patcher content.json files, inclusions and sideloads
Nearly every method in here is called by setup.py
Creates content-cleaned.json of broken Cpatcher json files.
"""
import copy
import itertools
import math
import os
import pprint
import re
import sys
import traceback

import pyjson5
from tqdm import tqdm

sys.path.append('..')
from lib.bracketReplacer import bracketReplacer
from lib.parseCPatcherWhens import parseWhens
from lib.mailParser import parseMail
from lib.parsePreconditions import parsePreconditions


def buildCPatcher(targetdir, maniList, maniIDs, vstrings, vnpcs, vevents, vsos, vsostrings, vlivestock, vbuildings, vmail, savedconfigs, vanillaids, vcatids, objids, questIDs, vfish, vsecretnotes, calendar, vfestivalMaps, errorlist):
    # returns [cPatcherList, i18n, outMail, configParams, dynamictokens, eventDict,
    #         moddedLocations, fishids, locationsRaw, editedlocationsRaw,
    #         newObjectsRaw, npcGiftsRaw, mailRaw, secretNotes, eventsRaw,
    #         specialOrdersRaw, mapChangesRaw, questIDs, eventDict, newnpcs, specialOrderStrings]
    # master method
    # roll vanilla data into new dicts
    newnpcs = {}
    for vname, vnpc in vnpcs.items():
        newnpcs[vname] = vnpc

    buildings = {}
    for vbk, vbv in vbuildings.items():
        buildings[vbk] = vbv

    festivalMaps = {}
    for vfmk, vfmv in vfestivalMaps.items():
        festivalMaps[vfmk] = vfmv

    # Find the all Cpatcher JSON, i18N and paths
    if "pathoschild.contentpatcher" in maniIDs:
        print("==========================\nContent Patcher\n==========================")
        fileOut = cPatcherwalk(targetdir, maniList, vstrings, savedconfigs, errorlist)
        #  [cPatcherList, includedPathsGlobal, mapEditingFile, i18n]
        cPatcherList = fileOut[0]
        includedPathsGlobal = fileOut[1]
        mapEditingFiles = fileOut[2]
        i18n = fileOut[3]
        errorlist = fileOut[4]

        if cPatcherList:
            cpFirstOut = parseCPatcher(cPatcherList, savedconfigs, vmail, maniList)
            # grabs everything outside of "Changes" nodes and wraps all the "Changes" nodes into changesRaw
            configParams = cpFirstOut[0]
            dynamictokens = cpFirstOut[1]
            changesRaw = cpFirstOut[2]
            outMail = cpFirstOut[3]  # now holds Repeating Mail
            eventDict = cpFirstOut[4]  # now holds Repeating Events
            moddedLocations = cpFirstOut[5]

            if changesRaw:
                cpSecondOut = parseChanges(changesRaw, dynamictokens, configParams, maniList, vanillaids, vcatids, objids,
                                           outMail, questIDs, newnpcs, buildings, includedPathsGlobal,
                                           mapEditingFiles, i18n, moddedLocations, vsecretnotes, calendar, festivalMaps, errorlist)
                newnpcs = cpSecondOut[0]
                locationsRaw = cpSecondOut[1]
                editedlocationsRaw = cpSecondOut[2]
                mailRaw = cpSecondOut[3]
                secretNotes = cpSecondOut[4]
                eventsRaw = cpSecondOut[5]
                specialOrdersRaw = cpSecondOut[6]
                buildings = cpSecondOut[7]
                mapChangesRaw = cpSecondOut[8]
                moddedLocations = cpSecondOut[9]
                questIDs = cpSecondOut[10]
                festivalMaps = cpSecondOut[11]
                errorlist = cpSecondOut[12]
            else:
                locationsRaw = []
                editedlocationsRaw = []
                mailRaw = []
                secretNotes = vsecretnotes
                eventsRaw = []
                specialOrdersRaw = []
                mapChangesRaw = []
                moddedLocations = []
        else:
            errorlist.append("You have Content Patcher installed but no Mods require it.")
            configParams = savedconfigs
            dynamictokens = {}
            changesRaw = []
            outMail = vmail
            eventDict = vevents
            moddedLocations = []
            locationsRaw = []
            editedlocationsRaw = []
            mailRaw = []
            secretNotes = vsecretnotes
            eventsRaw = []
            specialOrdersRaw = []
            mapChangesRaw = []
    else:
        cpsearch = [mk for mk, mv in maniList if mv["packFor"].lower() == "pathoschild.contentpatcher"]
        if cpsearch:
            errorlist.append("Config Alert: You have packs which require Content Patcher but do not have it installed.")
        outMail = vmail
        configParams = savedconfigs
        dynamictokens = {}
        eventDict = {}
        moddedLocations = []
        locationsRaw = []
        editedlocationsRaw = []
        mailRaw = []
        secretNotes = vsecretnotes
        eventsRaw = []
        specialOrdersRaw = []
        mapChangesRaw = []

    return [cPatcherList, i18n, outMail, configParams, dynamictokens, eventDict,
            moddedLocations, locationsRaw, editedlocationsRaw,
            mailRaw, secretNotes, eventsRaw,
            specialOrdersRaw, mapChangesRaw, questIDs, eventDict, newnpcs,
            buildings, festivalMaps, errorlist]


def cleanfile(filepath, errorlist):
    try:
        pyjson5.load(open(filepath, encoding="utf-8"))
        return [filepath.replace("\\", "/"), errorlist]
    except Exception:
        # it probably has unquoted keys. open it as a file,
        # replace those keys, and then try to read it.
        errorlist.append("Mod Bug: " + filepath + " is invalid JSON. Cleaning and outputting to content-cleaned.json.")
        with open(filepath, encoding="utf-8") as badFile:
            textString = badFile.read()
            regex1 = r"\{\s?([0-9]+):"  # as first key
            sub1 = r'{"\1":'
            regex2 = r",\s?([0-9]+):"  # as a subsequent key
            sub2 = r', "\1":'
            regex3 = r"^(\W+)([0-9]+):"  # beginning of a line for indented dictionaries
            sub3 = r'\1"\2":'
            textString = re.sub(regex1, sub1, textString)
            textString = re.sub(regex2, sub2, textString)
            textString = re.sub(regex3, sub3, textString, flags=re.M)
            # write to content-cleaned.json
            newPath = filepath.replace(".json", "-cleaned.json").replace("\\", "/")
            newFile = open(newPath, "w", encoding="utf-8")
            newFile.write(textString)
            newFile.close()
            return [newPath, errorlist]


def cPatcherwalk(rootdir, maniList, vstrings, configParams, errorlist):
    # return [cPatcherList, includedPathsGlobal, mapEditingFile, i18n]
    # finds contentpatcher json files and adds them to cpatcherList, returns list
    print("Searching for Content Patcher data..")
    cPatcherList = []
    preliminaryPaths = []
    includedPaths = []
    i18nPaths = []
    includedPathsGlobal = []
    mapEditingFiles = []
    i18n = {}
    manisearch = list(filter(None, [value if value["packFor"].lower() == "pathoschild.contentpatcher" else '' for value in maniList]))
    if len(manisearch) > 0:
        for mod in manisearch:
            fpath = rootdir + mod["ModFolder"] + "/content.json"
            preliminaryPaths.append(fpath)
            if "i18n" in mod:
                i18nPaths.append(mod["i18n"])
    for name in tqdm(preliminaryPaths, desc="Content Patcher Files"):
        # begin cPatcherList generation
        # Human-generated JSON sucks. Or Python Json5 modules suck at reading it.
        # We need to encase any integer keys in quotes.
        # If we already have a cleaned file, use it.
        test_clean_path = name.replace("\\", "/").rstrip(".json") + "-cleaned.json"
        if os.path.exists(test_clean_path):  # we already cleaned it
            clean_path = test_clean_path
        else:
            cleandata = cleanfile(name, errorlist)
            clean_path = cleandata[0]
            errorlist = cleandata[1]
        # A lot of frameworks use content.json files. Now that we have a clean file,
        # let's make sure that it's actually Content Patcher json.
        try:
            data = pyjson5.load(open(clean_path, encoding="utf-8"))
        except Exception:
            print(clean_path)
            traceback.print_exc()
            quit()
        if ("Format" in data or "format" in data) and ("Changes" in data or "changes" in data):
            # print(full_path + " is a Content Patcher Pack")
            masterDir = name.rsplit("/", 1)[0] + "/"
            # masterDir = masterDir.replace("\\", "/")
            cPatcherList.append([clean_path, masterDir])
            # Devs can split their CP files into many sub files.
            # Let's walk the same directory for more json files.
            parentDir = name.rstrip("content.json").replace("\\", "/")
            if "changes" in data:
                for node in data["changes"]:
                    if node["Action"] == "Include":
                        if "When" in node:
                            # we don't have dynamic tokens yet but we can figure out if there's a
                            # hasmod or config param in the node that would prevent this file
                            # from being included
                            parsedWhens = parseWhens(node, [], configParams, maniList, parentDir)
                            whenPCs = parsedWhens[0]
                            if "skip" in whenPCs and whenPCs["skip"] == True:
                                continue
                        incFileString = node["FromFile"]
                        incFileList = [x.strip() for x in incFileString.split(",")]
                        for incFilename in incFileList:
                            if incFilename.endswith(".json"):
                                incFullFile = masterDir + incFilename
                                incFullFile = incFullFile.replace("\\", "/")
                                includedPaths.append([incFullFile, parentDir])
                                includedPathsGlobal.append(incFullFile)
            elif "Changes" in data:
                for node in data["Changes"]:
                    if node["Action"] == "Include":
                        if "When" in node:
                            parsedWhens = parseWhens(node, [], configParams, maniList, parentDir)
                            try:
                                whenPCs = parsedWhens[0]
                            except KeyError:
                                pprint.pprint(parsedWhens)
                                quit()
                            if "skip" in whenPCs and whenPCs["skip"] == True:
                                continue
                        incFileString = node["FromFile"]
                        incFileList = [x.strip() for x in incFileString.split(",")]
                        for incFilename in incFileList:
                            if incFilename.endswith(".json"):
                                incFullFile = masterDir + incFilename
                                incFullFile = incFullFile.replace("\\", "/")
                                includedPaths.append([incFullFile, parentDir])
                                includedPathsGlobal.append(incFullFile)
            # print(parentDir)
            for sroot, sdirs, sfiles in os.walk(parentDir):
                for sname in sfiles:
                    if sname.endswith((".json")) and not sname.endswith(("content.json")) and not sname.endswith(("manifest.json")) and not sname.endswith(("config.json")) and not sname.endswith(("-cleaned.json")):
                        # print(sname)
                        sub_path = os.path.join(sroot, sname)
                        # Avoid obvious translations
                        avoid_paths = ["Disused", "Archiv", "i18n", "Translation", "Spanish", "/de.json", "/es.json", "/fr.json", "/hu.json", "/it.json", "/ko.json", "/pt.json", "/ru.json", "/th.json", "/tr.json", "/uk.json", "/zh.json"]
                        if all(x not in sub_path for x in avoid_paths):
                            cleandata = cleanfile(sub_path, errorlist)
                            clean_sub_path = cleandata[0]
                            errorlist = cleandata[1]
                            try:
                                data = pyjson5.load(open(clean_sub_path, encoding="utf-8"))
                                if "Changes" in data:
                                    for node in data["Changes"]:
                                        if node["Action"] == "Include":
                                            if "When" in node:
                                                parsedWhens = parseWhens(node, [], configParams, maniList, parentDir)
                                                whenPCs = parsedWhens[0]
                                                if "skip" in whenPCs and whenPCs["skip"] == True:
                                                    continue
                                            incFileString = node["FromFile"]
                                            incFileList = [x.strip() for x in incFileString.split(",")]
                                            for incFilename in incFileList:
                                                if incFilename.endswith(".json"):
                                                    incFullFile = masterDir + incFilename
                                                    incFullFile = incFullFile.replace("\\", "/")
                                                    includedPaths.append([incFullFile, parentDir])
                                                    includedPathsGlobal.append(incFullFile)
                                        if node["Action"] == "EditMap":
                                            mapEditingFiles.append(clean_sub_path)
                                elif "changes" in data:
                                    for node in data["changes"]:
                                        if node["Action"] == "Include":
                                            if "When" in node:
                                                parsedWhens = parseWhens(node, [], configParams, maniList, parentDir)
                                                whenPCs = parsedWhens[0]
                                                if "skip" in whenPCs and whenPCs["skip"] == True:
                                                    continue
                                            incFileString = node["FromFile"]
                                            incFileList = [x.strip() for x in incFileString.split(",")]
                                            for incFilename in incFileList:
                                                if incFilename.endswith(".json"):
                                                    incFullFile = masterDir + incFilename
                                                    incFullFile = incFullFile.replace("\\", "/")
                                                    includedPaths.append([incFullFile, parentDir])
                                                    includedPathsGlobal.append(incFullFile)
                                        if node["Action"] == "EditMap":
                                            mapEditingFiles.append(clean_sub_path)
                            except Exception:
                                print(clean_sub_path)
                                traceback.print_exc()
                                quit()
        # end cPatcherList loop
    # merge the included files with the main files
    toDelete = []
    for idx, incFileList in enumerate(includedPaths):
        # check if a cleaned file exists
        cleanPath = incFileList[0][0:-5] + "-cleaned.json"
        if os.path.exists(cleanPath):
            incFileList[0] = cleanPath
        avoid_paths = ["Disused", "Archiv", "i18n", "Translation", "Spanish", "/de.json", "/es.json", "/fr.json", "/hu.json", "/it.json", "/ko.json", "/pt.json", "/ru.json", "/th.json", "/tr.json", "/uk.json", "/zh.json"]
        if any(x in incFileList[0] for x in avoid_paths):
            toDelete.append(incFileList)
        if not os.path.exists(incFileList[0]):
            toDelete.append(incFileList)
    for delitem in toDelete:
        if delitem in includedPaths:
            includedPaths.remove(delitem)
    cPatcherList += includedPaths
    for name in tqdm(i18nPaths, desc="i18n Files"):
        try:
            data = pyjson5.load(open(name, encoding="utf-8"),)
            for key, pair in data.items():
                i18n[key] = pair
        except Exception:
            print("i18n error with " + name)
            traceback.print_exc
            quit()
        # end i18nPaths loop
    for key, pair in vstrings.items():
        i18n[key] = pair
    # remove duplicates
    cPatcherList.sort()
    cPatcherList = list(cPatcherList for cPatcherList, _ in itertools.groupby(cPatcherList))
    mapEditingFiles = list(set(mapEditingFiles))
    return [cPatcherList, includedPathsGlobal, mapEditingFiles, i18n, errorlist]


def intParse(valList, intList):
    newvalues = []
    for value in valList:
        if "{{i18n" in value:
            targetIntString = re.findall(r"{{i18n:(.*?)}}", value)
            if targetIntString[0] in intList:
                replacement = intList[targetIntString[0]]
                newvalue = re.sub(r"{{i18n:.*?}}", replacement, value)
            else:
                newvalue = targetIntString[0]
            newvalues.append(newvalue)
        else:
            newvalues.append(value)
    return newvalues


def parseBlueprints(bpdict, mode, vanillaids, modname):
    # returns list with two dicts [animalDict, buildingDict]
    outList = []
    animalDict = {}
    buildingDict = {}
    skipBPS = ["Greenhouse", "Mine Elevator"]
    for k, v in bpdict.items():
        if k in skipBPS and mode == "vanilla":
            # Greenhouse is technically a blueprint but you can't buy it.
            continue
        bpList = v.split("/")
        if bpList[0] == "animal":
            outDict = {"Money": int(bpList[1]), "Name": bpList[4], "Description": bpList[5], "ModName": modname}
            animalDict[k] = outDict
        else:
            outDict = {}
            itemList = bpList[0].split(" ")
            itemsRequired = {}
            start = 0
            end = len(itemList)
            step = 2
            for i in range(start, end, step):
                x = i
                thisItem = itemList[x:x + step]
                if len(thisItem) == 2:
                    if thisItem[0].lstrip("-").isnumeric():
                        intidx = int(thisItem[0])
                        # print(idx + str(intidx))
                        if intidx >= 0 and intidx < 1056:
                            try:
                                itemName = vanillaids[thisItem[0]]["Name"]
                            except KeyError:
                                # print("Vanilla ID Key Not found: " + str(idx))
                                continue
                    else:
                        itemName = thisItem[0]
                    itemQty = thisItem[1]
                    itemsRequired[itemName] = int(itemQty)
            outDict["Items"] = itemsRequired
            if bpList[7] == "null":
                outDict["InteriorMap"] = None
            else:
                outDict["InteriorMap"] = bpList[7]
            outDict["Name"] = bpList[8]
            outDict["Description"] = bpList[9]
            outDict["Type"] = bpList[10]
            if bpList[11] == "none":
                outDict["Upgrades"] = None
            else:
                outDict["Upgrades"] = bpList[11]
            outDict["MaxOccupants"] = bpList[14]
            if mode == "vanilla" and ("Obelisk" in bpList[8] or bpList[8] == "Gold Clock"):
                outDict["Perfection"] = True
            if modname == "[CP] Ridgeside Village":
                outDict["WhereToBuild"] = "Custom_Ridgeside_SummitFarm"
            else:
                outDict["WhereToBuild"] = bpList[16]
            if len(bpList) > 17:
                outDict["Money"] = int(bpList[17])
            if len(bpList) > 18:
                if bpList[18] == "true":
                    outDict["Source"] = "WizardHouse"
                elif bpList[18] == "false" and mode == "modded":
                    if modname == "[CP] Ridgeside Village":
                        outDict["Source"] = "IanShop"  # this is buried in the RSV c# code.
                    else:
                        outDict["Source"] = "RobinShop"
                elif mode == "vanilla" and bpList[18] == "false":
                    outDict["Source"] = "RobinShop"
            else:
                outDict["Source"] = "RobinShop"
            if (len(bpList) > 19 and bpList[19] == "0") or outDict["Source"] == "WizardHouse":
                outDict["InstantBuild"] = True
            else:
                outDict["InstantBuild"] = False
            outDict["ModName"] = modname
            buildingDict[k] = outDict
    outList = [animalDict, buildingDict]
    # pprint.pprint(outList)
    return outList


def parseChanges(changeList, dynamictokens, configParams, maniList, vanillaids, vcatids, objids, outMail, questIDs, newnpcs, buildings, includedPathsGlobal, mapEditingFiles, i18n, moddedLocations, vsecretnotes, calendar, festivalMaps, errorlist):
    # return [newnpcs, fishids, locationsRaw, editedlocationsRaw, newobjectsRaw, npcGiftsRaw,
    #         mailRaw, secretNotes, eventsRaw, specialOrdersRaw, specialOrderStrings,
    #         livestock, buildings, mapChangesRaw, moddedLocations, questIDs, fishpondsRaw]
    locationsRaw = []
    editedlocationsRaw = []
    mailRaw = []
    secretNotes = vsecretnotes
    eventsRaw = []
    specialOrdersRaw = []
    mapChangesRaw = []
    unparsedTargets = ['data/achievements', 'data/additionalfarms',
                       'data/additionalwallpaperflooring',
                       'data/boots', 'data/bundles', 'data/clothinginformation',
                       'data/crops', 'data/farmanimals',
                       'data/fruittrees', 'data/furniture', 'data/hats',
                       'data/homerenovations', 'data/movies',
                       'data/randombundles', 'data/tailoringrecipes',
                       'data/tv']
    parsedTargets = ['characters/schedules', 'data/antisocialnpcs',
                     'data/bigcraftablesinformation',
                     'data/blueprints', 'data/concessiontastes',
                     'data/cookingrecipes', 'data/craftingrecipes',
                     'data/customnpcexclusions', 'data/events', 'data/festivals', 'data/fish',
                     'data/fishponddata', 'data/locations', 'data/mail',
                     'data/monsters', 'data/moviesreactions', 'data/npcdispositions',
                     'data/npcgifttastes', 'data/objectcontexttags',
                     'data/objectinformation', 'data/quests', 'data/secretnotes',
                     'data/specialorders', 'data/warpnetwork/locations',
                     'data/weapons', 'maps/', 'strings/specialorderstrings']
    defaultFestivals = ["fall16", "fall27", "spring13", "spring24", "summer11", "summer28", "winter8", "winter25"]
    for change in tqdm(changeList, desc="CPatcher Changes"):
        node = change["data"]
        parentDir = change["parentDir"]
        modName = change["modName"]
        filepath = change["filepath"]
        loadedEntries = {}
        action = node["Action"].lower()
        # make sure we want to actually parse this node
        targetThis = False
        if "Target" in node:
            lowerTarget = node["Target"].lower()
            if lowerTarget in unparsedTargets:
                errorlist.append("For Dev: Unparsed Target " + lowerTarget + " in cpatcher file " + filepath[0])
            if any(x in lowerTarget for x in parsedTargets):
                targetThis = True
        elif action == "load" or action == "include":
            targetThis = True
        if not targetThis:
            continue
        # make sure it isn't a language variant, and if it isn't parse the "When" param
        english = True
        # printthis = False
        # if "Tristan" in filepath[0]:
        #     printthis = True
        if "When" in node:
            when = node["When"]
            if "Language" in when and when["Language"] != "en":
                english = False
            if not english:
                continue
            # whenDict = {"data": node, "path": parentDir}
            # eventWhens.append(whenDict)
            try:
                parsedWhens = parseWhens(node, dynamictokens, configParams, maniList, parentDir)
                whenPCs = parsedWhens[0]
                whenPCStrings = parsedWhens[1]
            except Exception:
                print(node["When"])
                traceback.print_exc()
                quit()
            if "skip" in whenPCs and whenPCs["skip"] == True:
                # requires a mod, file or config we don't have
                continue
            if whenPCs["ignore"]:
                # contains only verified static params and configs
                whenPCs = {}
        else:
            whenPCs = {}
            whenPCStrings = []
        if action == "load":
            # Entries will come from the loaded file.
            target = node["Target"]  # in this case do not convert case.
            if "," in target:
                targetList = target.split(",")
            else:
                targetList = [target]
            for targetPath in targetList:
                targetPath = targetPath.strip()
                # find the parent directory
                loadPath = ""
                targetWithoutPath = targetPath.split("/")[-1]
                if "{{target}}" in node["FromFile"].lower():
                    loadPath = node["FromFile"].replace("{{Target}}", targetPath).replace("{{target}}", targetPath)  # both cases
                elif "{{targetwithoutpath}}" in node["FromFile"].lower():
                    loadPath = node["FromFile"].replace("{{TargetWithoutPath}}", targetWithoutPath).replace("{{targetwithoutpath}}", targetWithoutPath)
                else:
                    loadPath = node["FromFile"]
                fullPath = parentDir + loadPath.strip()
                fullPath.replace("\\", "/")  # tidy up
                if node["FromFile"].endswith(".json") and len(loadPath) > 0:
                    # print("Loading file " + fullPath)
                    loadData = pyjson5.load(open(fullPath, encoding="utf-8"),)
                    # print(loadData)
                    for k, v in loadData.items():
                        loadedEntries[k] = v
                elif "Portraits" in targetPath:
                    # print(targetPath)
                    # get the portrait file location
                    if "{{Target}}" in loadPath:
                        loadPath = loadPath.replace("{{Target}}", targetPath)
                    npcname = targetPath.rsplit("/", 1)[1]
                    # print(npcname)
                    if npcname not in newnpcs:
                        newnpcs[npcname] = {}
                        newnpcs[npcname]["Portrait"] = fullPath
                    else:
                        newnpcs[npcname]["Portrait"] = fullPath
                elif "Maps/" in targetPath:
                    node["ChangeType"] = "Load"
                    node["ModName"] = modName
                    node["Path"] = parentDir
                    node["When"] = whenPCs
                    if whenPCs:
                        node["WhenStrings"] = whenPCStrings
                    moddedLocations.append(node)
            # print(loadedEntries)
        # endif action == load
        if (action == "editdata" and "Target" in node) or len(loadedEntries) > 0:
            if len(loadedEntries) > 0:
                node["Entries"] = loadedEntries
            target = node["Target"].lower()
            # print(filepath[0])
            node = bracketReplacer(node, configParams, dynamictokens, i18n)
            # print("Action: " + node["Action"] + " Target: " + node["Target"])
            # New fish have to go first as their IDs will be used for
            # anything which uses idtostring
            # locations
            if target == "data/locations":
                # can either have an Entries node or a TextOperations node
                # will often have a When node
                # requires complete fish IDs to parse, so store it in a var until the end
                if "Entries" in node:
                    locItem = {"Data": node["Entries"], "ModName": modName, "ExtraPCs": whenPCs}
                    locationsRaw.append(locItem)
                if "TextOperations" in node:
                    locItem = {"Data": node["TextOperations"], "ModName": modName, "ExtraPCs": whenPCs}
                    editedlocationsRaw.append(locItem)
            # Mail
            if "data/mail" in target:
                if "Entries" in node:
                    mailItem = {"Data": node, "ModName": modName, "ExtraPCs": whenPCs}
                    mailRaw.append(mailItem)
            # Secret Notes
            if "data/secretnotes" in target:
                if "Entries" in node:
                    for key, note in node["Entries"].items():
                        if "{{i18n" in note:
                            noteString = intParse([note], i18n)[0]
                        else:
                            noteString = note
                        # only the first line if possible.
                        if "^" in noteString:
                            noteString = noteString.split('^', 1)[0]
                        secretNotes[key] = noteString
                        # print(key + ": " + str(secretNotes[key]))
            # Quests
            if "data/quests" in target:
                if "Entries" in node:
                    questIDs = parseQuests(node["Entries"], modName, questIDs, i18n)
            # Events
            if "data/events" in target:
                # events require all the other lists to be complete,
                # so for now just put them into a list to process later
                if "Entries" in node:
                    location = node["Target"].rsplit("/", 1)[1]
                    eventItem = {"Data": node["Entries"], "Location": location, "ModName": modName, "ExtraPCs": whenPCs, "FromFile": filepath}
                    eventsRaw.append(eventItem)
            # Special Orders
            if "data/specialorders" in target:
                if "Entries" in node:
                    soItem = {"Data": node["Entries"], "ModName": modName, "ExtraPCs": whenPCs, "FromFile": filepath}
                    specialOrdersRaw.append(soItem)
            # Blueprints
            if "data/blueprints" in target:
                if "Entries" in node:
                    node["When"] = whenPCs
                    parsedBlueprints = parseBlueprints(node["Entries"], "modded", vanillaids, modName)
                    # returns [animalDict, buildingDict]
                    if len(parsedBlueprints[1].keys()) > 0:
                        for k, v in parsedBlueprints[1].items():
                            if k in buildings:
                                v["ReplacedBy"] = modName
                            v["Path"] = filepath[0]
                            buildings[k] = v
            if "data/festivals" in target:
                if target == "data/festivals/festivaldates":  # add to calendar
                    for dateString, festival in node["Entries"].items():
                        reDate = r"([a-z]+)([0-9]+)"
                        dateParsed = re.match(reDate, dateString)
                        if dateParsed:
                            festSeason = dateParsed.group(1).title()
                            festDate = dateParsed.group(2)
                            if "Festival" in calendar[festSeason][festDate]:
                                errorlist.append("Conflict Alert: Mod " + modName + "is adding a Festival on a date when one already exists.")
                                existingFest = calendar[festSeason][festDate]["Festival"]
                                calendar[festSeason][festDate]["Festival"] = [existingFest]
                                calendar[festSeason][festDate]["Festival"].append(festival)
                            else:
                                calendar[festSeason][festDate]["Festival"] = festival
                else:  # check for temp maps and add them to festivalMaps
                    if any(target.endswith(x) for x in defaultFestivals):
                        pass
                    else:
                        soughtKeys = ["conditions", "name", "set-up"]
                        if "Entries" in node and all(x in node["Entries"] for x in soughtKeys):
                            festName = node["Entries"]["name"]
                            condParts = node["Entries"]["conditions"].split("/")
                            condHours = condParts[1].split(" ")
                            startingMap = condParts[0]
                            setupParts = node["Entries"]["set-up"].split("/")
                            for sP in setupParts:
                                if sP.startswith("changeToTemporaryMap"):
                                    tempMap = sP.split(" ", 1)[1]
                                    break
                            festivalMaps[tempMap] = {"Festival": festName, "Parent": startingMap, "FestivalDate": target.rsplit("/", 1)[1], "StartTime": condHours[0], "EndTime": condHours[1]}
            # Begin Location Data, continues into Editmap and Includes
            if "data/warpnetwork/destinations" in target:
                if "Entries" in node:
                    hasConditions = False
                    hasConfigs = False
                    noWhens = False
                    whensVerified = True
                    occupiedkeys = []
                    if not whenPCs:
                        noWhens = True
                    else:
                        # check if the only "When" is a hasmod
                        node["When"] = whenPCs
                        occupiedkeys = whenPCStrings
                        if len(occupiedkeys) == 1 and occupiedkeys[0] == "static|hasmod":
                            noWhens = True
                        try:
                            if len(whenPCs["config"].keys()) > 0:
                                hasConfigs = True
                                for k, v in whenPCs["config"].items():
                                    if k == "Eval" and v == "false":
                                        whensVerified = False
                                        break
                        except KeyError:
                            pass
                        if "saveBased|player|eventsSeen" in occupiedkeys:
                            hasConditions = True
                        if "saveBased|player|mailReceived" in occupiedkeys:
                            hasConditions = True
                        if "saveBased|player|friendshipData" in occupiedkeys:
                            hasConditions = True
                    if not whensVerified:
                        continue
                    try:
                        knownKeys = ["mailReceived", "friendshipData"]
                        if any(x not in knownKeys for x in whenPCs['saveBased']['player'].keys()):
                            hasConditions = True
                    except KeyError:
                        pass
                    if hasConditions or hasConfigs or noWhens:
                        node["Path"] = parentDir
                        node["HasConditions"] = hasConditions
                        node["HasConfigs"] = hasConfigs
                        node["File"] = filepath[0]
                        node["Method"] = "WarpNetwork"
                        if whenPCs:
                            node["When"] = whenPCs
                            node["WhenStrings"] = whenPCStrings
                        if node not in mapChangesRaw:
                            mapChangesRaw.append(node)
            # endif action == editdata
        if action == "editmap" and filepath[0] not in includedPathsGlobal:
            # we only want edits that have hasFlag or hasSeenEvent conditions or specific dates
            hasConditions = False
            hasConfigs = False
            noWhens = False
            whensVerified = True
            occupiedkeys = whenPCStrings
            node = bracketReplacer(node, configParams, dynamictokens, i18n)
            node["WhenStrings"] = occupiedkeys
            if not whenPCs:
                noWhens = True
            else:
                node["When"] = whenPCs
                try:
                    if len(whenPCs["config"].keys()) > 0:
                        hasConfigs = True
                        for k, v in whenPCs["config"].items():
                            if k == "Eval" and v == "false":
                                whensVerified = False
                                break
                except KeyError:
                    pass
                if occupiedkeys:
                    hasConditions = True
            if not whensVerified:
                continue
            if hasConditions or hasConfigs or noWhens:
                node["Path"] = parentDir
                node["HasConditions"] = hasConditions
                node["HasConfigs"] = hasConfigs
                node["File"] = filepath[0]
                node["Method"] = "Default"
                if whenPCs:
                    node["When"] = whenPCs
                if node not in mapChangesRaw:
                    mapChangesRaw.append(node)
            # endif EditMap
        if action == "include":  # only for map editing files
            includedFiles = node["FromFile"].split(", ")
            for iF in includedFiles:
                # print(iF)
                ifPath = parentDir + iF
                # print(ifPath)
                if ifPath in mapEditingFiles:
                    whensVerified = True
                    hasConditions = False
                    hasConfigs = False
                    noWhens = False
                    occupiedkeys = whenPCStrings
                    # check if all config settings are true
                    if not whenPCs:
                        noWhens = True
                    if whenPCs:
                        node["When"] = whenPCs
                        try:
                            if len(whenPCs["config"].keys()) > 0:
                                hasConfigs = True
                                for k, v in whenPCs["config"].items():
                                    if k == "Eval" and v == "false":
                                        whensVerified = False
                                        break
                        except KeyError:
                            pass
                        if occupiedkeys:
                            hasConditions = True
                    if not whensVerified:
                        continue
                    if hasConditions or hasConfigs or noWhens:
                        includedData = pyjson5.load(open(ifPath, encoding="utf-8"))
                        if 'changes' in includedData:
                            changeKey = 'changes'
                        else:
                            changeKey = "Changes"
                        for subnode in includedData[changeKey]:
                            subhaswhens = False
                            subnode["WhenStrings"] = occupiedkeys
                            if subnode["Action"] == "EditMap":
                                subnode["Path"] = parentDir
                                subnode["File"] = ifPath
                                subnode["Method"] = "Included"
                                if "When" in subnode:
                                    # if ifPath == "E:/Program Files/SteamLibrary/steamapps/common/Stardew Valley/Mods/East Scarp 2.2/[CP] East Scarp/assets/Data/SVE.json":
                                    #     pprint.pprint(subnode["When"])
                                    # if the included node has whens of its own, they override the ones from the include node in the parent.
                                    try:
                                        parsedSubWhens = parseWhens(subnode, dynamictokens, configParams, maniList, parentDir)
                                        subwhens = parsedSubWhens[0]
                                        suboccupiedkeys = parsedSubWhens[1]
                                        if subwhens["ignore"]:
                                            subwhens = {}
                                    except Exception:
                                        print(subnode["When"])
                                        traceback.print_exc()
                                        quit()
                                    if "skip" in subwhens and subwhens["skip"] == True:
                                        continue
                                    if subwhens:
                                        subhaswhens = True
                                        subnode["When"] = subwhens
                                        subnode["WhenStrings"] = suboccupiedkeys
                                        # print(suboccupiedkeys)
                                        if len(suboccupiedkeys) == 1 and suboccupiedkeys[0] == "static|hasmod":
                                            subhaswhens = False
                                        elif suboccupiedkeys:
                                            subnode["HasConditions"] = True
                                        try:
                                            if len(subwhens["config"].keys()) > 0:
                                                for k, v in subwhens["config"].items():
                                                    if k == "Eval" and v == "false":
                                                        continue
                                                subnode["HasConfigs"] = True
                                        except KeyError:
                                            pass
                                if "HasConditions" not in subnode:
                                    subnode["HasConditions"] = hasConditions
                                if "HasConfigs" not in subnode:
                                    subnode['HasConfigs'] = hasConfigs
                                if not subhaswhens and "When" in node:
                                    # if the included node has no whens, the outer When from the parent still applies.
                                    subnode["When"] = node["When"]
                                if subnode not in mapChangesRaw:
                                    mapChangesRaw.append(subnode)
            # endif include
        # end location Data
        # end change loop
    # pprint.pprint(newnpcs)
    return [newnpcs, locationsRaw, editedlocationsRaw,
            mailRaw, secretNotes, eventsRaw, specialOrdersRaw,
            buildings, mapChangesRaw, moddedLocations, questIDs, festivalMaps,
            errorlist]


def parseCPatcher(filelist, savedconfigs, outMail, maniList):
    # returns [configParams, dynamictokens, changesRaw, outMail, eventDict, moddedLocations]
    changesRaw = []
    configParams = {}
    dynamictokens = []
    eventDict = {}
    eventDict["RepeatEvents"] = []
    eventDict["UnlimitedEvents"] = []
    moddedLocations = []
    # parses cpatcher files and appends results to our global lists
    # open our actual data file
    # print("Parsing " + filepath[0])
    for filepath in tqdm(filelist, desc="Reading Content Patcher Files"):
        data = pyjson5.load(open(filepath[0], encoding="utf-8"),)
        parentDir = filepath[1]
        # print(parentDir)
        modName = parentDir.rsplit("/", 2)[1]
        # print(modName)
        if "ConfigSchema" in data:
            # get the config file
            for key, val in data["ConfigSchema"].items():
                compcfData = savedconfigs[key][0]["value"]
                if "Description" in val:
                    desc = val["Description"]
                else:
                    desc = ""
                configParams[key] = {"value": compcfData, "description": desc, "default": val["Default"], "mod": modName}
        if "DynamicTokens" in data:
            for token in data["DynamicTokens"]:
                token["src"] = parentDir
                dynamictokens.append(token)
        if "Changes" in data:
            # we need complete dynamictokens and configParams to parse Changes.
            for node in data["Changes"]:
                dataDict = {
                    "data": node,
                    "parentDir": parentDir,
                    "modName": modName,
                    "filepath": filepath
                }
                changesRaw.append(dataDict)
        # endif Changes in data
        if "RepeatEvents" in data:
            for rEvent in data["RepeatEvents"]:
                eventDict["RepeatEvents"].append(rEvent)
        # endif RepeatEvents
        if "RepeatMail" in data:
            for rMail in data["RepeatMail"]:
                if rMail not in outMail:
                    outMail[rMail] = {"Description": ""}
                outMail[rMail]["Repeating"] = True
        # endif RepeatMail
        if "EventLimiterExceptions" in data:
            for ele in data["EventLimiterExceptions"]:
                eventDict["UnlimitedEvents"].append(ele)
        # endif EventLimiterExceptions
        if "CustomLocations" in data:
            for ele in data["CustomLocations"]:
                ele["ModName"] = modName
                ele["Path"] = parentDir
                ele["ChangeType"] = "CustomLocation"
                if "When" in ele:
                    try:
                        parsedWhens = parseWhens(ele, dynamictokens, configParams, maniList, parentDir)
                        whenPCs = parsedWhens[0]
                        whenPCStrings = parsedWhens[1]
                    except Exception:
                        print(ele["When"])
                        traceback.print_exc()
                        quit()
                    if "skip" in whenPCs and whenPCs["skip"] == True:
                        continue
                    ele["When"] = whenPCs
                    ele["WhenStrings"] = whenPCStrings
                moddedLocations.append(ele)
    return [configParams, dynamictokens, changesRaw, outMail, eventDict, moddedLocations]


def parseEvents(eventsRaw, eventDict, vevents, outMail, gpreconditions, commands, newnpcs, secretNotes, vanillaids, questIDs, i18n):
    # return [eventDict, mailToEvent]
    # get the vanilla events into eventDict
    for vk, vv in vevents.items():
        eventDict[vk] = vv
    # parse New Events
    for event in tqdm(eventsRaw, desc="CPatcher Events"):
        entries = event["Data"]
        modLocation = event["Location"]
        modname = event["ModName"]
        whenPCs = event["ExtraPCs"]
        for key, event in entries.items():
            preconditionList = []
            if "/" in key:
                keyItems = key.split("/")
                eventID = keyItems[0]
                # parse preconditions
                for pc in keyItems[1:]:  # loop through each condition
                    preconditionList.append(parsePreconditions(pc, key, secretNotes, outMail, vanillaids, gpreconditions))
            else:  # no params
                eventID = key
            # end precondition parsing
            # set up the event node in eventDict
            if eventID not in eventDict:
                eventDict[eventID] = {}
            else:
                # compare preconditions, locations and Whens
                existingPC = eventDict[eventID]["Preconditions"]
                pcDiff = [i for i in existingPC + preconditionList if i not in existingPC or i not in preconditionList]
                pcDiffResult = len(pcDiff) == 0  # returns True if the two lists of dicts are the same
                # print("\nExistingPC: " + str(existingPC))
                # print("New PC: " + str(preconditionList))
                # print("Same thing? " + str(pcDiffResult))
                # locations
                locComp = True
                if "Location" in eventDict[eventID]:
                    # print("Locations: " + eventDict[eventID]["Location"] + " " + modLocation)
                    if eventDict[eventID]["Location"] != modLocation:
                        locComp = False
                elif len(modLocation) > 0:
                    # print("Existing has no location. New location: " + modLocation)
                    locComp = False
                # print("Same Locations? " + str(locComp))
                # When conditions: neither have a When, old version has a When, only new version has a When
                # neither have a When
                whenComp = True
                if "When" in eventDict[eventID]:
                    existingWhen = eventDict[eventID]["When"]
                    whenComp = all((existingWhen.get(k) == v for k, v in whenPCs.items()))
                    # print("Existing When: " + str(existingWhen))
                    # print("New When: " + str(whenPCs))
                    # print("Same Thing? " + str(whenComp))
                elif len(whenPCs) > 0:
                    whenComp = False
                    # print("Existing version has no When")
                    # print("New When: " + str(whenPCs))
                    # print("Same Thing? " + str(whenComp))
                if pcDiffResult and whenComp and locComp:
                    # same event, replace it.
                    # print("Replacing...")
                    # print("Locations: " + eventDict[eventID]["Location"] + " " + modLocation)
                    # print("Mods: " + eventDict[eventID]["ModName"] + " " + modname)
                    eventDict[eventID] = {}
                    eventDict[eventID]["Replaced"] = True
                    # print(eventID)
                    # time.sleep(15)
                else:
                    # print("New Version.")
                    usedVersion = True
                    i = 1
                    while usedVersion:
                        eventIDversioned = eventID + "v" + str(i)
                        if eventIDversioned not in eventDict:
                            eventID = eventIDversioned
                            eventDict[eventID] = {}
                            usedVersion = False
                        i += 1
            eventDict[eventID]["Location"] = modLocation
            eventDict[eventID]["ModName"] = modname
            if "Preconditions" not in eventDict[eventID]:
                eventDict[eventID]["Preconditions"] = preconditionList
            else:
                eventDict[eventID]["Preconditions"].append(preconditionList)
            if len(whenPCs) > 0:
                eventDict[eventID]["When"] = whenPCs
            # Begin event command parsing. the event itself can actually be null.
            if event:
                # get any unnecessary slashes out of the event string
                phRegex = r"{{(?!i18n)[^}]*?\/{1}(.*?)}}"
                replacement = r"[\1]"
                if re.search(phRegex, event):
                    # print("Before:" + event)
                    event = re.sub(phRegex, replacement, event)
                    # print("\nAfter:" + event)
                    # quit()
                eventItems = event.split("/")
                # print("After parse: " + str(eventDict[eventID]["Preconditions"]))
                if len(eventItems) > 2:  # x precondition events have null values
                    # fork events should start processing commands at the first list item
                    # everything else should start at the 3rd list item
                    reCoords = r"^-?[0-9]+ -?[0-9]+$"
                    shouldBeCoords = eventItems[1]
                    if re.match(reCoords, shouldBeCoords):
                        # normal event
                        eventActions = eventItems[3:]
                        eventActors = eventItems[2].split(" ")
                        eventDict[eventID]["Actors"] = eventActors[0::4]
                    else:
                        # fork event
                        eventActions = eventItems[1:]
                        eventDict[eventID]["Actors"] = []
                    # eventDict[eventID]["OpeningCoords"] = eventItems[1].split(" ")
                    # parse item 2, the actors. format NPC X Y F
                    eventDict[eventID]["Results"] = []
                    eventDict[eventID]["Rewards"] = []
                    for eventAction in eventActions:
                        lcommands = copy.deepcopy(commands)
                        eventParts = eventAction.split(" ")
                        # print(eventParts)
                        command = eventParts[0]
                        # print(command)
                        if command == "end" and "newDay" in eventParts[1:]:
                            eventDict[eventID]["Results"].append(lcommands["end"])
                        elif command == "end" and ("invisible" in eventParts[1:] or "invisibleWarpOut" in eventParts[1:]):
                            endInvisible = {
                                "Description": "Ends event and " + eventParts[-1] + " is not available for rest of day",
                                "HasParams": True,
                                "Params": [eventParts[-1]]
                            }
                            eventDict[eventID]["Results"].append(endInvisible)
                        elif command == "farmerEat" or command == "removeItem":
                            selectedCommand = lcommands[command]
                            if str(eventParts[1]) in vanillaids:
                                item = vanillaids[str(eventParts[1])]["Name"]
                            else:
                                item = str(eventParts[1])
                            selectedCommand["Description"] = selectedCommand["Description"].format(
                                item)
                            selectedCommand["Params"] = [item]
                            eventDict[eventID]["Results"].append(selectedCommand)
                        elif command == "mail" or command == "addMailReceived":
                            selectedCommand = lcommands[command]
                            if str(eventParts[1]) in outMail:
                                mail = str(eventParts[1]) + " (" + outMail[str(eventParts[1])]["Description"] + ")"
                                if "Reward" in outMail[str(eventParts[1])]:
                                    rewardList = [outMail[str(eventParts[1])]["Reward"], outMail[str(eventParts[1])]["RewardType"]]
                                    eventDict[eventID]["Rewards"].append(rewardList)
                            else:
                                mail = str(eventParts[1])
                            selectedCommand["Description"] = selectedCommand["Description"].format(
                                mail)
                            selectedCommand["Params"] = [eventParts[1]]
                            eventDict[eventID]["Results"].append(selectedCommand)
                        elif command == "addQuest" or command == "removeQuest":
                            selectedCommand = lcommands[command]
                            if str(eventParts[1]) in questIDs:
                                quest = str(eventParts[1]) + " (" + questIDs[str(eventParts[1])]["Title"] + ")"
                            else:
                                quest = str(eventParts[1])
                            selectedCommand["Description"] = selectedCommand["Description"].format(
                                quest)
                            selectedCommand["Params"] = [eventParts[1]]
                            eventDict[eventID]["Results"].append(selectedCommand)
                        elif command == "addConversationTopic":
                            selectedCommand = lcommands[command]
                            selectedCommand["Params"] = eventParts[1:]
                            if len(eventParts) > 2:
                                selectedCommand["Description"] = selectedCommand["Description"].format(
                                    *tuple(eventParts[1:]))
                            else:
                                selectedCommand["Description"] = "Start conversation topic " + eventParts[1]
                        elif command == "speak":
                            # make sure all speaking actors are in the actors field
                            if eventParts[1] not in eventDict[eventID]["Actors"] and eventParts[1] in newnpcs:
                                eventDict[eventID]["Actors"].append(eventParts[1])
                            if "FirstLine" not in eventDict[eventID]:
                                eventSpeech = intParse([" ".join(eventParts[2:])], i18n)
                                # to make it easier to tell which event we're looking at from the json
                                firstline = {"Actor": eventParts[1], "Line": eventSpeech[0].strip('\"\\').replace("@", "[PlayerName]")}
                                eventDict[eventID]["FirstLine"] = firstline
                        elif command == "changeLocation" or command == "changeToTemporaryMap":
                            if "OtherLocations" not in eventDict[eventID]:
                                eventDict[eventID]["OtherLocations"] = []
                            if eventParts[1] not in eventDict[eventID]["OtherLocations"]:
                                eventDict[eventID]["OtherLocations"].append(eventParts[1])
                        elif command == "addCookingRecipe" or command == "addCraftingRecipe":
                            selectedCommand = lcommands[command]
                            recipename = " ".join(eventParts[1:])
                            selectedCommand["Description"] = selectedCommand["Description"].format(
                                recipename)
                            selectedCommand["Params"] = [recipename]
                            eventDict[eventID]["Results"].append(selectedCommand)
                        elif command != "end":
                            if command in commands:
                                selectedCommand = lcommands[command]
                                if selectedCommand["HasParams"]:
                                    try:
                                        selectedCommand["Description"] = selectedCommand["Description"].format(
                                            *tuple(eventParts[1:]))
                                        selectedCommand["Params"] = eventParts[1:]
                                    except Exception:
                                        print(event)
                                        quit()
                                eventDict[eventID]["Results"].append(selectedCommand)
    return eventDict


def parseNewMail(newMailData, outMail, vanillaids, objectIDs, cookingids, craftingids, questids, bcids, furnids, i18n):
    # returns [outMail, objectIDs, cookingids, craftingids, questids, bcids, furnids]
    # equivalent of mailToObjects in generatevanillajson
    for nmd in tqdm(newMailData, desc="CPatcher Mail"):
        node = nmd["Data"]
        # modName = nmd["ModName"]
        whenPCs = nmd["ExtraPCs"]
        for key, mailentry in node["Entries"].items():
            outMail[key] = {}
            if "{{i18n" in mailentry:
                mailString = intParse([mailentry], i18n)[0]
            else:
                mailString = mailentry
            if "%%" in mailString:  # parse Reward
                reReward = r"(%.*?%%)"
                rewardCheck = re.search(reReward, mailString)
                # replace Json Assets with actual object name
                if "{{" in rewardCheck.group():
                    rewardString = str(rewardCheck.group())
                    outMail[key]["Reward"] = rewardString
                else:
                    outMail[key]["Reward"] = rewardCheck.group()
            if "[#]" in mailString:
                outMail[key]["Description"] = mailString.rsplit("[#]", 1)[1]
            else:
                outMail[key]["Description"] = key
            # parse the rewards
            outMail[key] = parseMail(key, outMail[key], vanillaids, cookingids, questids, bcids, furnids)
            # pprint.pprint(outMail[key])
            if len(whenPCs) > 0:
                outMail[key]["When"] = whenPCs
            outMail[key]["ModName"] = nmd["ModName"]
            # add sources to assorted dicts
            # print(key + ": " + str(outMail[key]))
    return [outMail, objectIDs, cookingids, craftingids, questids, bcids, furnids]


def parseNewQuests(questids, lobjectIDs):
    # return objectIDs
    for k, v in questids.items():
        if v["Type"] in ["ItemDelivery", "LostItem"]:
            if "ModName" in v and v["ModName"] != "Vanilla":  # new quest
                itemParts = v["Trigger"].split(" ")
                if itemParts[1].isnumeric():
                    objectID = int(itemParts[1])
                    objsearch = [ok for ok, ov in enumerate(lobjectIDs) if "ID" in ov and "objects" in ov["ID"] and ov["ID"]["objects"] == objectID]
                else:
                    itemName = itemParts[1].replace("_", " ")
                    objsearch = [ok for ok, ov in enumerate(lobjectIDs) if ov["Name"] == itemName]
                if objsearch:
                    oidx = objsearch[0]
                    if "Quests" not in lobjectIDs[oidx]["Uses"]:
                        lobjectIDs[oidx]["Uses"]["Quests"] = []
                    if k not in lobjectIDs[oidx]["Uses"]["Quests"]:
                        lobjectIDs[oidx]["Uses"]["Quests"].append(k)
                    if lobjectIDs[oidx]["Category"] == "Unspecified":
                        lobjectIDs[oidx]["Category"] = "Quest"
                    # print("Added New Quest: " + k)
                    # pprint.pprint(objectIDs[oidx])
            if "Replaced" in v:  # edited vanilla quest
                itemParts = v["Trigger"].split(" ")
                if itemParts[1].isnumeric():
                    objectID = int(itemParts[1])
                    noLongerUsed = [ok for ok, ov in enumerate(lobjectIDs) if "ID" in ov and "objects" in ov["ID"] and ov["ID"]["objects"] != objectID and "Uses" in ov and "Quests" in ov["Uses"] and k in ov["Uses"]["Quests"]]
                    newlyUsed = [ok for ok, ov in enumerate(lobjectIDs) if "ID" in ov and "objects" in ov["ID"] and ov["ID"]["objects"] == objectID]
                else:
                    itemName = itemParts[1].replace("_", " ")
                    noLongerUsed = [ok for ok, ov in enumerate(lobjectIDs) if ov["Name"] != itemName and "Uses" in ov and "Quests" in ov["Uses"] and k in ov["Uses"]["Quests"]]
                    newlyUsed = [ok for ok, ov in enumerate(lobjectIDs) if ov["Name"] == itemName]
                # remove the quest from objects which are no longer involved
                if noLongerUsed:
                    for nlu in noLongerUsed:
                        lobjectIDs[nlu]["Uses"]["Quests"].remove(k)
                        # print("Removed quest " + k + " from object " + lobjectIDs[nlu]["Name"])
                        # pprint.pprint(objectIDs[nlu])
                # add it to objects which are now involved
                if newlyUsed:
                    oidx = newlyUsed[0]
                    if "Quests" not in lobjectIDs[oidx]["Uses"]:
                        lobjectIDs[oidx]["Uses"]["Quests"] = []
                    if k not in lobjectIDs[oidx]["Uses"]["Quests"]:
                        lobjectIDs[oidx]["Uses"]["Quests"].append(k)
                        # print("Added edited quest " + k + " to object " + lobjectIDs[oidx]["Name"])
                        # pprint.pprint(objectIDs[oidx])
    # print("ObjectIDs in module: " + str(len(lobjectIDs)))
    return lobjectIDs


def parseQuests(entries, modName, questIDs, i18n):
    # parses quests
    for key, entry in entries.items():
        questdata = {}
        questParts = entry.split("/")
        questParts = intParse(questParts, i18n)
        questdata["Type"] = questParts[0]
        questdata["Title"] = questParts[1]
        questdata["Details"] = questParts[2]
        questdata["Hint"] = questParts[3]
        questdata["Trigger"] = questParts[4]
        questdata["NextQuest"] = questParts[5]
        questdata["Gold"] = int(questParts[6])
        questdata["Reward"] = questParts[7]
        questdata["Cancellable"] = questParts[8]
        questdata["ModName"] = modName
        if key not in questIDs:
            questIDs[key] = questdata
        else:
            questdata["Replaced"] = True
            questIDs[key] = questdata
    return questIDs
