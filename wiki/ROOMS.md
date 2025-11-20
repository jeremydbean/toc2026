
<p><font size="3">This section should be fairly self-explanatory.
Here is an example of a room from the #ROOMS section of an area:</font></p>

<p><font size="3">#QQ00</font><br>
<font size="3">Rock Carving~</font><br>
<font size="3">You scramble through this mountain pass, the
frightening stony walls</font><br>
<font size="3">reaching to the sky on either side of you. A
powerful, eerie wind whips</font><br>
<font size="3">the air into a frenzy about you. Cut into the rock
face is an imposing,</font><br>
<font size="3">monolithic statue of a long forgotten king. You
feel a sudden sense of</font><br>
<font size="3">uneasiness as you pass beneath his glowering,
silent gaze. Ahead, to the</font><br>
<font size="3">north, an immense set of iron gates block further
passage. The pass leads</font><br>
<font size="3">north beyond the gates, and back to the south.</font><br>
<font size="3">~</font><br>
<font size="3">QQ 0 5</font><br>
<br>
<font size="3">D0</font><br>
<font size="3">A pass through tall iron gates.</font><br>
<font size="3">gates~</font><br>
<font size="3">~</font><br>
<font size="3">2 -1 QQ01</font><br>
<font size="3">D2</font><br>
<font size="3">A pass through the mountains.</font><br>
<font size="3">~</font><br>
<font size="3">~</font><br>
<font size="3">0 -1 QQ02</font><br>
<font size="3">E</font><br>
<font size="3">statue~</font><br>
<font size="3">This impressive statue is a depiction of the
ancient king, and now</font><br>
<font size="3">awesomely powerful God, Ozymandias. Bold of gaze
and fierce</font><br>
<font size="3">of stature, this being is one you'd NOT like to
cross if you ran</font><br>
<font size="3">into him. Brrr!</font><br>
<font size="3">~</font><br>
<font size="3">S</font><br>
<br>
<font size="3">#QQ01</font><br>
And so on...</p>

<p><font size="4">And now for the explanation of each line:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">#QQ00 </font></td>
        <td><font size="2">This is the room's VNUM</font></td>
    </tr>
    <tr>
        <td><font size="2">Rock Carving~ </font></td>
        <td><font size="2">The room's name </font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">You scramble through this
        mountain pass, the frightening stony walls</font><br>
        <font size="2">reaching to the sky on either side of you.
        A powerful, eerie wind whips</font><br>
        <font size="2">the air into a frenzy about you. Cut into
        the rock face is an imposing,</font><br>
        <font size="2">monolithic statue of a long forgotten
        king. You feel a sudden sense of</font><br>
        <font size="2">uneasiness as you pass beneath his
        glowering, silent gaze. Ahead, to the</font><br>
        <font size="2">north, an immense set of iron gates block
        further passage. The pass leads</font><br>
        <font size="2">north beyond the gates, and back to the
        south.</font></td>
        <td valign="top"><font size="2">The room's description. </font></td>
    </tr>
    <tr>
        <td>~</td>
        <td><font size="2">a tilde on a separate line</font></td>
    </tr>
    <tr>
        <td><font size="2">QQ 0 5</font></td>
        <td><font size="2">&lt;first 2 numbers of the area
        number&gt; &lt;room-flags&gt; &lt;sector-type&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">D0</font></td>
        <td><font size="2">&lt;exit marker &amp; direction exit
        is in&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">A pass through tall, iron gates.</font></td>
        <td><font size="2">&lt;exit description&gt; What you
        would see if you type exit</font></td>
    </tr>
    <tr>
        <td><font size="2">gate~</font></td>
        <td><font size="2">&lt;door (if there is one) keyword&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">~</font></td>
        <td><font size="2">&lt;tilde or secret name ending with
        tilde if door is secret&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">2 QQ00 QQ01</font></td>
        <td><font size="2">&lt;locks-number&gt;
        &lt;key-number&gt; &lt;to_room-number&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">D2</font></td>
        <td><font size="2">&lt;next door number, and so on...&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">A pass through the mountains.</font></td>
        <td><font size="2">&lt;next exit desc...&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">~</font></td>
        <td><font size="2">&lt;door (if there is one) keyword&gt;
        Here its just a doorless exit.</font></td>
    </tr>
    <tr>
        <td><font size="2">~</font></td>
        <td><font size="2">&lt;tilde or secret name ending with
        tilde if door is secret&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">0 -1 QQ02</font></td>
        <td><font size="2">&lt;next lock-num.&gt; &lt;next
        key-num.&gt; &lt;next to_room-num.&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">E</font></td>
        <td><font size="2">&lt;extended description section&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">statue~</font><br>
        <font size="2">This impressive statue is a depiction of
        the ancient king, and</font> <font size="2">now</font><br>
        <font size="2">awesomely powerful God, Ozymandias. Bold
        of gaze and</font> <font size="2">fierce</font><br>
        <font size="2">of stature, this being is one you'd NOT
        like to cross if</font> <font size="2">you ran</font><br>
        <font size="2">you ran into him. Brrrr...</font></td>
        <td valign="top"><font size="2">&lt;extended desc.
        keywords followed by tilde and the description&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">~</font></td>
        <td><font size="2">a tilde on a separate line</font></td>
    </tr>
    <tr>
        <td><font size="2">S</font></td>
        <td><font size="2">&lt;the 'S' marks the end of the room.
        It is NOT optional.&gt;</font></td>
    </tr>
    <tr>
        <td><font size="2">#QQ01</font></td>
        <td><font size="2">&lt;next room vnum, and so on...&gt;</font></td>
    </tr>
