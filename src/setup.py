"""
Stardew Modded Copilot Preflight Setup
Generates manifest.json, objects.json, refs/contextcats.json, saves/configparams.json
Links save file to saves directory
"""
# import argparse
import configparser
import copy
from inspect import currentframe, getframeinfo
import os
import pprint
import re
import shutil
import sys
import traceback
# if os.name == "nt":
#     import _winapi

import pyjson5
from tqdm import tqdm

from cls.data import Data as jsonData
from lib.mailParser import mailWalk, parseMFM
from lib.utils import errorsOut, writeJson
from setup.cpatcherSetup import (buildCPatcher,
                                 parseEvents,
                                 parseNewMail,
                                 parseNewQuests)
from setup.ftmSetup import buildFTM
from setup.mapSetup import buildMaps


def manifestwalk(errorlist):
    # returns list of [maniList, maniIDs, configs, JADirs, errorlist]
    # searches for manifests and config files, writes manifests.json
    # checks for framework dependencies and returns error if any are missing
    print("Searching for manifests and config files...")
    # outbound
    configs = {}
    JADirs = []
    maniList = []
    maniIDs = []

    # local
    fileList = []
    frameworkList = {}
    optionalFrameworkList = {}
    i18ns = {}
    modCount = 0
    packCount = 0
    configCount = 0

    def objectscan(path):
        # print("Searching for objects via os.scandir...")
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                yield from objectscan(entry.path)
            elif entry.name.endswith(("manifest.json")) or entry.name.endswith(("config.json")) or entry.name.endswith(("default.json")) or entry.name.endswith(("content-pack.json")):
                yield entry

    def fileToList(filePath):
        fileList.append(filePath)

    for entry in objectscan(targetdir):
        fileToList(entry.path)

    for name in fileList:
        full_path = name.replace("\\", "/")  # posix pls
        subpath = full_path.split(targetdir)[1].rsplit("/")[0:-1]
        subpath = "/".join(subpath)
        if name.endswith(("manifest.json")):
            manidata = {}
            try:
                data = pyjson5.load(open(full_path, encoding="utf-8"))
                # print(data)
                # some mods provide sample packs for devs. We don't want those.
                sampleIDs = ["YourName.YouPackNameForCustomCrystalariumMod",
                             "YourName.YouPackNameForMailFrameworkMod",
                             "YourName.YouPackNameForProducerFrameworkMod",
                             "YourName.YouPackNameForCustomCaskMod"]
                if data["UniqueID"] in sampleIDs:
                    continue
                manidata["Name"] = data["Name"]
                manidata["ID"] = data["UniqueID"]
                maniIDs.append(manidata["ID"].lower())
                manidata["ModFolder"] = subpath
                manidata["Dependencies"] = []
                if "ContentPackFor" in data:
                    cpf = data["ContentPackFor"]["UniqueID"]
                    manidata["packFor"] = cpf
                    if cpf not in frameworkList:
                        frameworkList[cpf] = 1
                    else:
                        frameworkList[cpf] += 1
                    if cpf.lower() == "spacechase0.jsonassets":
                        root = full_path[0:-13]
                        japath = root.replace("\\", "/")
                        JADirs.append(japath)
                    packCount += 1
                else:
                    manidata["packFor"] = ""
                    modCount += 1
                if "Dependencies" in data:
                    for dp in data["Dependencies"]:
                        dpf = dp["UniqueID"]
                        if "IsRequired" not in dp or dp["IsRequired"] == True:
                            if dpf not in frameworkList:
                                frameworkList[dpf] = 1
                            else:
                                frameworkList[dpf] += 1
                        else:
                            if dpf not in optionalFrameworkList:
                                optionalFrameworkList[dpf] = 1
                            else:
                                optionalFrameworkList[dpf] += 1
                        manidata["Dependencies"].append(dp)
                maniList.append(manidata)

            except Exception:
                errorlist.append('For Dev: Could not parse ' + full_path)
                errorlist.append("Traceback: " + traceback.format_exc())
            # endif manifest
        if name.endswith("config.json"):
            try:
                data = pyjson5.load(open(full_path, encoding="utf-8"))
                # print(data)
                for k, v in data.items():
                    cfDict = {"value": v, "modpath": subpath}
                    if k in configs:
                        configs[k].append(cfDict)
                    else:
                        configs[k] = [cfDict]
                configCount += 1
            except Exception:
                errorlist.append('For Dev: Could not parse ' + full_path)
                errorlist.append("Traceback: " + traceback.format_exc())
        if "i18n" in full_path and name.endswith("default.json"):
            modpath = subpath.rsplit("/", 1)[0]
            i18ns[modpath] = full_path
        if name.endswith("content-pack.json"):
            # content-pack.json files don't need to be parsed but they indicate
            # the presence of JA files in the directory
            dirpath = full_path.rsplit("/", 1)[0] + "/"
            JADirs.append(dirpath)

    # frameworkList = list(set(frameworkList))
    for fW in frameworkList.keys():
        if fW.lower() not in maniIDs:
            errorlist.append("Config Alert: Required Mod " + fW + " is not installed.")

    for k, v in i18ns.items():
        for mk, mod in enumerate(maniList):
            if mod["ModFolder"] == k:
                maniList[mk]["i18n"] = v

    print("Ingested " + str(modCount) + " mods, " + str(packCount)
          + " content packs and " + str(configCount) + " config files.")

    needString = ["This document exists so you can verify if you still need a specific framework mod in your loadout.\nIf a mod is not listed here, you can safely remove it.\n"]
    for fW, val in frameworkList.items():
        needString.append(fW + ":\n")
        needString.append("\tRequired by " + str(val) + " Mods.\n")
        if fW in optionalFrameworkList:
            needString.append("\tOptional for " + str(optionalFrameworkList[fW]) + " Mods.\n")
            del optionalFrameworkList[fW]

    for fW, val in optionalFrameworkList.items():
        needString.append(fW + ":\n")
        needString.append("\tOptional for " + str(val) + " Mods.\n")
    with open("../notes/Dependencies.txt", 'w') as f:
        f.writelines(needString)
    print("Dependency List written to notes/Dependencies.txt")
    return [maniList, maniIDs, configs, JADirs, errorlist]


