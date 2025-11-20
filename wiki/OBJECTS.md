
<p><font size="3">The #OBJECTS section is similar to the #MOBILES
section. However, the main difference is that the values in the
#OBJECTS section depend on the TYPE of object being described,
i.e., weapon, scroll, potion, treasure, etc. Below I am
presenting an example of how an object should look in this
section:</font></p>

<p><font size="3">Example:</font></p>

<p><font size="3">#QQ01</font><br>
<font size="3">sword underworld~</font><br>
<font size="3">The Sword of the Underworld~</font><br>
<font size="3">A large, dark sword of solid obsidian gleams
evilly here.~</font><br>
<font size="3">adamantite~</font><br>
<font size="3">5 ABCEJL AN</font><br>
<font size="3">1 11 6 6 DE</font><br>
<font size="3">50 30 350 P</font><br>
<font size="3">E</font><br>
<font size="3">sword underworld~</font><br>
<font size="3">This heavy sword has an evil, dark shine to its
metal. The pommel is</font><br>
<font size="3">formed into the shape of a large ram's head and is
set with several large</font><br>
<font size="3">rubies.</font><br>
<font size="3">~</font><br>
<font size="3">A</font><br>
<font size="3">1 1</font><br>
<font size="3">A</font><br>
<font size="3">5 1</font><br>
<font size="3">A</font><br>
<font size="3">14 -35</font><br>
<font size="3">A</font><br>
<font size="3">18 1</font><br>
<font size="3">A</font><br>
<font size="3">19 1</font><br>
<font size="3">#QQ02 this begins the next object in the #OBJECTS
section...</font><br>
<br>
<font size="3">Explanation of each line:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="3">#QQ01 </font></td>
        <td><font size="3">this is the vnum unique to this object
        </font></td>
    </tr>
    <tr>
        <td><font size="3">sword underworld~ </font></td>
        <td><font size="3">these are the keywords for the object </font></td>
    </tr>
    <tr>
        <td><font size="3">The Sword of the Underworld~ </font></td>
        <td><font size="3">the name of the object </font></td>
    </tr>
    <tr>
        <td><font size="3">A large, dark sword of solid obsidian
        gleams evilly here.~ </font></td>
        <td><font size="3">the long description of the object</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="3">adamantite~</font></td>
        <td><font size="3">the 'material' of the object. Use the
        common materials that</font><font size="4"><br>
        </font><font size="3">are already in the const.c table in
        the ROM code. A list of </font><font size="4"><br>
        </font><font size="3">materials is provided at the end of
        the help for #OBJECTS</font><font size="4"><br>
        </font><font size="3">section. This is similar to the
        'race' part of the #MOBILES,</font><font size="4"><br>
        </font><font size="3">and is what prevents some objects
        from being burned, while</font><font size="4"><br>
        </font><font size="3">objects made of wood, paper and
        glass CAN be destroyed by</font><font size="4"><br>
        </font><font size="3">dragon fire, for example.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">5 ABCEJL AN</font></td>
        <td><font size="2"><strong>&lt;ITEM TYPE&gt;
        &lt;flags&gt; &lt;flags2&gt; &lt;wear flags&gt;</strong></font><font
        size="4"><br>
        </font><font size="2">A listing of item types, flags and
        wear flags is provided at the</font><font size="4"><br>
        </font><font size="2">end of the help for #OBJECTS
        section. The item type is just</font><font size="4"><br>
        </font><font size="2">that; 5 = weapon, as reflected
        here. The flags add additional</font><font size="4"><br>
        </font><font size="2">flags to the item, i.e., evil,
        magic, humming, glowing, etc.</font><font size="4"><br>
        </font><font size="2">The wear flags tell where and if an
        item can be worn and</font><font size="4"><br>
        </font><font size="2">where. A and N tell the code that
        this sword can be 'taken'</font><font size="4"><br>
        </font><font size="2">and 'wielded' as a weapon; A =
        take, and N= wield. Without</font><font size="4"><br>
        </font><font size="2">the 'A', this item couldn&#146;t
        even be picked up from the ground.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">1 11 6 6 DE</font></td>
        <td><font size="2"><strong>&lt;weapon class&gt; &lt; #
        dice&gt; &lt;type of dice&gt; &lt;damage type&gt;</strong>
        </font><font size="4"><br>
        <br>
        </font><font size="2"><strong>*IMPORTANT*</strong> This
        is the VALUES line, and it varies</font><font size="4"><br>
        </font><font size="2">depending on the 'ITEM TYPE' as
        declared in the above line.</font><font size="4"><br>
        </font><font size="2">At the end of this section,
        following the value tables, is the</font><font size="4"><br>
        </font><font size="2">breakdown of this line for all the
        other object types. This</font><font size="4"><br>
        </font><font size="2">example here, is geared for objects
        that are weapons. In the</font><font size="4"><br>
        </font><font size="2">example here, this line is as
        follows:</font><font size="4"><br>
        <br>
        </font><font size="2">The weapon class is what sort of
        weapon it is; sword, dagger,</font><font size="4"><br>
        </font><font size="2">whip, etc. A '1' = sword in this
        example. Damage is</font><font size="4"><br>
        </font><font size="2">calculated by the 'dice' method.
        The first number is the</font><font size="4"><br>
        </font><font size="2">number of dice; the second is the
        type of dice rolled. In this</font><font size="4"><br>
        </font><font size="2">example, The Sword of the
        Underworld has 11 and 6 as</font><font size="4"><br>
        </font><font size="2">values; that is 11d6, or 11
        six-sided dice for damage. In</font><font size="4"><br>
        </font><font size="2">other words, 11 times 6 is the max
        damage, and roughly half </font><font size="4"><br>
        </font><font size="2">that is the average damage. Thus,
        this sword has an average</font><font size="4"><br>
        </font><font size="2">damage of 33.</font><font size="4"><br>
        <br>
        </font><font size="2">The DAMAGE TYPE is crush, slash,
        pound, etc., and uses</font><font size="4"><br>
        </font><font size="2">the same damage type chart from
        #MOBILES.</font><font size="4"><br>
        <br>
        </font><font size="2">The WEAPON TYPES gives the weapon
        additional</font><font size="4"><br>
        </font><font size="2">characteristics, i.e., two-handed,
        vorpal, vampiric, etc. </font><font size="4"><br>
        <br>
        </font><font size="2">Listings for the WEAPON CLASS,
        DAMAGE TYPES, and</font><font size="4"><br>
        </font><font size="2">WEAPON TYPES can be found at the
        end of this</font><font size="4"><br>
        </font><font size="2">#OBJECTS help section.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">50 30 35000 P</font></td>
        <td><font size="2"><strong>&lt;object level&gt;
        &lt;object weight&gt; &lt;object value&gt; &lt;object
        condition&gt;</strong></font><font size="4"><br>
        <br>
        </font><font size="2">This line should be
        self-explanatory; the value of the object is</font><font
        size="4"><br>
        </font><font size="2">what you would purchase it for, in
        gold, if it was for sale in</font><font size="4"><br>
        </font><font size="2">the Weapons Shop. Item condition is
        needed, but is generally</font><font size="4"><br>
        </font><font size="2">P which equals perfect condition.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">E</font></td>
        <td><font size="2">this is if you want extra descriptive
        keywords; the 'E' section</font><font size="4"><br>
        </font><font size="2">in #OBJECTS allows for this. When
        someone 'looks' at the</font><font size="4"><br>
        </font><font size="2">object they will be given an
        additional description; this is</font><font size="4"><br>
        </font><font size="2">optional, however, this is what
        separates the junk area writers</font><font size="4"><br>
        </font><font size="2">from the pros, as it shows the
        writer as a true artist of their craft!</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">sword underworld~</font><font
        size="4"><br>
        <br>
        </font><font size="2">This heavy sword has an evil, dark
        shine to its metal.</font><font size="4"><br>
        </font><font size="2">The pommel is formed into the shape
        of a large ram's</font><font size="4"><br>
        </font><font size="2">head and is set with several large
        rubies.</font></td>
        <td valign="top"><font size="2">the keywords for the 'E'
        section.</font><font size="4"><br>
        <br>
        </font><font size="2">the 'extra description', as in what
        the player sees when they look at</font><font size="4"><br>
        </font>it.</td>
    </tr>
    <tr>
        <td>~</td>
        <td><font size="2">The tilde goes on its own separate
        line for formatting purposes.</font></td>
    </tr>
    <tr>
        <td valign="top"><font size="2">A</font></td>
        <td><font size="2"><strong>Note: These are OPTIONAL, and
        are to be used RARELY!</strong></font><font size="4"><br>
        </font><font size="2"><strong>For every</strong></font><font
        size="4"> </font><font size="2"><strong>bonus</strong></font><font
        size="4"> </font><font size="2"><strong>there should be
        an equal, balancing, detriment</strong></font><font
        size="4"><br>
        </font><font size="2"><strong>as well. These</strong></font><font
        size="4"> </font><font size="2"><strong>values will be
        scrutinized very closely by me,</strong></font><font
        size="4"><br>
        </font><font size="2"><strong>and if deemed out of</strong></font><font
        size="4"> </font><font size="2"><strong>balance, will be
        adjusted. If</strong></font><font size="4"> </font><font
        size="2"><strong>objects are</strong></font><font
        size="4"><br>
        </font><font size="2"><strong>frequently made too</strong></font><font
        size="4"> </font><font size="2"><strong>powerful, the
        area may be rejected until</strong></font><font size="4"><br>
        </font><font size="2"><strong>the author fixes it</strong></font><font
        size="4"> </font><font size="2"><strong>themself.</strong></font><font
        size="4"><br>
        <br>
        </font><font size="2">this is for adding abilities and
        other attributes to the object.</font><font size="4"><br>
        </font><font size="2">An 'A' section ('apply' section)
        contains an apply-type and an</font><font size="4"><br>
        </font><font size="2">apply-value. When a character uses
        this object as equipment</font><font size="4"><br>
        </font><font size="2">(holds, wields, or wears it), then
        the value of the 'apply-value'</font><font size="4"><br>
        </font><font size="2">is added to the character attribute
        identified by the apply-type.</font><font size="4"><br>
        </font><font size="2">In other words, if you construct an
        'A' value for +strength for</font><font size="4"><br>
        </font><font size="2">an object, of say +1, for example,
        when a character uses it as</font><font size="4"><br>
        </font><font size="2">equipment, the strength of the
        character increases by 1.</font></td>
    </tr>
    <tr>
        <td><font size="2">1 1</font></td>
        <td><font size="2"><strong>&lt;apply-type&gt;
        &lt;apply-value&gt;</strong></font><font size="4"><br>
        </font><font size="2">This gives plus 1 to the strength
        of the player using it. Here, the apply</font><font
        size="4"><br>
        </font><font size="2">type</font><font size="4"> </font><font
        size="2">value is 1, which is</font><font size="4"> </font><font
        size="2">+strength, and the 'apply-value' of 1 means an</font><font
        size="4"><br>
        </font><font size="2">additional 1</font><font size="4"> </font><font
        size="2">point to the player's strength value</font>.</td>
    </tr>
    <tr>
        <td>A</td>
        <td><font size="2">another 'A' value, and so on...</font></td>
    </tr>
