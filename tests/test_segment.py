import math

import pytest

from waam.segment import Mode, Segment, SegmentError, check_chain


def seg(rid=1, mode="D", t0=0.0, t1=1.0, p0=(0, 0, 1), p1=(8, 0, 1)):
    return Segment(rid, mode, t0, t1, p0, p1)


def test_basic_fields_and_normalisation():
    s = Segment(1, "D", 4, 14, [0, 0, 2], [80, 0, 2])
    assert s.mode is Mode.D
    assert (s.start_time_s, s.end_time_s) == (4.0, 14.0)
    assert s.start_xyz_mm == (0.0, 0.0, 2.0) and s.end_xyz_mm == (80.0, 0.0, 2.0)
    assert s.duration_s == 10.0 and s.length_xy_mm == 80.0 and s.length_mm == 80.0
    assert Segment(2, Mode.W, 0, 1, (1, 1, 1), (1, 1, 1)).mode is Mode.W


def test_frozen():
    with pytest.raises(Exception):
        seg().mode = Mode.T  # type: ignore[misc]


@pytest.mark.parametrize("bad", [0, 4, -1, True, "1", None])
def test_bad_robot_id(bad):
    with pytest.raises(SegmentError):
        seg(rid=bad)


@pytest.mark.parametrize("bad", ["d", "X", "", None, 1])
def test_bad_mode(bad):
    with pytest.raises(SegmentError):
        seg(mode=bad)


@pytest.mark.parametrize("t0,t1", [(1.0, 1.0), (2.0, 1.0), (-0.5, 1.0),
                                   (0.0, math.inf), (math.nan, 1.0), (0.0, math.nan)])
def test_bad_times(t0, t1):
    with pytest.raises(SegmentError):
        seg(t0=t0, t1=t1)


@pytest.mark.parametrize("p", [(0, 0), (0, 0, 0, 0), (math.nan, 0, 0), (0, math.inf, 0),
                               ("a", 0, 0), None, 5])
def test_bad_xyz(p):
    with pytest.raises(SegmentError):
        seg(p0=p)
    with pytest.raises(SegmentError):
        seg(p1=p)


def _chain():
    return [
        seg(mode="T", t0=0.0, t1=4.0, p0=(-1000, -600, 100), p1=(-40, 0, 2)),
        seg(mode="D", t0=4.0, t1=14.0, p0=(-40, 0, 2), p1=(40, 0, 2)),
        seg(mode="W", t0=14.0, t1=18.0, p0=(40, 0, 2), p1=(40, 0, 2)),
    ]


def test_chain_ok():
    check_chain(_chain())


def test_chain_rejects_each_violation():
    with pytest.raises(SegmentError):
        check_chain([])
    c = _chain()
    c[0] = seg(mode="T", t0=0.5, t1=4.0, p0=(-1000, -600, 100), p1=(-40, 0, 2))
    with pytest.raises(SegmentError, match="start at 0.0"):
        check_chain(c)
    c = _chain()
    c[1] = seg(mode="D", t0=4.5, t1=14.0, p0=(-40, 0, 2), p1=(40, 0, 2))
    with pytest.raises(SegmentError, match="gap"):
        check_chain(c)
    c = _chain()
    c[1] = seg(mode="D", t0=3.0, t1=14.0, p0=(-40, 0, 2), p1=(40, 0, 2))
    with pytest.raises(SegmentError, match="gap/overlap"):
        check_chain(c)
    c = _chain()
    c[1] = seg(mode="D", t0=4.0, t1=14.0, p0=(-41, 0, 2), p1=(40, 0, 2))
    with pytest.raises(SegmentError, match="jump"):
        check_chain(c)
    c = _chain()
    c[2] = seg(mode="T", t0=14.0, t1=18.0, p0=(40, 0, 2), p1=(40, 0, 2))
    with pytest.raises(SegmentError, match="last segment must be W"):
        check_chain(c)
    c = _chain()
    c[1] = seg(rid=2, mode="D", t0=4.0, t1=14.0, p0=(-40, 0, 2), p1=(40, 0, 2))
    with pytest.raises(SegmentError, match="mixed robot"):
        check_chain(c)
