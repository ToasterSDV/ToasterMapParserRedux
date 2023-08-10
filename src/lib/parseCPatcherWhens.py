"""
Content Patcher Parser
used in content_patcher_setup.py
"""
import configparser
import os
import re
import sys
import traceback
import pyjson5

sys.path.append("..")
from cls.data import Data as jsonData
from lib.bracketReplacer import bracketReplacer
from lib.whenstripper import stripWhens


def parseWhens(whenDict, dynamicTokens, configParams, manifests, parentDir):
    staticKeys = [
        "hasmod",
        "hasfile"
    ]
    configKeys = []
    for ckey in configParams.keys():
        configKeys.append(ckey.lower())
    # save based keys can be found by parsing the save file and are
    # unlikely to change in between save points.
    saveBasedKeys = [
        "childnames",
        "childgenders",
        "dailyluck",
        "day",
        "dayevent",
        "daysplayed",
        "dayofweek",
        "farmcave",
        "farmhouseupgrade",
        "farmname",
        "farmtype",
        "hasactivequest",
        "hascaughtfish",
        "hascookingrecipe",
        "hascraftingrecipe",
        "hasdialogueanswer",
        "hasflag",
        "hasprofession",
        "hasreadletter",
        "hasseenevent",
        "haswalletitem",
        "havingchild",
        "hearts",
        "iscommunitycentercomplete",
        "isjojamartcomplete",
        "ismainplayer",
        "playergender",
        "playername",
        "preferredpet",
        "pregnant",
        "relationship",
        "roommate",
        "season",
        "spouse",
        "weather",
        "year"
    ]
    # instant Keys can change between the time of last save and the time
    # the user checks the website.
    instantKeys = [
        "hasconversationtopic",
        "isoutdoors",
        "locationcontext",
        "locationname",
        "locationownerid",
        "time",
        "random",
        "skilllevel",
    ]
    dynamicKeys = []
    # print(staticKeys)
    for dT in dynamicTokens:
        dynamicKeys.append(dT["Name"].lower())
    dynamicKeys = list(set(dynamicKeys))
    specialKeys = ["query", "hasvalue"]
    # print(dynamicKeys)
    outWhens = {"static": {},
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
                }
    for key, value in whenDict["When"].items():
        isDynamic = False
        trueKey = key
        keyTarget = ""
        keyParams = []
        if "|" in trueKey:
            keyParts = trueKey.split("|")
            trueKey = keyParts[0].strip()
            keyParams = keyParts[1:]
        if ":" in trueKey:
            keyParts = trueKey.split(":")
            trueKey = keyParts[0].strip()
            keyTarget = keyParts[1].strip()
        # handle special cases
        if trueKey.lower() == "hasvalue":
            soughtValues = [x.strip("{}") for x in keyTarget.split("}}")]
            for sv in soughtValues:
                vList = [sv, bool(value)]
                if "/" in sv:
                    outWhens["extant"]["smapi"].append(vList)
                elif sv.lower() in configKeys:
                    outWhens["extant"]["config"].append(vList)
                elif sv.lower() in saveBasedKeys:
                    outWhens["extant"]["saveBased"].append(vList)
                elif sv.lower() in dynamicKeys:
                    outWhens["extant"]["dynamic"].append(vList)
                elif sv.lower() in instantKeys:
                    outWhens["extant"]["instant"].append(vList)
            # print(outWhens)
        elif trueKey.lower() == "query":
            # print("\n" + str(whenDict["When"]))
            # print("Key: " + trueKey + " KeyTarget: " + str(keyTarget) + " KeyParams: " + str(keyParams) + " Value: " + str(value))
            # our previous slicing can really muck up queries so let's reslice.
            actualQuery = key.split(":", 1)[1].strip()
            # print("\n" + actualQuery)
            reWithOperand = r"(.*?)(?<!\|contains)([><=]|IN|LIKE)(.*)"
            opCheck = re.match(reWithOperand, actualQuery)
            if opCheck:
                # query has an operand
                # print(str(opCheck.groups()))
                soughtValue = opCheck.group(1).strip("{}' ")
                # print(soughtValue)
                if "/" in soughtValue:
                    qkey = "smapi"
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                elif soughtValue.lower() in configKeys:
                    # TODO: if you ever encouter a config query, try to eval it.
                    qkey = "config"
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                elif soughtValue.lower() in saveBasedKeys:
                    qkey = 'saveBased'
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                elif soughtValue.lower() in dynamicKeys:
                    qkey = 'dynamic'
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                elif soughtValue.lower() in instantKeys:
                    qkey = "instant"
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                elif soughtValue.lower() in staticKeys:
                    # TODO: if you ever encounter a Hasmod, try to eval it here.
                    qkey = "static"
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                else:
                    # TODO: try to eval basic math queries
                    qkey = "misc"
                    operation = str(opCheck.group(2)) + str(opCheck.group(3))
                    operation = operation.replace("{{", "[").replace("}}", "]")
                    queryDict = {"Sought": soughtValue, "Operation": operation, "If": bool(value)}
                    try:
                        evaled = eval(actualQuery)
                        queryDict["Eval"] = evaled
                    except Exception:
                        pass
                outWhens["query"][qkey].append(queryDict)
                # print(outWhens["query"])
            else:
                reToken = r"{{.*?}}"
                tokens = re.findall(reToken, actualQuery)
                # print("\n" + str(actualQuery))
                # print(str(tokens))
                for token in tokens:
                    tokenParts = [x.strip() for x in token.strip("{}").split("|")]
                    # print(tokenParts)
                    trueToken = tokenParts[0]
                    if trueToken.lower() == "hasmod":
                        qkey = "static"
                        # we can eval this before sending it on.
                        soughtMods = [x.strip().lower() for x in tokenParts[1].split("=")[1].split(",")]
                        # print(soughtMods)
                        maniSearch = list(filter(None, [value if value["ID"].lower() in soughtMods else '' for value in manifests]))
                        # print(maniSearch)
                        if len(maniSearch) == len(soughtMods):
                            # print("All required Mods exist.")
                            evalResult = "true"
                        else:
                            # print("Missing a required mod.")
                            evalResult = "false"
                            outWhens["Skip"] = True
                        queryDict = {"Sought": trueToken, "If": soughtMods, "Eval": evalResult}
                        # endif trueToken is hasmod
                    elif trueToken.lower() == "hasfile":
                        # we can also eval this one.
                        # print(soughtFiles)
                        qkey = "static"
                        soughtFiles = [tokenParts[1].replace("{{FromFile}}", whenDict["FromFile"])]
                        if len(soughtFiles) == 1 and "{{Target}}" in soughtFiles[0]:
                            targets = [x.strip() for x in whenDict["Target"].split(",")]
                            for target in targets:
                                soughtFiles.append(soughtFiles[0].replace("{{Target}}", target))
                            soughtFiles = soughtFiles[1:]  # get rid of that first one with the placeholder
                        if all([os.path.exists(os.path.join(parentDir, f)) for f in soughtFiles]):
                            # print("All required files exist.")
                            evalResult = "true"
                        else:
                            # print("Missing required files.")
                            evalResult = "false"
                        queryDict = {"Sought": trueToken, "If": soughtFiles, "Eval": evalResult}
                        # endif trueToken is hasfile
                    elif trueToken.lower() in configKeys:
                        qkey = "config"
                        if isinstance(configParams[trueToken], list):
                            thisConfig = configParams[trueToken][0]
                        else:
                            thisConfig = configParams[trueToken]
                        soughtValues = [x.strip() for x in tokenParts[1].split("=")[1].split(",")]
                        if all(sV in thisConfig["value"] for sV in soughtValues):
                            evalResult = "true"
                        else:
                            evalResult = "false"
                            outWhens["skip"] = True
                        queryDict = {"Sought": trueToken, "If": soughtValues, "Eval": evalResult}
                    elif trueToken.lower() in dynamicKeys:
                        qkey = "dynamic"
                        queryDict = {"Sought": trueToken, "If": tokenParts[1:]}
                    elif trueToken.lower() in instantKeys:
                        qkey = "instant"
                        queryDict = {"Sought": trueToken, "If": tokenParts[1:]}
                    elif trueToken.lower() in saveBasedKeys:
                        qkey = "saveBased"
                        queryDict = {"Sought": trueToken, "If": tokenParts[1:]}
                        # endif in configKeys
                    outWhens["query"][qkey].append(queryDict)
                    # end for loop
                # print(outWhens["query"])
                # end non-operand queries
            # print(outWhens)
            # end if query
        if trueKey.lower() in dynamicKeys and trueKey.lower() in configKeys:
            # e.g. RivalHearts for East Scarp (config) vs RivalHearts for Tristan (dynamic)
            dynamicDict = list(filter(None, [value if value["Name"] == trueKey else '' for value in dynamicTokens]))
            if len(dynamicDict) > 0:
                for dd in dynamicDict:
                    if parentDir == dd["src"]:
                        isDynamic = True
                        break
        if (trueKey.lower() not in staticKeys
                and trueKey.lower() not in saveBasedKeys
                and trueKey.lower() not in instantKeys
                and trueKey.lower() not in dynamicKeys
                and trueKey.lower() not in configKeys
                and trueKey.lower() not in specialKeys):
            # print("I don't know what to do with:\nKey: " + key + " TrueKey: "
            #       + trueKey.lower() + "KeyTarget: " + keyTarget + "KeyParams: "
            #       + str(keyParams))
            outWhens["unknownkeys"].append(trueKey)
        elif trueKey.lower() in staticKeys:
            if trueKey.lower() == "hasmod":
                if "hasmod" not in outWhens['static']:
                    outWhens["static"]["hasmod"] = []
                mustHaveMod = True
                if isinstance(value, bool):  # HasMod has a contains param
                    soughtMods = [x.strip().lower() for x in keyParams[0].split("=")[1].split(",")]
                    if value == False:
                        mustHaveMod = False
                else:
                    soughtMods = [x.strip().lower() for x in value.split(",")]
                # print(soughtMods)
                maniSearch = list(filter(None, [value if value["ID"].lower() in soughtMods else '' for value in manifests]))
                # print(maniSearch)
                if mustHaveMod:
                    if len(maniSearch) == len(soughtMods):
                        # print("All required Mods exist.")
                        outWhens["static"]["hasmod"].append({"Positive": soughtMods})
                    else:
                        # print("Missing a required mod.")
                        outWhens["skip"] = True
                        outWhens["static"]["hasmod"].append({"Positive": soughtMods})
                        strippedWhens = stripWhens(outWhens)
                        return strippedWhens
                else:
                    if len(maniSearch) > 0:
                        # print("Found Mod excluded by HasMod")
                        outWhens["skip"] = True
                        outWhens["static"]["hasmod"].append({"Negative": soughtMods})
                        strippedWhens = stripWhens(outWhens)
                        return strippedWhens
                    else:
                        # print("Forbidden Mods not found.")
                        outWhens["static"]["hasmod"].append({"Negative": soughtMods})
                # endif hasmod
            elif trueKey.lower() == "hasfile":
                # print(soughtFiles)
                if "hasfile" not in outWhens["static"]:
                    outWhens["static"]["hasfile"] = []
                mustHaveFile = True
                if isinstance(value, bool):
                    soughtFiles = [keyTarget.replace("{{FromFile}}", whenDict["FromFile"])]
                    if value == False:
                        mustHaveFile = False
                else:
                    soughtFiles = [value.replace("{{FromFile}}", whenDict["FromFile"])]
                if len(soughtFiles) == 1 and "{{Target}}" in soughtFiles[0]:
                    targets = [x.strip() for x in whenDict["Target"].split(",")]
                    for target in targets:
                        soughtFiles.append(soughtFiles[0].replace("{{Target}}", target))
                    soughtFiles = soughtFiles[1:]  # get rid of that first one with the placeholder
                if mustHaveFile:
                    if all([os.path.exists(os.path.join(parentDir, f)) for f in soughtFiles]):
                        # print("All required files exist.")
                        outWhens["static"]["hasfile"].append({"Positive": soughtFiles})
                    else:
                        # print("Missing required files.")
                        outWhens["skip"] = True
                        outWhens["static"]["hasfile"].append({"Positive": soughtFiles})
                        strippedWhens = stripWhens(outWhens)
                        return strippedWhens
                else:
                    if any([os.path.exists(os.path.join(parentDir, f)) for f in soughtFiles]):
                        # print("Forbidden file exists.")
                        outWhens["skip"] = True
                        outWhens["static"]["hasfile"].append({"Negative": soughtFiles})
                        strippedWhens = stripWhens(outWhens)
                        return strippedWhens
                    else:
                        # print("No Forbidden files found.")
                        outWhens["static"]["hasfile"].append({"Negative": soughtFiles})
                # print(soughtFiles)
                # endif hasfile
            # endif staticKeys
        elif trueKey.lower() in configKeys and not isDynamic:  # configParams
            # We could outright reject based on configParams as they are semi-permanent.
            # However, players can change config values mid-run, so we will pass them on and let
            # a quick config parser check for changes when the miniserver starts.
            if isinstance(configParams[trueKey], list):
                thisConfig = configParams[trueKey][0]
            else:
                thisConfig = configParams[trueKey]
            # print(trueKey)
            # print("Config: " + thisConfig["value"])
            if trueKey not in outWhens["config"]:
                outWhens["config"][trueKey] = []
            if len(keyParams) > 0:
                soughtValues = [x.strip() for x in keyParams[0].split("=")[1].split(",")]
                # print(soughtValues)
                thisWhenDict = {"keys": soughtValues, "value": value}
                if value == True:
                    if all(sV in thisConfig["value"] for sV in soughtValues):
                        # print("All config values are set.")
                        thisWhenDict["Eval"] = "true"
                    else:
                        # print("Required config value missing")
                        thisWhenDict["Eval"] = "false"
                        outWhens["skip"] = True
                else:
                    if any(sV in thisConfig["value"] for sV in soughtValues):
                        # print("Forbidden Config setting found.")
                        thisWhenDict["Eval"] = "false"
                        outWhens["skip"] = True
                    else:
                        # print("No forbidden config settings found.")
                        thisWhenDict["Eval"] = "true"
            else:
                # print("Value lowered: " + str(value).lower())
                # print(thisConfig)
                # print("Config lowered: " + str(thisConfig["value"]).lower())
                thisWhenDict = {"keys": [], "value": value}
                if str(value).lower() == str(thisConfig["value"]).lower():  # convert to strings and transform to handle booleans in json
                    # print("Config value matches requirements")
                    thisWhenDict["Eval"] = "true"
                else:
                    # print("Config value does not match requirements")
                    thisWhenDict["Eval"] = "false"
                    outWhens["skip"] = True
            outWhens["config"][trueKey].append(thisWhenDict)
            # end if configkeys
        elif trueKey.lower() in saveBasedKeys:
            # convert keys to savefile keys
            outValues = {"Positive": [], "Negative": [], "Target": keyTarget}
            # value translation
            if "{{Range:" in str(value):
                value = value.strip("{}")
                rangeMargins = [x.strip() for x in str(value).split(":")[1].split(",")]
                valString = "Between " + str(rangeMargins[0]) + " and " + str(rangeMargins[1])
                soughtValues = [valString]
            if trueKey.lower() == "iscommunitycentercomplete":
                soughtValues = ["ccIsComplete"]
            elif trueKey.lower() == "isjojamartcomplete":
                soughtValues = ["jojaMember"]
            elif "=" in trueKey.lower() and (isinstance(value, bool) or str(value).lower() == "true" or str(value).lower() == "false"):
                # print("This one")
                soughtValues = [x.strip() for x in keyParams[0].split("=")[1].split(",")]
            elif keyParams and "=" in keyParams[0]:
                # print("No, this one")
                soughtValues = [x.strip() for x in keyParams[0].split("=")[1].split(",")]
            else:
                # print("Nope, it's me")
                soughtValues = [x.strip() for x in str(value).split(",")]
            # handle keytargets vs values
            if str(value).lower() == "false":
                outValues["Negative"] += soughtValues
            else:
                outValues["Positive"] += soughtValues

            straightKeys = ['daysplayed', 'farmname', 'spouse', 'year']
            calcKeys = ['dailyluck', 'dayevent', 'dayofweek', 'farmhouseupgrade', 'haswalletitem', 'havingchild', 'hearts', 'ismainplayer', 'pregnant']
            mailKeys = ['hasflag', 'hasreadletter', 'iscommunitycentercomplete', 'isjojamartcomplete']
            playerKeys = ['hasactivequest', 'hascaughtfish', 'hascookingrecipe',
                          'hascraftingrecipe', 'hasdialogueanswer', 'hasseenevent',
                          'playergender', 'playername', 'preferredpet']
            friendKeys = ['hearts', 'relationship']
            if trueKey.lower() == "childnames" or trueKey.lower() == "childgenders" or trueKey.lower() in straightKeys:
                if trueKey.lower() not in outWhens["saveBased"]:
                    outWhens["saveBased"][trueKey.lower()] = []
                outWhens["saveBased"][trueKey.lower()].append(outValues)
            elif trueKey.lower() in calcKeys:
                if trueKey.lower() not in outWhens["saveBased"]["calculated"]:
                    outWhens["saveBased"]["calculated"][trueKey.lower()] = []
                outWhens["saveBased"]["calculated"][trueKey.lower()].append(outValues)
            elif trueKey.lower() in mailKeys:
                outWhens["saveBased"]["player"]["mailReceived"].append(outValues)
            elif trueKey.lower() in playerKeys:
                translatedKey = cpToSave(trueKey)
                if translatedKey not in outWhens["saveBased"]["player"]:
                    outWhens["saveBased"]["player"][translatedKey] = []
                outWhens["saveBased"]["player"][translatedKey].append(outValues)
            elif trueKey.lower() in friendKeys:
                translatedKey = cpToSave(trueKey)
                if translatedKey not in outWhens["saveBased"]["player"]["friendshipData"]:
                    outWhens["saveBased"]["player"]["friendshipData"][translatedKey] = []
                outWhens["saveBased"]["player"]["friendshipData"][translatedKey].append(outValues)
            elif trueKey.lower() == "hasprofession":
                profIDX = {"rancher": 0,
                           "tiller": 1,
                           "coopmaster": 2,
                           "shepherd": 3,
                           "artisan": 4,
                           "agriculturist": 5,
                           "fisher": 6,
                           "trapper": 7,
                           "angler": 8,
                           "pirate": 9,
                           "mariner": 10,
                           "luremaster": 11,
                           "forester": 12,
                           "gatherer": 13,
                           "lumberjack": 14,
                           "tapper": 15,
                           "botanist": 16,
                           "tracker": 17,
                           "miner": 18,
                           "geologist": 19,
                           "blacksmith": 20,
                           "prospector": 21,
                           "excavator": 22,
                           "gemologist": 23,
                           "fighter": 24,
                           "scout": 25,
                           "brute": 26,
                           "defender": 27,
                           "acrobat": 28,
                           "desperado": 29}
                convertedValues = []
                for stringVal in outValues["Positive"]:
                    convertedValues.append(profIDX[stringVal.lower()])
                outValues["Positive"] = convertedValues
                convertedValues = []
                for stringVal in outValues["Negative"]:
                    convertedValues.append(profIDX[stringVal.lower()])
                outValues["Negative"] = convertedValues
                if "professions" not in outWhens["saveBased"]["player"]:
                    outWhens["saveBased"]["player"]["professions"] = []
                outWhens["saveBased"]["player"]["professions"].append(outValues)
            else:
                translatedKey = cpToSave(trueKey)
                if translatedKey not in outWhens["saveBased"]:
                    outWhens["saveBased"][translatedKey] = []
                outWhens["saveBased"][translatedKey].append(outValues)
            # endif saveBased
        elif trueKey.lower() in dynamicKeys:
            outValues = {"Positive": [], "Negative": [], "Target": keyTarget}
            if "{{Range:" in str(value):
                value = value.strip("{}")
                rangeMargins = [x.strip() for x in str(value).split(":")[1].split(",")]
                valString = "Between " + str(rangeMargins[0]) + " and " + str(rangeMargins[1])
                soughtValues = [valString]
            elif isinstance(value, bool) or str(value).lower() == "true" or str(value).lower() == "false":
                if len(keyParams) > 0:
                    soughtValues = [x.strip() for x in keyParams[0].split("=")[1].split(",")]
                else:
                    soughtValues = [str(value)]
            else:
                soughtValues = [x.strip() for x in str(value).split(",")]
            # handle keytargets vs values
            if str(value).lower() == "false":
                outValues["Negative"] += soughtValues
            else:
                outValues["Positive"] += soughtValues
            if trueKey not in outWhens["dynamic"]:
                outWhens["dynamic"][trueKey] = []
            outWhens["dynamic"][trueKey].append(outValues)  # preserve key case here
            # print(outWhens)
            # endif dynamicKeys
        elif trueKey.lower() in instantKeys:
            # print("\n" + str(whenDict["When"]))
            # print("Key: " + key + " TrueKey: " + trueKey.lower(), "KeyTarget: " + keyTarget, "KeyParams: " + str(keyParams) + " Value: " + str(value))
            outValues = {"Positive": [], "Negative": [], "Target": keyTarget}
            if "{{range:" in str(value).lower():
                value = value.strip("{}")
                rangeMargins = [x.strip() for x in str(value).split(":")[1].split(",")]
                valString = "Between " + str(rangeMargins[0]) + " and " + str(rangeMargins[1])
                soughtValues = [valString]
            elif isinstance(value, bool) or str(value).lower() == "true" or str(value).lower() == "false":
                if len(keyParams) > 0:
                    soughtValues = [x.strip() for x in keyParams[0].split("=")[1].split(",")]
                else:
                    soughtValues = [str(value)]
            else:
                soughtValues = [x.strip() for x in str(value).split(",")]
            # handle keytargets vs values
            if str(value).lower() == "false":
                outValues["Negative"] += soughtValues
            else:
                outValues["Positive"] += soughtValues
            if trueKey not in outWhens["instant"]:
                outWhens["instant"][trueKey] = []
            outWhens["instant"][trueKey].append(outValues)  # preserve key case here
            # print(outWhens)
            # endif instantKeys
        # this leaves us with number manipulation, string manipulation, render, firstvalidfile
    strippedWhens = stripWhens(outWhens)  # list
    # outWhensStripped = strippedWhens[0]
    # print(outWhensStripped.keys())
    # cannotIgnore = ["saveBased", "unknownkeys", "instant", 'dynamic', 'smapi']
    return strippedWhens


