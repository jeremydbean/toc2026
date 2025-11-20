
<p align="left"><font size="3"><strong><u>Definitions</u></strong></font></p>

<table border="2">
    <tr>
        <td><font size="2">VNUM </font></td>
        <td><font size="3">The virtual number of the mobile,
        object, or room.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">KEYWORDS </font></td>
        <td><font size="3">The words which can be used in
        commands to identify mobiles or objects when looking at,
        attacking,</font><br>
        <font size="3">getting, wearing, etc.</font></td>
    </tr>
    <tr>
        <td><font size="2">SHORT DESCRIPTION</font></td>
        <td><font size="3">The description used to identify the
        mobile, or object when they are intereacted with.</font></td>
    </tr>
    <tr>
        <td><font size="2">LONG DESCRIPTION</font></td>
        <td><font size="3">The description used when a character
        walks in the room and the mobile or object is visible.</font></td>
    </tr>
    <tr>
        <td><font size="2">DESCRIPTION</font></td>
        <td><font size="3">The description is used when a
        character explicitly looks at the mobile or object.</font></td>
    </tr>
    <tr>
        <td><font size="2">ACT FLAGS</font></td>
        <td><font size="3">They define how a mobile acts.</font></td>
    </tr>
    <tr>
        <td><font size="2">AFFECTED_BY FLAGS</font></td>
        <td><font size="3">These generally define what the mobile
        is 'affected' by. Therefore the affected_by flag of
        AFF_BLIND for</font><br>
        <font size="3">example means that this particular mobile
        will be blind, and <strong>NOT</strong> that the mobile
        casts a blindness spell.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">ALIGNMENT</font></td>
        <td><font size="3">This ranges from -1000 to 1000, the
        higher being good, the lower being evil, with '0' being
        true neutral. Keep in mind that certain spells
        ('protection' and 'dispel evil') give characters fighting
        evil monsters anadvantage, and that experience earned is
        influenced by alignment. The frequency of &quot;Pure
        Good&quot; or &quot;Pure</font> <font size="3">Evil&quot;
        beings should be VERY rare, with only the
        &quot;Boss&quot; mob and maybe one or two of its minions
        being</font> <font size="3">of a &quot;pure&quot; or
        &quot;near pure&quot; alignment. So I would ask that you
        keep the majority of your mobs within the -500 to 500
        range.</font></td>
    </tr>
    <tr>
        <td><font size="2">LEVEL</font></td>
        <td><font size="3">Typically a number from 1 to 59,
        although there is no upper limit.</font></td>
    </tr>
</table>

<p><font size="3">O.K., here where it gets to be more confusing.
First of all, let me provide an example of what part of the
#MOBILES section may look like, by providing an example of a
mobile, and then by following with the syntax explanation of each
line:</font></p>

<p><font size="3">#MOBILES</font><br>
<font size="3">#QQ01</font><br>
<font size="3">prisoner amazon~</font><br>
<font size="3">an amazon prisoner~</font><br>
<font size="3">An amazon prisoner rests here in shackles.</font><br>
<font size="3">~</font><br>
<font size="3">You see a tall, beautiful female warrior in
glittering armor.</font><br>
<font size="3">~</font><br>
<font size="3">human~</font><br>
<font size="3">BT N 850 S</font><br>
<font size="3">35 3 1d1+749 1d1+297 12d4+10 5</font><br>
<font size="3">-5 -5 -5 0</font><br>
<font size="3">EDFHIKLNU 0 0 0</font><br>
<font size="3">8 8 2 0</font><br>
<font size="3">0 0 M 0</font><br>
<br>
<font size="3">#QQ02 THIS BEGINS THE NEXT MOBILE, AND SO ON....</font><br>
<br>
<font size="3">Explanation of each line:</font></p>

