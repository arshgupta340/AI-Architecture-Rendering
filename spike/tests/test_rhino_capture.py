"""Pure-python tests for spike/rhino_capture.py.

rhino_capture must import cleanly WITHOUT the Rhino runtime; everything
Rhino-dependent is exercised live via the Rhino MCP, not here.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rhino_capture as rc  # noqa: E402


def test_imports_without_rhino():
    assert rc.HAVE_RHINO is False
    with pytest.raises(RuntimeError, match="inside Rhino"):
        rc.capture("anywhere")


# ---- ID encoding ----------------------------------------------------------

def test_id_color_plane_zero_matches_e1_scheme():
    # r=0, g=5*(i//52), b=5*(i%52) — the proven E1/E2 encoding
    assert rc.id_color(0) == (0, 0, 0)
    assert rc.id_color(1) == (0, 0, 5)
    assert rc.id_color(52) == (0, 5, 0)
    assert rc.id_color(2703) == (0, 255, 255)


def test_id_color_r_plane_extension():
    assert rc.id_color(2704) == (5, 0, 0)
    assert rc.id_color(2704 + 53) == (5, 5, 5)
    assert rc.id_color(rc.MAX_OBJECTS - 1) == (255, 255, 255)
    with pytest.raises(ValueError, match="at most"):
        rc.id_color(rc.MAX_OBJECTS)
    with pytest.raises(ValueError):
        rc.id_color(-1)


def test_id_key_format_backward_compatible():
    assert rc.id_key(1) == "0,5"          # plane 0 keeps the "g,b" form
    assert rc.id_key(2704) == "5,0,0"     # r-planes use "r,g,b"


def test_id_colors_unique():
    seen = set()
    for i in range(0, rc.MAX_OBJECTS, 997):  # sparse but cross-plane sample
        c = rc.id_color(i)
        assert c not in seen
        seen.add(c)


# ---- semantic rules -------------------------------------------------------

def test_csi_rules_match_e2_house_mapping():
    expected = {
        "03 - CONCRETE::03-01-Concrete Foundation": "foundation",
        "06 - WOOD PLASTICS & COMPOSITES::06-00 - Wood Framing (General)": "other",
        "06 - WOOD PLASTICS & COMPOSITES::06-01 - Floor Assemblies": "floor",
        "06 - WOOD PLASTICS & COMPOSITES::06-02 - Exterior Wall Assemblies": "wall",
        "06 - WOOD PLASTICS & COMPOSITES::06-03 - Interior Wall Assemblies": "wall_interior",
        "06 - WOOD PLASTICS & COMPOSITES::06-04 - Roof Assemblies": "roof",
        "06 - WOOD PLASTICS & COMPOSITES::06-05 - Exterior Stairs": "stair",
        "08 - OPENINGS": "window",
        "08 - OPENINGS::08-01 - Opening Frames": "window",
        "08 - OPENINGS::08-21 - Door Panels": "door",
        "08 - OPENINGS::08-22 - Door Hardware": "door",
        "09 - FINISHES::09-01 - Misc Exterior Finishes": "trim",
        "09 - FINISHES::09-03- Exterior Finished Floor": "floor",
        "09 - FINISHES::09-50 - Exterior Stair Finishes": "stair",
        "09 - FINISHES::09-62 - Interior Stair Railings": "stair",
        "31 - SITE::31-00 - Site-Misc": "ground",
        "31 - SITE::31-03 - Site-Concrete": "paving",
        "31 - SITE::31-04 - Site-Asphalt": "paving",
    }
    for layer, semantic in expected.items():
        assert rc.semantic_from_layer(layer, rc.CSI_RULES) == semantic, layer


def test_keyword_rules_match_e1_mapping():
    expected = {
        "ENSCAPE::GLASS::MULLIONSS": "mullion",   # MULLION wins over GLASS
        "ENSCAPE::GLASS": "window_glass",
        "ENSCAPE::DOOR": "door",
        "ENSCAPE::EXTERIOR WALL::CONCRETE PANELS": "wall",
        "FLOORPLATE": "floorplate",
        "Pergola": "pergola",
        "3D::Massing::Daycare": "massing",
        "Bart context": "context",
        "SITE::buildings": "context",
        "3D": "other",
        "Default": "other",
    }
    for layer, semantic in expected.items():
        assert rc.semantic_from_layer(layer, rc.KEYWORD_RULES) == semantic, layer


def test_semantic_from_layer_handles_none_and_unknown():
    assert rc.semantic_from_layer(None, rc.CSI_RULES) == "other"
    assert rc.semantic_from_layer("Layer 01", rc.KEYWORD_RULES) == "other"


# ---- ruleset auto-pick ----------------------------------------------------

def test_pick_ruleset_sniffs_csi():
    assert rc.pick_ruleset(["08 - OPENINGS::08-01", "31 - SITE"]) == "csi"
    assert rc.pick_ruleset(["ENSCAPE::GLASS", "FLOORPLATE", "3D"]) == "keyword"
    assert rc.pick_ruleset([]) == "keyword"


def test_resolve_rules():
    name, rules = rc.resolve_rules("auto", ["06 - WOOD::06-02"])
    assert (name, rules) == ("csi", rc.CSI_RULES)
    name, rules = rc.resolve_rules(None, ["ENSCAPE::GLASS"])
    assert (name, rules) == ("keyword", rc.KEYWORD_RULES)
    name, rules = rc.resolve_rules("keyword", [])
    assert (name, rules) == ("keyword", rc.KEYWORD_RULES)
    custom = [("FACADE", "wall")]
    name, rules = rc.resolve_rules(custom, [])
    assert name == "custom" and rules == custom
    with pytest.raises(ValueError, match="unknown ruleset"):
        rc.resolve_rules("bogus", [])
