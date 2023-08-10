"""
Parses rewards from mail
"""
import configparser
import copy
import os
import pprint
import re
import sys
import traceback
import pyjson5

from tqdm import tqdm

sys.path.append("..")
from cls.data import Data as jsonData
from lib.parsePreconditions import parsePreconditions
from lib.whenstripper import stripWhens


def buildMFMWhen(mailDict, key, secretNotes, existingmail, vanillaids, gpreconditions):
    # return mailWhen
    mailWhen = {"saveBased": {"calculated": {}, "locations": {},
                              "player": {"mailReceived": [], "friendshipData": {}}
                              },
                "instant": {},
                "preconditions": [],
                "skip": False,
                "unknownkeys": []
                }
    if "Date" in mailDict:
        dateParts = mailDict["Date"].split(" ")  # format dd MM "Y"y
        dateDate = dateParts[0]
        dateSeason = dateParts[1]
        dateYear = dateParts[2][1:]
        mailWhen["saveBased"]["year"] = dateYear
        mailWhen["saveBased"]["season"] = dateSeason
        mailWhen["saveBased"]["dayOfMonth"] = dateDate
    if "Days" in mailDict:
        mailWhen["saveBased"]["dayOfMonth"] = mailDict["Days"]
    if "Seasons" in mailDict:
        mailWhen["saveBased"]["currentSeason"] = mailDict["Seasons"]
    if "Weather" in mailDict:
        mailWhen["saveBased"]["locationWeather"] = [mailDict["Weather"]]
    if "HouseUpgradeLevel" in mailDict:
        mailWhen["saveBased"]["farmhouseupgrade"] = [mailDict["HouseUpgradeLevel"]]
    if "DeepestMineLevel" in mailDict:
        mailWhen["saveBased"]["deepestMineLevel"] = [mailDict["DeepestMineLevel"]]
    if "CurrentMoney" in mailDict:
        mailWhen["instant"]["money"] = [mailDict["CurrentMoney"]]
    if "TotalMoneyEarned" in mailDict:
        mailWhen["saveBased"]["totalMoneyEarned"] = [mailDict["TotalMoneyEarned"]]
    if "FriendshipConditions" in mailDict:
        for fC in mailDict["FriendshipConditions"]:
            npcName = fC["NpcName"]
            if "FriendshipLevel" in fC:
                mailWhen["saveBased"]["calculated"]["hearts"] = {"Positive": [fC["FriendshipLevel"]], "Target": npcName}
            if "FriendshipStatus" in fC:
                mailWhen["saveBased"]["player"]["friendshipData"][npcName] = {"Status": [{"Positive": [fC["FriendshipStatus"]], "Target": npcName}]}
    if "SkillConditions" in mailDict:
        mailWhen["instant"]["skilllevel"] = []
        for sC in mailDict["SkillConditions"]:
            slDict = {"Positive": [sC["SkillLevel"]], "Target": sC["SkillName"]}
            mailWhen["instant"]["skilllevel"].append(slDict)
    if "StatsConditions" in mailDict:
        mailWhen["saveBased"]["player"]["stats"] = {}
        mailWhen["saveBased"]["player"]["stat_dictionary"] = {}
        for sC in mailDict["StatsConditions"]:
            if "StatsName" in sC:
                mailWhen["saveBased"]["player"]["stats"][sC["StatsName"]] = sC["Amount"]
            elif "StatsLabel" in sC:
                mailWhen["saveBased"]["player"]["stat_dictionary"][sC["StatsLabel"]] = sC["Amount"]
    if "CollectionConditions" in mailDict:
        for cC in mailDict["CollectionConditions"]:
            if cC["Collection"] == "Shipped":
                mKey = "basicShipped"
            elif cC["Collection"] == "Fish":
                mKey = "fishCaught"
            elif cC["Collection"] == "Artifacts":
                mKey = "archaeologyFound"
            elif cC["Collection"] == "Minerals":
                mKey = "mineralsFound"
            elif cC["Collection"] == "Cooking":
                mKey = "recipesCooked"
            elif cC["Collection"] == "Crafting":
                mKey = "craftingRecipes"
            if mKey not in mailWhen["saveBased"]["player"]:
                mailWhen["saveBased"]["player"][mKey] = {}
            if "Name" in cC:
                soughtItem = cC["Name"]
            else:
                soughtItem = vanillaids[str(cC["Index"])]["Name"]
            # print(soughtItem)
            mailWhen["saveBased"]["player"][mKey][soughtItem] = cC["Amount"]
        # endif CollectionConditions
    if "ExpandedPrecondition" in mailDict:
        pcs = mailDict["ExpandedPrecondition"].split("/")
        for pc in pcs:
            mailWhen["preconditions"].append(parsePreconditions(pc, key, secretNotes, existingmail, vanillaids, gpreconditions))
    if "ExpandedPreconditions" in mailDict:
        for pcstring in mailDict["ExpandedPreconditions"]:
            pcs = pcstring.split("/")
            for pc in pcs:
                mailWhen["preconditions"].append(parsePreconditions(pc, key, secretNotes, existingmail, vanillaids, gpreconditions))
    if "RandomChance" in mailDict:
        mailWhen["instant"]["random"] = [mailDict["RandomChance"]]
    if "Buildings" in mailDict:
        mailWhen["saveBased"]["locations"]["Farm"] = {}
        mailWhen["saveBased"]["locations"]["Farm"]["buildings"] = {"Which": mailDict["Buildings"], "Scope": "any"}
    if "RequireAllBuildings" in mailDict and str(mailDict["RequireAllBuildings"]).lower() == "true":
        mailWhen["saveBased"]["locations"]["Farm"]["buildings"]["Scope"] = "all"
    if "MailReceived" in mailDict:
        flagDict = {"Positive": mailDict["MailReceived"], "Scope": "any"}
        if "RequireAllMailReceived" in mailDict and str(mailDict["RequireAllMailReceived"]).lower() == "true":
            flagDict["Scope"] = "all"
        mailWhen["saveBased"]["player"]["mailReceived"].append(flagDict)
    if "MailNotReceived" in mailDict:
        flagDict = {"Negative": mailDict["MailNotReceived"], "Scope": "any"}
        if "RequireAllMailReceived" in mailDict and str(mailDict["RequireAllMailReceived"]).lower() == "true":
            flagDict["Scope"] = "all"
        mailWhen["saveBased"]["player"]["mailReceived"].append(flagDict)
    if "EventsSeen" in mailDict:
        if "eventsSeen" not in mailWhen["saveBased"]["player"]:
            mailWhen["saveBased"]["player"]["eventsSeen"] = []
        flagDict = {"Positive": mailDict["EventsSeen"], "Scope": "any"}
        if "RequireAllEventsSeen" in mailDict and str(mailDict["RequireAllEventsSeen"]).lower() == "true":
            flagDict["Scope"] = "all"
        mailWhen["saveBased"]["player"]["eventsSeen"].append(flagDict)
    if "EventsNotSeen" in mailDict:
        if "eventsSeen" not in mailWhen["saveBased"]["player"]:
            mailWhen["saveBased"]["player"]["eventsSeen"] = []
        flagDict = {"Negative": mailDict["EventsNotSeen"], "Scope": "any"}
        if "RequireAllEventsSeen" in mailDict and str(mailDict["RequireAllEventsSeen"]).lower() == "true":
            flagDict["Scope"] = "all"
        mailWhen["saveBased"]["player"]["eventsSeen"].append(flagDict)
    if "RecipesKnown" in mailDict:
        if "recipesknown" not in mailWhen["saveBased"]["calculated"]:
            mailWhen["saveBased"]["calculated"]["recipesknown"] = []
        rDict = {"Positive": mailDict["RecipesKnown"], "Scope": "any"}
        if "RequireAllRecipesKnown" in mailDict and str(mailDict["RequireAllRecipesKnown"]).lower() == "true":
            rDict["Scope"] = "all"
        mailWhen["saveBased"]["calculated"]["recipesknown"].append(rDict)
    if "RecipesNotKnown" in mailDict:
        if "recipesknown" not in mailWhen["saveBased"]["calculated"]:
            mailWhen["saveBased"]["calculated"]["recipesknown"] = []
        rDict = {"Negative": mailDict["RecipesNotKnown"], "Scope": "any"}
        if "RequireAllRecipesKnown" in mailDict and str(mailDict["RequireAllRecipesKnown"]).lower() == "true":
            rDict["Scope"] = "all"
        mailWhen["saveBased"]["calculated"]["recipesknown"].append(rDict)
    # print(mailWhen)
    strippedWhens = stripWhens(mailWhen)  # list
    # print(strippedWhens[0])
    return strippedWhens[0]


