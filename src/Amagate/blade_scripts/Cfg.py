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
    "../../3dchars/3dObjs.mmp",
    "../../3dchars/bolarayos.mmp",
    "../../3dchars/CilindroMagico.mmp",
    "../../3dchars/CilindroMagico2.mmp",
    "../../3dchars/CilindroMagico3.mmp",
    "../../3dchars/conos.mmp",
    "../../3dchars/dalblade.mmp",
    "../../3dchars/esferagemaazul.mmp",
    "../../3dchars/esferagemaroja.mmp",
    "../../3dchars/esferagemaverde.mmp",
    "../../3dchars/esferanegra.mmp",
    "../../3dchars/esferaorbital.mmp",
    "../../3dchars/espectro.mmp",
    "../../3dchars/firering.mmp",
    "../../3dchars/genericos.mmp",
    "../../3dchars/halfmoontrail.mmp",
    "../../3dchars/luzdivina.mmp",
    "../../3dchars/magicshield.mmp",
    "../../3dchars/nube.mmp",
    "../../3dchars/objetos_p.mmp",
    "../../3dchars/ondaexpansiva.mmp",
    "../../3dchars/Pfern.mmp",
    "../../3dchars/pmiguel.mmp",
    "../../3dchars/rail.mmp",
    "../../3dchars/telaranya.mmp",
    "../../3dchars/vortice.mmp",
    "../../3dchars/weapons.mmp",
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
