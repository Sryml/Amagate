import os
import string

import Basic_Funcs
import ItemTypes
import Actions
import Bladex


char = Bladex.CreateEntity("Player1", "Knight_N", 0, 0, 0, "Person")
char.Position = mapcfg["player_pos"]
# char.Angle=2.37
char.Level = 19
char.SetOnFloor()
# char.SetMesh("KgtSkin1")

char.SendTriggerSectorMsgs = 1
char.Data = Basic_Funcs.PlayerPerson(char)
char.Data.FAttack = 1.1

inv = char.GetInventory()

o = Bladex.CreateEntity("InvPrb1", "Gladius", 0, 0, 0, "Weapon")
ItemTypes.ItemDefaultFuncs(o)
Actions.TakeObject(char.Name, o.Name)


#

o = Bladex.CreateEntity("BowInvPrb1", "Arco", 0, 0, 0, "Weapon")
ItemTypes.ItemDefaultFuncs(o)
inv.AddBow(o.Name)


o = Bladex.CreateEntity("QuiverInvPrb1", "Carcaj", 0, 0, 0)
ItemTypes.ItemDefaultFuncs(o)
inv.AddQuiver(o.Name)
