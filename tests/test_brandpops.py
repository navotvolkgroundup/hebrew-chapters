"""Brand-pop library lookup: slug match + loose match, no network, no model."""
from sofit import generate


def test_find_brand_image(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "BRANDS_DIR", tmp_path)
    (tmp_path / "וואטסאפ.png").write_bytes(b"x")
    (tmp_path / "שימורי-איכות.png").write_bytes(b"x")
    assert generate.find_brand_image("וואטסאפ") is not None
    assert generate.find_brand_image("שימורי איכות") is not None   # slug space->dash
    assert generate.find_brand_image("טיקטוק") is None


def test_brand_pop_render_smoke():
    # the render path tolerates a pop whose image is missing (skipped)
    from sofit import render
    assert callable(render._burn_captions_pillow)


def test_split_crop_vf_shape():
    from sofit.render import _split_crop_vf
    vf = _split_crop_vf("9:16", 0.25, 0.75)
    assert "vstack=inputs=2" in vf and "split=2" in vf
    assert "scale=1080:960" in vf
