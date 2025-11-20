
<p><font size="3">This is the section that installs all the
mobiles in their various locations, equips the mobiles, locks and
closes any necessary doors, randomizes any random room exits, and
generally sets up the area and populates it.</font></p>

<p><font size="3">To reset an area, the server executes each
command in the list of reset commands once. Each area is reset
once when the server loads, and again periodically as it ages. An
area is reset if it is at least 3 area-minutes old and is empty
of players, or if it is 15 area-minutes old and has players in
it.</font></p>

<p><font size="3">An 'area-minute' varies between 30 and 90
seconds of real time, with an average of 60 seconds. The
variation defeats area time-keepers.</font></p>

<p><font size="3">The #RESETS section contains a series of single
lines.</font></p>

<p><font size="3">The reset commands are:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">* </font></td>
        <td><font size="2">comments (used for describing a line
        in resets or leaving notes to self/imms in area file) </font></td>
    </tr>
    <tr>
        <td><font size="2">D </font></td>
        <td><font size="2">sets state of a door </font></td>
    </tr>
    <tr>
        <td><font size="2">E </font></td>
        <td><font size="2">equipts object on mobile (wear/wield) </font></td>
    </tr>
    <tr>
        <td><font size="2">G </font></td>
        <td><font size="2">&quot;give&quot; an object to mobile
        (loads in inventory) </font></td>
    </tr>
    <tr>
        <td><font size="2">H</font></td>
        <td><font size="2">loads a mob in a container type
        object, like red and green tooth in mud school</font></td>
    </tr>
    <tr>
        <td><font size="2">M </font></td>
        <td><font size="2">load a mobile in a room</font></td>
    </tr>
    <tr>
        <td><font size="2">O </font></td>
        <td><font size="2">load an object in a room</font></td>
    </tr>
    <tr>
        <td><font size="2">P</font></td>
        <td><font size="2">put an object in a container object
        (gold in a safe, treasure in a chest, etc.)</font></td>
    </tr>
    <tr>
        <td><font size="2">R</font></td>
        <td><font size="2">randomize room exits like wander area
        in Shadow Grove or Sands of Sorrow</font></td>
    </tr>
    <tr>
        <td><font size="2">S</font></td>
        <td><font size="2">stop (Indicates end of reset section)</font></td>
    </tr>
</table>

<p><font size="3">Here is the format for the various reset
commands:</font></p>

<p><font size="3">D &lt;unused&gt; &lt;room-vnum&gt;
&lt;door-number&gt; &lt;state-number&gt;</font></p>