<table border="2">
    <tr>
        <td><font size="2">#MOBILES </font></td>
        <td><font size="2">the beginning of the mobile section.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">#QQ01</font></td>
        <td><font size="2">mobile-vnum that is unique to this
        mobile. Use QQ unless </font><a
        href="mailto:trinidad@iglou.com"><font size="2">Trinidad</font></a><font
        size="2"> has given you a set of</font><br>
        <font size="2">VNUMs to work with already.</font></td>
    </tr>
    <tr>
        <td><font size="2">prisoner amazon~ </font></td>
        <td><font size="2">the keywords for the mobile</font></td>
    </tr>
    <tr>
        <td><font size="2">an amazon prisoner~</font></td>
        <td><font size="2">the short description (what you see
        when the mob acts)</font></td>
    </tr>
    <tr>
        <td><font size="2">An amazon prisoner rests here in
        shackles. </font></td>
        <td><font size="2">the long desc (what you see when you
        enter a room)</font></td>
    </tr>
    <tr>
        <td><font size="2">~</font></td>
        <td><font size="2">put the tilde for the long desc. on
        the next line, like so.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">BT N 850 S</font></td>
        <td><font size="2"><strong>&lt;ACT FLAGS&gt;
        &lt;Affected_by&gt; &lt;Align.&gt; &lt;S&gt;</strong></font><br>
        <font size="2">(<strong>Note:</strong> <strong>ALWAYS</strong>
        end this above line with acapital 'S'after the alignment
        number, as is shown</font><br>
        <font size="2">here. In the original Diku mob format,
        'S'stands for simple.</font> <font size="2">Merc supports
        only simple mobs,</font><br>
        <font size="2">so the 'S' is redundant, but ROM</font> <font
        size="2">supports both simple (S) and</font> <font
        size="2">modified (M) mobs. It is</font><br>
        <font size="2">retained not only for compatibility</font>
        <font size="2">with the Diku format, but also because</font>
        <font size="2">it helps the</font><br>
        <font size="2">server report errors more accurately.</font><br>
        <font size="2">Don't create M type mobs unless you have
        much</font> <font size="2">experience with them.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">35 3 1d1+749 1d1+297
        12d4+10 5</font></td>
        <td><font size="2"><strong>&lt;level of mobile&gt;
        &lt;bonus hitroll&gt; &lt;hit points&gt; &lt;mana&gt;
        &lt;damage&gt;&lt;DAMAGE TYPE&gt;</strong></font><br>
        <font size="2">(<strong>NOTE</strong>: DAMAGE TYPE is the
        natural damage type, not the damage type inflicted when </font><br>
        <font size="2">wielding a weapon)</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">-5 -5 -5 0</font></td>
        <td><font size="2">Armor Class (AC) values for <strong>&lt;piercing&gt;
        &lt;bashing&gt; &lt;slashing&gt; &lt;magic&gt;</strong>.</font><br>
        <font size="2"><strong>NOTE!!:</strong> A common
        misconception is that these values you install in this
        line</font><br>
        <font size="2">will be the mob's TOTAL ACs for the 4 AC
        values. This is not so. The Merc</font><br>
        <font size="2">code automatically calculates an AC value
        based on the level of the mobile. It</font><br>
        <font size="2">then ADDS what you put in this line to the
        calculated value for a total. So, if you</font><br>
        <font size="2">were to have a level 50 mobile with an AC
        line like: 0 0 0 0, for the 4 values,</font><br>
        <font size="2">the mobile would still have a good AC from
        the level of the mobile and the</font><br>
        <font size="2">Merc code. Use this line for giving a
        mobile addition AC bonuses to be added</font><br>
        <font size="2">to its inherent AC. Therefore, these
        amazon prisoners will NOT have AC</font><br>
        <font size="2">values of -5 -5 -5 and 0 total, but rather
        a value calculated from the mobile level</font><br>
        <font size="2">of 35 with these -5s ADDED to that for a
        total AC for each of the 4 values.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">EDFHIKLNU 0 0 0</font></td>
        <td><font size="2"><strong>&lt;Off_bits&gt;
        &lt;Immunities&gt; &lt;Resistances&gt;
        &lt;vulnerabilities&gt;</strong></font><br>
        <font size="2">A list of the Off_bits, and the
        immunities, resistances and vulnerabilities is at</font><br>
        <font size="2">the end of this section, as well as
        listings of the Affected_by and ACT bits of</font><br>
        <font size="2">above. The 'Off_bits' are composed of the
        'skills' that the mobile has, as well as</font><br>
        <font size="2">whether or not this mobile will assist
        other mobiles of the same vnum,</font><br>
        <font size="2">alignment, etc. In the case here, with
        this amazon mobile having DFHIKLNU,</font><br>
        <font size="2">as you will see by looking up these values
        below, gives this mobile the</font><br>
        <font size="2">following skills: Disarm, Berserk, Dodge,
        Fast, Kick, Parry, Rescue, Trip, and</font><br>
        <font size="2">Assist_vnum. A nice combination for a
        warrior-type mobile, over all.</font><br>
        <font size="2">This amazon mobile also, as can be seen by
        the three '0's, has no particular</font><br>
        <font size="2">immunities or vulnerabilities.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">8 8 2 0</font></td>
        <td><font size="2"><strong>&lt;normal position&gt;
        &lt;current position&gt; &lt;sex &gt; &lt;gold&gt;</strong></font><br>
        <font size="2">The position numbers most commonly used
        are the 8 8 combination, which</font><br>
        <font size="2">means the mobile is normally standing,
        rather than sitting, sleeping, etc. A</font><br>
        <font size="2">listing of all the position values is
        given at the end of this section, with the</font><br>
        <font size="2">other value listings. The last value is
        the gold that the mobile has in its</font><br>
        <font size="2">possession. As this particular example is
        an amazon &#145;prisoner', I elected to</font><br>
        <font size="2">make the amazon poor...as prisoners rarely
        have money. =)</font><br>
        <strong>NOTE: Do NOT go nuts with gold, gold should be
        VERY hard to come by!</strong></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">0 0 M 0</font></td>
        <td><font size="2">The first two numbers and the last
        number are always zeros, ('0's), as they</font><br>
        <font size="2">represent part-types (brains, legs, guts,
        tail, arms, heart, etc.) for when they die,</font><br>
        <font size="2">and other values that are now taken care
        of by the Merc code. Most of this is</font><br>
        <font size="2">calculated based on the 'race' of the
        mobile, from one of the earlier lines. So</font><br>
        <font size="2">just simply use zeros for these three
        values. The 'M' represents the SIZE of the</font><br>
        <font size="2">mobile.</font></td>
    </tr>
</table>

<p><font size="2"><b><u>MOBILE VALUE CHART</u></b></font></p>

<p><font size="3">Now here are the listings of all the necessary
values for making your mobiles; the flags will be on the left,
and the letter and old number values you use are on the right
column.( <strong>NOTE:</strong> The old number values are only
provided for help in maybe converting an old Merc or Diku area
you wrote at one time. <strong>DO NOT USE THE OLD NUMBER VALUE</strong>
in your area, <strong>USE THE LETTER VALUE</strong>):</font></p>

