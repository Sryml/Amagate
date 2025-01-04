import Bladex
import LoadBar
import os
import string

LoadBar.ECTSProgressBar(100, "Blade_progress.jpg")


# Delete Player info when loading after playing main maps.

Bladex.DeleteStringValue("MainChar")

############################

for i in ("Pak/BODPak.dat", "Pak/pf.pak"):
    if os.path.exists(i):
        os.remove(i)


execfile("../../Scripts/sys_init.py")
#
execfile("mapcfg.py")

for f in os.listdir("textures"):
    name, ext = os.path.splitext(f)
    if string.lower(ext) == ".bmp":
        Bladex.ReadBitMap("textures/" + f, name)

Bladex.LoadWorld(mapcfg["bw_file"])
#
execfile("../../Scripts/BladeInit.py")
