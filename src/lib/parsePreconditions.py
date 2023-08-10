import copy
import pyjson5
import sys
import traceback


def parsePreconditions(pc, key, secretNotes, mailIDs, vanillaids, gpreconditions):
    # takes individual pc string (separate at slashes before submitting)
    # returns dict
    # print("Hello")
    outPC = {"Code": "", "Condition": "", "Params": []}
    lPrec = copy.deepcopy(gpreconditions)
    pcItems = pc.strip().split(" ")
    # print(pcItems)
    param = ""
    # print("\n" + str(pcItems))
    # print(pcItems)
    # print(preconditions['e'])
    inverted = False
    # print(lPrec[pcItems[0]])
    try:
        if pcItems[0][0] == "!":
            pCode = pcItems[0][1:]
            inverted = True
        else:
            pCode = pcItems[0]
    except IndexError:
        print(key)
        print(pc)
        quit()
    if pCode not in lPrec:
        outPC["Code"] = "Custom Flag"
        outPC["Condition"] = pcItems[0].strip("{}")
        return outPC
    else:
        precondition = lPrec[pCode]
    outPC["Code"] = pCode
    multiParam = ["d", "e", "q", "u", "HasMod", "FarmHouseUpgradeLevel"]
    mailParam = ["*l", "*n", "Hl", "Hn", "l", "n"]
    itemParam = ["s", "HasItem"]
    if precondition["HasParams"]:
        if pCode in multiParam:
            param = str(", ".join(pcItems[1:]))
            outPC["Params"] = pcItems[1:]
            try:
                if inverted:
                    conditionString = precondition["Inverted"].format(
                        param)
                    outPC["Params"].append("inverted")
                else:
                    conditionString = precondition["Condition"].format(
                        param)
                outPC["Condition"] = conditionString
            except IndexError:
                print(key)
                print(param)
                quit()
        elif pCode == "i":  # item lookup
            if str(pcItems[1]) in vanillaids:
                param = vanillaids[str(pcItems[1])]["Name"]
            else:
                param = str(pcItems[1])
            outPC["Params"] = [param]
            if inverted:
                conditionString = precondition["Inverted"].format(
                    param)
                outPC["Params"].append("inverted")
            else:
                conditionString = precondition["Condition"].format(
                    param)
            outPC["Condition"] = conditionString
        elif pCode in itemParam:  # item lookup
            if str(pcItems[1]) in vanillaids:
                param = [pcItems[2],
                         vanillaids[str(pcItems[1])]["Name"]]
            else:
                param = [pcItems[2], pcItems[1]]
            outPC["Params"] = param
            if inverted:
                conditionString = precondition["Inverted"].format(
                    *tuple(param))
                outPC["Params"].append("inverted")
            else:
                conditionString = precondition["Condition"].format(
                    *tuple(param))
            outPC["Condition"] = conditionString
        elif pCode == "S":  # secret note
            if str(pcItems[1]) in secretNotes:
                param = str(pcItems[1]) + " (" + \
                    secretNotes[str(pcItems[1])] + ")"
            else:
                param = pcItems[1]
            outPC["Params"] = [
                pcItems[1], secretNotes[str(pcItems[1])]]
            if inverted:
                conditionString = precondition["Inverted"].format(
                    param)
                outPC["Params"].append("inverted")
            else:
                conditionString = precondition["Condition"].format(
                    param)
            outPC["Condition"] = conditionString
        elif pCode == "y":  # year
            outPC["Params"] = [pcItems[1]]
            if inverted:
                if int(pcItems[1]) == 1:
                    conditionString = "After First Year"
                elif int(pcItems[1]) > 1:
                    conditionString = "Year is not " + str(pcItems[1]) + " or later"
                outPC["Params"].append("inverted")
            else:
                if int(pcItems[1]) == 1:
                    conditionString = "First Year Only"
                elif int(pcItems[1]) > 1:
                    conditionString = "Year " + str(pcItems[1]) + " or later"
            outPC["Condition"] = conditionString
        elif pCode == "f":  # friendship
            outPC["Params"] = pcItems[1:]
            fnpcs = pcItems[1::2]
            heartpts = pcItems[2::2]
            hearts = []
            for ptval in heartpts:
                hearts.append(int(int(ptval) / 250))
            cStrings = []
            for idx, fnpc in enumerate(fnpcs):
                cString = str(hearts[idx]) + " heart(s) with " + fnpcs[idx]
                cStrings.append(cString)
            if inverted:
                conditionString = "Player friendship levels are less than "
                outPC["Params"].append("inverted")
            else:
                conditionString = "Player friendship levels are at least "
            conditionString += ", ".join(cStrings)
            outPC["Condition"] = conditionString
        elif pCode == "SkillLevel":
            skills = pcItems[1::2]
            levels = pcItems[2::2]
            skillStrings = []
            outPC["Params"] = []
            for idx, skill in enumerate(skills):
                outPC["Params"].append([skill, levels[idx]])
                if inverted:
                    skillStrings.append(skills[idx].title() + " skill level below " + str(levels[idx]))
                    outPC["Params"].append("inverted")
                else:
                    skillStrings.append(skills[idx].title() + " skill level at least " + str(levels[idx]))
            outPC["Condition"] = ", ".join(skillStrings)
        elif pCode in mailParam:
            # mail condition doubles as flag condition. If it isn't in mail, it's a flag
            mailstring = " ".join(pcItems[1:])
            if str(mailstring) in mailIDs:
                param = str(mailstring) + " (" + \
                    str(mailIDs[mailstring]["Description"]) + ")"
                outPC["Params"] = [mailstring, param]
            else:
                if pCode == "x":
                    outPC["Condition"] = "Mark event seen and send letter {} tomorrow morning."
                elif inverted:
                    outPC["Condition"] = "Player has not set flag {}"
                else:
                    outPC["Condition"] = "Player has set flag {}"
                param = str(mailstring)
                outPC["Params"] = [param]
            if inverted:
                conditionString = precondition["Inverted"].format(
                    param)
                outPC["Params"].append("inverted")
            else:
                conditionString = precondition["Condition"].format(
                    param)
            outPC["Condition"] = conditionString
        elif pCode == "NPCAt":
            outPC["Params"] = pcItems[1:]
            xvals = pcItems[2::2]
            yvals = pcItems[3::2]
            coordStrings = []
            for idx, xval in enumerate(xvals):
                coordStrings.append("X " + xval + ", Y " + yvals[idx])
            if inverted:
                conditionString = pcItems[1] + " is not at " + ", ".join(coordStrings)
                outPC["Params"].append("inverted")
            else:
                conditionString = pcItems[1] + " is at " + ", ".join(coordStrings)
            outPC["Condition"] = conditionString
        elif pCode == "HasToolLevel":
            outPC["Params"] = pcItems[1:]
            if int(pcItems[1]) == 0:
                outString = "Basic"
            elif int(pcItems[1]) == 1:
                outString = "Copper"
            elif int(pcItems[1]) == 2:
                outString = "Iron"
            elif int(pcItems[1]) == 3:
                outString = "Gold"
            elif int(pcItems[1]) == 4:
                outString = "Iridium"
            if inverted:
                conditionString = "Player does not have a tool of at most " + outString + " in inventory"
            else:
                conditionString = "Player has a tool of at most " + outString + " in inventory"
            outPC["Condition"] = conditionString
        elif pCode == "SaveStatEval":
            outPC["Params"] = [" ".join(pcItems[1:])]
            if inverted:
                conditionString = "Savegame Stat equation '" + outPC["Params"][0] + "' evals to False"
                outPC["Params"].append("inverted")
            else:
                conditionString = "Savegame Stat equation '" + outPC["Params"][0] + "' evals to True"
            outPC["Condition"] = conditionString
        elif pCode == "HasItems":
            outPC["Params"] = [pcItems[1], " ".join(pcItems[2:])]
            if inverted:
                conditionString = "Player does not have at least " + str(pcItems[1]) + " " + " ".join(pcItems[2:]) + " in inventory"
                outPC["Params"].append("inverted")
            else:
                conditionString = "Player has at least " + str(pcItems[1]) + " " + " ".join(pcItems[2:]) + " in inventory"
            outPC["Condition"] = conditionString
        elif pCode in ["HasCookingRecipe", "HasCraftingRecipe"]:
            if pCode == "HasCookingRecipe":
                thiscat = "Cooking"
            else:
                thiscat = "Crafting"
            outPC["Params"] = [" ".join(pcItems[1:]).replace("-", " ")]
            if inverted:
                conditionString = "Player has not unlocked " + thiscat + " Recipe " + " ".join(pcItems[1:]).replace("-", " ")
                outPC["Params"].append("inverted")
            else:
                conditionString = "Player has unlocked " + thiscat + " Recipe " + " ".join(pcItems[1:]).replace("-", " ")
            outPC["Condition"] = conditionString
        else:
            try:
                param = pcItems[1:]
                outPC["Params"] = param
                # print(param)
                if inverted:
                    conditionString = precondition["Inverted"].format(
                        *tuple(param))
                    outPC["Params"].append("inverted")
                else:
                    conditionString = precondition["Condition"].format(
                        *tuple(param))
                outPC["Condition"] = conditionString
            except IndexError:
                print(key)
                print(param)
                quit()
        return outPC
        # print(conditionString)
        # print(param)
    else:  # HasParams == False
        conditionString = precondition["Condition"]
        outPC["Condition"] = conditionString
        outPC["Code"] = pCode
        outPC["Params"] = []
        return outPC
    # outPC["Condition"] = conditionString
    # print(outPC)
    # print("Full List: " + str(preconditionList))


if __name__ == "__main__":
    import configparser
    sys.path.append("..")
    from cls.data import Data as jsonData

    config = configparser.ConfigParser()
    config.read("../config.ini")
    jsonpath = config["PATHS"]["project_root"] + "json/"
    errorlist = []

    vanillaids = jsonData(jsonpath, "vanillaids", "vanilla").data
    gpreconditions = jsonData(jsonpath, "preconditions", "refs").data
