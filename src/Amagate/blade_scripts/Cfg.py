import Bladex
import LoadBar
import os
import string
import BBLib

LoadBar.ECTSProgressBar(100, "Blade_progress.jpg")


# Delete Player info when loading after playing main maps.

Bladex.DeleteStringValue("MainChar")

############################

for i in ("Pak/BODPak.dat", "Pak/pf.pak"):
    if os.path.exists(i):
        os.remove(i)


execfile("../../Scripts/sys_init.py")

Bladex.ReadLevel("AG_dome.lvl")
#
execfile("AG_MapCfg.py")

for f in os.listdir("textures"):
    name, ext = os.path.splitext(f)
    if string.lower(ext) == ".bmp":  # type: ignore
        Bladex.ReadBitMap("textures/" + f, name)

general_texture = (
    "../../3dobjs/3dobjs.mmp",
    "../../3dobjs/genericos.mmp",
    "../../3dobjs/weapons.mmp",
    "../../3dobjs/objetos_p.mmp",
)
for f in general_texture:
    BBLib.ReadMMP(f)


Bladex.LoadWorld(AG_MapCfg["bw_file"])
#
execfile("../../Scripts/BladeInit.py")

#
execfile("AG_Script.py")
