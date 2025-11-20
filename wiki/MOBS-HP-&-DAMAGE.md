
<p align="center"><font size="5"><strong><u>How to assign HP and
DAMDICE values to Mobs</u></strong></font></p>

<p><font size="3">Here's the formula that the game uses to
automatically calculate mob&#146;s HP Values, and this is what
they will be assigned if you create mobs with all ZEROs instead
of actual numbers, like so: 20 0 <u>0d0+0</u> <u>0d0+0</u> <u>0d0+0</u>
5</font></p>

<p><font size="3">The explanation:</font></p>

<p><font size="3">The 20, as we know from the #MOBILES section
specifies the level of the mob, the 0 is a bonus to the mob's
hitroll, the 0d0+0 is the mobs hp slot, the second 0d0+0 is the
mobs mana slot, the third 0d0+0 is the mobs damdie value (see
chart below), and the 5 is the mobs damage type (the unarmed
message that player gets when fighting the mob)..</font></p>

<p><font size="3">The formula:</font></p>

<p><font size="3">(level * 8 + number_range(level * level/4,
level * level) ) * .9 Inserting a value for level, say 20th gives
this end results:</font></p>

<p><font size="3">hit_points = (160 + (a number between 100 and
400) ) * .9</font></p>

<p><font size="3">This equates to around 234-504 hp for a level
20 mob, or 12-25 hp/level. I'm letting you know how old fromat
mob hp are generated because your going to have to give them all
a hp value. Here's what I'd like ya to do.</font></p>

<p><font size="3">Calculate the general hp of the mob using the
format: (level)d(level*.75)</font></p>

<p><font size="3">20 3 20d15+240 10d20+120 6d4+1 5</font></p>

<p><font size="3">Here is a chart for manually adding HP to a mob
which is based on the above formula. It would be used instead of
using 0d0+0 entries and allowing code to generate it for you. I
would prefer that you let the code generate HP values, and unless
you get permission from me to deviate from this, your area may be
rejected.</font></p>

<p><font size="3">The AC value may also be used for adding AC
values to armor items in #OBJECTS. For example, if an item is a
level 5 helmet, you would assign a 5 to helmet's bash value
&lt;value 1&gt;. If you just use all ZEROs (0), then the game
code will autoassign this value anyways, so it is certainly
easier and quicker for you to just use all ZEROs.. The only
exception to this would be to make a piece of extra powerful
equipment... BUT, for that you need my permission &lt;grin&gt;.
Don't mean to sound like a jerk, but I need to keep tight control
of these things, or else everything will get way out of balance
and you'll have level 3 players running around with level 55
equivalent eq.. NOT a pretty picture &lt;double grin&gt;.</font></p>

