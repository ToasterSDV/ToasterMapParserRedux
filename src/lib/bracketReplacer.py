import re
import pyjson5
import traceback


def bracketReplacer(node, configs, dynos, i18n, mode="entries"):
    globaltokens = ["day", "dayevent", "dayofweek", "daysplayed", "season",
                    "time", "weather", "year", "dailyluck", "farmhouseupgrade",
                    "hasactivequest", "hascaughtfish", "hasconversationtopic",
                    "hascookingrecipe", "hascraftingrecipe", "hasdialogueanswer",
                    "hasflag", "hasprofession", "hasreadletter", "hasseenevent",
                    "haswalletitem", "ismainplayer", "isoutdoors",
                    "locationcontext", "locationname", "locationuniquename",
                    "locationownerid", "playergender", "playername",
                    "preferredpet", "skilllevel", "childnames", "childgenders",
                    "hearts", "relationship", "roommate", "spouse", "farmcave",
                    "farmname", "farmtype", "iscommunitycentercomplete",
                    "isjojamartcomplete", "havingchild", "pregnant"]

    def findBracketReplacement(match):
        group = match.group(1)
        # print(group)
        dynoSearch = list(filter(None, [value if value["Name"].lower() == group.lower() else '' for value in dynos]))
        if group.startswith("i18n:"):
            searchString = group[5:]
            # print(searchString)
            if "[SMAPI:" in searchString:
                result = "(Custom Token)"
            else:
                try:
                    result = i18n[searchString]
                except KeyError:
                    result = "(Missing Translation)"
        elif group.lower().startswith("random:"):
            groupOptions = group[7:].split(",")
            result = groupOptions[0].strip()
        elif group.lower().startswith("range"):
            result = group[6:].split(",")[0]
        elif group.lower().startswith("query"):
            # for now our only queries are "Query: [SMAPI:RSVInstallDay] + N"
            reEndDigits = r".*?([0-9]*?)$"
            result = re.sub(reEndDigits, r"\1", group)
        elif group.lower().startswith("spacechase0.jsonassets"):
            # Json assets
            groupParts = group.split(":")
            result = groupParts[1].replace(" ", "_")
        elif "/" in group:
            # custom token, must come after Json Assets test
            groupParts = group.split("/")
            result = "[SMAPI:" + groupParts[1] + "]"
        elif group.lower() in globaltokens:
            result = "[" + group + "]"
        elif len(dynoSearch) > 0:
            result = dynoSearch[0]["Value"]
        elif group in configs:
            result = configs[group]["value"]
        elif group.lower().startswith("target"):
            if group.lower() == "target":
                result = nodeTarget
            else:
                targetParts = nodeTarget.split("/")
                if group.lower() == "targetpathonly":
                    result = targetParts[0]
                else:  # targetwithoutpath
                    result = targetParts[1]
        else:
            print("I don't know what to do with " + group)
            quit()
        result = result.replace('"', '\\"').replace('\n', '')
        return result

    def findBracketReplacementWhen(match):
        group = match.group(1)
        # print(group)
        dynoSearch = list(filter(None, [value if value["Name"].lower() == group.lower() else '' for value in dynos]))
        if group.startswith("i18n:"):
            searchString = group[5:]
            # print(searchString)
            if "[SMAPI:" in searchString:
                result = "(Custom Token)"
            else:
                try:
                    result = i18n[searchString]
                except KeyError:
                    result = "(Missing Translation)"
        elif group.lower().startswith("random:"):
            groupOptions = group[7:].split(",")
            result = groupOptions[0].strip()
        elif group.lower().startswith("range"):
            result = group[6:].split(",")[0]
        elif group.lower().startswith("query"):
            # for now our only queries are "Query: [SMAPI:RSVInstallDay] + N"
            reEndDigits = r".*?([0-9]*?)$"
            result = re.sub(reEndDigits, r"\1", group)
        elif group.lower().startswith("spacechase0.jsonassets"):
            # Json assets
            groupParts = group.split(":")
            result = groupParts[1].replace(" ", "_")
        elif "/" in group:
            # custom token, must come after Json Assets test
            groupParts = group.split("/")
            result = "[SMAPI:" + groupParts[1] + "]"
        elif group.lower() in globaltokens:
            result = "[" + group + "]"
        elif len(dynoSearch) > 0:
            result = dynoSearch[0]["Value"]
        elif group in configs:
            result = configs[group]["value"]
        elif group.lower().startswith("target"):
            if group.lower() == "target":
                result = nodeTarget
            else:
                targetParts = nodeTarget.split("/")
                if group.lower() == "targetpathonly":
                    result = targetParts[0]
                else:  # targetwithoutpath
                    result = targetParts[1]
        else:
            print("I don't know what to do with " + group)
            quit()
        result = result.replace('"', '\\"').replace('\n', '')
        return result

    def findBracketReplacementFiles(match):
        group = match.group(1)
        # print(group)
        dynoSearch = list(filter(None, [value if value["Name"].lower() == group.lower() else '' for value in dynos]))
        if group.lower() == "season":
            result = "spring"
        elif group.lower().startswith("random:"):
            groupOptions = group[7:].split(",")
            result = groupOptions[0].strip()
        elif group in configs:
            print(group)
            result = configs[group][0]["value"]
        elif len(dynoSearch) > 0:
            # print(dynoSearch[0]["Value"])
            result = dynoSearch[0]["Value"]
        else:
            print("I don't know what to do with " + group)
            quit()
        result = result.replace('"', '\\"').replace('\n', '')
        return result

    reInnerMost = r"{{([^{]*?)}}"
    if mode != "filenames" and isinstance(node, dict):
        nodeTarget = node["Target"]
    if "Entries" in node and mode == "entries":
        newEntries = {}
        oldKeys = []
        for key, value in node["Entries"].items():
            # print("\nKeyStart:" + key)
            oldKeys.append(key)
            newkey = key
            while re.search(reInnerMost, newkey):
                newkey = re.sub(reInnerMost, findBracketReplacement, newkey)
            # print("KeyEnd: " + newkey)
            nodestring = pyjson5.dumps(value)
            # print("\nValstart: " + nodestring)
            while re.search(reInnerMost, nodestring):
                nodestring = re.sub(reInnerMost, findBracketReplacement, nodestring)
            # print("Nodestring out: " + nodestring)
            newvalue = pyjson5.loads(nodestring)
            newEntries[newkey] = newvalue
        for oldKey in oldKeys:
            del node["Entries"][oldKey]
        for newKey, newVal in newEntries.items():
            node["Entries"][newKey] = newVal
    elif "When" in node and mode == "whens":
        newWhens = {}
        oldKeys = []
        for key, value in node["When"].items():
            oldKeys.append(key)
            newkey = key
            while re.search(reInnerMost, newkey):
                newkey = re.sub(reInnerMost, findBracketReplacementWhen, newkey)
            # print("KeyEnd: " + newkey)
            nodestring = pyjson5.dumps(value)
            # print("\nValstart: " + nodestring)
            while re.search(reInnerMost, nodestring):
                nodestring = re.sub(reInnerMost, findBracketReplacementWhen, nodestring)
            # print("Nodestring out: " + nodestring)
            newvalue = pyjson5.loads(nodestring)
            newWhens[newkey] = newvalue
        for oldKey in oldKeys:
            del node["When"][oldKey]
        for newKey, newVal in newWhens.items():
            node["When"][newKey] = newVal
    elif mode == "filenames" and isinstance(node, str):
        while re.search(reInnerMost, node):
            node = re.sub(reInnerMost, findBracketReplacementFiles, node)

    # print(node)
    # quit()
    return node
