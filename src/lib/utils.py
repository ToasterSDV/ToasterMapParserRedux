"""
Utilities
"""
from datetime import datetime
import os

import pyjson5


def errorsOut(errorlist, method, logpath):
    configerrors = []
    conflicts = []
    modbugs = []
    fordev = []
    courtesy = []
    outText = ""
    for error in errorlist:
        if error.startswith("Mod Bug:"):
            modbugs.append(error[9:])
        if error.startswith("For Dev:") or error.startswith("Traceback:"):
            fordev.append(error.split(":", 1)[1])
        if error.startswith("Config Alert:"):
            configerrors.append(error[14:])
        if error.startswith("Conflict Alert:"):
            conflicts.append(error[16:])
        if error.startswith("Courtesy Notice:"):
            courtesy.append(error[17:])
    if configerrors:
        outText += "\nConfig Errors:"
        for ce in configerrors:
            for splitlog in logsplitter(ce):
                outText += "\n\t" + splitlog
    if conflicts:
        outText += "\nMod Conflicts:"
        for cf in conflicts:
            for splitlog in logsplitter(cf):
                outText += "\n\t" + splitlog
    if modbugs:
        outText += "\nMod Bugs:"
        for mb in modbugs:
            for splitlog in logsplitter(mb):
                outText += "\n\t" + splitlog
    if courtesy:
        outText += "\nCourtesy Notices:"
        for cn in courtesy:
            for splitlog in logsplitter(cn):
                outText += "\n\t" + splitlog
    if fordev:
        outText += "\nPlease notify the app dev about the following bugs:"
        for fd in fordev:
            for splitlog in logsplitter(fd):
                outText += "\n\t" + splitlog
    ct = datetime.now()
    datestring = ct.strftime("%Y%m%d%H%M%S")
    filename = "log-" + datestring
    filepath = os.path.join(logpath, filename)
    with open(filepath, "w") as outfile:
        outfile.write(outText)
    print("Errors logged to " + filepath + "\n")
    if method == "verbose":
        print("The following errors were found:")
        print(outText)


def logsplitter(logstring):
    # splits logs into 40 char chunks
    termsize = os.get_terminal_size()
    maxwidth = int(termsize.columns) - 10
    logParts = logstring.split(" ")
    logOut = []
    str = ""
    for part in logParts:
        if len(str) + len(part) < maxwidth:
            str += part + " "
        else:
            logOut.append(str)
            str = ""
            str += part + " "
    if str:
        logOut.append(str)
    return logOut


def writeJson(data, filename, path, subpath=None):
    output = pyjson5.dumps(data)
    if subpath:
        path += subpath + "/"
    path += filename + ".json"
    with open(path, "w") as outfile:
        outfile.write(output)


if __name__ == "__main__":
    import configparser
    config = configparser.ConfigParser()
    config.read("../config.ini")
    jsonpath = config["PATHS"]["project_root"] + "json/"
