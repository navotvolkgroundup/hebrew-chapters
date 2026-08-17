

def test_pers_suffix_stripped_and_style_tagged():
    from sofit.publog import _clip_and_variant
    assert _clip_and_variant("WS205_clip-7.pers.mp4") == ("clip-7", 0)
    assert _clip_and_variant("clip-7.hook2.pers.mp4") == ("clip-7", 2)