def cpToSave(inString):
    # translates content patcher tokens to savegame keys
    if inString.lower() == "day":
        return "dayOfMonth"
    if inString.lower() == "daysplayed":
        return "daysPlayed"
    if inString.lower() == "farmcave":
        return "caveChoice"
    if inString.lower() == "farmname":
        return "farmName"
    if inString.lower() == "farmtype":
        return "whichFarm"
    if inString.lower() == "hasactivequest":
        return "questLog"
    if inString.lower() == "hascaughtfish":
        return "fishCaught"
    if inString.lower() == "hascookingrecipe":
        return "cookingRecipes"
    if inString.lower() == "hascraftingrecipe":
        return "craftingRecipes"
    if inString.lower() == "hasdialogueanswer":
        return "dialogueQuestionsAnswered"
    if inString.lower() == "hasprofession":
        return "professions"
    if inString.lower() == "hasseenevent":
        return "eventsSeen"
    if inString.lower() == "playergender":
        return "isMale"
    if inString.lower() == "playername":
        return "name"
    if inString.lower() == "preferredpet":
        return "catPerson"
    if inString.lower() == "relationship":
        return "Status"
    if inString.lower() == "roommate":
        return "RoommateMarriage"
    if inString.lower() == "season":
        return "currentSeason"
    if inString.lower() == "weather":
        return "locationWeather"
    return inString


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("../config.ini")
    targetdir = config["PATHS"]["mod_directory"]
    savedir = config["PATHS"]["stardew_save"]
    jsonpath = config["PATHS"]["project_root"] + "json/"
    processed = []

    dynamicTokens = jsonData(jsonpath, "dynamictokens", "refs").data
    eventwhens = jsonData(jsonpath, "events").data
    manifests = jsonData(jsonpath, "manifests").data

    cfgFile = "../../saves/configParams.json"
    configParams = pyjson5.load(open(cfgFile),)

    # for when in eventwhens:
    #     outWhen = parseWhens(when, dynamicTokens, configParams, manifests)
    #     if outWhen:
    #         outDict = {"In": when["data"], "Out": outWhen}
    #         processed.append(outDict)
    #
    # output = pyjson5.dumps(processed)
    # with open("../json/temp/temp-processedwhens.json", "w") as outfile:
    #     outfile.write(output)
    parentDir = "E:/Program Files/SteamLibrary/steamapps/common/Stardew Valley/Mods/Stardew Valley Expanded/[CP] Stardew Valley Expanded/"
    tempVar = {}
    tempVar["When"] = {"Season": "Fall", "SeasonalEdits": True, "HasMod |contains=flashshifter.immersivefarm2remastered": False}
    tempVar["When"] = {"HasMod |contains=spacechase0.JsonAssets": True}
    outWhen = parseWhens(tempVar, dynamicTokens, configParams, manifests, parentDir)
    print(outWhen)
    # print(parseWhens(thisWhen))
    # parseWhens(eventwhens[0])
