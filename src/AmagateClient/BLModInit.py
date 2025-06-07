####################################################################################
## BODLoader Mod Init File
####################################################################################

# Mod imports

import Bladex
import Reference
import GameText

# Translations

import Language
import MenuText

import sys
import os

#
PACKAGE = "AmagateClient"
sys.path.append("../../BODLoader/Mods")

#####################
m_name = "%s.Scripts" % PACKAGE
if sys.modules.get(m_name):
    del sys.modules[m_name]

for f_name in os.listdir("../../BODLoader/Mods/AmagateClient/Scripts"):
    m_name = "%s.Scripts.%s" % (PACKAGE, os.path.splitext(f_name)[0])
    if sys.modules.get(m_name):
        del sys.modules[m_name]

from AmagateClient.Scripts import AmagateMenu

global ModMenu
ModMenu = AmagateMenu.ModMenu
#####################

# sys.path.remove("../../BODLoader/Mods")
