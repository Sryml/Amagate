# Author: Sryml
# Email: sryml@hotmail.com
# Python Version: 1.5
# License: MIT

import os
import sys
import shutil
import string

#
import Bladex
import Console
import Menu
import MenuText
import BUIx
import Raster
import MenuWidget
import ScorerWidgets
import BBLib
import BCopy
import Reference
import Language
import MemPersistence
import BODLoader

#
from AmagateClient.Scripts import ag_client

#
MenuFontSmall = Language.LetrasMenuSmall
MenuFontMed = Language.LetrasMenu
MenuFontBig = Language.LetrasMenuBig


############################
KEY = ag_client.KEY

MOD_PATH = "../../BODLoader/Mods/AmagateClient/"
MENU_LOGO_FILE = (
    MOD_PATH + "Amagate.png",
    "AmagateLogo",
)
Bladex.ReadBitMap(MENU_LOGO_FILE[0], MENU_LOGO_FILE[1])


############################
def InitConnectedStatus(target):
    if Bladex.GetStringValue(KEY):
        target.Text = "Status: Connected"
        target.Color = BODLoader.B_MenuColor.Green
    else:
        target.Text = "Status: Not connected"
        target.Color = BODLoader.B_MenuColor.Red


def CMD_Connect(target):
    ag_client.connect_server(
        callback=InitConnectedStatus,
        callback_args=(BODLoader.GetMenuWidget("ConnectedStatus"),),
    )
    InitConnectedStatus(BODLoader.GetMenuWidget("ConnectedStatus"))


def CMD_Disconnect(target):
    ag_client.disconnect_server(
        callback=InitConnectedStatus,
        callback_args=(BODLoader.GetMenuWidget("ConnectedStatus"),),
    )


############################
class M_B_LogoWidget(BUIx.B_RectWidget):
    def __init__(self, Parent, MenuDescr, StackMenu):
        LogoFile = MenuDescr["LogoFile"]
        # self.Bitmap = {}

        logo = BBLib.B_BitMap24()
        logo.ReadFromFile(LogoFile[0])

        self.vidw, self.vidh = MenuDescr.get("Size", logo.GetDimension())
        GetScale = MenuDescr.get("Scale", 1.0)
        self.vidw, self.vidh = self.vidw * GetScale, self.vidh * GetScale
        BUIx.B_RectWidget.__init__(
            self, Parent, MenuDescr["Name"], self.vidw, self.vidh
        )
        # self.Selected = 0
        # self.Solid = 0
        # self.Border = 0
        # self.SetBorder(1)
        self.SetSolid(1)
        self.SetColor(255, 255, 255)
        self.SetAlpha(1)
        self.SetVisible(1)

        self.SetBitmap(LogoFile[1])
        # self.SetAutoScale(1)
        # self.SetDrawFunc(self.Draw)

    def Draw(self, x, y, time):
        Raster.SetPosition(x, y)
        Raster.DrawImage(self.vidw, self.vidh, "RGB", "Normal", self.Logobmp.GetData())
        self.DefDraw(x, y, time)

    def FinalRelease(self):
        BUIx.B_RectWidget.FinalRelease(self)

    def AcceptsFocus(self):
        return 0


############################

ModMenu = [
    {
        "Name": "MENU_LOGO",
        "Kind": M_B_LogoWidget,
        "VSep": 10,  # 0
        "LogoFile": MENU_LOGO_FILE,
        "Scale": 0.2,
    },
    {
        "Name": "ConnectedStatus",
        # "Text": "[Status: Not connected]",
        "Focusable": 0,
        "Kind": BODLoader.B_MenuItemTextNoFX,
        "VSep": "1em",
        "FontScale": BODLoader.FontScale["M"],
        "PostInitCommand": InitConnectedStatus,
    },
    {
        "Name": MenuText.GetMenuText("Connect"),
        "VSep": "2em",
        "FontScale": BODLoader.FontScale["M"],
        "Command": CMD_Connect,
        "Kind": BODLoader.B_MenuItemTextNoFX,
    },
    {
        "Name": MenuText.GetMenuText("Disconnect"),
        "VSep": "0.5em",
        "FontScale": BODLoader.FontScale["M"],
        "Command": CMD_Disconnect,
        "Kind": BODLoader.B_MenuItemTextNoFX,
    },
    #
    {
        "Name": MenuText.GetMenuText("BACK"),
        "FontScale": BODLoader.FontScale["M"],
        "VSep": "3em",
        "Command": Menu.BackMenu,
        "Kind": BODLoader.B_MenuItemTextNoFX,
    },
    {"Name": "Back", "Kind": MenuWidget.B_BackBlank},
]