<p><font size="3">For the 'unused' value, simply put a '0'. The
room-vnum is the vnum of the room that the door IS IN. The
door-number is just that; i.e., 0=north, 1=west, 2=south, etc.
(see the help section for #ROOMS, above). The last number, the
'state-number', is the &quot;state&quot; of the door (whether it
is open, closed, locked, etc.). A listing for the 'state-number'
values is provided at the end of the #RESETS helps section. </font></p>

<p><font size="3">E &lt;number&gt; &lt;object-vnum&gt;
&lt;limit-number&gt; &lt;wear_loc-number&gt;</font></p>

<p><font size="3">The first number is the number (amount) of an
object equipped on the mobile. The object-vnum is just that. The
limit number is the same as in the 'G' command (see above). The
'wear_loc-number' is the wear location that the object is
equipped on the mobile's body. A listing of the wear_loc values
is given at the end of this #RESETS help section.</font></p>

<p><font size="3">G &lt;number&gt; &lt;object-vnum&gt;
&lt;limit-number&gt;</font></p>

<p><font size="3">For the 'G' command, there is no fourth number.
Only use three numbers. The 'G' command MUST follow an 'M'
command, as it 'gives' the object to the whatever mobile in a 'M'
command is above it. Note the reason for this is due to the fact
that no mobile-vnum is listed in the 'G' command. The first
number is the number (amount) of this particular object to be
given to the mobile. The object-vnum is the vnum of the object
given. The limit-number is the amount of times this object will
be 'given' to the mobile. I.E., the Calico cat from the Mage
Tower area of ROM2 (and other muds as well...) has a spiked
collar that is only loaded on the cat at the start of the game,
at a reboot. After that, the cat has no collar, until another
reboot. It is often a good idea to limit the number of objects in
this manner to be given or equipped on a mobile, unless the
object is relatively low level.</font></p>

<p><font size="3">H &lt;unused&gt; &lt;vnum object&gt; &lt;number
of mobs in it&gt; &lt;mob vnum&gt;</font></p>

<p><font size="3">For the H command, the item type you are
loading must be a bottle. It must also have a G type reset
(above) immediately after it.</font></p>

<p><font size="3">M &lt;unused&gt; &lt;mobile-vnum&gt;
&lt;limit-number&gt; &lt;room-vnum&gt;</font></p>

<p><font size="3">For the 'unused' value, simply put a '0'. The
mobile-vnum is the vnum of the mobile loaded. The limit-number is
the limit of how many of this mobile may be present in the world.
The last number, the room-vnum, is the vnum of the room where the
mobile is loaded. </font></p>

<p><font size="3">O &lt;unused&gt; &lt;object-vnum&gt;
&lt;limit-number&gt; &lt;room-vnum&gt;</font></p>

<p><font size="3">For the 'unused' value, simply put a '0'. The
object-vnum is the vnum of the object loaded. The limit-number is
the limit of how many of this object may be present in the world.
The last number, the room-vnum, is the vnum of the room where the
object is loaded.</font></p>

<p><font size="3">P &lt;number&gt; &lt;object-vnum&gt;
&lt;limit-number&gt; &lt;in_object-vnum&gt;</font></p>

<p><font size="3">The number is the number (amount) of the first
object that is placed into another object (i.e., a desk, coffer,
safe, etc.). The object-vnum is the vnum of the object loaded.
The limit-number is the limit of how many of these objects may be
present in the world, or 'put' into the other object. The game
will load a coffer, for example, a certain amount of times. After
that, the coffer will always be empty, until another reboot. The
last number, the 'in_object-vnum', is the vnum of the object into
which the other object is placed, i.e., the actual container
(safe, desk, etc.).</font></p>

<p><font size="3">R &lt;unused&gt; &lt;room-vnum&gt;
&lt;last_door-number&gt;</font></p>

<p><font size="3">For the 'R' command, there are only three
values, and the first value is always 0 as it is unused. The
second number is the vnum of a room. The third number is a
last_door-number. When this command is used, the doors from 0 to
the indicated 'last_door-number' are shuffled. The room will
still have the same exits leading to the same other rooms as
before, the DIRECTIONS will be different at each reboot. Thus, a
last_door-number of 4 makes a two-dimensional maze room; a door
number of 6 makes a three-dimensional maze room.</font></p>

<p><font size="3">Use of both the 'D' and 'R' commands on the
same room will yield UNPREDICTABLE results, so take care how you
utilize the 'R' command.</font></p>

<p><font size="3">Any line (except an 'S' line) may have a
comment at the end.</font></p>

<p><font size="3"><b>NOTES -</b> <b>IMPORTANT!</b></font></p>

<p><font size="3">End the #RESETS section in your area with an
'S' on the line after the last reset command, much the same as
you do for the #ROOMS section.</font></p>

<p><font size="3">For the 'P' command, the actual container used
is the MOST RECENTLY loaded object with the right vnum; for best
results, there should be only one such container in the world.
The is not loaded if no container object exists, or if someone is
carrying it, or if it already contains on of the to-be-loaded
objects.</font></p>

<p><font size="3">Remember, for all LIMIT-NUMBERS, a '-1' means
an infinite number of the objects, mobiles, etc. can exist in the
world, and the game will keep loading up these objects/mobiles
every reset. Keep this in mind, if you are thinking of using a
'-1' for a limit-number.</font></p>

<p><font size="3">For the 'E' and 'G' command, if the most recent
'M' command succeeded (e.g. the mobile limit wasn't exceeded),
the object is given to that mobile. If the most recent 'M'
command FAILED (due to hitting mobile limit), then the object is
not loaded.</font></p>

<p><font size="3">Also remember, EACH MOBILE in your area (not
just each type) must be loaded with the 'M' command. For example,
if you have 20 cityguards total wandering about your town, you
must do 20 reset lines of the 'M' command; for cityguard 1,
cityguard 2, cityguard 3, etc., through cityguard 20. You can see
how writing the #RESETS section of your area can rapidly become
tiresome, but try to take extra care with this section, as it is
easy to make a small typo, and these are a pain to debug if you
end up with numerous reset errors!</font></p>

<p><font size="3"><b>IMPORTANT!!</b>: For the 'D' command: ROOM
EXITS MUST BE COHERENT! If room 1 had an exit East going to room
2, and room 2 has an exit in the reverse direction (West), that
exit MUST GO BACK to room 1. This doesn't prevent one-way exits;
room 2 doesn't HAVE to have an exit in the reverse direction.</font></p>

<p><font size="3">EXAMPLE:</font></p>

<p><font size="3">Please note how each line has an explaination
to the right of it, and also note how nice and neatly its done.
This format makes it much easier for Soulcrusher to debug your
area if there is a problem. Areas submitted without using the
below format, will be sent back to author for correction.</font></p>

<p><font size="3">The following is an example of several of the
above reset commands as they appear in the area Dresden. Use
these to see how #RESETS works (note: this example, while taken
from the Dresden.are file #RESETS section, it is not in the same
order as in the actual file, as only a small part of that section
is represented below, just to give you an idea of the various
reset commands, and how they should appear):</font></p>

<table border="0">
    <tr>
        <td><font size="2">#RESETS </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">* Northern Dresden </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Comments are useful in keeping track
        of your reset commands. </font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ11 1 QQ01</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">The Watcher</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ05 1 16</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- wield scimitar</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ60 12 QQ04 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Cityguard 1</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ65 -1 0</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip banner</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ64 -1 1</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip signet ring</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ50 -1 16</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip sword</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ53 -1 5 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip vest</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ55 -1 4</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip cloak</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ60 12 QQ14</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Cityguard 2</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ65 -1 0</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip banner</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ64 -1 1</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip signet ring</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ50 -1 16</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip sword</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ53 -1 5</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip vest</font></td>
    </tr>
    <tr>
        <td><font size="2">E 1 QQ56 -1 6</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- equip helmet</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ64 3 QQ07</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">A Happy Drunk (at Inn)</font></td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ65 2 QQ44</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">A Beggar in poor alley</font></td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ65 2 QQ48</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">A Beggar in Grubby Inn</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ12 1 QQ54</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Healer at temple altar</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">M 0 QQ00 1 QQ06</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Maid in Park Cafe (Shopkeeper)</font></td>
    </tr>
    <tr>
        <td><font size="2">G 1 QQ00 -1</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- cup of tea</font></td>
    </tr>
    <tr>
        <td><font size="2">G 1 QQ01 -1</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- cup of coffee</font></td>
    </tr>
    <tr>
        <td><font size="2">G 1 QQ02 -1</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- cup of water</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">O 0 QQ35 1 QQ41</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">load dry Fountain on Penny Lane</font></td>
    </tr>
    <tr>
        <td><font size="2">P 0 QQ36 1 QQ41</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- put coins in fountain</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">O 0 QQ30 1 QQ42</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">load the desk</font></td>
    </tr>
    <tr>
        <td><font size="2">P 1 QQ23 1 QQ30</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- put brass key in desk</font></td>
    </tr>
    <tr>
        <td><font size="2">O 0 QQ31 1 QQ42</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">load the safe</font></td>
    </tr>
    <tr>
        <td><font size="2">P 1 QQ32 1 QQ31</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">- put cash in safe</font></td>
    </tr>
    <tr>
        <td>*</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">O 0 QQ10 1 QQ54</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">load Donation pit</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">D 0 QQ10 3 2</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Lock Captain's door from outside</font></td>
    </tr>
    <tr>
        <td><font size="2">D 0 QQ42 1 2</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Lock Captain's door from inside</font></td>
    </tr>
    <tr>
        <td><font size="2">D 0 QQ42 2 2</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Lock jail from outside</font></td>
    </tr>
    <tr>
        <td><font size="2">D 0 QQ43 0 2</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">Lock jail from inside</font></td>
    </tr>
    <tr>
        <td><font size="2">*</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">S</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">REMEMBER: end the #RESETS section with
        an 'S'.</font></td>
    </tr>
</table>

<p><font size="3"><b><u>Wear_location values for the 'E' reset
command</u></b>:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">WEAR_NONE </font></td>
        <td><font size="2">-1 </font></td>
        <td>Item is not worn by the mob *seldom used as being
        pointless* </td>
    </tr>
    <tr>
        <td><font size="2">WEAR_LIGHT</font></td>
        <td>0</td>
        <td>Item loads in mob's light slot, as in a torch</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_FINGER_L </font></td>
        <td>1 </td>
        <td>Item loads on mob's left finger, as in ruby ring</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_FINGER_R </font></td>
        <td>2 </td>
        <td>Item loads on mob's right finger, as in ruby ring</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_NECK_1</font></td>
        <td>3</td>
        <td>Item loads on mob's neck slot 1, as in spiked collar</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_NECK_2</font></td>
        <td>4</td>
        <td>Item loads on mob's neck slot 2, as in spiked collar</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_BODY</font></td>
        <td>5</td>
        <td>Item loads on mob's body, as in leather jerkin</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_HEAD</font></td>
        <td>6</td>
        <td>Item loads on mob's head, as in steel helmet</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_LEGS</font></td>
        <td>7</td>
        <td>Item loads on mob's legs, as in brass leggings</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_FEET</font></td>
        <td>8</td>
        <td>Item loads on mob's feet, as in boots</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_HANDS</font></td>
        <td>9</td>
        <td>Item loads on mob's hands, as in gloves</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_ARMS</font></td>
        <td>10</td>
        <td>Item loads on mob's arms, as in chain sleeves</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_SHIELD</font></td>
        <td>11</td>
        <td>Item loads in mob's shield slot</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_ABOUT</font></td>
        <td>12</td>
        <td>Item loads about mob, as in a cloak</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_WAIST</font></td>
        <td>13</td>
        <td>Item loads around mob's waist, as in a belt</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_WRIST_L</font></td>
        <td>14 </td>
        <td>Item loads on mob's left wrist, as in a leather
        bracer</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_WRIST_R</font></td>
        <td>15 </td>
        <td>Item loads on mob's right wrist, as in a leather
        bracer</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_WIELD</font></td>
        <td>16</td>
        <td>Item loads in mob's wield slot, as in a longsword</td>
    </tr>
    <tr>
        <td><font size="2">WEAR_HOLD</font></td>
        <td>17</td>
        <td>Item loads in mob's held slot, as in a mudschool
        diploma</td>
    </tr>
</table>

<p><a
href="http://www.ofchaos/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
<a href="http://www.ofchaos.com/Building/objects.html">#OBJECTS</a>
<a href="http://www.ofchaos.com/Building/rooms.html">#ROOMS</a>
<a href="http://www.ofchaos.com/Building/shops.html">#SHOPS</a>
<a href="http://www.ofchaos.com/Building/special.html">#SPECIALS</a></p>

<p><a
href="http://www.ofchaos.com/Building/spelslot.html"><font
color="#000000"><strong><u>Spell Slot Values</u></strong></font></a></p>

<p><a
href="http://www.ofchaos.com/Building/old_new_values.html"><font
color="#000000"><strong><u>Old Numeric to New Alpha Value
Conversion Table</u></strong></font></a></p>

<p><a
href="http://www.ofchaos.com/Building/hpchart.html"><strong><u>How
to assign HP and DAMDICE values to Mobs</u></strong></a></p>
</body>
</html>