<table border="1">
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@">&nbsp;</td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>AVG</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@">&nbsp;</td>
        <td align="right" valign="bottom">&nbsp;</td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@">&nbsp;</td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>AVG</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@">&nbsp;</td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@">&nbsp;</td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>LVL</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>HP</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>AC</strong></font></td>
        <td valign="bottom"><font face="Arial"><strong>DAMAGE</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>LVL</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>HP</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>AC</strong></font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial"><strong>DAMAGE </strong></font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">1</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d6+10</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">9</font></td>
        <td valign="bottom"><font face="Arial">1d4+0</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">31</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d12+928</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-10</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d6+9</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d7+21</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8</font></td>
        <td valign="bottom"><font face="Arial">1d5+0</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">32</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-10</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d4+9</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d6+35</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">7</font></td>
        <td valign="bottom"><font face="Arial">1d6+0</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">33</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1100</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-11</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d4+10</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d7+46</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6</font></td>
        <td valign="bottom"><font face="Arial">1d5+1</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">34</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1200</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-11</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d7+10</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d6+60</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5</font></td>
        <td valign="bottom"><font face="Arial">1d6+1</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">35</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1300</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-11</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d7+11</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d7+71</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4</font></td>
        <td valign="bottom"><font face="Arial">1d7+1</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">36</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1400</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-12</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d10+11</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">7</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d6+85</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4</font></td>
        <td valign="bottom"><font face="Arial">1d8+1</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">37</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-12</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d10+12</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d7+96</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3</font></td>
        <td valign="bottom"><font face="Arial">1d7+2</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">38</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d10+1600</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-13</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d6+12</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">9</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d6+110</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2</font></td>
        <td valign="bottom"><font face="Arial">1d8+2</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">39</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">15d10+1700</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-13</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d6+13</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d7+121</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">1</font></td>
        <td valign="bottom"><font face="Arial">2d4+2</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">40</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">15d10+1850</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-13</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d8+13</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">11</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d8+134</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">1</font></td>
        <td valign="bottom"><font face="Arial">1d10+2</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">41</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+2000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-14</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d8+14</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">12</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d10+150</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">0</font></td>
        <td valign="bottom"><font face="Arial">1d10+3</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">42</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+2250</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-14</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d12+14</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">13</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d10+170</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-1</font></td>
        <td valign="bottom"><font face="Arial">2d5+3</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">43</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+2500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-15</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d12+15</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">14</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">2d10+190</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-1</font></td>
        <td valign="bottom"><font face="Arial">1d12+3</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">44</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+2750</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-15</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8d4+15</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">15</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+208</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-2</font></td>
        <td valign="bottom"><font face="Arial">2d6+3</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">45</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+3000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-15</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8d4+16</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">16</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+233</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-2</font></td>
        <td valign="bottom"><font face="Arial">2d6+4</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">46</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+3250</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-16</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d6+16</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">17</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+258</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-3</font></td>
        <td valign="bottom"><font face="Arial">3d4+4</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">47</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+3500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-17</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d6+17</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">18</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+283</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-3</font></td>
        <td valign="bottom"><font face="Arial">2d7+4</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">48</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25d10+3750</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-18</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d6+18</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">19</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+308</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-4</font></td>
        <td valign="bottom"><font face="Arial">2d7+5</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">49</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+4000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-19</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d10+18</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">20</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">3d9+333</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-4</font></td>
        <td valign="bottom"><font face="Arial">2d8+5</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+4500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-20</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d8+19</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">21</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">4d10+360</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-5</font></td>
        <td valign="bottom"><font face="Arial">4d4+5</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">51</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+5000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-21</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d8+20</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">22</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+400</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-5</font></td>
        <td valign="bottom"><font face="Arial">4d4+6</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">52</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+5500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-22</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d7+20</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">23</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+450</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-6</font></td>
        <td valign="bottom"><font face="Arial">3d6+6</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">53</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+6000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-23</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d7+21</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">24</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-6</font></td>
        <td valign="bottom"><font face="Arial">2d10+6</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">54</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+6500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-24</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">7d6+22</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">25</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+550</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-7</font></td>
        <td valign="bottom"><font face="Arial">2d10+7</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">55</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+7000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-25</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d4+23</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">26</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+600</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-7</font></td>
        <td valign="bottom"><font face="Arial">3d7+7</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">56</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+7500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-26</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">10d4+24</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">27</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+650</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-8</font></td>
        <td valign="bottom"><font face="Arial">5d4+7</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">57</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+8000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-27</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d8+24</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">28</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d12+703</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-8</font></td>
        <td valign="bottom"><font face="Arial">2d12+8</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">58</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+8500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-28</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">5d10+25</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">29</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d12+778</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-9</font></td>
        <td valign="bottom"><font face="Arial">2d12+8</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">59</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+9000</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-29</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8d6+26</font></td>
    </tr>
    <tr>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">30</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">6d12+853</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-9</font></td>
        <td valign="bottom"><font face="Arial">4d6+8</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">60</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">50d10+9500</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">-30</font></td>
        <td valign="bottom" style="vnd.ms-excel.numberformat:@"><font
        face="Arial">8d6+28</font></td>
    </tr>
</table>

<p><font size="3">Below are some notes on how to read the above
chart, and any exceptions/modifications to it.</font></p>

<p><font size="3">AC: - if a mob has a lot of eq (which also
lowers ac) then use these bottom values for ac.</font></p>

<p><font size="3">- if a mob has little/no eq then lower these
basic ac values.</font></p>

<p><font size="3">- for lower lvl mobs, till +- lvl 15, one
should stick to these values.</font></p>

