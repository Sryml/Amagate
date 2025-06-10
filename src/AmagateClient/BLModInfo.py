####################################################################################
## BODLoader
####################################################################################

####################################################################################
# Global variables
####################################################################################

import string

global ModName
global ModDesc
global ModVersion
global ModAuthor
global ModAuthorInfo
global ModArenaMode
global NewFiles
global RepFiles
global MakeDirs

####################################################################################
# Mod Info
####################################################################################

# Mod Name
ModName = "Amagate Client"
# Mod Description
ModDesc = (
    """"""
)

# Multilanguage descriptions:

# if Language.Current == "Spanish":
#  ModDesc          = (
#                    """Spanish Description line 1\n"""
# 	            """Spanish Description line 2\n"""
# 	            """Spanish Description line 3\n"""
# 	             )
# else:
#  ModDesc          = (
#                    """Description line 1\n"""
# 	            """Description line 2\n"""
# 	            """Description line 3\n"""
# 	             )

# Mod Version
version = open("../../BODLoader/Mods/AmagateClient/version","r")
ModVersion = string.strip(version.read()) # type: ignore
version.close()
# Author name
ModAuthor = "Sryml"
# Author info: email, url,...
ModAuthorInfo = "sryml@hotmail.com"

####################################################################################
# Mod Data
####################################################################################

# Base dir for all paths: BOD\Maps\Casa

# Make new directories

# MakeDirs = ["../../Config/BLConfig/Amagate Client"]

# New Files added by Mod and destination directory

# NewFiles[0] = {"File": "File1.py", "Dest": "..\MapName"}

# Replaced Files
# RepFiles[1] = {"File": "Blade.exe", "Dest": "..\..\bin"}

# Setup to 1 for enable this mod in Arena mode
ModArenaMode = 0
