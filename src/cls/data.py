"""
Defines all our Data Dicts
"""
import os
import pyjson5
import pprint


class Data:
    def __init__(self, jsonpath, filename, subdir=""):
        if not jsonpath.endswith("/"):
            path = jsonpath + "/"
        else:
            path = jsonpath
        if subdir:
            path += subdir + "/"
        path += filename + ".json"
        if os.path.isfile(path):
            self.data = pyjson5.load(open(path, encoding="utf-8"))


if __name__ == "__main__":
    ljsonpath = "../../json/"
    hatdata = Data(ljsonpath, "achievementHats", "refs")
    pprint.pprint(hatdata.data)