</table>

<p><font size="2"><b>NOTE</b>: The optional 'E' sections and 'A'
sections come after the main data. An 'E' section ('extra
description section' contains a keyword-list and a string
associated with those keywords. This description string is used
when a character looks at a word on the keyword list, as
explained above. A single object may have an unlimited number of
'E' and 'A' sections.</font></p>

<p><font size="3"><strong>Common Materials for the 'material'
section:</strong></font></p>

<p><font size="2">This is where you specifiy the material of the
object, keeping in mind that paper, glass, wood, etc., all may be
destroyed by fire and acid.</font></p>

<table border="2" cellpadding="0" cellspacing="20">
    <tr>
        <td valign="top">adamantite </td>
        <td valign="top">food</td>
        <td valign="top">leather </td>
        <td valign="top">steel </td>
    </tr>
    <tr>
        <td valign="top">brass </td>
        <td valign="top">gold </td>
        <td valign="top">paper </td>
        <td valign="top">stone </td>
    </tr>
    <tr>
        <td valign="top">bronze </td>
        <td valign="top">glass </td>
        <td valign="top">pill </td>
        <td valign="top">vellum </td>
    </tr>
    <tr>
        <td valign="top">cloth</td>
        <td valign="top">iron* </td>
        <td valign="top">silver* </td>
        <td valign="top">wood* </td>
    </tr>
</table>

<p>*These entries come into play with the vulnerabilities of
mobs. If a mob is flagged vulnerable to one of these materials,
or are inherently vulnerable, like elves are to iron, undead are
to silver, etc., weapons made of these materials will do double
damage to that mob. Items that may be eaten to bestow a
&quot;magic spell&quot;, need to be made of pill material. Items
that may be eaten to satisfy hunger, need to be made of food
material. Objects made of gold material will be autolooted just
as coins are, even if the player has their autoloot toggled off.
This can be useful if you have a devious mind and want to force a
cursed, no-drop object to be looted by all players kill the mob
that has it.</p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2"><b><u>OBJECT TYPES</u></b><b> </b></font></td>
        <td><font size="2"><b><u>VALUE</u></b><b> </b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b><b> </b></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_LIGHT</font></td>
        <td>1</td>
        <td><font size="2">Item used as a light source </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_SCROLL</font></td>
        <td>2</td>
        <td><font size="2">Item is a scroll (recite)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WAND</font></td>
        <td>3</td>
        <td><font size="2">Item is a wand (zap)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_STAFF</font></td>
        <td>4</td>
        <td><font size="2">Item is a staff (brandish)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAPON </font></td>
        <td>5</td>
        <td><font size="2">Item is a weapon (wield)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TREASURE </font></td>
        <td>8</td>
        <td><font size="2">Item may be sold to shopkeeper like
        Jeweler </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ARMOR</font></td>
        <td>9</td>
        <td><font size="2">Item is armor (wear)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_POTION</font></td>
        <td>10</td>
        <td><font size="2">Item is a potion (quaff) </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CLOTHING </font></td>
        <td>11</td>
        <td><font size="2">Item is armor (wear, but low A/C
        value) </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FURNITURE </font></td>
        <td>12</td>
        <td><font size="2">Item is just a prop, can&#146;t be
        taken, sac&#146;d or sold </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TRASH</font></td>
        <td>13</td>
        <td><font size="2">Item is junk, not sellable nor
        saccable</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CONTAINER </font></td>
        <td>15</td>
        <td><font size="2">Item is a container (put objects in
        it)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_DRINK_CON </font></td>
        <td>17</td>
        <td><font size="2">Item is a drink container (drink)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_KEY</font></td>
        <td>18</td>
        <td><font size="2">Item is a key for locked objects and
        doors</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FOOD</font></td>
        <td>19</td>
        <td><font size="2">Item is food (eat)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MONEY</font></td>
        <td>20</td>
        <td><font size="2">Item is money (coins/gold)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_BOAT</font></td>
        <td>22</td>
        <td><font size="2">Item is a boat, needed to cross water</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CORPSE_NPC </font></td>
        <td>23</td>
        <td><font size="2">Item is a corpse, may contain items</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FOUNTAIN</font></td>
        <td>25</td>
        <td><font size="2">Item is a fountain (drink/fill)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_PILL</font></td>
        <td>26</td>
        <td><font size="2">Item is a pill (eat)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MAP</font></td>
        <td>28</td>
        <td><font size="2">Item is a map when looked at, the
        description will show an ascii map of an area,
        bought/sold in map shops</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_SCUBA_GEAR </font></td>
        <td>29</td>
        <td><font size="2">Item is scuba gear, needed for
        underwater areas</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_PORTAL</font></td>
        <td>30</td>
        <td><font size="2">Item is a portal (enter)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MANIPULATION </font></td>
        <td>31</td>
        <td><font size="2">Item may be manipulated to make
        something happen</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_SADDLE</font></td>
        <td>33</td>
        <td><font size="2">Item is a saddle, needed to mount mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ACTION</font></td>
        <td>37</td>
        <td><font size="2">Similar to manipulation, in that
        object must be interacted with</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>OBJECT FLAGS</u></b><b> </b></font></td>
        <td><font size="3"><b><u>FLAG</u></b><b> </b></font></td>
        <td><font size="3"><b><u>DESCRIPTION</u></b> </font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_GLOW</font></td>
        <td>A</td>
        <td><font size="2">Gives item the (GLOWING) flag.
        Normally associated with magic items and light providing
        objects</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_HUM</font></td>
        <td>B</td>
        <td><font size="2">Gives item the (HUMMING) flag.
        Normally associated with magic items or items that
        contain power</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_DARK</font></td>
        <td>C</td>
        <td><font size="2">Gives item the (DARK) flag. Normally
        associated with evil aligned items.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_LOCK</font></td>
        <td>D</td>
        <td><font size="2">Gives item the (LOCKED) flag. Requires
        either pick skill or a designated key item to unlock and
        open.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_EVIL</font></td>
        <td>E</td>
        <td><font size="2">Gives item red aura with detect evil,
        should be used in conjuction with ITEM_ANTI_GOOD flag
        below</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_INVIS</font></td>
        <td>F</td>
        <td><font size="2">Makes object invisible. Detect
        invisible spell/potion needed to see it.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MAGIC</font></td>
        <td>G</td>
        <td><font size="2">Gives item magical flag with detect
        magic. Normally used in conjunction with GLOW or HUM
        flags.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_NODROP</font></td>
        <td>H</td>
        <td><font size="2">Makes item un-droppable from
        inventory.. i.e., cursed. Also normally used with GLOW or
        HUM flags.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_BLESS</font></td>
        <td>I</td>
        <td><font size="2">Gives item &quot;holy&quot; properties
        and gives blue aura with detect good.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ANTI_GOOD</font></td>
        <td>J</td>
        <td><font size="2">Makes item zap good aligned PCs <strong>AND</strong>
        Mobs, causing them to drop it.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ANTI_EVIL</font></td>
        <td>K</td>
        <td><font size="2">Makes item zap evil aligned PCs <strong>AND</strong>
        Mobs, causing them to drop it.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ANTI_NEUTRAL</font></td>
        <td>L</td>
        <td><font size="2">Makes item zap neutral aligned PCs <strong>AND</strong>
        Mobs, causing them to drop it.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_NOREMOVE</font></td>
        <td>M</td>
        <td><font size="2">Makes item non-removeable once worn,
        held or wielded.. i.e., cursed.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_INVENTORY</font></td>
        <td>N</td>
        <td><font size="2">Makes item NOT take up inventory item
        slot <strong>*USE SPARINGLY AND WITH PERMISSION*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_NOPURGE</font></td>
        <td>O</td>
        <td><font size="2">Makes item non-purgeable by IMMs..
        normally used for fountains, donation pits, etc.</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ROT_DEATH</font></td>
        <td>P</td>
        <td><font size="2">Makes item decay after certain amount
        of ticks</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_BOUNCE</font></td>
        <td>S</td>
        <td><font size="2">Makes item randomly tport from room to
        room within a single area</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TPORT</font></td>
        <td>T</td>
        <td><font size="2">Makes item randomly tport from area to
        area</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_NOIDENTIFY</font></td>
        <td>U</td>
        <td><font size="2">Makes item immune to identify spell</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_NOLOCATE </font></td>
        <td>V</td>
        <td><font size="2">Makes item immune to locate object
        spell</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_RACE_RESTRICTED </font></td>
        <td>W</td>
        <td><font size="2">Makes item only wearable by specified
        race (requires a ITEM_FLAGS2 below)</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FLAGS2</font></td>
        <td>Z</td>
        <td><font size="2">Tells game that ITEM_FLAG2 is to
        follow</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>ITEM FLAGS2</u></b></font></td>
        <td><font size="3"><b><u>FLAG</u></b><b> </b></font></td>
        <td><font size="3"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_HUMAN_ONLY</font></td>
        <td>A</td>
        <td><font size="2">Item only wearable by human players <strong>AND</strong>
        mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_HALFLING_ONLY</font></td>
        <td>B</td>
        <td><font size="2">Item only wearable by halfling players
        <strong>AND</strong> mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_DWARF_ONLY</font></td>
        <td>C</td>
        <td><font size="2">Item only wearable by dwarven players <strong>AND</strong>
        mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_ELF_ONLY</font></td>
        <td>D</td>
        <td><font size="2">Item only wearable by elven players <strong>AND</strong>
        mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_SAURIAN_ONLY</font></td>
        <td>E</td>
        <td><font size="2">Item only wearable by saurian players <strong>AND</strong>
        mobs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_ADD_INVIS</font></td>
        <td>F</td>
        <td><font size="2">Item bestows invisibility on player
        when worn, held or wielded. *</font><font size="1"><strong>USE
        ONLY WITH PERMISSION</strong></font><font size="2"><strong>*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_ADD_DETECT_INVIS </font></td>
        <td>G</td>
        <td><font size="2">Item bestows detect invis on player
        when worn, held or wielded. *</font><font size="1"><strong>USE
        ONLY WITH PERMISSION</strong></font><font size="2"><strong>*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM2_ADD_FLY</font></td>
        <td>H</td>
        <td><font size="2">Item bestows fly on player when worn,
        held or wielded. *</font><font size="1"><strong>USE ONLY
        WITH PERMISSION</strong></font><font size="2"><strong>*</strong></font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="3"><b><u>WEAR FLAGS</u></b></font></td>
        <td><font size="3"><b><u>FLAG</u></b></font></td>
        <td><font size="3"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TAKE</font></td>
        <td>A</td>
        <td><font size="2">Required to allow item to be picked up
        or gotten</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_FINGER</font></td>
        <td>B</td>
        <td><font size="2">Item is wearable upon fingers</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_NECK</font></td>
        <td>C</td>
        <td><font size="2">Item is wearable upon neck</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_BODY</font></td>
        <td>D</td>
        <td><font size="2">Item is wearable upon body</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_HEAD</font></td>
        <td>E</td>
        <td><font size="2">Item is wearable upon head</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_LEGS</font></td>
        <td>F</td>
        <td><font size="2">Item is wearable upon legs</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_FEET</font></td>
        <td>G</td>
        <td><font size="2">Item is wearable upon feet</font></td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAR_HANDS</font></td>
        <td>H</td>
        <td>Item is wearable upon hands</td>
    </tr>
    <tr>
        <td>ITEM_WEAR ARMS</td>
        <td>I</td>
        <td>Item is wearable upon arms</td>
    </tr>
    <tr>
        <td>ITEM_WEAR_SHIELD</td>
        <td>J</td>
        <td>Item is wearable as a shield</td>
    </tr>
    <tr>
        <td>ITEM_WEAR_ABOUT</td>
        <td>K</td>
        <td>Item is worn about body</td>
    </tr>
    <tr>
        <td>ITEM_WEAR_WAIST</td>
        <td>L</td>
        <td>Item is worn about waist</td>
    </tr>
    <tr>
        <td>ITEM_WEAR_WRIST</td>
        <td>M</td>
        <td>Item is wearable upon wrists</td>
    </tr>
    <tr>
        <td>ITEM_WIELD</td>
        <td>N</td>
        <td>Item is wieldable as a weapon</td>
    </tr>
    <tr>
        <td>ITEM_HOLD</td>
        <td>O</td>
        <td>Item may be held</td>
    </tr>
    <tr>
        <td>ITEM_TWO_HANDS</td>
        <td>P</td>
        <td>Item requires two hands free to wield. Requires
        weapon type of <font size="1">WEAPON_TWO_HANDS</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>WEAPON CLASS</u></b></font></td>
        <td><font size="2"><b><u>VALUE</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_EXOTIC</font></td>
        <td>0</td>
        <td><font size="2">Object is an exotic type weapon.
        Immune to enchantment spells.</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_SWORD</font></td>
        <td>1</td>
        <td><font size="2">Object is a sword</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_DAGGER</font></td>
        <td>2</td>
        <td><font size="2">Object is a dagger</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_SPEAR</font></td>
        <td>3</td>
        <td><font size="2">Object is a spear</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_MACE</font></td>
        <td>4</td>
        <td><font size="2">Object is a mace</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_AXE</font></td>
        <td>5</td>
        <td><font size="2">Object is an axe</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_FLAIL</font></td>
        <td>6</td>
        <td><font size="2">Object is a flail</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_WHIP</font></td>
        <td>7</td>
        <td><font size="2">Object is a whip</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_POLEARM</font></td>
        <td>8</td>
        <td><font size="2">Object is a polearm</font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_BOW</font></td>
        <td>9</td>
        <td><font size="2">Object is a bow. Archery skill
        required to wield.</font></td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2"><b><u>WEAPON TYPES</u></b></font></td>
        <td><font size="2"><b><u>FLAGS</u></b></font></td>
        <td><font size="2"><b><u>DESCRIPTION</u></b></font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_FLAMING</font></td>
        <td>A</td>
        <td>Weapon does fire type damage</td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_FROST</font></td>
        <td>B</td>
        <td>Weapon does cold type damage</td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_VAMPIRIC</font></td>
        <td>C</td>
        <td>Weapon saps victim and gives to wielder in addition
        to normal damage <font size="3"><strong>*disabled*</strong></font></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_SHARP</font></td>
        <td>D</td>
        <td>Weapon never needs sharpening (repair) <strong>*disabled*</strong></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_VORPAL</font></td>
        <td>E</td>
        <td>Weapon has minor chance of decapitation (fatality) <strong>*disabled*</strong></td>
    </tr>
    <tr>
        <td><font size="2">WEAPON_TWO_HANDS</font></td>
        <td>F</td>
        <td>Weapon requires two hands to wield. Also requires
        wear flag of<font size="2"> ITEM_TWO_HANDS</font></td>
    </tr>
</table>

<p><font size="3"><b><u>APPLY TYPES</u></b><u> (for the 'A'
section of #OBJECTS):</u></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">APPLY_STR </font></td>
        <td>1 </td>
        <td>Applies specified amount to natural strength of
        player </td>
    </tr>
    <tr>
        <td><font size="2">APPLY_DEX</font></td>
        <td>2 </td>
        <td>Applies specified amount to natural dexterity of
        player </td>
    </tr>
    <tr>
        <td><font size="2">APPLY_INT </font></td>
        <td>3</td>
        <td>Applies specified amount to natural intelligence of
        player </td>
    </tr>
    <tr>
        <td><font size="2">APPLY_WIS </font></td>
        <td>4</td>
        <td>Applies<font size="3"> specified amount to natural
        intelligence of player</font></td>
    </tr>
    <tr>
        <td><font size="2">APPLY_CON </font></td>
        <td>5</td>
        <td>Applies specified amount to natural constitution of
        player </td>
    </tr>
    <tr>
        <td><font size="2">APPLY_SEX </font></td>
        <td>6</td>
        <td>Shifts player's sex by amount.. i.e., if player is
        male, and apply amount is 2, player would become neuter. </td>
    </tr>
    <tr>
        <td><font size="2">APPLY_MANA </font></td>
        <td>12 </td>
        <td>Applies specified amount to natural mana of player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_HIT</font></td>
        <td>13</td>
        <td>Applies specified amount to natural to hitpoints of
        player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_MOVE</font></td>
        <td>14</td>
        <td>Applies specified amount to natural endurance of
        player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_AC</font></td>
        <td>17</td>
        <td>Applies specified amount to natural armor class of
        player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_HITROLL </font></td>
        <td>18</td>
        <td>Applies specified amount to natural hitroll of player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_DAMROLL </font></td>
        <td>19</td>
        <td>Applies specified amount to natural damroll of player</td>
    </tr>
    <tr>
        <td><font size="2">APPLY_SAVING_BREATH </font></td>
        <td>23 </td>
        <td>Applies specified amount to natural save vs breath
        roll of player. <strong>*Use sparingly*</strong></td>
    </tr>
    <tr>
        <td><font size="2">APPLY_SAVING_SPELL</font></td>
        <td>24</td>
        <td>Applies specified amount to natural save vs spell
        roll of player. <strong>*Use sparingly*</strong></td>
    </tr>
</table>

<p><font size="3"><b><u>CONTAINER FLAGS</u></b><u> (if OBJECT
TYPE is container only)</u></font></p>

<p><font size="3"><strong><u>These values are added together to
achieve total &quot;condition&quot;.</u></strong></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">CONT_CLOSEABLE </font></td>
        <td>1 </td>
        <td>Item may be closed </td>
    </tr>
    <tr>
        <td><font size="2">CONT_PICKPROOF </font></td>
        <td>2</td>
        <td>Item's lock may not be picked </td>
    </tr>
    <tr>
        <td><font size="2">CONT_CLOSED</font></td>
        <td>4 </td>
        <td>Item's natural state is closed</td>
    </tr>
    <tr>
        <td><font size="2">CONT_LOCKED</font></td>
        <td>8</td>
        <td>Item's natural state is locked</td>
    </tr>
    <tr>
        <td><font size="2">CONT_TRAPPED</font></td>
        <td>16 </td>
        <td>Item is set with a trap upon it that will go off when
        attempt is made to open it. </td>
    </tr>
</table>

<p><font size="3"><b><u>LIQUID VALUES FOR DRINK CONTAINERS</u></b><u>
(value2 on the value line)</u></font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">LIQ_WATER </font></td>
        <td>0 </td>
        <td>Liquid in container is water.. quenches thirst
        normally.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_BEER</font></td>
        <td>1</td>
        <td>Liquid in container is alcohol. Makes drinker drunker
        as more is drank. (say that 10 times fast)</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_WINE</font></td>
        <td>2 </td>
        <td>Same as above</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_ALE</font></td>
        <td>3 </td>
        <td>Same as above</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_DARK_ALE </font></td>
        <td>4</td>
        <td>Same as above</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_WHISKEY</font></td>
        <td>5</td>
        <td>Same as above</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_LEMONADE </font></td>
        <td>6</td>
        <td>Liquid in container is lemonade.. quenches thirst
        better.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_FIREBREATHER </font></td>
        <td>7</td>
        <td>Liquid in container is alcohol. Makes drinker
        instantly drunk with one drink.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_LOCAL_SPECIALTY </font></td>
        <td>8</td>
        <td>Liquid in container is alcohol. Makes drinker
        instantly drunk with one drink.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_SLIME_MOLD_JUICE </font></td>
        <td>9</td>
        <td>Liquid in container is disgusting and makes drinker
        sick (poison).</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_MILK</font></td>
        <td>10 </td>
        <td>Liquid in container, in addition to quenching thirst,
        also applies slightly to hunger.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_TEA</font></td>
        <td>11</td>
        <td>Quenches thirst normally, but random and rare minor
        damage due to burning.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_COFFEE</font></td>
        <td>12 </td>
        <td>Quenches thirst normally, but random and rare minor
        damage due to burning.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_BLOOD</font></td>
        <td>13</td>
        <td>Quenches thirst and hunger for vampires.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_SALT_WATER</font></td>
        <td>14</td>
        <td>Adds to thirst level, making drinker more thirsty
        rather than less.</td>
    </tr>
    <tr>
        <td><font size="2">LIQ_COLA</font></td>
        <td>15</td>
        <td>Quenches thirst normally.. causes random belching.</td>
    </tr>
</table>

<p><font size="3"><b>NOTE</b>: LIQUID VALUES greater than 15
default to LIQ_WATER; so just use the above values, 0 to 15, for
your liquid type in drink container objects.</font></p>

<p><font size="3">Value lines and format for all the various
OBJECT TYPES are as follows:</font></p>

<p><font size="4">&lt;value0&gt; &lt;value1&gt; &lt;value2&gt;
&lt;value3&gt; &lt;value4&gt;</font></p>

<p><font size="3"><b>NOTE</b>: if a value is shown to be
'unused', place a zero, '0', for that value. <strong>DO NOT</strong>
skip it or leave it blank.</font></p>

<p><font size="3"><strong>ITEM_LIGHT:</strong></font><font
size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt; &lt;Hours of
light available&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3">Hours are measured in game hours, where 0 =
dead and 9999 = infinite</font></p>

<p><font size="3"><strong>ITEM_SCROLL:</strong></font><font
size="4"><br>
</font><font size="3">&lt;spell lvl&gt; &lt;spell 1&gt; &lt;spell
2&gt; &lt;spell 3&gt; &lt;unused&gt;</font></p>

<p><font size="3"><b>NOTE</b>: spell lvl is the level at which
the spell will be cast, NOT the level of the reader of the
scroll.</font></p>

<p><font size="3"><b>NOTE</b>: spell # is the number unique spell
slot to that particular spell in the game. If you are an immortal
with the 'vnum' command, you can type 'vnum spell &lt;spell
name&gt;' to get the slot number. If not, ask an immortal for the
slot number of a particular spell you may be thinking of using
for a potion, scroll, wand, staff, or pill in your #OBJECTS
section.</font></p>

<p><font size="3"><strong>ITEM_WAND:</strong></font><font
size="4"><br>
</font><font size="3">&lt;spell lvl&gt; &lt;maximum charges&gt;
&lt;current charges&gt; &lt;sn&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_STAFF:</strong></font><font
size="4"><br>
</font><font size="3">&lt;spell lvl&gt; &lt;maximum charges&gt;
&lt;current charges&gt; &lt;sn&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_WEAPON:</strong></font><font
size="4"><br>
</font><font size="3">&lt;weapon class&gt; &lt;# dice&gt;
&lt;type of dice&gt; &lt;damage type&gt; &lt;weapon type&gt;</font></p>

<p><font size="3"><strong>ITEM_TREASURE:</strong></font><font
size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_ARMOR:</strong></font><font
size="4"><br>
</font><font size="3">&lt;value for pierce&gt; &lt;value for
bash&gt; &lt;value for slash&gt; &lt;value for magic&gt;
&lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_POTION:</strong></font><font
size="4"><br>
</font><font size="3">&lt;spell lvl&gt; &lt;sn1&gt; &lt;sn2&gt;
&lt;sn3&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_PILL:</strong></font><font
size="4"><br>
</font><font size="3">&lt;spell lvl&gt; &lt;spell 1&gt; &lt;spell
2&gt; &lt;spell 3&gt; &lt;unused&gt;</font></p>

<p><font size="3"><b>NOTE</b>: Potions, pills, and scrolls can
have up to 3 spells in them. If you use only 1 or 2, put a zero
for each of the unused values. See ITEM_SCROLL above for further
explaination.</font></p>

<p><font size="3"><strong>ITEM_FURNITURE:</strong></font><font
size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><b>NOTE</b>: the benches in Southern Midgaard
are an example of a furniture object, they basically just sit
there.</font></p>

<p><font size="3"><strong>ITEM_TRASH:</strong></font><font
size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_CONTAINER:</strong></font><font
size="4"><br>
</font><font size="3">&lt;wgt. capacity&gt; &lt;container
FLAGS&gt; &lt;key vnum&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><b>NOTE</b>: Use the Container FLAGS listed
earlier for this value; the key vnum is ONLY USED if there is a
key to unlock the container - otherwise put a zero for that
value.</font></p>

<p><font size="3"><strong>ITEM_DRINK_CONTAINER:</strong></font><font
size="4"><br>
</font><font size="3">&lt;liquid capacity&gt; &lt;current
quantity&gt; &lt;liquid #&gt; &lt;0&gt; &lt;unused&gt;</font></p>

<p><font size="3"><b>NOTE</b>: if the third value is a NON-ZERO
number, the drink is poisoned</font></p>

<p><font size="3"><b>NOTE</b>: Use already existing drink
containers in the game to get an idea as to a reasonable liquid
capacity. For example, the water skin for sale at the Grocer's
Shop in Dresden has a liquid capacity of 20. Additionally, the
'liquid #' value here tells whether it is beer, water, ale, etc.,
that is in the container. I have provided a listing above for the
liquid type values.</font></p>

<p><font size="3"><strong>ITEM_KEY:</strong></font><font size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_FOOD:</strong></font><font
size="4"><br>
</font><font size="3">&lt;hours of food value&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>Note:</strong> &lt;hours of food
value&gt; is in game hours, and denotes the amount of hours the
player's hunger will be satisfied before being hungry again.</font></p>

<p><font size="3"><strong>ITEM_MONEY:</strong></font><font
size="4"><br>
</font><font size="3">&lt;value in gold&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_BOAT:</strong></font><font
size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_FOUNTAIN:</strong></font><font
size="4"><br>
</font><font size="3">&lt;capacity&gt; &lt;current quantity&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3">&lt;capacity&gt; is total hours of drink
available within, normally 9999, and &lt;current quantity&gt; is
how much is left in it and normally should be the same value as
&lt;capacity&gt;.</font></p>

<p><font size="3"><strong>ITEM_MAP:</strong></font><font size="4"><br>
</font><font size="3">&lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_PORTAL:</strong></font></p>

<p><font size="3">&lt;portal type&gt; &lt;to_room&gt;
&lt;timer&gt; &lt;closeable/lockable&gt; &lt;key vnum&gt;</font></p>

<p><strong>NOTE:</strong><font size="4"><br>
</font><strong>&lt;to_room&gt;</strong> is the room VNUM that
portal leads to.<font size="4"><br>
</font><strong>&lt;timer&gt;</strong> is the amount of ticks
until the portal activates, otherwise use a ZERO (0) for its
value.<font size="4"><br>
</font><strong>&lt;closeable/lockable&gt;</strong> only applies
to portals that you want to be able to close and/or lock the
portal. Otherwise, use a ZERO (0) for its value . Don't forget,
to create and load an ITEM_KEY object.<font size="4"><br>
</font><strong>&lt;key vnum&gt;</strong> is only used if
closeable/lockable values were used, otherwise use a ZERO (0) for
its value.</p>

<p><font size="4">Portal type Values:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td>1 </td>
        <td><font size="2">Portal like one in Hall of Hero's.
        &lt;to_room and timer not used.&gt; </font></td>
    </tr>
    <tr>
        <td>4 </td>
        <td><font size="2">Portal used to create crystal ball
        objects. &lt;timer optional&gt;</font></td>
    </tr>
    <tr>
        <td>5 </td>
        <td><font size="2">Portal like berry to smurfs, clown to
        froboz, etc.</font></td>
    </tr>
    <tr>
        <td>6 </td>
        <td><font size="2">Portal is Closeable/Lockable, but
        functions like type 5 portal otherwise</font></td>
    </tr>
</table>

<p><font size="3"><strong>ITEM_MANIPULATION:</strong></font><font
size="4"><br>
</font><font size="3">&lt;type of manip&gt; &lt;room goes to&gt;
&lt;door&gt; &lt;object state&gt; &lt;special&gt;</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td>Value </td>
        <td>Type of manip </td>
    </tr>
    <tr>
        <td>1</td>
        <td>Flip</td>
    </tr>
    <tr>
        <td>2</td>
        <td>Move</td>
    </tr>
    <tr>
        <td>3</td>
        <td>Pull</td>
    </tr>
    <tr>
        <td>4</td>
        <td>Push</td>
    </tr>
    <tr>
        <td>5</td>
        <td>Turn</td>
    </tr>
    <tr>
        <td>6</td>
        <td>Climb Up</td>
    </tr>
    <tr>
        <td>7</td>
        <td>Climb Down</td>
    </tr>
    <tr>
        <td>8</td>
        <td>Crawl</td>
    </tr>
    <tr>
        <td>9</td>
        <td>Jump</td>
    </tr>
</table>

<p><strong>&lt;Room goes to&gt;</strong> is the room VNUM that
the object opens a secret door to.<font size="4"><br>
</font><strong>&lt;door&gt;</strong> is the direction of the door
that is opened.<font size="4"><br>
</font><strong>&lt;object state&gt;</strong> <font size="3">This
is the state of the object. 1 is up, 2 is down. Some objects do
not use this value, but a value of 1 or 2 needs to be here
regardless, except if special 3 is used, then must be a 0. If
type of manip is jump</font><font size="2">: </font><font
size="3">1 down, 2 up, 3 across, 4 off, 5 on</font><font size="4"><br>
</font><font size="3"><strong>&lt;special&gt;</strong></font><font
size="4"> </font><font size="3">This value is always ZERO (0)..</font></p>

<p><font size="3"><strong>ITEM_CASTLE_RELIC:</strong></font></p>

<p><font size="3">&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_SADDLE:</strong></font></p>

<p><font size="3">&lt;unused&gt; &lt;unused&gt; &lt;unused&gt;
&lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3"><strong>ITEM_ACTION:</strong></font></p>

<p><font size="3">&lt;type&gt; &lt;unused&gt; &lt;poison duration
in game hours, otherwise 0&gt; &lt;unused&gt; &lt;unused&gt;</font></p>

<p><font size="3">Action Item types:</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td>1 </td>
        <td>Recall </td>
        <td>Causes player to instantly recall. </td>
    </tr>
    <tr>
        <td>2 </td>
        <td>Death</td>
        <td>Causes player to be killed instantly. </td>
    </tr>
    <tr>
        <td>3</td>
        <td>Poison</td>
        <td>Causes player to be instantly poisoned, with no save
        vs poison roll, unless player's race is immune to poison.
        </td>
    </tr>
</table>

<p><font size="3">ITEM WEAR MESSAGE</font></p>

<p><font size="3">There is now a new flag that you can use in the
#OBJECTS section of an area file. Like extended descriptions, you
can now add a message to objects that will be triggered by
equiping the object... to see it in practical use I have included
the following object from the Assassin&#146;s Guild:</font></p>

<p><font size="3">#QQ01</font><font size="4"><br>
</font><font size="3">soul dagger~</font><font size="4"><br>
</font><font size="3">The Soul Dagger~</font><font size="4"><br>
</font><font size="3">A very cold looking blade lies on the
floor.~</font><font size="4"><br>
</font><font size="3">adamantite~</font><font size="4"><br>
</font><font size="3">5 CJ AN</font><font size="4"><br>
</font><font size="3">2 7 10 3 B</font><font size="4"><br>
</font><font size="3">53 15 250 P</font><font size="4"><br>
</font><font size="3">A</font><font size="4"><br>
</font><font size="3">1 -3</font><font size="4"><br>
</font><font size="3">T &lt;==== This is where this new flag
entry goes</font><font size="4"><br>
</font><font size="3">$p gives $n the rough side of its blade for
wielding it!~ &lt;==== This is the message that players in the
room will see</font><font size="4"><br>
</font><font size="3">$p smirks at the gall you have in wielding
it!~ &lt;==== This is the message the wearer will see</font><font
size="4"><br>
<br>
</font><font size="3">NOTE: $p will display the objects name in
the message</font><font size="4"><br>
</font><font size="3">$n will display the player's name in the
message</font></p>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
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