<table border="2">
    <tr>
        <td><font size="2"><b><u>ACT FLAGS</u></b><b> </b></font></td>
        <td><font size="2"><b><u>FLAG</u></b><b> </b></font></td>
        <td><font size="2"><b><u>OLD</u></b></font> <font
        size="2"><b><u>VALUE</u></b><b> </b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_IS_NPC </font></td>
        <td><font size="3">A</font></td>
        <td><font size="3">1</font></td>
        <td><font size="3">autoset for mobs by the code</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_SENTINEL </font></td>
        <td><font size="3">B</font></td>
        <td><font size="3">2</font></td>
        <td><font size="3">stays in one room, never able to move</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_SCAVENGER </font></td>
        <td><font size="3">C</font></td>
        <td><font size="3">4</font></td>
        <td><font size="3">picks up objects</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_IS_HEALER </font></td>
        <td><font size="3">D</font></td>
        <td><font size="3">8</font></td>
        <td><font size="3">acts as a healer <strong>*USE ONLY
        WITH PERMISSION*</strong></font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_GAIN </font></td>
        <td><font size="3">E</font></td>
        <td><font size="3">16</font></td>
        <td><font size="3">can use 'gain' at this mobile <strong>*USE
        ONLY WITH PERMISSION*</strong></font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_AGGRESSIVE </font></td>
        <td><font size="3">F</font></td>
        <td><font size="3">32</font></td>
        <td><font size="3">attacks player's characters</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_STAY_AREA </font></td>
        <td><font size="3">G</font></td>
        <td><font size="3">64</font></td>
        <td><font size="3">mob is confined to its own area</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_WIMPY </font></td>
        <td><font size="3">H</font></td>
        <td><font size="3">128</font></td>
        <td><font size="3">will flee if hp gets too low</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_PET</font></td>
        <td><font size="3">I</font></td>
        <td><font size="3">256</font></td>
        <td><font size="3">autoset for pets by the code</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_TRAIN </font></td>
        <td><font size="3">J</font></td>
        <td><font size="3">512</font></td>
        <td><font size="3">can train PC's <strong>*USE ONLY WITH
        PERMISSION*</strong></font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_PRACTICE</font></td>
        <td><font size="3">K</font></td>
        <td><font size="3">1024</font></td>
        <td><font size="3">can practice PC's <strong>*USE ONLY
        WITH PERMISSION*</strong></font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_UPDATE_ALWAYS </font></td>
        <td><font size="3">L</font></td>
        <td><font size="3">2048</font></td>
        <td><font size="3">mob always resets</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_NOPUSH</font></td>
        <td><font size="3">M</font></td>
        <td><font size="3">4096</font></td>
        <td><font size="3">mob cannot be shoved</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_UNDEAD</font></td>
        <td><font size="3">O</font></td>
        <td><font size="3">16384</font></td>
        <td><font size="3">mob has basic undead skills</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_CLERIC</font></td>
        <td>Q</td>
        <td>65536</td>
        <td><font size="3">mob has basic cleric skills</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_MAGE</font></td>
        <td>R</td>
        <td>131072</td>
        <td><font size="3">mob has basic mage skills</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_THIEF</font></td>
        <td>S</td>
        <td>262144</td>
        <td>mob has basic thief skills (i.e., steal)</td>
    </tr>
    <tr>
        <td><font size="3">ACT_WARRIOR</font></td>
        <td>T</td>
        <td>524288</td>
        <td><font size="3">mob has basic warrior skills</font></td>
    </tr>
    <tr>
        <td><font size="3">ACT_NOALIGN</font></td>
        <td>U</td>
        <td>1048576</td>
        <td>doesn't affect players alignment when killed (<strong>use
        sparingly</strong>)</td>
    </tr>
    <tr>
        <td><font size="3">ACT_NOPURGE</font></td>
        <td>V</td>
        <td>2091752</td>
        <td>mob cannot be purged with Immortal purge command</td>
    </tr>
    <tr>
        <td><font size="3">ACT_MOUNTABLE </font></td>
        <td>W</td>
        <td>&nbsp;</td>
        <td>mob may be ridden</td>
    </tr>
    <tr>
        <td><font size="3">ACT_NOKILL</font></td>
        <td>X</td>
        <td>&nbsp;</td>
        <td>mob vanishes if player tries to kill it (charmies)</td>
    </tr>
    <tr>
        <td><font size="3">ACT_FLAGS2</font></td>
        <td>Z</td>
        <td>&nbsp;</td>
        <td><font size="3">informs game that act_flags2 are to
        follow</font></td>
    </tr>
</table>

<p>&nbsp;</p>

<table border="2">
    <tr>
        <td><font size="3"><strong><u>ACT_FLAGS2</u></strong><strong>
        </strong></font></td>
        <td><strong><u>FLAGS</u></strong><strong> </strong></td>
        <td><strong><u>DESCRIPTION</u></strong></td>
    </tr>
    <tr>
        <td><strong>*None yet implemented </strong></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
</table>

<p><font size="3"><b><u>RACES</u></b></font></p>

<p><font size="3">Here are some common races; remember, the race
you pick for the mobile does not have to reflect what the mobile
is. You can have an Ogre mobile with a race of human, elf, etc.
More races can be defined or deleted as deemed necessary.</font></p>