</table>

<p><font size="3">The 'room vnum' is the virtual number of the
room.</font></p>

<p><font size="3">The 'room name' is the name of the room.</font></p>

<p><font size="3">The 'room description' is the long multi-line
description of the room.</font></p>

<p><font size="3">The 'area number' is unused at the moment, but
will later be used for exploding items in specific area's. Make
sure that the area number remains the same if the rooms are
considered in the area.</font></p>

<p><font size="3">The 'ROOM-FLAGS' describe more attributes of
the room, and a listing of possible FLAGS is given at the end of
the #ROOMS help section in this file.</font></p>

<p><font size="3">The 'SECTOR-TYPE' identifies the type of
terrain. This affects movement cost through the room. Certain
sector types (AIR and WATER) require special capabilities to
enter, i.e., a flying potion or spell for air, and a boat or raft
for water.</font></p>

<p><font size="3">The 'tport' data only needs to be placed when a
room is defined as being a tport room in the ROOM_FLAGS section.
Not sure how long increased values are in real time length, but
will soon. Last part for this section, if value is a 1, PC will
do an autolook when moved, else if 0, will not.</font></p>

<p><font size="3">Unlike mobiles and objects, rooms don't have
any keywords associated with them. One may not manipulate a room
in the same way one manipulates a mobile or object.</font></p>

<p><font size="3">The optional 'D' sections and 'E' sections come
after the main data. A 'D' section contains one or more 'doors'
in the range from 0 to 5. The numbers represent the 6 possible
directions. These direction values are given at the end of this
#ROOMS section. A 'D' command also contains a 'description' for
that direction, and 'keywords' for manipulating the door. 'Doors'
include not just real doors, but ANY kind of exit from the room.
The 'locks-number' defines whether or not the door is locked or
not, and if it can be picked or not. The values for the
'locks-numbers' is given at the end of the #ROOMS section. The
'key- number' is the vnum of an object which locks and unlocks
the door. IMPORTANT: If there is NO key for opening the door,
either because the door is unlocked, is a simple, unhindered
exit, or because you want a locked door with no key in the game,
use '-1' for the 'key-number', NOT a '0'. Lastly,
'to_room-number' is the vnum of the room to which this door
leads.</font></p>

<p><font size="3">Unless you want a one-way exit, you must
specify two 'D' sections, one for each side of the door; i.e.,
one leaving one room and one in the other room the door goes to.
Otherwise, you will end up with a one-way exit.</font></p>

<p><font size="3">An 'E' section (extended description) contains
a 'keywords' string and a 'description' string. As you might
guess, looking at one of the words in the 'keywords' yields the
'description' string.</font></p>

<p><font size="3">The 'S' at the end marks the end of the room. <strong>IT
IS NOT OPTIONAL</strong>. This is where most new builders mess up
most often, causing me many hours of searching for the error when
the area fails to boot up with the game. It is probably one of
the most difficult errors to find when debugging an area.</font></p>

