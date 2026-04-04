#!/usr/bin/env python3
"""Batch fix typos across all .are files."""

fixes = {
    "area/limbo.are": [
        ("a few to many of his award winning", "a few too many of his award winning"),
        ("one to many lighting", "one too many lightning"),
        ("spells he use to know", "spells he used to know"),
        ("a elite elf guard~", "an elite elf guard~"),
        ("a elite hobbit guard~", "an elite hobbit guard~"),
    ],
    "area/limbo_halloween.are": [
        ("a few to many of his award winning", "a few too many of his award winning"),
        ("one to many lighting", "one too many lightning"),
        ("spells he use to know", "spells he used to know"),
    ],
    "area/limbo_xmas.are": [
        ("a few to many of his award winning", "a few too many of his award winning"),
        ("one to many lighting", "one too many lightning"),
        ("spells he use to know", "spells he used to know"),
    ],
    "area/acult.are": [
        ("eminates magic", "emanates magic"),
        ("As you you plunge", "As you plunge"),
    ],
    "area/ag.are": [
        ("suddenly dissapears into the wall.", "suddenly disappears into the wall."),
        ("slams shut behind you and dissapears into the wall.", "slams shut behind you and disappears into the wall."),
        ("As the door dissapears,", "As the door disappears,"),
        ("he is a old man but upon", "he is an old man but upon"),
        ("This is a old ruined archers station.", "This is an old ruined archers station."),
        ("touch and eminates no heat.", "touch and emanates no heat."),
        ("most powerfull men in the realm.", "most powerful men in the realm."),
    ],
    "area/ancala.are": [
        ("bridge spans the the stalactite-roofed cavern!", "bridge spans the stalactite-roofed cavern!"),
        ("Unlike the the small intestine,", "Unlike the small intestine,"),
    ],
    "area/arac.are": [
        ("the hole is completly dark,", "the hole is completely dark,"),
        ("to dark to see anything", "too dark to see anything"),
        ("Before you you see a large,", "Before you, you see a large,"),
    ],
    "area/arena.are": [
        ("will also recieve a KILLER", "will also receive a KILLER"),
        ("attack players in thier own CASTLE", "attack players in their own CASTLE"),
    ],
    "area/astral.are": [
        ("around you you see glowing", "around you, you see glowing"),
        ("occasional flashes of of light.", "occasional flashes of light."),
        ("in in a field of blackness, filled with tiny tendrils", "in a field of blackness, filled with tiny tendrils"),
    ],
    "area/camelot.are": [
        ("to protect his posessions.", "to protect his possessions."),
        ("in you travels. You have encounterd knights", "in your travels. You have encountered knights"),
        ("A extremely beautifully carved", "An extremely beautifully carved"),
    ],
    "area/campus.are": [
        ("is to dark to tell what it is.", "is too dark to tell what it is."),
    ],
    "area/catacomb.are": [
        ("You sense a evil growl", "You sense an evil growl"),
    ],
    "area/daycare.are": [
        ("Be carefull! Else", "Be careful! Else"),
    ],
    "area/drow1.are": [
        ("you is a enormous illusion", "you is an enormous illusion"),
    ],
    "area/emerald.are": [
        ("could accomodate", "could accommodate"),
    ],
    "area/firenewt.are": [
        ("an occassional shower", "an occasional shower"),
    ],
    "area/forsaken.are": [
        ("throw away thier worries", "throw away their worries"),
    ],
    "area/froboz.are": [
        ("all the wierd surfaces", "all the weird surfaces"),
        ("some sort of wierd", "some sort of weird"),
    ],
    "area/galaxy.are": [
        ("around you you see stars", "around you, you see stars"),
    ],
    "area/haon.are": [
        ("pillars in a enormous,", "pillars in an enormous,"),
    ],
    "area/haven.are": [
        ("as if a hatching just occured.", "as if a hatching just occurred."),
    ],
    "area/hell.are": [
        ("This is a ancient stone archway.", "This is an ancient stone archway."),
        ("go get thier own treasures!", "go get their own treasures!"),
        ("within the the white flames", "within the white flames"),
    ],
    "area/highland.are": [
        ("picturing a ugly man", "picturing an ugly man"),
    ],
    "area/hood.are": [
        ("drink them selves", "drink themselves"),
    ],
    "area/horde.are": [
        ("an occassional spurt", "an occasional spurt"),
    ],
    "area/istari.are": [
        ("most embarassing experience", "most embarrassing experience"),
        ("just as embarassing is", "just as embarrassing is"),
    ],
    "area/kerofk.are": [
        ("intersection of of Center Road", "intersection of Center Road"),
        ("Around you you see small cultivated", "Around you, you see small cultivated"),
        ("Seems all it is is war news.", "Seems all it is war news."),
    ],
    "area/korzath1.are": [
        ("eminates from a blacksmith", "emanates from a blacksmith"),
        ("    to to here.  Once he has arrived", "    to here.  Once he has arrived"),
        ("don't recieve the", "don't receive the"),
    ],
    "area/korzath2.are": [
        ("     your self?  Fools.", "     yourself?  Fools."),
        ("A rank raw smell eminates from that", "A rank raw smell emanates from that"),
    ],
    "area/lakes.are": [
        ("an opening the the trees.", "an opening in the trees."),
    ],
    "area/lud.are": [
        ("a jagged black chasm seperates you from Mid-World.", "a jagged black chasm separates you from Mid-World."),
        ("the barricade that seperates the Gray's side", "the barricade that separates the Gray's side"),
    ],
    "area/mahntor.are": [
        ("glows with a eerie blue light.", "glows with an eerie blue light."),
        ("Another window the the north", "Another window to the north"),
    ],
    "area/mid_hall.are": [
        ("opens into a a beautiful atrium,", "opens into a beautiful atrium,"),
        ("The bar is one of the wierdest", "The bar is one of the weirdest"),
    ],
    "area/mid_ruin.are": [
        ("dissapears into tthe forest.", "disappears into the forest."),
        ("leaving just theis\nentrance.", "leaving just this\nentrance."),
    ],
    "area/midennir.are": [
        ("the highway continues the the east.", "the highway continues to the east."),
        ("it hasn't been to long since this cart was burned", "it hasn't been too long since this cart was burned"),
        ("while is much to thick to explore west,", "while it is much too thick to explore west,"),
        ("near the the barren wastes", "near the barren wastes"),
    ],
    "area/mountain.are": [
        ("with a odd shaped broom.", "with an odd-shaped broom."),
    ],
    "area/mushroom.are": [
        ("music with a fast rythm", "music with a fast rhythm"),
    ],
    "area/nether.are": [
        ("some great fire occured here", "some great fire occurred here"),
    ],
    "area/nethril1.are": [
        ("four seperate ways to travel.", "four separate ways to travel."),
        ("recieved a strange addiction", "received a strange addiction"),
        ("little to close to the disc", "little too close to the disc"),
    ],
    "area/northsea.are": [
        ("to accomodate approximately 10", "to accommodate approximately 10"),
    ],
    "area/ofcol.are": [
        ("of the wierdest drinks", "of the weirdest drinks"),
    ],
    "area/randtowr.are": [
        ("to accomodate approximately 10", "to accommodate approximately 10"),
    ],
    "area/rom.are": [
        ("their priveleges.", "their privileges."),
        ("in your posession.", "in your possession."),
        ("Monsters recieve a save against gate,", "Monsters receive a save against gate,"),
    ],
    "area/school.are": [
        ("a door with a open hand painted on it", "a door with an open hand painted on it"),
        ("The blood and gore are to thick", "The blood and gore are too thick"),
    ],
    "area/sewer.are": [
        ("apart from in you direction.", "apart from in your direction."),
    ],
    "area/social.are": [
        ("you give your self a thumbs up.", "you give yourself a thumbs up."),
    ],
    "area/solace.are": [
        ("farmers go to sell thier harvests.", "farmers go to sell their harvests."),
    ],
    "area/tarin.are": [
        ("assembling wierd powers of evil.", "assembling weird powers of evil."),
        ("devil with a evil look", "devil with an evil look"),
    ],
    "area/toc.are": [
        ("occassionally you find", "occasionally you find"),
    ],
    "area/uargo.are": [
        ("there are definately the", "there are definitely the"),
        ("it's definately the", "it's definitely the"),
    ],
    "area/ultima.are": [
        ("to bad these monster", "too bad these monsters"),
    ],
    "area/underdrk.are": [
        ("Some massive battle occured", "Some massive battle occurred"),
    ],
    "area/valhalla.are": [
        ("accomodate a place to sit.", "accommodate a place to sit."),
        ("In thier natural habitats.", "In their natural habitats."),
        ("Emblazoned on thier tunics is", "Emblazoned on their tunics is"),
        ("blue glow that eminates from", "blue glow that emanates from"),
    ],
    "area/world.are": [
        ("a jagged black chasm seperates you from the City of Lud.", "a jagged black chasm separates you from the City of Lud."),
        ("are seperated far enough apart", "are separated far enough apart"),
    ],
}

total_replaced = 0
files_changed = 0
for filepath in sorted(fixes.keys()):
    replacements = fixes[filepath]
    with open(filepath, 'rb') as f:
        data = f.read()
    file_count = 0
    for old, new in replacements:
        old_b = old.encode('utf-8')
        new_b = new.encode('utf-8')
        c = data.count(old_b)
        if c > 0:
            data = data.replace(old_b, new_b)
            file_count += c
            total_replaced += c
        else:
            print(f"  NOT FOUND ({filepath}): {old[:70]}")
    if file_count > 0:
        with open(filepath, 'wb') as f:
            f.write(data)
        files_changed += 1
        print(f"  {filepath}: {file_count} replacements")

print(f"\nTotal: {total_replaced} replacements in {files_changed} files")