# custom objects for the context categories in artisan recipes
if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")
    targetdir = config["PATHS"]["mod_directory"]
    jsonpath = config["PATHS"]["project_root"] + "json/"
    imgpath = config["PATHS"]["project_root"] + "img/"
    logpath = config["PATHS"]["log_path"]
    output_method = config["OUTPUT"]["output_method"]
    errorlist = []

    # paths that are opened elsewhere
    vmapfile = jsonpath + "vanilla/vanillamapwarps.json"
    vmapstaticfile = jsonpath + "refs/vanillamapstatic.json"

    # load all our ref files
    # refs directory
    catids = jsonData(jsonpath, "vanillacategories", "refs").data
    commands = jsonData(jsonpath, "eventcommands", "refs").data
    gpreconditions = jsonData(jsonpath, "preconditions", "refs").data
    vfestivalMaps = jsonData(jsonpath, "vanillamapstatic", "refs").data["vanillaFestivalMaps"]
    vmbos = jsonData(jsonpath, "vanillamapblockingobjects", "refs").data
    vsecretNotes = jsonData(jsonpath, "vanillasecretnotes", "refs").data
    vsostrings = jsonData(jsonpath, "vanillaspecialorderstrings", "refs").data
    vstrings = jsonData(jsonpath, "vanillastrings", "refs").data

    # vanilla directory
    vbclist = jsonData(jsonpath, "vanillabigobjects", "vanilla").data
    vbcrecipes = jsonData(jsonpath, "vanillacrafting", "vanilla").data
    vbuildings = jsonData(jsonpath, "vanillabuildings", "vanilla").data
    vcalendar = jsonData(jsonpath, "vanillacalendar", "vanilla").data
    vckrecipes = jsonData(jsonpath, "vanillacooking", "vanilla").data
    vclothing = jsonData(jsonpath, "vanillaclothingids", "vanilla").data
    vevents = jsonData(jsonpath, "vanillaevents", "vanilla").data
    vfish = jsonData(jsonpath, "vanillafish", "vanilla").data
    vfurniture = jsonData(jsonpath, "vanillafurnitureids", "vanilla").data
    vlivestock = jsonData(jsonpath, "vanillalivestock", "vanilla").data
    vmail = jsonData(jsonpath, "vanillamail", "vanilla").data
    vnpcs = jsonData(jsonpath, "vanillanpcs", "vanilla").data
    vobjlist = jsonData(jsonpath, "vanillaids", "vanilla").data
    vquestIDs = jsonData(jsonpath, "vanillaquests", "vanilla").data
    vsos = jsonData(jsonpath, "vanillaspecialorders", "vanilla").data
    vweapons = jsonData(jsonpath, "vanillaweapons", "vanilla").data

    targetdir = targetdir.replace("\\", "/")
    if targetdir[-1] != "/":
        targetdir = targetdir + "/"

    # find the manifests
    maniOut = manifestwalk(errorlist)
    maniList = maniOut[0]
    maniIDs = maniOut[1]  # just the IDs all lower case
    savedconfigs = maniOut[2]
    JADirs = maniOut[3]
    errorlist = maniOut[4]

    # replace the data normally created by the JSON Assets parser that was ripped out for this version
    objList = []
    for k, v in vobjlist.items():
        v["ID"] = {}
        v["ID"]["objects"] = k
        objList.append(v)

    bcList = copy.deepcopy(vbclist)
    bcrecipes = copy.deepcopy(vbcrecipes)
    ckrecipes = copy.deepcopy(vckrecipes)
    clothingDict = copy.deepcopy(vclothing)
    furnitureids = copy.deepcopy(vfurniture)
    weaponDict = copy.deepcopy(vweapons)

    # first pass on Content Patcher to get any fish into our objects file
    # will return empty datasets if Cpatcher is not installed or no packs available.
    cpOut = buildCPatcher(targetdir, maniList, maniIDs, vstrings, vnpcs, vevents, vsos, vsostrings, vlivestock, vbuildings, vmail, savedconfigs, vobjlist, catids, objList, vquestIDs, vfish, vsecretNotes, vcalendar, vfestivalMaps, errorlist)
    cPatcherList = cpOut[0]
    i18n = cpOut[1]
    mail = cpOut[2]  # currently just vanilla mail
    configParams = cpOut[3]
    dynamictokens = cpOut[4]
    eventDict = cpOut[5]
    moddedLocations = cpOut[6]
    locationsRaw = cpOut[7]
    editedlocationsRaw = cpOut[8]
    mailRaw = cpOut[9]  # all the new mail, unparsed
    secretNotes = cpOut[10]
    eventsRaw = cpOut[11]
    specialOrdersRaw = cpOut[12]
    mapChangesRaw = cpOut[13]
    questids = cpOut[14]
    eventDict = cpOut[15]  # currently just the repeating events
    newnpcs = cpOut[16]
    buildings = cpOut[17]
    festivalMaps = cpOut[18]  # will now contain vfestivalMaps no matter what
    errorlist = cpOut[19]

    print("==========================\nMail\n==========================")
    # That about wraps up Json Assets. Back to Content Patcher.
    if mailRaw:
        mailOut = parseNewMail(mailRaw, mail, vobjlist, objList, ckrecipes, bcrecipes, questids, bcList, furnitureids, i18n)
        mail = mailOut[0]
        objList = mailOut[1]
        ckrecipes = mailOut[2]
        bcrecipes = mailOut[3]
        questids = mailOut[4]
        bcList = mailOut[5]
        furnitureids = mailOut[6]

    # MFM File Walk
    mfmOut = mailWalk(targetdir, maniList, maniIDs, errorlist)
    mfmMail = mfmOut[0]
    errorlist = mfmOut[1]

    # blend Mail from CPatcher with mail from Mail Framework Mod
    if mfmMail:
        mfmParsedOut = parseMFM(mfmMail, vobjlist, objList, secretNotes, mail, gpreconditions, ckrecipes, bcrecipes, questids, bcList, furnitureids, weaponDict, clothingDict)
        mail = mfmParsedOut[0]
        objList = mfmParsedOut[1]
        ckrecipes = mfmParsedOut[2]
        bcrecipes = mfmParsedOut[3]
        questids = mfmParsedOut[4]
        bcList = mfmParsedOut[5]
        furnitureids = mfmParsedOut[6]
        weaponDict = mfmParsedOut[7]
        clothingDict = mfmParsedOut[8]

    # parse Quest Rewards into object Sources
    objList = parseNewQuests(questids, objList)
    if eventsRaw:
        print("==========================\nContent Patcher Second Pass\n==========================")
        eventDict = parseEvents(eventsRaw, eventDict, vevents, mail, gpreconditions, commands, newnpcs, secretNotes, vobjlist, questids, i18n)
    else:
        eventDict = vevents

    # FTM Parser self-checks for files.
    mbos = buildFTM(targetdir, maniList, vmbos, vstrings, objList, dynamictokens, configParams, secretNotes, mail, vobjlist, gpreconditions, clothingDict, bcList, furnitureids, weaponDict, errorlist)

    # MapWarps (must come after FTM and all of CPatcher)
    if (mbos != vmbos) or mapChangesRaw or moddedLocations or (eventDict != vevents) or (festivalMaps != vfestivalMaps):
        localMode = "modded"
        pmdOut = buildMaps(localMode, targetdir, errorlist, vmapstaticfile,
                           maniList, mbos, "", vmapfile,
                           mapChangesRaw, moddedLocations, savedconfigs, dynamictokens,
                           eventDict, buildings, festivalMaps)
        mapData = pmdOut[0]
        festivalShops = pmdOut[1]
        errorlist = pmdOut[2]
    else:
        mapData = jsonData(jsonpath, "vanillamapwarps", "vanilla").data

    writeJson(buildings, "buildings", jsonpath)
    writeJson(configParams, "configparams", jsonpath, "refs")
    writeJson(cPatcherList, "contentpatcherfiles", jsonpath, "refs")
    writeJson(dynamictokens, "dynamictokens", jsonpath, "refs")
    writeJson(eventDict, "events", jsonpath)
    writeJson(festivalMaps, "festivalmaps", jsonpath, "refs")
    writeJson(maniList, "manifests", jsonpath)
    writeJson(maniIDs, "manifestIDs", jsonpath, "refs")
    writeJson(mapData, "mapwarps", jsonpath)
    writeJson(mbos, "mapblockingobjects", jsonpath)
    writeJson(mapChangesRaw, "mapchanges", jsonpath, "refs")
    writeJson(moddedLocations, "moddedmaps", jsonpath, "refs")
    print("Setup Complete!")
    if errorlist:
        errorsOut(errorlist, output_method, logpath)