<p><font size="3"><b>IMPORTANT</b>!! When your #ROOMS sections is
complete, to end the #ROOMS section, you must put '#0' on the
line after the 'S' line of the last room in the #ROOMS section of
your area.</font></p>

<p><font size="3"><b><u>Direction Values for the 'D' section</u></b></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td>North </td>
        <td>0 </td>
    </tr>
    <tr>
        <td>East</td>
        <td>1 </td>
    </tr>
    <tr>
        <td>South </td>
        <td>2 </td>
    </tr>
    <tr>
        <td>West </td>
        <td>3 </td>
    </tr>
    <tr>
        <td>Up</td>
        <td>4</td>
    </tr>
    <tr>
        <td>Down </td>
        <td>5 </td>
    </tr>
    <tr>
        <td>Northeast </td>
        <td>6 </td>
    </tr>
    <tr>
        <td>Northwest </td>
        <td>7</td>
    </tr>
    <tr>
        <td>Southeast </td>
        <td>8</td>
    </tr>
    <tr>
        <td>Southwest </td>
        <td>9 </td>
    </tr>
</table>

<p><font size="3"><b><u>Door Type Values for the 'D' section</u></b></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">EX_ISDOOR </font></td>
        <td>1 </td>
    </tr>
    <tr>
        <td><font size="2">EX_LOCKED </font></td>
        <td>2 </td>
    </tr>
    <tr>
        <td><font size="2">EX_PICKPROOF </font></td>
        <td>3 </td>
    </tr>
    <tr>
        <td><font size="2">EX_SECRET</font></td>
        <td>4 </td>
    </tr>
    <tr>
        <td><font size="2">EX_WIZLOCKED </font></td>
        <td>5 </td>
    </tr>
    <tr>
        <td><font size="2">EX_TRAPPED</font></td>
        <td>6</td>
    </tr>
</table>

<p>&nbsp;</p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2"><b><u>ROOM-FLAGS</u></b> </font></td>
        <td><font size="2"><b><u>FLAG</u></b> </font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_DARK</font></td>
        <td>A</td>
        <td><font size="2">Must have a light to see in this room </font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_NO_MOB </font></td>
        <td>C</td>
        <td><font size="2">Mobiles cannot move into this room.
        Used to create buffer zones between areas, or safe points
        to rest. </font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_INDOORS</font></td>
        <td>D</td>
        <td><font size="2">Room is indoors and immune to most
        types of weather.</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_RIVER</font></td>
        <td>E</td>
        <td><font size="2">Room is a river, acts as a tport,
        &quot;pushing&quot; player along to next room</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_TELEPORT </font></td>
        <td>F</td>
        <td><font size="2">Room is teleport room. Transports
        player to designated room after number of ticks
        specified.</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_AFF_BY</font></td>
        <td><font size="2">H</font></td>
        <td><font size="2">Room is affected by a defined room
        affect <strong>*see below*</strong></font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">ROOM_DEATHTRAP </font></td>
        <td>I</td>
        <td><font size="2">Room is a deathtrap, instantly killing
        all in the room. Entrances to this room should include
        hints that they lead to a deathtrap room. <strong>This
        flag is to be used sparingly and only with permission!</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_PRIVATE</font></td>
        <td>J</td>
        <td><font size="2">Room may only be occupied by 2 players
        or mobs at a time. Normally would include NO_MOB flag as
        well.</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_SAFE</font></td>
        <td><font size="2">K</font></td>
        <td><font size="2">Room is no fighting zone. <strong>This
        flag is to be used sparingly and only with permission!</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_SOLITARY</font></td>
        <td><font size="2">L</font></td>
        <td><font size="2">Room may only be occupied by 1 player
        or mob at a time. Normally would include NO_MOB flag as
        well.</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_PET_SHOP</font></td>
        <td><font size="2">M</font></td>
        <td><font size="2">Room is designated a pet shop. <strong>This
        flag is to be used only with permission!</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_NO_RECALL </font></td>
        <td><font size="2">N</font></td>
        <td><font size="2">Room is no recall room. Players may
        not recall, cast word of recall, nor recite recall scroll
        from within this room.</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_SILENT</font></td>
        <td><font size="2">X</font></td>
        <td><font size="2">Room is silent (no spells may be
        cast).</font></td>
    </tr>
    <tr>
        <td><font size="2">ROOM_FLAGS2</font></td>
        <td><font size="2">Z</font></td>
        <td><font size="2">Tells game that ROOM_FLAGS2 are to
        follow</font></td>
    </tr>
