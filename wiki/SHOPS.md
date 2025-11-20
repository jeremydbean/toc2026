

<p><font size="3">If you intend on having shops in your area,
then you will need a #SHOPS section. This section, in fact, is
the easiest of all the sections in an area to do, and takes very
little time.</font></p>

<p><font size="3">First, I'll provide an example from the
Dresden.are area file of some of the shops from Dresden's #SHOPS
section:</font></p>

<table border="0">
    <tr>
        <td><font size="2">#SHOPS</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td><font size="2">QQ00 2 3 4 10 0 105 15 0 23 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Wizard </font></td>
    </tr>
    <tr>
        <td><font size="2">QQ01 0 0 0 0 0 110 100 0 23 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Baker</font></td>
    </tr>
    <tr>
        <td><font size="2">QQ02 1 8 13 15 19 150 40 0 23 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Grocer </font></td>
    </tr>
    <tr>
        <td><font size="2">QQ03 5 0 0 0 0 130 40 0 23 </font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Weaponsmith </font></td>
    </tr>
    <tr>
        <td><font size="2">QQ04 9 0 0 0 0 100 50 0 23</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Armourer</font></td>
    </tr>
    <tr>
        <td><font size="2">QQ06 22 0 0 0 0 120 90 6 22</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td><font size="2">; The Captain</font></td>
    </tr>
    <tr>
        <td><font size="2">0</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
</table>

<p><font size="3"><b>IMPORTANT!!</b>: You end your #SHOPS section
with a ZERO (0) on the line after the last shop.</font></p>

<p><font size="3">The syntax of the #SHOPS is as follows:</font></p>

<p><font size="3"><strong>&lt;mob vnum&gt; &lt;trade0&gt;
&lt;trade1&gt; &lt;trade2&gt; &lt;trade3&gt; &lt;trade4&gt;
&lt;buy %&gt; &lt;sell %&gt; &lt;open hr&gt;&lt;close hr&gt;</strong></font></p>

<p><font size="3">The first value, the mobile-vnum, is the
'keeper', or the mobile who is the shopkeeper. ALL MOBILES with
that vnum will be shopkeepers.</font></p>

<p><font size="3">The trade0 through trade4 are item types which
the shopkeeper will buy. Unused slots should have a '0' in them';
for instance, a shopkeeper who doesn't buy anything would have
five zeroes. The item types are the same values from the #OBJECTS
section, in the OBJECT TYPE table. I am providing this table
again, for this purpose, at the end of this #SHOPS help section.</font></p>

<p><font size="3">The 'buy %' number is a markup for players
buying the item, in percentage points. 100 is nominal price; 150
is 50% markup, and so on. The 'sell %l' number is a markdown for
players selling the item, in percentage points. 100 is nominal
price, 75 is 25% markdown, and so on. The buying markup should be
at least 100, generally greater, and the selling markdown should
be no more than 100, generally lower.</font></p>

<p><font size="3">The 'open-hour' and 'close-hour' numbers define
the hours when the shopkeeper will do business. For a 24-hour
shop, these numbers would be 0 and 23.</font></p>

<p><font size="3">Everything beyond 'close-hour' to the end of
the line is taken to be a comment.</font></p>

<p><font size="3">Note that there is no room number for a shop.
Just load the shopkeeper mobile in to the room of your choice,
via that #RESETS section, and make the mobile a sentinel in the
ACT-FLAGS section of the mobile in #MOBILES. Or, for a wandering
shopkeeper, just make it non-sentinel.</font></p>

<p><font size="3">The objects the shopkeeper sells are exactly
those loaded by the 'G' reset command in #RESETS for that
shopkeeper. These items replenish automatically. If a player
sells an object to a shopkeeper, the shopkeeper will keep it for
resale if he, she, or it doesn't already have an identical
object. The items a player sells to a shopkeeper, however, do not
replenish.</font></p>

<p><font size="3"><b><u>OBJECT TYPES</u></b> (items a shopkeeper
will buy from player):</font></p>

<table border="2" cellpadding="0">
    <tr>
        <td><font size="2">ITEM_LIGHT </font></td>
        <td>1 </td>
    </tr>
    <tr>
        <td><font size="2">ITEM_SCROLL </font></td>
        <td>2</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WAND</font></td>
        <td>3</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_STAFF</font></td>
        <td>4</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_WEAPON </font></td>
        <td>5</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TREASURE </font></td>
        <td>6</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_ARMOR</font></td>
        <td>7</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_POTION</font></td>
        <td>8</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CLOTHING </font></td>
        <td>9</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FURNITURE </font></td>
        <td>10</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_TRASH</font></td>
        <td>11</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CONTAINER </font></td>
        <td>12</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_DRINK_CON </font></td>
        <td>13</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_KEY</font></td>
        <td>14</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_FOOD</font></td>
        <td>15</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MONEY</font></td>
        <td>16</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_BOAT</font></td>
        <td>17</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_CORPSE_NPC </font></td>
        <td>23</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_PILL</font></td>
        <td>24</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_MAP</font></td>
        <td>25</td>
    </tr>
    <tr>
        <td><font size="2">ITEM_SCUBA_GEAR </font></td>
        <td>26</td>
    </tr>
</table>

<p><font size="3"><b>NOTE</b>: In general, when designing a
mobile as a shopkeeper in the #MOBILES section, you should make
him/her IMMUNE to all forms of attack by having the mobile immune
to magic, disease, poison, and weapons using the IMM_BITS in the
immunities section of the mob in #MOBILES. Also, it is generally
a good idea to make these mobiles NOPURGE by having an 'ACT_FLAG'
of ACT_NOPURGE for the mobile in the #MOBILES section. After all,
you don't want your players killing the shopkeepers, or a
purge-happy immortal accidentally purging the shopkeeper with a
purge command.</font></p>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
<a href="http://www.ofchaos.com/Building/objects.html">#OBJECTS</a>
<a href="http://www.ofchaos.com/Building/rooms.html">#ROOMS</a>
<a href="http://www.ofchaos.com/Building/resets.html">#RESETS</a>
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
