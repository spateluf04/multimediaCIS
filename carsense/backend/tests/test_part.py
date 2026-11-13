import pytest

from carsense.knowledge.part import Part


def test_stub_entry():
    p = Part.from_dict({"id": "brake_pads", "name": "Brake pads", "cost_level": "Low"})
    assert p.id == "brake_pads"
    assert p.name == "Brake pads"
    assert p.cost_level == "Low"
    assert p.description == ""
    assert p.images == []
    assert p.video is None
    assert p.cost_range is None


def test_full_entry():
    p = Part.from_dict({
        "id": "wheel_bearing",
        "name": "Wheel bearing",
        "cost_level": "Medium",
        "description": "Lets the wheel spin smoothly on the axle.",
        "images": ["images/wheel_bearing_1.jpg", "images/wheel_bearing_2.jpg"],
        "video": "videos/wheel_bearing.mp4",
        "cost_range": "$150-$400",
    })
    assert len(p.images) == 2
    assert p.video == "videos/wheel_bearing.mp4"
    assert p.cost_range == "$150-$400"


@pytest.mark.parametrize("key", ["id", "name", "cost_level"])
def test_missing_required(key):
    data = {"id": "battery", "name": "Battery", "cost_level": "Low"}
    del data[key]
    with pytest.raises(ValueError):
        Part.from_dict(data)


def test_extra_keys_ignored():
    p = Part.from_dict({"id": "battery", "name": "Battery", "cost_level": "Low", "labor_hours": 0.5})
    assert not hasattr(p, "labor_hours")


def test_images_copied():
    images = ["images/battery.jpg"]
    p = Part.from_dict({"id": "battery", "name": "Battery", "cost_level": "Low", "images": images})
    images.append("images/other.jpg")
    assert p.images == ["images/battery.jpg"]


def test_to_dict():
    data = {
        "id": "suspension",
        "name": "Suspension parts",
        "cost_level": "Medium",
        "description": "",
        "images": [],
        "video": None,
        "cost_range": None,
    }
    assert Part.from_dict(data).to_dict() == data
