"""
Test stripping nested dict to only keys with values
"""
import pprint
import pyjson5


def stripWhens(nodeDict):
    # can pass either a full node or just a When
    if "When" in nodeDict:
        thisWhen = nodeDict["When"]
    else:
        thisWhen = nodeDict

    canIgnore = True

    unnestedkeys = ["config", "dynamic", "instant", "static", "unknownkeys", "preconditions"]  # preconditions only in mfm Whens
    nestedkeys = ["extant", "query", "saveBased"]
    ignorablekeys = ["config", "static", "hasmod", "hasfile"]
    occupiedkeys = []

    delkeys = []
    if "saveBased" in thisWhen and "player" in thisWhen["saveBased"]:
        for k, v in thisWhen["saveBased"]['player'].items():
            if not v:
                delkeys.append(k)
            else:
                # print("Cannot ignore due to saveBased key")
                canIgnore = False
                keystring = "saveBased|player|" + k
                occupiedkeys.append(keystring)
        for dk in delkeys:
            del thisWhen["saveBased"]["player"][dk]

    delkeys = []
    if "query" in thisWhen:
        for k, v in thisWhen["query"].items():
            if not v:
                delkeys.append(k)
            else:
                if k not in ignorablekeys:
                    # print("Cannot ignore due to " + k + " in query")
                    canIgnore = False
                soughtkeys = []
                for sV in v:
                    soughtkeys.append(sV["Sought"])
                skstring = "|".join(soughtkeys)
                keystring = "query|" + k + "|" + skstring
                occupiedkeys.append(keystring)
    for dk in delkeys:
        del thisWhen["query"][dk]

    for uK in unnestedkeys:
        if uK in thisWhen and not thisWhen[uK]:
            del thisWhen[uK]
        elif uK in thisWhen:
            if uK not in ignorablekeys:
                # print("Cannot ignore due to " + uK + " in unnestedkeys")
                canIgnore = False
            for sK in thisWhen[uK]:
                keystring = uK + "|" + str(sK)
                occupiedkeys.append(keystring)

    for nK in nestedkeys:
        delkeys = []
        if nK in thisWhen:
            for sK, sV in thisWhen[nK].items():
                if not sV:
                    delkeys.append(sK)
                elif sK != "player":
                    if nK not in ignorablekeys:
                        # print("Cannot ignore due to " + nK + " in nestedkeys")
                        canIgnore = False
                    keystring = nK + "|" + sK
                    occupiedkeys.append(keystring)
            for dK in delkeys:
                del thisWhen[nK][dK]

    for nK in nestedkeys:
        if nK in thisWhen and not thisWhen[nK]:
            del thisWhen[nK]

    if "skip" in thisWhen and not thisWhen["skip"]:
        del thisWhen["skip"]
    elif "skip" in thisWhen:
        occupiedkeys.append("skip")
        canIgnore = False
    # print(occupiedkeys)
    if canIgnore:
        thisWhen["ignore"] = True
    else:
        thisWhen["ignore"] = False
    return [thisWhen, occupiedkeys]


if __name__ == "__main__":
    testdict = {"When": {'static': {'hasmod': [{'Positive': ['lemurkat.eastscarpe.ja']}]}, 'saveBased': {'calculated': {}, 'locations': {}, 'player': {'mailReceived': [], 'friendshipData': {}}}, 'instant': {}, 'dynamic': {}, 'config': {}, 'extant': {'config': [], 'saveBased': [], 'instant': [], 'dynamic': [], 'smapi': []}, 'query': {'config': [], 'saveBased': [], 'instant': [], 'dynamic': [], 'smapi': [], 'misc': [], 'static': []}, 'skip': False, 'unknownkeys': []}}
    newWhen = stripWhens(testdict)
    pprint.pprint(newWhen)
