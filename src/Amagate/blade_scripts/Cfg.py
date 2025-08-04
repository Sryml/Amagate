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

original_texture = (
    "../../3dobjs/3dObjs.mmp",
    "../../3dobjs/bolarayos.mmp",
    "../../3dobjs/CilindroMagico.mmp",
    "../../3dobjs/CilindroMagico2.mmp",
    "../../3dobjs/CilindroMagico3.mmp",
    "../../3dobjs/conos.mmp",
    "../../3dobjs/dalblade.mmp",
    "../../3dobjs/esferagemaazul.mmp",
    "../../3dobjs/esferagemaroja.mmp",
    "../../3dobjs/esferagemaverde.mmp",
    "../../3dobjs/esferanegra.mmp",
    "../../3dobjs/esferaorbital.mmp",
    "../../3dobjs/espectro.mmp",
    "../../3dobjs/firering.mmp",
    "../../3dobjs/genericos.mmp",
    "../../3dobjs/halfmoontrail.mmp",
    "../../3dobjs/luzdivina.mmp",
    "../../3dobjs/magicshield.mmp",
    "../../3dobjs/nube.mmp",
    "../../3dobjs/objetos_p.mmp",
    "../../3dobjs/ondaexpansiva.mmp",
    "../../3dobjs/Pfern.mmp",
    "../../3dobjs/pmiguel.mmp",
    "../../3dobjs/rail.mmp",
    "../../3dobjs/telaranya.mmp",
    "../../3dobjs/vortice.mmp",
    "../../3dobjs/weapons.mmp",
    #
    "../../3dchars/Actors.mmp",
    "../../3dchars/actors_javi.mmp",
    "../../3dchars/Amz.mmp",
    "../../3dchars/Amzskin1.mmp",
    "../../3dchars/Amzskin2.mmp",
    "../../3dchars/Bar.mmp",
    "../../3dchars/Barskin1.mmp",
    "../../3dchars/Barskin2.mmp",
    "../../3dchars/Chk.mmp",
    "../../3dchars/cosita.mmp",
    "../../3dchars/Crow.mmp",
    "../../3dchars/DalGurak.mmp",
    "../../3dchars/DarkKnight.mmp",
    "../../3dchars/darklord.mmp",
    "../../3dchars/Dork.mmp",
    "../../3dchars/dwf.mmp",
    "../../3dchars/Dwfskin1.mmp",
    "../../3dchars/Dwfskin2.mmp",
    "../../3dchars/enanos.mmp",
    "../../3dchars/Gdemon.mmp",
    "../../3dchars/Glm_cl.mmp",
    "../../3dchars/Glm_ic.mmp",
    "../../3dchars/Glm_lv.mmp",
    "../../3dchars/Glm_mt.mmp",
    "../../3dchars/Glm_st.mmp",
    "../../3dchars/Gok.mmp",
    "../../3dchars/Kgt.mmp",
    "../../3dchars/Kgtskin1.mmp",
    "../../3dchars/Kgtskin2.mmp",
    "../../3dchars/lch.mmp",
    "../../3dchars/Ldm.mmp",
    "../../3dchars/min.mmp",
    "../../3dchars/NPK.mmp",
    "../../3dchars/Org.mmp",
    "../../3dchars/ork.mmp",
    "../../3dchars/rgn.mmp",
    "../../3dchars/roturas.mmp",
    "../../3dchars/Skl.mmp",
    "../../3dchars/Slm.mmp",
    "../../3dchars/spd.mmp",
    "../../3dchars/TKN.mmp",
    "../../3dchars/trl_dk.mmp",
    "../../3dchars/trl_SN.mmp",
    "../../3dchars/Vmp.mmp",
    "../../3dchars/wyv.mmp",
    "../../3dchars/zkn.mmp",
)
for f in original_texture:
    BBLib.ReadMMP(f)


Bladex.LoadWorld(AG_MapCfg["bw_file"])
#
execfile("../../Scripts/BladeInit.py")

#
execfile("AG_Script.py")
execfile("AG_Objs.py")