def mailToObjects(mail, mailToEvent, mailToOrder, objList, bcList, ckrecipes, bcrecipes, furnitureids, weaponDict, clothingDict):
    for k, v in mail.items():
        printthis = False
        # if k == "Clint.Auto.Mill":
        #     printthis = True
        if printthis:
            print(v)
        if "Reward" in v:
            # print(v["RewardType"])
            isFriendship = False
            friendSource = None
            isSkill = False
            skillSource = None
            sourceDict = {}
            if "When" in v:
                # figure out if it's actually based on friendship or skill
                try:
                    friendshipData = v["When"]["saveBased"]["calculated"]["hearts"]
                    isFriendship = True
                    friendSource = friendshipData["Target"] + " " + str(friendshipData["Positive"][0])
                    sourceDict = {"Friendship": friendSource}
                except Exception:
                    if printthis:
                        traceback.print_exc()
                    pass
                try:
                    skillData = v["When"]["instant"]["skillLevel"]
                    isSkill = True
                    skillSource = skillData["Target"] + " " + str(skillData["Positive"][0])
                    print(skillSource)
                    sourceDict = {"Skill": skillSource}
                except Exception:
                    if printthis:
                        traceback.print_exc()
                    pass
            if isinstance(mailToEvent, dict) and k in mailToEvent:
                sourceDict = {"EventMail": [mailToEvent[k]]}
            elif isinstance(mailToOrder, dict) and k in mailToOrder:
                sourceDict = {"SpecialOrder": [mailToOrder[k]]}
            if not isSkill and not isFriendship and not sourceDict:
                sourceDict = {"Mail": [k]}
            if printthis:
                print(sourceDict)
            # RewardType can be object, bigobject, furniture, craftingRecipe, cookingRecipe, weapon, ring, boots
            if "RewardType" not in v:
                print(v)
            if v["RewardType"] in ["object", "ring"]:
                if "RewardIDs" not in v:
                    print(v)
                    quit()
                for rID in v["RewardIDs"]:
                    if isinstance(rID, str):
                        objsearch = [ok for ok, ov in enumerate(objList) if ov["Name"] == rID]
                    else:
                        objsearch = [ok for ok, ov in enumerate(objList) if "ID" in ov and "objects" in ov["ID"] and ov["ID"]["objects"] == rID]
                    if objsearch:
                        oidx = objsearch[0]
                        # if it isn't actually coming from Mail but objList currently thinks it is, swap the keys around
                        if "Mail" not in sourceDict and "Mail" in objList[oidx]["Sources"] and k in objList[oidx]["Sources"]["Mail"]:
                            objList[oidx]["Sources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in objList[oidx]["Sources"]:
                                objList[oidx]["Sources"][scK] = []
                            if isinstance(scV, str):
                                objList[oidx]["Sources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in objList[oidx]["Sources"][scK]:
                                        objList[oidx]["Sources"][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(objList[oidx])
            elif v["RewardType"] == "bigobject":
                for rID in v["RewardIDs"]:
                    if isinstance(rID, str):
                        bcsearch = [bk for bk, bv in enumerate(bcList) if bv["Name"] == rID]
                    else:
                        bcsearch = [bk for bk, bv in enumerate(bcList) if "ID" in bv and "bigcraftables" in bv["ID"] and bv["ID"]["bigcraftables"] == rID]
                    if bcsearch:
                        bidx = bcsearch[0]
                        # if it isn't actually coming from Mail but objList currently thinks it is, swap the keys around
                        if "Mail" not in sourceDict and "Mail" in bcList[bidx]["Sources"] and k in bcList[bidx]["Sources"]["Mail"]:
                            bcList[bidx]["Sources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in bcList[bidx]["Sources"]:
                                bcList[bidx]["Sources"][scK] = []
                            if isinstance(scV, str):
                                bcList[bidx]["Sources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in bcList[bidx]["Sources"][scK]:
                                        bcList[bidx]["Sources"][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(bcList[bidx])
            elif v["RewardType"] == "furniture":
                for rID in v["RewardIDs"]:
                    if isinstance(rID, int) or rID.isnumeric():
                        fsearch = [str(rID)]
                    else:
                        fsearch = [fk for fk, fv in furnitureids.items() if fv["Name"] == rID]
                    if fsearch:
                        fidx = fsearch[0]
                        if "Sources" not in furnitureids[fidx]:
                            furnitureids[fidx]["Sources"] = {}
                        if "Mail" not in sourceDict and "Mail" in furnitureids[fidx]["Sources"] and k in furnitureids[fidx]["Sources"]["Mail"]:
                            furnitureids[fidx]["Sources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in furnitureids[fidx]["Sources"]:
                                furnitureids[fidx]["Sources"][scK] = []
                            if isinstance(scV, str):
                                furnitureids[fidx]["Sources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in furnitureids[fidx]["Sources"][scK]:
                                        furnitureids[fidx]["Sources"][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(furnitureids[fidx])
            elif v["RewardType"] == "craftingRecipe":
                if printthis:
                    print("hi")
                for rID in v["RewardIDs"]:
                    cfsearch = [str(rID)]
                    if cfsearch:
                        if printthis:
                            print("hello")
                        cidx = cfsearch[0]
                        if "RecipeSources" not in bcrecipes[cidx]:
                            bcrecipes[cidx]["RecipeSources"] = {}
                        if "Mail" not in sourceDict and "Mail" in bcrecipes[cidx]["RecipeSources"] and k in bcrecipes[cidx]["RecipeSources"]["Mail"]:
                            bcrecipes[cidx]["RecipeSources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in bcrecipes[cidx]["RecipeSources"]:
                                bcrecipes[cidx]["RecipeSources"][scK] = []
                            if isinstance(scV, str):
                                bcrecipes[cidx]["RecipeSources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in bcrecipes[cidx]["RecipeSources"][scK]:
                                        bcrecipes[cidx]["RecipeSources"][scK].append(mv)
                            if printthis:
                                print("\nNew Key: " + scK)
                                pprint.pprint(bcrecipes[cidx])
            elif v["RewardType"] == "cookingRecipe":
                for rID in v["RewardIDs"]:
                    if isinstance(rID, int) or rID.isnumeric():
                        cfsearch = [str(rID)]
                    else:
                        cfsearch = [fk for fk, fv in ckrecipes.items() if fv["Product"] == rID]
                    if cfsearch:
                        cidx = cfsearch[0]
                        if "RecipeSources" not in ckrecipes[cidx]:
                            ckrecipes[cidx]["RecipeSources"] = {}
                        if "Mail" not in sourceDict and "Mail" in ckrecipes[cidx]["RecipeSources"] and k in ckrecipes[cidx]["RecipeSources"]["Mail"]:
                            ckrecipes[cidx]["RecipeSources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in ckrecipes[cidx]["RecipeSources"]:
                                ckrecipes[cidx]["RecipeSources"][scK] = []
                            if isinstance(scV, str):
                                ckrecipes[cidx]["RecipeSources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in ckrecipes[cidx]["RecipeSources"][scK]:
                                        ckrecipes[cidx]["RecipeSources"][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(ckrecipes[cidx])
            elif v["RewardType"] == "weapon":
                for rID in v["RewardIDs"]:
                    if isinstance(rID, int) or rID.isnumeric():
                        wsearch = [str(rID)]
                    else:
                        wsearch = [fk for fk, fv in weaponDict.items() if fv["Name"] == rID]
                    if wsearch:
                        widx = wsearch[0]
                        if "Sources" not in weaponDict[widx]:
                            weaponDict[widx]["Sources"] = {}
                        if "Mail" not in sourceDict and "Mail" in weaponDict[widx]["Sources"] and k in weaponDict[widx]["Sources"]["Mail"]:
                            weaponDict[widx]["Sources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in weaponDict[widx]["Sources"]:
                                weaponDict[widx]["Sources"][scK] = []
                            if isinstance(scV, str):
                                weaponDict[widx]["Sources"][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in weaponDict[widx]["Sources"][scK]:
                                        weaponDict[widx]["Sources"][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(weaponDict[widx])
            if v["RewardType"] in ["ring", "boots"]:  # can't do an elif here since we already used ring
                if v["RewardType"] == "ring":
                    ckey = "Rings"
                else:
                    ckey = "Boots"
                for rID in v["RewardIDs"]:
                    if isinstance(rID, int) or rID.isnumeric():
                        csearch = [str(rID)]
                    else:
                        csearch = [fk for fk, fv in clothingDict[ckey].items() if fv["Name"] == rID]
                    if csearch:
                        cidx = wsearch[0]
                        if "Sources" not in clothingDict[ckey][cidx]:
                            clothingDict[ckey][cidx]["Sources"] = {}
                        if "Mail" not in sourceDict and "Mail" in clothingDict[ckey][cidx]["Sources"] and k in clothingDict[ckey][cidx]["Sources"]["Mail"]:
                            clothingDict[ckey][cidx]["Sources"]["Mail"].remove(k)
                        for scK, scV in sourceDict.items():
                            if scK not in clothingDict[ckey][cidx]["Sources"]:
                                clothingDict[ckey][cidx][scK] = []
                            if isinstance(scV, str):
                                clothingDict[ckey][cidx][scK] = scV
                            else:
                                for mv in scV:
                                    if mv not in clothingDict[ckey][cidx]["Sources"][scK]:
                                        clothingDict[ckey][cidx][scK].append(mv)
                            # print("\nNew Key: " + scK)
                            # pprint.pprint(clothingDict[ckey][cidx])
    return [objList, bcList, furnitureids, bcrecipes, ckrecipes, weaponDict, clothingDict]


def mailWalk(targetdir, maniList, maniIDs, errorlist):
    # search for Mail Framework Mod files and add to list.
    mailPaths = []
    mfmMail = {}
    hasMFM = False
    if "digus.mailframeworkmod" in maniIDs:
        hasMFM = True
    manisearch = list(filter(None, [value if value["packFor"].lower() == "digus.mailframeworkmod" else '' for value in maniList]))
    if manisearch:
        if not hasMFM:
            errorlist.append("Config Alert: You have Packs for Mail Framework Mod but do not have it installed.")
            return [mfmMail, errorlist]
        else:
            for mod in manisearch:
                if "ContentPackTemplate" not in mod["ModFolder"]:
                    mailPath = targetdir + mod["ModFolder"] + "/mail.json"
                    mailPaths.append(mailPath)
            for name in mailPaths:
                try:
                    mailPath = name.replace("\\", "/")
                    mfmMail[mailPath] = []
                    data = pyjson5.load(open(name, encoding="utf-8"),)
                    for mailItem in data:
                        mfmMail[mailPath].append(mailItem)
                except Exception:
                    errorlist.append("For Dev: MailWalk error: " + name)
                    errorlist.append("Traceback: " + traceback.format_exc())
    else:
        if hasMFM:
            errorlist.append("Config Alert: You have Mail Framework Mod installed but no packs for it")
    return [mfmMail, errorlist]


# def parseMFM(newmaildata, filepath, vanillaids, objids, secretNotes, mailIDs, gpreconditions):
def parseMFM(mfmMail, vanillaids, objList, secretNotes, mail, gpreconditions, ckrecipes, bcrecipes, questids, bcList, furnitureids, weaponDict, clothingDict):
    outMail = copy.deepcopy(mail)
    # print("\n" + filepath)
    for k, v in tqdm(mfmMail.items(), desc="Mail Framework Mod Mail"):
        newmaildata = v
        modname = k.rsplit("/", 2)[1]
        i18nPath = k.rsplit("/", 1)[0] + "/i18n/default.json"
        if os.path.exists(i18nPath):
            i18n = pyjson5.load(open(i18nPath, encoding="utf-8"),)
        else:
            i18n = {}
        for newmail in newmaildata:
            # print(mail)
            key = newmail["Id"]
            if key in outMail:
                outMail[key]["EditedBy"] = modname
            else:
                outMail[key] = {}
                outMail[key]["ModName"] = modname
            unparsedKeys = ['GroupId', 'Title', 'Repeatable', 'AutoOpen']
            for mkey in unparsedKeys:
                if mkey in newmail:
                    outMail[key][mkey] = newmail[mkey]
            if "Title" in outMail[key]:
                try:
                    outMail[key]["Description"] = i18n[outMail[key]["Title"]]
                except KeyError:
                    outMail[key]["Description"] = outMail[key]["Title"]
                del outMail[key]["Title"]
            else:
                outMail[key]["Description"] = newmail["Id"]
            if "AdditionalMailReceived" in newmail:
                outMail[key]["ExtraFlags"] = newmail["AdditionalMailReceived"]
            # begin preconditions
            outMail[key]["When"] = buildMFMWhen(newmail, key, secretNotes, mail, vanillaids, gpreconditions)
            # end preconditions
    return [outMail, objList, ckrecipes, bcrecipes, questids, bcList, furnitureids, weaponDict, clothingDict]


def parseMail(mailKey, mail, vanillaids, cookingids, questids, bcids, furnids, mode="modded"):
    # print(mailKey)
    if "Reward" not in mail:
        if mode == "vanilla":
            mail["ModName"] = "Vanilla"
        return mail
    else:
        inReward = mail["Reward"]
        rewardIDs = []
        # print(inReward)
        if inReward == "%secretsanta":
            outReward = "Secret Santa NPC Name"
            rewardType = "SecretSanta"
        else:
            # get rid of the excess chrome
            outReward = inReward.strip('%')[5:].strip()
            rewardParts = outReward.split(" ")
            rewardType = rewardParts[0]
            if rewardType == "object":
                rewardOptions = []
                rewardQtys = []
                rewardStrings = []
                for rewardID in rewardParts[1::2]:
                    if rewardID.isnumeric():
                        rewardName = vanillaids[str(rewardID)]["Name"]
                        rewardIDs.append(int(rewardID))
                    else:
                        rewardName = rewardID.replace("_", " ")
                        rewardIDs.append(rewardName)
                    rewardOptions.append(rewardName)
                for qty in rewardParts[2::2]:
                    rewardQtys.append(qty)
                for idx, reward in enumerate(rewardOptions):
                    rewardString = rewardQtys[idx] + " " + reward
                    rewardStrings.append(rewardString)
                outReward = " or ".join(rewardStrings)
                # endif object
            elif rewardType == "bigobject":
                rewardIDList = rewardParts[1:]
                rewardNames = []
                for rID in rewardIDList:
                    if rID.isnumeric():
                        if mode == "vanilla":
                            bcsearch = [str(rID)]
                        else:
                            bcsearch = [bk for bk, bv in enumerate(bcids) if "ID" in bv and "bigcraftables" in bv["ID"] and bv["ID"]["bigcraftables"] == int(rID)]
                        if bcsearch:
                            rewardName = bcids[bcsearch[0]]["Name"]
                        else:
                            rewardName = "Something Would Be Here If I hadn't gutted the Json Assets module"
                        rewardIDs.append(int(rID))
                    else:
                        rewardName = rID.replace("_", " ")
                        rewardIDs.append(rewardName)
                    rewardNames.append(rewardName)
                outReward = " or ".join(rewardNames)
            elif rewardType == "furniture":
                rewardIDList = rewardParts[1:]
                rewardNames = []
                for rID in rewardIDList:
                    if rID.isnumeric():
                        rewardName = furnids[str(rID)]["Name"]
                        rewardIDs.append(int(rID))
                    else:
                        rewardName = rID
                        rewardIDs.append(rID)
                    rewardNames.append(rewardName)
                outReward = " or ".join(rewardNames)
            elif rewardType == "money":
                rewardAmount = rewardParts[1]
                outReward = str(rewardAmount) + "g"
            elif rewardType == "quest":
                skippable = ' (Optional)'
                if len(rewardParts) > 2:
                    skippable = ""
                outReward = questids[str(rewardParts[1])]["Title"] + skippable
            elif rewardType == "conversationTopic":
                topic = rewardParts[1]
                days = rewardParts[2]
                outReward = topic + " for " + str(days) + " day(s)"
            elif rewardType == "craftingRecipe":
                outReward = "Recipe: " + rewardParts[1].replace("_", " ")
                rewardIDs.append(rewardParts[1].replace("_", " "))
            elif rewardType == "itemRecovery":
                outReward = "Found Item"
            elif rewardType == "cookingRecipe":
                npcName = mailKey[0:-7]  # strip the "cooking" off the key
                # print(npcName)
                rewardList = []
                possibleRecipes = [idx for idx in cookingids if cookingids[idx].get("Source") == npcName]
                if len(possibleRecipes) > 0:
                    for recipeName in possibleRecipes:
                        rewardList.append(recipeName)
                        rewardIDs.append(recipeName)
                    outReward = "Recipe: " + " or ".join(rewardList)
                else:
                    outReward = "Cooking Recipe (see Description)"
            else:
                # print(inReward)
                outReward = inReward
                rewardType = None
        # print(outReward)
        if mode == "modded":
            outMail = {"Description": mail["Description"], "Reward": outReward, "RewardType": rewardType, "RewardIDs": rewardIDs}
        else:
            outMail = {"Description": mail["Description"], "Reward": outReward, "RewardType": rewardType, "RewardIDs": rewardIDs, "ModName": "Vanilla"}
        return outMail


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("../config.ini")
    targetdir = config["PATHS"]["mod_directory"]
    savedir = config["PATHS"]["stardew_save"]
    jsonpath = config["PATHS"]["project_root"] + "json/"
    errorlist = []

    gpreconditions = jsonData(jsonpath, "preconditions", "refs").data
    lbcids = jsonData(jsonpath, "bigobjects").data
    lclothingDict = jsonData(jsonpath, "apparel").data
    lcookingids = jsonData(jsonpath, "cooking").data
    lcraftingids = jsonData(jsonpath, "crafting").data
    lfurnids = jsonData(jsonpath, "furniture").data
    lmailIDs = jsonData(jsonpath, "mail").data
    lobjids = jsonData(jsonpath, "objects").data
    lquestids = jsonData(jsonpath, "quests").data
    lvanillaids = jsonData(jsonpath, "vanillaids", "vanilla").data
    lweaponDict = jsonData(jsonpath, "weapons").data
    maniList = jsonData(jsonpath, "manifests").data
    secretNotes = jsonData(jsonpath, "vanillasecretNotes", "refs").data

    # outMail = {}
    # processed = []

    # for key, mail in mailIDs.items():
    #     outMail[key] = parseMail(key, mail, vanillaids, cookingids, questids, bcids, furnids)
    #     # outDict = {"In": mail, "Out": outMail[key]}
    #     # processed.append(outDict)
    #

    # mfmOut = mailWalk(targetdir, maniList, errorlist)
    # mfmMail = mfmOut[0]
    # errorlist = mfmOut[1]
    # # pprint.pprint(mfmMail)
    #
    # mfmParsedOut = parseMFM(mfmMail, lvanillaids, lobjids, secretNotes, lmailIDs, gpreconditions, lcookingids, lcraftingids, lquestids, lbcids, lfurnids, lweaponDict, lclothingDict)
    # outMail = mfmParsedOut[0]
    # objList = mfmParsedOut[1]
    # ckrecipes = mfmParsedOut[2]
    # bcrecipes = mfmParsedOut[3]
    # questids = mfmParsedOut[4]
    # bcList = mfmParsedOut[5]
    # furnitureids = mfmParsedOut[6]
    # weaponDict = mfmParsedOut[7]
    # clothingDict = mfmParsedOut[8]

    mailToEvent = {}

    mailToOrder = {}

    mailToObjects(lmailIDs, mailToEvent, mailToOrder, lobjids, lbcids, lcookingids, lcraftingids, lfurnids, lweaponDict, lclothingDict)

    # output = pyjson5.dumps(outMail)
    # with open("../../json/mail-rebase-postmfm.json", "w") as outfile:
    #     outfile.write(output)