<table border="2" cellpadding="0" cellspacing="20">
    <tr>
        <td><font size="1">bat </font></td>
        <td><font size="2">elf </font></td>
        <td><font size="2">hobgoblin </font></td>
        <td><font size="2">plant </font></td>
        <td><font size="2">undead </font></td>
    </tr>
    <tr>
        <td><font size="2">bear </font></td>
        <td><font size="2">fido </font></td>
        <td><font size="2">horse </font></td>
        <td><font size="2">rabbit </font></td>
        <td><font size="2">unique </font></td>
    </tr>
    <tr>
        <td><font size="2">cat </font></td>
        <td><font size="2">fish </font></td>
        <td><font size="2">human </font></td>
        <td><font size="2">saurian </font></td>
        <td><font size="2">vampire </font></td>
    </tr>
    <tr>
        <td><font size="2">centipede </font></td>
        <td><font size="2">fox </font></td>
        <td><font size="2">kobold </font></td>
        <td><font size="2">school monster </font></td>
        <td><font size="2">water fowl </font></td>
    </tr>
    <tr>
        <td><font size="2">dog </font></td>
        <td><font size="2">giant </font></td>
        <td><font size="2">lizard </font></td>
        <td><font size="2">snake </font></td>
        <td><font size="2">wolf </font></td>
    </tr>
    <tr>
        <td><font size="2">doll</font></td>
        <td><font size="2">goblin </font></td>
        <td><font size="2">modron </font></td>
        <td><font size="2">song bird </font></td>
        <td><font size="2">wyvern </font></td>
    </tr>
    <tr>
        <td><font size="2">dragon </font></td>
        <td><font size="2">head </font></td>
        <td><font size="2">orc </font></td>
        <td><font size="2">tree</font></td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">dwarf </font></td>
        <td><font size="2">hobbit </font></td>
        <td><font size="2">pig </font></td>
        <td><font size="2">trol</font>l</td>
        <td align="right" valign="top">&nbsp;</td>
    </tr>
</table>

<p><font size="3"><b><u>MOBILE SIZE</u></b></font></p>

<table border="2" cellpadding="0" cellspacing="20">
    <tr>
        <td><font size="3">T= Tiny</font></td>
        <td><font size="3">S = Small</font><font size="2"> </font></td>
        <td><font size="3">M = Medium</font><font size="2"> </font></td>
    </tr>
    <tr>
        <td>L = Large</td>
        <td>H = Huge</td>
        <td>G = Giant</td>
    </tr>
</table>

<p><font size="3">Use common sense when it comes to flags. Like,
if you flag a mob which happens to be a thief type mob that would
be expected to have sneak or hide, then it would make sense to
flag the mob with one or both of those affects. However, flagging
other mobs with sneak or hide just for the fun of it, doesn't
make sense, and unless you can convince me otherwise, I will
remove it from the area file.</font></p>

<table border="2">
    <tr>
        <td><font size="2"><b><u>AFFECTED BY</u></b><strong> </strong></font></td>
        <td><font size="2"><b><u>FLAG</u></b> </font></td>
        <td><font size="2"><b><u>OLD VALUE</u></b> </font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b> </font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_BLIND</font></td>
        <td>A</td>
        <td>1</td>
        <td>Mob is blind</td>
    </tr>
    <tr>
        <td><font size="3">AFF_INVISIBLE</font><font size="2"> </font></td>
        <td>B</td>
        <td>2</td>
        <td><font size="3">Mob is invisible</font> </td>
    </tr>
    <tr>
        <td><font size="3">AFF_DETECT_EVIL </font></td>
        <td>C</td>
        <td>4</td>
        <td>Mob can detect evil </td>
    </tr>
    <tr>
        <td><font size="3">AFF_DETECT_INVIS</font><font size="2">
        </font></td>
        <td><font size="2">D</font></td>
        <td><font size="3">8</font></td>
        <td><font size="3">Mob can detect Invisible </font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_DETECT_MAGIC</font><font size="2">
        </font></td>
        <td>E</td>
        <td>16</td>
        <td>Mob can detect magic </td>
    </tr>
    <tr>
        <td><font size="3">AFF_DETECT_HIDDEN</font><font size="2">
        </font></td>
        <td>F</td>
        <td>32</td>
        <td>Mob can detect hidden </td>
    </tr>
    <tr>
        <td><font size="3">AFF_BERSERK</font><font size="2"> </font></td>
        <td><font size="3">G</font></td>
        <td><font size="3">64</font></td>
        <td><font size="3">Mob is berserked</font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_SANCTUARY</font></td>
        <td><font size="3">H</font></td>
        <td><font size="3">128</font></td>
        <td><font size="3">Mob is Sanc'd</font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_FAERIE_FIRE</font></td>
        <td><font size="3">I</font></td>
        <td><font size="3">256</font></td>
        <td><font size="3">Mob is faerie fired</font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_INFRAVISION</font></td>
        <td><font size="3">J</font></td>
        <td><font size="3">512</font></td>
        <td><font size="3">Mob can see in the dark</font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_CURSE</font></td>
        <td><font size="3">K</font></td>
        <td><font size="3">1024</font></td>
        <td><font size="3">Mob is cursed</font></td>
    </tr>
    <tr>
        <td><font size="3">AFF_SWIM</font></td>
        <td><font size="3">L</font></td>
        <td><font size="3">2048</font></td>
        <td><font size="3">Mob is swimming</font></td>
    </tr>
    <tr>
        <td>AFF_POISON</td>
        <td>M</td>
        <td>4096</td>
        <td>Mob is poisoned</td>
    </tr>
    <tr>
        <td>AFF_PROTECT</td>
        <td>N</td>
        <td>8192</td>
        <td>Mob is protected from evil </td>
    </tr>
    <tr>
        <td>AFF_REGENERATION</td>
        <td>O</td>
        <td>16384</td>
        <td>Mob regenerates HP quickly (i.e., Trolls) </td>
    </tr>
    <tr>
        <td>AFF_SNEAK</td>
        <td>P</td>
        <td>32768</td>
        <td>Mob is sneaking</td>
    </tr>
    <tr>
        <td>AFF_HIDE</td>
        <td>Q</td>
        <td>65536</td>
        <td>Mob is hidden</td>
    </tr>
    <tr>
        <td>AFF_SLEEP</td>
        <td>R</td>
        <td>131072</td>
        <td>Mob is affected by Sleep spell</td>
    </tr>
    <tr>
        <td>AFF_CHARM</td>
        <td>S</td>
        <td>262144</td>
        <td>Mob is charmed</td>
    </tr>
    <tr>
        <td>AFF_FLYING</td>
        <td>T</td>
        <td>524288</td>
        <td>Mob is flying</td>
    </tr>
    <tr>
        <td>AFF_PASS_DOOR</td>
        <td>U</td>
        <td>1048576</td>
        <td>Mob is affected by Pass Door spell</td>
    </tr>
    <tr>
        <td>AFF_HASTE</td>
        <td>V</td>
        <td>2091752</td>
        <td>Mob is affected by Haste spell</td>
    </tr>
    <tr>
        <td>AFF_CALM</td>
        <td>W</td>
        <td>4194304</td>
        <td>Mob can't be attacked</td>
    </tr>
    <tr>
        <td>AFF_PLAGUE</td>
        <td>X</td>
        <td>8388608</td>
        <td>Mob is affected by Plague spell</td>
    </tr>
    <tr>
        <td>AFF_WEAKEN</td>
        <td>Y</td>
        <td>16777216</td>
        <td>Mob is affected by Weaken spell</td>
    </tr>
    <tr>
        <td>AFF2_FLAGS</td>
        <td>Z</td>
        <td>&nbsp;</td>
        <td>Tells game AFF2 flags to follow</td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><strong>AFF2 FLAGS</strong></td>
        <td><strong>FLAG </strong></td>
        <td>&nbsp;</td>
        <td><strong>DESCRIPTION</strong></td>
    </tr>
    <tr>
        <td>AFF2_DARK_VISION</td>
        <td>A</td>
        <td>&nbsp;</td>
        <td>Mob can see clearly in the dark</td>
    </tr>
    <tr>
        <td>AFF2_DETECT_GOOD</td>
        <td>B</td>
        <td>&nbsp;</td>
        <td>Mob affected by Detect Good spell</td>
    </tr>
    <tr>
        <td>AFF2_HOLD</td>
        <td>C</td>
        <td>&nbsp;</td>
        <td>*Disabled*</td>
    </tr>
    <tr>
        <td>AFF2_FLAMING</td>
        <td>D</td>
        <td>&nbsp;</td>
        <td>Mob is affected by Fireshield spell</td>
    </tr>
    <tr>
        <td>AFF2_FLAMING_COLD </td>
        <td>E</td>
        <td>&nbsp;</td>
        <td>Mob is affected by Frostshield spell</td>
    </tr>
    <tr>
        <td>AFF2_STEALTH</td>
        <td>F</td>
        <td>&nbsp;</td>
        <td>Mob is stealthed</td>
    </tr>
