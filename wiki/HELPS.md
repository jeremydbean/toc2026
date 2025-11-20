

<p><font size="3">This section is rarely used. It is simply for
placing keywords and a help section about your area for
players/immortals to read and to get help about your area or its
format. However, it is really only necessary if you feel there
may be some complications in your area. We basically only use
this area for our castle area files, so that prospective castle
initiates may learn about each castle before deciding on which
one to join. If you desire to use a #HELPS section, its format as
it appeared in the Merc 2.1 code is as follows:</font></p>

<p><font size="3">#HELPS</font></p>

<p><font size="3">&lt;level:number&gt; &lt;keywords:string&gt;~</font></p>

<p><font size="3">&lt;help-text:string&gt;</font></p>

<p><font size="3">~</font></p>

<p><font size="3">0 $</font></p>

<p><font size="3">The 'level' number is the minimum character
level needed to read this section. This allows for immortal-only
help text, or any other help type that would be restricted to a
certain minimum level.</font></p>

<p><font size="3">The 'key-words' are the set of keywords that
one would type to view the help section.</font></p>

<p><font size="3">The 'help-text' is the help text itself.</font></p>

<p><font size="3">Normally when a player uses 'help', both the
keywords and the help-text are shown. If the 'level' is negative,
however, the keywords are suppressed. This allows the help file
mechanism to be used for certain other commands, such as the
initial 'greetings' text.</font></p>

<p><font size="3">If a 'help-text' begins with a leading '.', the
'.' is stripped off during viewing on the mud. This provides for
an escape mechanism from the usual leading-blank stripping of
strings, so that picturesque greeting screens may be used.</font></p>

<p><font size="3">Remember, ALL strings must be followed by a
tilde, the '~' symbol, to end that particular string. FAILURE to
place the tilde will result in an error in your area file,
thereby preventing the game to load.</font></p>

<p><a
href="http://www.ofchaos.com/Building/building.html">HOME</a><font
size="2"><i> </i></font><a
href="http://www.ofchaos.com/Building/area.html">#AREA</a>
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

<p><a
href="http://www.ofchaos.com/Building/hpchart.html"><strong><u>How
to assign HP and DAMDICE values to Mobs</u></strong></a><font
color="#000000"><strong><u></u></strong></font></p>
</body>
</html>