<p><font size="3">HP: - if the mob has many immunities, you might
also want to give the mob less hp and attempt to balance them
out. One or two &quot;Boss&quot; type mobs in an area is okay, in
which case you might want to make the mob impossible to solo, and
also very tough to beat with a group. An example of when this is
acceptable, would be when the mobs hold some piece(s) of
equipment that have very good stats. Try to keep exceptional mobs
and exceptional equipment in check though, too much throws the
balance of the game way off. It&#146;s quite easy to get carried
away when designing mobs and equipment..</font></p>

<p><font size="3">Thief* mobiles should read their hp, ac, and
damage at one level lower than their actual level.</font></p>

<p><font size="3">Mage mobiles should read hp and ac at one level
lower, and damage three levels lower</font></p>

<p><font size="3">Cleric mobiles should read hit points at one
level lower and damage at two levels lower</font></p>

<p><font size="3">Warrior mobiles should read hit points and
damage one level higher</font></p>

<p><font size="3">Armor class against magical attacks should be
computed by this formula:</font></p>

<p><font size="3">(ac - 10) / n + 10, where n is 4 for most
mobiles, 3 for thieves and clerics, and 2 for mages.</font></p>

<p><font size="3">Mana is more flexible than the other
statistics. A good guideline is 100 mana for creatures with no
(zero, zip, completely none) magical talent, 100 + 1d10/level
mana for creatures with spells, and 100+ 1d5/level mana for
normal mobiles. Particularly powerful spell casters may have more
mana, but not too much more.</font></p>

<p><font size="3">* a thief mobile either has ACT_THIEF set or is
decidely thief-like in nature. The same holds true for the other
modifiers.</font></p>

<p><font size="3">Some items are loaded on different level mobs.
With new format objects, this creates a problem, because you wind
up giving high level mobs low level EQ, and vice versa. To avoid
level conflicts, you can now set the &lt;obj level&gt; field of
an object to -1. By setting it to -1, the game will give the
object a level roughly equal to the mob that holds it. Now, most
of us know what objects are loaded on which mobiles, and if
you&#146;re not sure, check for the vnum of the object in the
reset section and look for an 'O' next to it. Objects not loaded
on mobiles should be given a level = to the average area level.
Level values on wands and staff's will be set ccording to mobile
it's loaded on, provided that the level of the object is set to
-1. Game will also generate values for armor using the formula I
gave you &lt;it will not however assign a value to the armor for
magic. This will be 0 with a -1 lvl object&gt;, and weapon damage
values will be generated according to the chart below. This chart
also gives all the dice combinations for the values when setting
them manually. They can be varied a little as far as start and
end damage is concerned, but try and keep em close to the listed
parameters. It&#146;s preferrable that you only use the -1 option
if you can't figure out what values should be inserted, or if the
object is loaded on multiple mobiles of differing levels.</font></p>

<p><font size="3">The below chart may be used for both mobs and
weapons when determining damage die.</font></p>

