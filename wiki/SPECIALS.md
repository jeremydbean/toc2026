
<p><font size="3">Like the #RESETS section, the #SPECIALS section
has one command per line.</font></p>

<p><font size="3">This section defines special functions
(spec-fun's) for mobiles. A spec-fun is a C function which gives
additional behavior to all mobiles with a given vnum, such as the
peripatetic mayor, the beholder casting spells in combat, Tiamat
the dragon breathing her breath weapons in combat, and the Grand
Mistress teleporting characters she is fighting.</font></p>

<p><font size="3">The 'M' command assigns 'spec-fun' to all
mobiles of that vnum. An 'M' line may have a comment at the end.</font></p>

<p><font size="3">Every three seconds, the server function
'mobile_update' examines every mobile in the game. If the mobile
has an associated spec-fun, then 'mobile_update' calls that
spec=fun with a single parameter, the 'ch' pointer for that mob.
The spec-fun returns TRUE if the mobile did something, or FALSE
if it did not. If the spec-fun returns TRUE, then further
activity by that mobile is suppressed. All this just basically
means that the game checks periodically for mobiles with
spec-fun's and causes them to act out their assigned functions,
either while wandering about Dresden and locking the gates, as
the mayor does, or while in combat and casting spells and breath
weapons, as Tiamat, or the Beholder do.</font></p>

<p><font size="3">For this help file, I am not including material
on how to add a NEW special function to the code. That
information can be found elsewhere, and needs to be coded by the
IMP into the 'C' code itself. However, below you can see how to
use ALREADY existing spec-funs for your mobiles. I have also
provided a listing of the spec-funs available in the game so far.</font></p>

<p><font size="3"><b>NOTE:</b> As spec_fun's DO add (much more
than other things) to lag in the game, try NOT to OVER DO IT.
Feel free to use a #SPECIALS section, but don't make 100
different dragon or spell-casting type mobiles each with special
functions!</font></p>

<p><font size="3">Example of #SPECIALS, as found in Dresden.are
area file:</font></p>

<table border="0">
    <tr>
        <td><font size="3">#SPECIALS</font></td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>;This begins the #SPECIALS section</td>
    </tr>
    <tr>
        <td>M </td>
        <td><font size="2">QQ00 </font></td>
        <td><font size="2">spec_cast_mage </font></td>
        <td>;Dresden's Wizard</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ05</font></td>
        <td><font size="2">spec_thief</font></td>
        <td>;Thief on Warrior's Way </td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ11</font></td>
        <td><font size="2">spec_executioner </font></td>
        <td>;The Watcher</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ12 </font></td>
        <td><font size="2">spec_cast_adept </font></td>
        <td>;Healer at Pit</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ20 </font></td>
        <td><font size="2">spec_cast_mage</font></td>
        <td>;Mage Guildmaster</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ60 </font></td>
        <td><font size="2">spec_guard</font></td>
        <td>;Cityguards</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ61</font></td>
        <td><font size="2">spec_janitor</font></td>
        <td>;Wandering Janitors</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ62</font></td>
        <td><font size="2">spec_fido</font></td>
        <td>;Beastly Fidos</td>
    </tr>
    <tr>
        <td>M</td>
        <td><font size="2">QQ43</font></td>
        <td><font size="2">spec_mayor</font></td>
        <td>;Mayor of Dresden</td>
    </tr>
    <tr>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
    </tr>
    <tr>
        <td>#$</td>
        <td>&nbsp;</td>
        <td>&nbsp;</td>
        <td>This marks the end of the area file</td>
    </tr>
</table>

<p><font size="3">The syntax is simple, and is as follows:</font></p>

<p><font size="3"><strong>M &lt;mobile-vnum&gt; &lt;spec-fun&gt;</strong></font></p>

<p><font size="3">The mobile vnum is the vnum of the mobile with
that particular special function.</font></p>

<p><font size="3"><b><u>List of SPEC-FUN's</u></b>:</font></p>

<p><font size="3">spec_breath_any</font> (randomly breathes all
of the breath specials below)<br>
<font size="3">spec_breath_acid</font><br>
<font size="3">spec_breath_fire</font><br>
<font size="3">spec_breath_frost</font><br>
<font size="3">spec_breath_gas</font><br>
<font size="3">spec_breath_lightning</font><br>
<font size="3">spec_breath_dispel</font> (breathes dispel magic)<br>
<font size="3">spec_cast_adept</font> (healer)<br>
<font size="3">spec_cast_cleric</font> (can cast any cleric spell
up to the level of the mob)<br>
<font size="3">spec_cast_judge</font> (can cast general purpose
ammo and high explosive, like Judge Dredd in MegaCity)<br>
<font size="3">spec_cast_mage</font> (can cast any mage spells up
to the level of the mob)<br>
<font size="3">spec_cast_undead</font> (can cast any undead
spells, like chill touch, vampiric touch, etc)<br>
<font size="3">spec_psionic (best given to mobs in silent rooms)</font><br>
<font size="3">spec_executioner</font> (Attacks all with Killer
&amp; Thief flag, like The Watcher in Dresden)<br>
<font size="3">spec_fido</font> (eats corpses)<br>
<font size="3">spec_guard</font> (attacks all with Killer &amp;
Thief flag, assists victim if players or mobs are attacked in its
presence)<br>
<font size="3">spec_janitor</font> (picks up corpses and objects
it finds on the ground)<br>
<font size="3">spec_poison</font> (can cast poison spell only)<br>
<font size="3">spec_thief</font> (can steal from players it comes
into contact with)<br>
</p>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
<a href="http://www.ofchaos.com/Building/objects.html">#OBJECTS</a>
<a href="http://www.ofchaos.com/Building/rooms.html">#ROOMS</a>
<a href="http://www.ofchaos.com/Building/resets.html">#RESETS</a>
<a href="http://www.ofchaos.com/Building/shops.html">#SHOPS</a></p>

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