</table>

<p><font size="3">Remember: unless you desire your mobile to be
poisoned, plagued, weakened, cursed, or sleeping, do not use
those particular &#145;Affected_by' flags. However, it could be
amusing to have a 'walking plague spreader' in an area, for
example, and you may desire to have a mobile affected by the
plague, and consequently spreading it to other PC's it runs in
contact with.</font></p>

<p><font size="3">Use common sense when it comes to flags. Like,
if you flag a mob which happens to be a black dragon that has
acid breath, then it would make sense that the mob would be
immune to acid. However, making other mobs immune to acid just
for the fun of it, doesn't make sense, and unless you can
convince me otherwise, I will remove it from the area file.</font></p>

<table border="2">
    <tr>
        <td><font size="3"><b><u>OFF BITS</u></b></font><font
        size="2"> </font></td>
        <td><font size="3"><b><u>FLAG</u></b></font><font
        size="2"><strong> </strong></font></td>
        <td><strong><u>DESCRIPTION</u></strong> </td>
    </tr>
    <tr>
        <td><font size="2">OFF_AREA_ATTACK </font></td>
        <td>A</td>
        <td><font size="2">Mob can cast area attack spells with
        proper special </font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_BACKSTAB</font></td>
        <td>B</td>
        <td><font size="2">Mob can backstab opponent</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_BASH</font></td>
        <td>C</td>
        <td><font size="2">Mob can bash</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_BERSERK</font></td>
        <td>D</td>
        <td><font size="2">Mob can berserk</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_DISARM</font></td>
        <td>E</td>
        <td><font size="2">Mob can disarm opponent</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_DODGE</font></td>
        <td>F</td>
        <td><font size="2">Mob can dodge</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_FADE</font></td>
        <td>G</td>
        <td><font size="2">Mob fades in and out of view (hard to
        hit)</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_FAST</font></td>
        <td>H</td>
        <td><font size="2">Mob is fast (2 attacks per round or
        more)</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_KICK</font></td>
        <td><font size="2">I</font></td>
        <td><font size="2">Mob may kick opponent</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_KICK_DIRT</font></td>
        <td>J</td>
        <td><font size="2">Mob can dirt kick opponent</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_PARRY</font></td>
        <td>K</td>
        <td><font size="2">Mob can parry</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_RESCUE</font></td>
        <td><font size="2">L</font></td>
        <td><font size="2">Mob can rescue (pets/charmies) (and
        same align/same vnum if flagged with assist flags below) </font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_TAIL</font></td>
        <td><font size="2">M</font></td>
        <td><font size="2">Mob has extra attack with its tail</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_TRIP</font></td>
        <td><font size="2">N</font></td>
        <td><font size="2">Mob can trip opponent</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_CRUSH</font></td>
        <td>O</td>
        <td><font size="2">Mob has extra crushing attack</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_ALL</font></td>
        <td>P</td>
        <td><font size="2">Mob assists anyone (random) in a
        fight, if its not currently fighting</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_ALIGN</font></td>
        <td>Q</td>
        <td><font size="2">Mob assists anyone within its align
        range</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_RACE</font></td>
        <td><font size="2">R</font></td>
        <td><font size="2">Mob assists anyone of its own race</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_PLAYERS</font></td>
        <td><font size="2">S</font></td>
        <td><font size="2">Mob assists all players if they
        arecurrently fighting other mobs in the same room</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_GUARDS</font></td>
        <td><font size="2">T</font></td>
        <td><font size="2">Mob assists guards</font></td>
    </tr>
    <tr>
        <td><font size="2">ASSIST_VNUM</font></td>
        <td><font size="2">U</font></td>
        <td><font size="2">Mob assists mobs with same VNUM</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_SUMMONER</font></td>
        <td><font size="2">V</font></td>
        <td><font size="2">Mob may summon aggie to assist it</font></td>
    </tr>
    <tr>
        <td><font size="2">NEEDS_MASTER</font></td>
        <td><font size="2">W</font></td>
        <td><font size="2">Autosets for pets</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_FLAGS2</font></td>
        <td><font size="2">Z</font></td>
        <td><font size="2">Tells game that OFF_FLAGS2 are to
        follow</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>OFF_FLAGS2</u></b></font></td>
        <td><font size="3"><b><u>FLAG</u></b> </font></td>
        <td><strong><u>DESCRIPTION</u></strong> </td>
    </tr>
    <tr>
        <td><font size="2">OFF2_HUNTER</font></td>
        <td><font size="2">A</font></td>
        <td><font size="2">Mob hunts PC until either mob or pc is
        dead.</font></td>
    </tr>
    <tr>
        <td><font size="2">OFF_ATTACK_DOOR_OPENER</font></td>
        <td><font size="2">X</font></td>
        <td><font size="2">Mob attacks first PC to open the door
        to/from a room.</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>IMMUNITIES</u></b> </font></td>
        <td><table border="0">
            <tr>
                <td><font size="3"><b><u>FLAG</u></b> </font></td>
            </tr>
        </table>
        </td>
        <td><strong><u>DESCRIPTION</u></strong> </td>
    </tr>
    <tr>
        <td><font size="2">IMM_SUMMON</font></td>
        <td>A</td>
        <td><font size="2">Mob may not be gated to. Flag all but
        one or two mobs with this flag ALWAYS!</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_CHARM</font></td>
        <td>B</td>
        <td><font size="2">Mob cannot be charmed. Flag most if
        not all mobs with this flag ALWAYS!</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_MAGIC</font></td>
        <td>C</td>
        <td><font size="2">Mob cannot be affected by magic</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_WEAPON</font></td>
        <td>D</td>
        <td><font size="2">Mob cannot be affected by weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_BASH</font></td>
        <td>E</td>
        <td><font size="2">Mob cannot be bashed</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_PIERCE</font></td>
        <td>F</td>
        <td><font size="2">Mob cannot be harmed by pierce weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_SLASH</font></td>
        <td>G</td>
        <td><font size="2">Mob cannot be harmed by slash weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_FIRE</font></td>
        <td>H</td>
        <td><font size="2">Mob cannot be harmed by fire type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_COLD</font></td>
        <td>I</td>
        <td><font size="2">Mob cannot be harmed by cold type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_LIGHTNING</font></td>
        <td>J</td>
        <td><font size="2">Mob cannot be harmed by lightning type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_ACID</font></td>
        <td>K</td>
        <td><font size="2">Mob cannot be harmed by acid type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_POISON</font></td>
        <td>L</td>
        <td><font size="2">Mob cannot be poisoned</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_NEGATIVE</font></td>
        <td>M</td>
        <td><font size="2">Mob cannot be harmed by negative type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_HOLY</font></td>
        <td>N</td>
        <td><font size="2">Mob cannot be harmed by holy type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_ENERGY</font></td>
        <td>O</td>
        <td><font size="2">Mob cannot be harmed by energy type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_MENTAL</font></td>
        <td>P</td>
        <td><font size="2">Mob cannot be harmed by mental attacks
        (PSI)</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_DISEASE</font></td>
        <td>Q</td>
        <td><font size="2">Mob cannot be plagued</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_DROWNING</font></td>
        <td>R</td>
        <td><font size="2">Mob cannot be affected by water damage
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_LIGHT</font></td>
        <td>S</td>
        <td><font size="2">Mob cannot be harmed by light type
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">IMM_FLAGS2</font></td>
        <td>Z</td>
        <td><font size="2">Tells game that IMM_FLAGS2 are to
        follow</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>IMM_FLAGS2</u></b></font></td>
        <td><font size="3"><b><u>FLAG</u></b></font></td>
        <td><font size="3"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><strong>*None yet implemented</strong></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>RESISTANCES</u></b></font></td>
        <td><font size="3"><b><u>FLAG</u></b></font></td>
        <td><font size="3"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">RES_CHARM</font></td>
        <td><font size="2">B</font></td>
        <td><font size="2">Mob is difficult to charm</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_MAGIC</font></td>
        <td><font size="2">C</font></td>
        <td><font size="2">Mob takes less than normal damage from
        magic</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_WEAPON</font></td>
        <td><font size="2">D</font></td>
        <td><font size="2">Mob takes less than normal damage from
        weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_BASH</font></td>
        <td><font size="2">E</font></td>
        <td><font size="2">Mob is less apt to be affected by bash</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_PIERCE</font></td>
        <td><font size="2">F</font></td>
        <td><font size="2">Mob takes less than normal damage from
        piercing</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_SLASH</font></td>
        <td><font size="2">G</font></td>
        <td><font size="2">Mob takes less than normal damage from
        slashing</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_FIRE</font></td>
        <td><font size="2">H</font></td>
        <td><font size="2">Mob takes less than normal damage from
        fire</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_COLD</font></td>
        <td><font size="3">I</font></td>
        <td><font size="2">Mob takes less than normal damage from
        cold</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_LIGHTNING</font></td>
        <td>J</td>
        <td><font size="2">Mob takes less than normal damage from
        lightning</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_ACID</font></td>
        <td><font size="2">K</font></td>
        <td><font size="2">Mob takes less than normal damage from
        acid</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_POISON</font></td>
        <td><font size="2">L</font></td>
        <td><font size="2">Mob is less apt to be affected by
        poison</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_NEGATIVE</font></td>
        <td><font size="2">M</font></td>
        <td><font size="2">Mob is less apt to be affected by
        negative spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_HOLY</font></td>
        <td><font size="2">N</font></td>
        <td><font size="2">Mob is less apt to be affected by holy
        items/spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_ENERGY</font></td>
        <td><font size="2">O</font></td>
        <td><font size="2">Mob is less apt to be affected by
        energy spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_MENTAL</font></td>
        <td><font size="2">P</font></td>
        <td><font size="2">Mob is less apt to be affected by
        mental spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_DISEASE</font></td>
        <td><font size="2">Q</font></td>
        <td><font size="2">Mob is less apt to be affected by
        plague</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_DROWNING</font></td>
        <td>R</td>
        <td><font size="2">Mob is less apt to be affected by
        water areas/spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_LIGHT</font></td>
        <td><font size="2">S</font></td>
        <td><font size="2">Mob is less apt to be affected by
        light spells</font></td>
    </tr>
    <tr>
        <td><font size="2">RES_FLAGS2</font></td>
        <td><font size="2">Z</font></td>
        <td><font size="2">Tells game that RES_FLAGS2 are to
        follow</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><strong><u>RES_FLAGS2</u></strong></font></td>
        <td><strong><u>FLAG</u></strong></td>
        <td><strong><u>DESCRIPTION</u></strong></td>
    </tr>
    <tr>
        <td><strong>*None yet implemented</strong></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>VULNERABILITIES</u></b></font></td>
        <td><font size="2"><b><u>FLAG</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_MAGIC</font></td>
        <td>C</td>
        <td><font size="2">Mob takes double damage from magic</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_WEAPON</font></td>
        <td>D</td>
        <td><font size="2">Mob takes double damage from any
        weapon</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_BASH</font></td>
        <td><font size="2">E</font></td>
        <td><font size="2">Mob is twice as likely to be affected
        by bash</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_PIERCE</font></td>
        <td><font size="2">F</font></td>
        <td><font size="2">Mob takes double damage from any
        piercing weapon</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_SLASH</font></td>
        <td><font size="2">G</font></td>
        <td><font size="2">Mob takes double damage from any
        slashing weapon</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_FIRE</font></td>
        <td><font size="2">H</font></td>
        <td><font size="2">Mob takes double damage from fire
        spells and flaming weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_COLD</font></td>
        <td><font size="2">I</font></td>
        <td><font size="2">Mob takes double damage from cold
        spells and freezing weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_LIGHTNING</font></td>
        <td><font size="2">J</font></td>
        <td><font size="2">Mob takes double damage from lightning
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_ACID</font></td>
        <td><font size="2">K</font></td>
        <td><font size="2">Mob takes doulbe damage from acid
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_POISON</font></td>
        <td><font size="2">L</font></td>
        <td><font size="2">Mob takes double damage from poison
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_NEGATIVE</font></td>
        <td><font size="2">M</font></td>
        <td><font size="2">Mob takes double damage from negative
        psionics/spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_HOLY</font></td>
        <td><font size="2">N</font></td>
        <td><font size="2">Mob takes double damage from holy
        spells/weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_ENERGY</font></td>
        <td><font size="2">O</font></td>
        <td><font size="2">Mob takes double damage from energy
        psionics/spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_MENTAL</font></td>
        <td><font size="2">P</font></td>
        <td><font size="2">Mob takes double damage from mental
        psionics</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_DISEASE</font></td>
        <td><font size="2">Q</font></td>
        <td><font size="2">Mob takes double damage from plague</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_DROWNING</font></td>
        <td><font size="2">R</font></td>
        <td><font size="2">Mob takes double damage from water
        spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_LIGHT</font></td>
        <td><font size="2">S</font></td>
        <td><font size="2">Mob takes double damage from light
        psionics/spells</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_WOOD</font></td>
        <td><font size="2">T</font></td>
        <td><font size="2">Mob takes double damage from wooden
        weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_SILVER</font></td>
        <td><font size="2">U</font></td>
        <td><font size="2">Mob takes double damage from silver
        weapons</font></td>
    </tr>
    <tr>
        <td><font size="2">VULN_FLAGS2</font></td>
        <td><font size="2">Z</font></td>
        <td><font size="2">Tells game that VULN_FLAGS2 are to
        follow</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>VULNERABILITIES 2</u></b></font></td>
        <td><font size="2"><b><u>FLAG</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">VULN2_IRON</font></td>
        <td><font size="2">A</font></td>
        <td><font size="2">Mob takes double damage from iron
        weapons (i.e., elves)</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>POSITIONS</u></b></font></td>
        <td><font size="2"><b><u>FLAG</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_DEAD</font></td>
        <td><font size="2">0</font></td>
        <td><font size="2">Mob is dead <strong>*INTERNAL USE
        ONLY*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_MORTAL</font></td>
        <td><font size="2">1</font></td>
        <td><font size="2">Mob is mortally wounded <strong>*INTERNAL
        USE ONLY*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_INCAP</font></td>
        <td><font size="2">2</font></td>
        <td><font size="2">Mob is incompacitated (near death) <strong>*INTERNAL
        USE ONLY*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_STUNNED</font></td>
        <td><font size="2">3</font></td>
        <td><font size="2">Mob is stunned <strong>*INTERNAL USE
        ONLY*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_SLEEPING</font></td>
        <td><font size="2">4</font></td>
        <td><font size="2">Mob is sleeping</font></td>
    </tr>
    <tr>
        <td><font size="2">POS_RESTING</font></td>
        <td><font size="2">5</font></td>
        <td><font size="2">Mob is resting</font></td>
    </tr>
    <tr>
        <td><font size="2">POS_SITTING</font></td>
        <td><font size="2">6</font></td>
        <td><font size="2">Mob is sitting</font></td>
    </tr>
    <tr>
        <td><font size="2">POS_FIGHTING</font></td>
        <td><font size="2">7</font></td>
        <td><font size="2">Mob is fighting <strong>*INTERNAL USE
        ONLY*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">POS_STANDING</font></td>
        <td><font size="2">8</font></td>
        <td><font size="2">Mob is standing</font></td>
    </tr>
    <tr>
        <td><font size="2">POS_MOUNTED</font></td>
        <td><font size="2">9</font></td>
        <td><font size="2">Mob is mounted on another mob</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>SEX</u></b></font></td>
        <td><font size="2"><b><u>FLAG</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">NEUTER</font></td>
        <td><font size="2">0</font></td>
        <td><font size="2">Mob is an it</font></td>
    </tr>
    <tr>
        <td><font size="2">MALE</font></td>
        <td><font size="2">1</font></td>
        <td><font size="2">Mob is a male</font></td>
    </tr>
    <tr>
        <td><font size="2">FEMALE</font></td>
        <td><font size="2">2</font></td>
        <td><font size="2">Mob is a female</font></td>
    </tr>