<table border="1">
    <tr>
        <td valign="bottom">&nbsp;</td>
        <td valign="bottom">&nbsp;</td>
        <td valign="bottom"><font face="Arial">Avg</font></td>
        <td valign="bottom"><font face="Arial">Suggested</font></td>
        <td valign="bottom"><font face="Arial">Value game will
        use</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">Lvl </font></td>
        <td valign="bottom"><font face="Arial">Range</font></td>
        <td valign="bottom"><font face="Arial">Dam</font></td>
        <td valign="bottom"><font face="Arial">Damage Die</font></td>
        <td valign="bottom"><font face="Arial">+/-1 on each value</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">1</font></td>
        <td valign="bottom"><font face="Arial">2-7</font></td>
        <td valign="bottom"><font face="Arial">5</font></td>
        <td valign="bottom"><font face="Arial">2d4, 3d2</font></td>
        <td valign="bottom"><font face="Arial">2d4</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">2</font></td>
        <td valign="bottom"><font face="Arial">3-8</font></td>
        <td valign="bottom"><font face="Arial">6</font></td>
        <td valign="bottom"><font face="Arial">2d5,3d3</font></td>
        <td valign="bottom"><font face="Arial">3d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">3</font></td>
        <td valign="bottom"><font face="Arial">3-8</font></td>
        <td valign="bottom"><font face="Arial">6</font></td>
        <td valign="bottom"><font face="Arial">2d5,3d3</font></td>
        <td valign="bottom"><font face="Arial">3d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">4</font></td>
        <td valign="bottom"><font face="Arial">3-9</font></td>
        <td valign="bottom"><font face="Arial">6</font></td>
        <td valign="bottom"><font face="Arial">2d5,3d3,4d2</font></td>
        <td valign="bottom"><font face="Arial">3d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">5</font></td>
        <td valign="bottom"><font face="Arial">3-10</font></td>
        <td valign="bottom"><font face="Arial">7</font></td>
        <td valign="bottom"><font face="Arial">2d6,3d4</font></td>
        <td valign="bottom"><font face="Arial">3d4</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">6</font></td>
        <td valign="bottom"><font face="Arial">4-11</font></td>
        <td valign="bottom"><font face="Arial">8</font></td>
        <td valign="bottom"><font face="Arial">2d7,4d3</font></td>
        <td valign="bottom"><font face="Arial">4d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">7</font></td>
        <td valign="bottom"><font face="Arial">4-11</font></td>
        <td valign="bottom"><font face="Arial">8</font></td>
        <td valign="bottom"><font face="Arial">2d7,4d3 </font></td>
        <td valign="bottom"><font face="Arial">4d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">8</font></td>
        <td valign="bottom"><font face="Arial">4-12</font></td>
        <td valign="bottom"><font face="Arial">8</font></td>
        <td valign="bottom"><font face="Arial">2d7,4d3 </font></td>
        <td valign="bottom"><font face="Arial">4d3</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">9</font></td>
        <td valign="bottom"><font face="Arial">4-13</font></td>
        <td valign="bottom"><font face="Arial">9</font></td>
        <td valign="bottom"><font face="Arial">2d8,3d5,6d2 </font></td>
        <td valign="bottom"><font face="Arial">3d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">10</font></td>
        <td valign="bottom"><font face="Arial">5-14</font></td>
        <td valign="bottom"><font face="Arial">10</font></td>
        <td valign="bottom"><font face="Arial">2d9,3d6 </font></td>
        <td valign="bottom"><font face="Arial">3d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">11</font></td>
        <td valign="bottom"><font face="Arial">5-14</font></td>
        <td valign="bottom"><font face="Arial">10</font></td>
        <td valign="bottom"><font face="Arial">2d9,3d6,4d4,5d3 </font></td>
        <td valign="bottom"><font face="Arial">3d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">12</font></td>
        <td valign="bottom"><font face="Arial">5-15</font></td>
        <td valign="bottom"><font face="Arial">10</font></td>
        <td valign="bottom"><font face="Arial">2d9,
        3d6,4d4,5d3,7d2</font></td>
        <td valign="bottom"><font face="Arial">4d4</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">13</font></td>
        <td valign="bottom"><font face="Arial">5-16</font></td>
        <td valign="bottom"><font face="Arial">11</font></td>
        <td valign="bottom"><font face="Arial">2d10,3d7,4d4 </font></td>
        <td valign="bottom"><font face="Arial">4d4</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">14</font></td>
        <td valign="bottom"><font face="Arial">6-17</font></td>
        <td valign="bottom"><font face="Arial">12</font></td>
        <td valign="bottom"><font face="Arial">2d11,3d7,4d5,5d4 </font></td>
        <td valign="bottom"><font face="Arial">4d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">15</font></td>
        <td valign="bottom"><font face="Arial">6-17</font></td>
        <td valign="bottom"><font face="Arial">12</font></td>
        <td valign="bottom"><font face="Arial">2d11,3d7,4d5,6d3 </font></td>
        <td valign="bottom"><font face="Arial">4d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">16</font></td>
        <td valign="bottom"><font face="Arial">6-18</font></td>
        <td valign="bottom"><font face="Arial">13</font></td>
        <td valign="bottom"><font face="Arial">2d12,3d8,4d5 </font></td>
        <td valign="bottom"><font face="Arial">4d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">17</font></td>
        <td valign="bottom"><font face="Arial">6-19</font></td>
        <td valign="bottom"><font face="Arial">13</font></td>
        <td valign="bottom"><font face="Arial">2d12,3d8,4d5 </font></td>
        <td valign="bottom"><font face="Arial">4d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">18</font></td>
        <td valign="bottom"><font face="Arial">7-20</font></td>
        <td valign="bottom"><font face="Arial">14</font></td>
        <td valign="bottom"><font face="Arial">2d13,4d6 </font></td>
        <td valign="bottom"><font face="Arial">4d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">19</font></td>
        <td valign="bottom"><font face="Arial">7-20</font></td>
        <td valign="bottom"><font face="Arial">14</font></td>
        <td valign="bottom"><font face="Arial">2d13,4d6,7d3 </font></td>
        <td valign="bottom"><font face="Arial">4d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">20</font></td>
        <td valign="bottom"><font face="Arial">7-21</font></td>
        <td valign="bottom"><font face="Arial">14</font></td>
        <td valign="bottom"><font face="Arial">2d13,4d6,7d3,9d2 </font></td>
        <td valign="bottom"><font face="Arial">4d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">21</font></td>
        <td valign="bottom"><font face="Arial">7-22</font></td>
        <td valign="bottom"><font face="Arial">15</font></td>
        <td valign="bottom"><font face="Arial">2d14,3d9,5d5,6d4,10d2</font></td>
        <td valign="bottom"><font face="Arial">5d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">22</font></td>
        <td valign="bottom"><font face="Arial">8-23</font></td>
        <td valign="bottom"><font face="Arial">16</font></td>
        <td valign="bottom"><font face="Arial">2d15,3d10 </font></td>
        <td valign="bottom"><font face="Arial">5d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">23</font></td>
        <td valign="bottom"><font face="Arial">8-23</font></td>
        <td valign="bottom"><font face="Arial">16</font></td>
        <td valign="bottom"><font face="Arial">2d15,3d10,4d7 </font></td>
        <td valign="bottom"><font face="Arial">4d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">24</font></td>
        <td valign="bottom"><font face="Arial">8-24</font></td>
        <td valign="bottom"><font face="Arial">16</font></td>
        <td valign="bottom"><font face="Arial">2d15,3d10,4d7,8d3</font></td>
        <td valign="bottom"><font face="Arial">4d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">25</font></td>
        <td valign="bottom"><font face="Arial">8-25</font></td>
        <td valign="bottom"><font face="Arial">17</font></td>
        <td valign="bottom"><font face="Arial">2d16,5d6,7d4 </font></td>
        <td valign="bottom"><font face="Arial">5d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">26</font></td>
        <td valign="bottom"><font face="Arial">9-26</font></td>
        <td valign="bottom"><font face="Arial">18</font></td>
        <td valign="bottom"><font face="Arial">2d17,3d11 </font></td>
        <td valign="bottom"><font face="Arial">7d4</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">27</font></td>
        <td valign="bottom"><font face="Arial">9-26</font></td>
        <td valign="bottom"><font face="Arial">18</font></td>
        <td valign="bottom"><font face="Arial">2d17,3d11,4d8 </font></td>
        <td valign="bottom"><font face="Arial">4d8</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">28</font></td>
        <td valign="bottom"><font face="Arial">9-27</font></td>
        <td valign="bottom"><font face="Arial">18</font></td>
        <td valign="bottom"><font face="Arial">2d17,3d11,4d8,6d5,9d3</font></td>
        <td valign="bottom"><font face="Arial">6d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">29</font></td>
        <td valign="bottom"><font face="Arial">9-28</font></td>
        <td valign="bottom"><font face="Arial">19</font></td>
        <td valign="bottom"><font face="Arial">3d12 </font></td>
        <td valign="bottom"><font face="Arial">6d5</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">30</font></td>
        <td valign="bottom"><font face="Arial">10-29</font></td>
        <td valign="bottom"><font face="Arial">20</font></td>
        <td valign="bottom"><font face="Arial">4d9,5d7 </font></td>
        <td valign="bottom"><font face="Arial">5d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">31</font></td>
        <td valign="bottom"><font face="Arial">10-29</font></td>
        <td valign="bottom"><font face="Arial">20</font></td>
        <td valign="bottom"><font face="Arial">4d9,5d7,8d4 </font></td>
        <td valign="bottom"><font face="Arial">5d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">32</font></td>
        <td valign="bottom"><font face="Arial">10-30</font></td>
        <td valign="bottom"><font face="Arial">20</font></td>
        <td valign="bottom"><font face="Arial">4d9,5d7,8d4,10d3 </font></td>
        <td valign="bottom"><font face="Arial">5d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">33</font></td>
        <td valign="bottom"><font face="Arial">10-31</font></td>
        <td valign="bottom"><font face="Arial">21</font></td>
        <td valign="bottom"><font face="Arial">3d13,6d6,7d5 </font></td>
        <td valign="bottom"><font face="Arial">6d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">34</font></td>
        <td valign="bottom"><font face="Arial">11-32</font></td>
        <td valign="bottom"><font face="Arial">22</font></td>
        <td valign="bottom"><font face="Arial">3d14,4d10,9d4 </font></td>
        <td valign="bottom"><font face="Arial">6d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">35</font></td>
        <td valign="bottom"><font face="Arial">11-32</font></td>
        <td valign="bottom"><font face="Arial">22</font></td>
        <td valign="bottom"><font face="Arial">3d14,4d10,9d4,11d3</font></td>
        <td valign="bottom"><font face="Arial">6d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">36</font></td>
        <td valign="bottom"><font face="Arial">11-33</font></td>
        <td valign="bottom"><font face="Arial">22</font></td>
        <td valign="bottom"><font face="Arial">3d14,4d10,9d4,11d3</font></td>
        <td valign="bottom"><font face="Arial">6d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">37</font></td>
        <td valign="bottom"><font face="Arial">11-34</font></td>
        <td valign="bottom"><font face="Arial">23</font></td>
        <td valign="bottom"><font face="Arial">3d14,4d10,9d4,11d3</font></td>
        <td valign="bottom"><font face="Arial">6d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">38</font></td>
        <td valign="bottom"><font face="Arial">12-35</font></td>
        <td valign="bottom"><font face="Arial">24</font></td>
        <td valign="bottom"><font face="Arial">3d15,4d11 </font></td>
        <td valign="bottom"><font face="Arial">6d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">39</font></td>
        <td valign="bottom"><font face="Arial">12-35</font></td>
        <td valign="bottom"><font face="Arial">24</font></td>
        <td valign="bottom"><font face="Arial">3d15,4d11,6d7,7d6</font></td>
        <td valign="bottom"><font face="Arial">7d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">40</font></td>
        <td valign="bottom"><font face="Arial">12-36</font></td>
        <td valign="bottom"><font face="Arial">24</font></td>
        <td valign="bottom"><font face="Arial">3d15,4d11,6d7,7d6,8d5</font></td>
        <td valign="bottom"><font face="Arial">7d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">41</font></td>
        <td valign="bottom"><font face="Arial">12-37</font></td>
        <td valign="bottom"><font face="Arial">25</font></td>
        <td valign="bottom"><font face="Arial">3d16,5d9,10d4 </font></td>
        <td valign="bottom"><font face="Arial">7d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">42</font></td>
        <td valign="bottom"><font face="Arial">13-38</font></td>
        <td valign="bottom"><font face="Arial">26</font></td>
        <td valign="bottom"><font face="Arial">4d12,13d3 </font></td>
        <td valign="bottom"><font face="Arial">5d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">43</font></td>
        <td valign="bottom"><font face="Arial">13-38</font></td>
        <td valign="bottom"><font face="Arial">26</font></td>
        <td valign="bottom"><font face="Arial">4d12,13d3 </font></td>
        <td valign="bottom"><font face="Arial">5d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">44</font></td>
        <td valign="bottom"><font face="Arial">13-39</font></td>
        <td valign="bottom"><font face="Arial">26</font></td>
        <td valign="bottom"><font face="Arial">4d12,13d3 </font></td>
        <td valign="bottom"><font face="Arial">5d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">45</font></td>
        <td valign="bottom"><font face="Arial">13-40</font></td>
        <td valign="bottom"><font face="Arial">27</font></td>
        <td valign="bottom"><font face="Arial">3d17,5d10,6d8,9d5,11d4
        </font></td>
        <td valign="bottom"><font face="Arial">6d8</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">46</font></td>
        <td valign="bottom"><font face="Arial">14-41</font></td>
        <td valign="bottom"><font face="Arial">28</font></td>
        <td valign="bottom"><font face="Arial">4d13,7d7,8d6, </font></td>
        <td valign="bottom"><font face="Arial">7d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">47</font></td>
        <td valign="bottom"><font face="Arial">14-41</font></td>
        <td valign="bottom"><font face="Arial">28</font></td>
        <td valign="bottom"><font face="Arial">4d13,7d7,8d6 </font></td>
        <td valign="bottom"><font face="Arial">8d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">48</font></td>
        <td valign="bottom"><font face="Arial">14-42</font></td>
        <td valign="bottom"><font face="Arial">28</font></td>
        <td valign="bottom"><font face="Arial">4d13,7d7,8d6,14d3</font></td>
        <td valign="bottom"><font face="Arial">8d6</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">49</font></td>
        <td valign="bottom"><font face="Arial">14-43</font></td>
        <td valign="bottom"><font face="Arial">29</font></td>
        <td valign="bottom"><font face="Arial">8d6,4d14,6d9</font></td>
        <td valign="bottom"><font face="Arial">6d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">50</font></td>
        <td valign="bottom"><font face="Arial">15-44</font></td>
        <td valign="bottom"><font face="Arial">30</font></td>
        <td valign="bottom"><font face="Arial">4d14,5d11,6d9</font></td>
        <td valign="bottom"><font face="Arial">6d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">51</font></td>
        <td valign="bottom"><font face="Arial">15-44</font></td>
        <td valign="bottom"><font face="Arial">30</font></td>
        <td valign="bottom"><font face="Arial">4d14,5d11,6d9,10d5</font></td>
        <td valign="bottom"><font face="Arial">6d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">52</font></td>
        <td valign="bottom"><font face="Arial">15-45</font></td>
        <td valign="bottom"><font face="Arial">30</font></td>
        <td valign="bottom"><font face="Arial">4d14,5d11,6d9,10d5</font></td>
        <td valign="bottom"><font face="Arial">6d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">53</font></td>
        <td valign="bottom"><font face="Arial">15-46</font></td>
        <td valign="bottom"><font face="Arial">31</font></td>
        <td valign="bottom"><font face="Arial">7d8,9d6 </font></td>
        <td valign="bottom"><font face="Arial">7d8</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">54</font></td>
        <td valign="bottom"><font face="Arial">16-47</font></td>
        <td valign="bottom"><font face="Arial">32</font></td>
        <td valign="bottom"><font face="Arial">4d15,5d12,8d7,11d5</font></td>
        <td valign="bottom"><font face="Arial">8d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">55</font></td>
        <td valign="bottom"><font face="Arial">16-47</font></td>
        <td valign="bottom"><font face="Arial">32</font></td>
        <td valign="bottom"><font face="Arial">4d15,5d12,8d7,11d5</font></td>
        <td valign="bottom"><font face="Arial">8d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">56</font></td>
        <td valign="bottom"><font face="Arial">16-48</font></td>
        <td valign="bottom"><font face="Arial">32</font></td>
        <td valign="bottom"><font face="Arial">4d15,5d12,8d7,11d5</font></td>
        <td valign="bottom"><font face="Arial">8d7</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">57</font></td>
        <td valign="bottom"><font face="Arial">16-49</font></td>
        <td valign="bottom"><font face="Arial">33</font></td>
        <td valign="bottom"><font face="Arial">4d16,5d13,8d8,11d6</font></td>
        <td valign="bottom"><font face="Arial">8d8</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">58</font></td>
        <td valign="bottom"><font face="Arial">17-50</font></td>
        <td valign="bottom"><font face="Arial">34</font></td>
        <td valign="bottom"><font face="Arial">4d17,5d14,8d9,11d7</font></td>
        <td valign="bottom"><font face="Arial">8d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">59</font></td>
        <td valign="bottom"><font face="Arial">17-50</font></td>
        <td valign="bottom"><font face="Arial">34</font></td>
        <td valign="bottom"><font face="Arial">4d17,5d14,8d9,11d7</font></td>
        <td valign="bottom"><font face="Arial">8d9</font></td>
    </tr>
    <tr>
        <td valign="bottom"><font face="Arial">60</font></td>
        <td valign="bottom"><font face="Arial">17-51</font></td>
        <td valign="bottom"><font face="Arial">35</font></td>
        <td valign="bottom"><font face="Arial">4d18,5d15,9d10,11d8</font></td>
        <td valign="bottom"><font face="Arial">9d10</font></td>
    </tr>
</table>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
<a href="http://www.ofchaos.com/Building/helps.html">#HELPS</a>
<a href="http://www.ofchaos.com/Building/mobiles.html">#MOBILES</a>
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
</body>
</html>