</table>

<p><font size="3"><strong>NOTE</strong>: When using ROOM_AFF_BY
flag (H), you must follow the below format:</font></p>

<p><font size="2">#QQ00</font><br>
<font size="2">The Fire Chamber~</font><br>
<font size="2">The fire ruler sits upon a throne made of blue
flame. Little flickers of</font><br>
<font size="2">flame dance to and fro for the entertainment of
the ruler.</font><br>
<font size="2">~</font><br>
<font size="2">QQ H 3</font><br>
<font size="2">3 20 0 0 0 0 0 3 8</font> &lt;============ See
explaination below for this line<br>
<font size="2">D1</font><br>
<font size="2">~</font><br>
<font size="2">~</font><br>
<font size="2">0 -1 QQ01</font><br>
<br>
<font size="2">S</font><br>
</p>

<p>Explaination:<br>
<font size="2">&lt;type&gt; &lt;level&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt; &lt;unused&gt;
&lt;dam dice&gt; &lt;dam number&gt;</font><br>
<br>
Types:<br>
<font size="2">STINKING_CLOUD 1</font> <font size="2">&lt;poisons
all pc's in room and makes them choke and gag&gt;</font><br>
<font size="2">VOLCANIC 3 &lt;flame/heat damage to all pc&#146;s
in room&gt;</font><br>
<font size="2">SHOCKER 4 &lt;electrical damage to all pc&#146;s
in room&gt;</font><br>
<br>
&lt;level&gt; is the level a player must be to enter the room. In
the example above, room is AFF_BY VOLCANIC, players must be level
20 or above to enter, &lt;dam dice&gt; in the example is a 3
sided die or values 1-3, and &lt;dam number&gt; is the number of
3 sided die that are rolled.. so, the max damage per tick done in
this particular room would be 24 (3x8=24).<br>
<br>
<font size="2"><b><u>ROOM_FLAGS2</u></b></font></p>

<p>*None at this time*</p>

<p><font size="2"><b><u>SECTOR-TYPES</u></b></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">SECT_INSIDE </font></td>
        <td>0 </td>
        <td><font size="2">Room is in a building. Immune from
        most weather. </font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_CITY</font></td>
        <td>1</td>
        <td><font size="2">Room is on city streets. Minimal
        endurance is used.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_FIELD</font></td>
        <td>2</td>
        <td><font size="2">Room is field type terrain. Little
        endurance is used.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_FOREST </font></td>
        <td>3</td>
        <td><font size="2">Room is forest type terrain. Slightly
        more endurance is used.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_HILLS</font></td>
        <td>4</td>
        <td><font size="2">Room is hilly terrain. Higher amount
        of endurance is used.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_MOUNTAIN </font></td>
        <td>5</td>
        <td><font size="2">Room is mountainous. Much endurance is
        used.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_WATER_SWIM </font></td>
        <td>6</td>
        <td><font size="2">Room is water, but players can cross
        without boat.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_WATER_NOSWIM </font></td>
        <td>7</td>
        <td><font size="2">Room is water, players need a boat to
        cross.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_UNDER_WATER</font></td>
        <td>8 </td>
        <td><font size="2">Room is below water. Players need
        scuba gear to breathe, or suffer water damage. (drowning)
        </font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_AIR</font></td>
        <td>9</td>
        <td><font size="2">Room is in the air. Players need to be
        flying to enter/move.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_DESERT</font></td>
        <td>10 </td>
        <td><font size="2">Room is desert terrain. Thirsty
        quicker. Uses more endurance.</font></td>
    </tr>
    <tr>
        <td><font size="2">SECT_UNDERGROUND</font></td>
        <td>11</td>
        <td><font size="2">Room is underground as in caves and
        caverns. Immune from most types of weather.</font></td>
    </tr>
</table>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
<a href="http://www.ofchaos.com/Building/objects.html">#OBJECTS</a>
<a href="http://www.ofchaos.com/Building/resets.html">#RESETS</a>
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