</table>

<p><font size="2"><strong>DAMAGE TYPES</strong> (these values
also used for weapons in #OBJECTS):</font></p>

<table border="2" cellpadding="0" cellspacing="20">
    <tr>
        <td valign="top"><font size="2">HIT </font></td>
        <td valign="top"><font size="2">0 </font></td>
        <td valign="top"><font size="2">PUNCH</font></td>
        <td valign="top"><font size="2">17</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">SLICE </font></td>
        <td valign="top"><font size="2">1 </font></td>
        <td valign="top"><font size="2">WRATH </font></td>
        <td valign="top"><font size="2">18 </font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">STAB </font></td>
        <td valign="top"><font size="2">2 </font></td>
        <td valign="top"><font size="2">MAGIC </font></td>
        <td valign="top"><font size="2">19 </font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">SLASH </font></td>
        <td valign="top"><font size="2">3</font></td>
        <td valign="top"><font size="2">DIVINE POWER </font></td>
        <td valign="top"><font size="2">20 </font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">WHIP</font></td>
        <td valign="top"><font size="2">4 </font></td>
        <td valign="top"><font size="2">CLEAVE</font></td>
        <td valign="top"><font size="2">21</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">CLAW</font></td>
        <td valign="top"><font size="2">5 </font></td>
        <td valign="top"><font size="2">SCRATCH</font></td>
        <td valign="top"><font size="2">22</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">BLAST </font></td>
        <td valign="top"><font size="2">6</font></td>
        <td valign="top"><font size="2">PECK (Pierce)</font></td>
        <td valign="top"><font size="2">23</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">POUND </font></td>
        <td valign="top"><font size="2">7 </font></td>
        <td valign="top"><font size="2">PECK (Bash)</font></td>
        <td valign="top"><font size="2">24</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">CRUSH </font></td>
        <td valign="top"><font size="2">8 </font></td>
        <td valign="top"><font size="2">CHOP</font></td>
        <td valign="top"><font size="2">25</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">GREP</font></td>
        <td valign="top"><font size="2">9 </font></td>
        <td valign="top"><font size="2">STING</font></td>
        <td valign="top"><font size="2">26</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">BITE </font></td>
        <td valign="top"><font size="2">10 </font></td>
        <td valign="top"><font size="2">SMASH</font></td>
        <td valign="top"><font size="2">27</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">PIERCE </font></td>
        <td valign="top"><font size="2">11</font></td>
        <td valign="top"><font size="2">SHOCKING BITE </font></td>
        <td valign="top"><font size="2">28</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">SUCTION </font></td>
        <td valign="top"><font size="2">12 </font></td>
        <td valign="top"><font size="2">FLAMING BITE</font></td>
        <td valign="top"><font size="2">29 </font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">BEATING </font></td>
        <td valign="top"><font size="2">13 </font></td>
        <td valign="top"><font size="2">FREEZING BITE</font></td>
        <td valign="top"><font size="2">30</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">DIGESTION </font></td>
        <td valign="top"><font size="2">14</font></td>
        <td valign="top"><font size="2">ACIDIC BITE</font></td>
        <td valign="top"><font size="2">31</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">CHARGE</font></td>
        <td valign="top"><font size="2">15</font></td>
        <td valign="top"><font size="2">CHOMP</font></td>
        <td valign="top"><font size="2">32</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">SLAP</font></td>
        <td valign="top"><font size="2">16</font></td>
        <td valign="top">&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
</table>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/objects.html">#OBJECTS</a>
<a href="http://www.ofchaos.com/Building/rooms.html">#ROOMS</a>
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
