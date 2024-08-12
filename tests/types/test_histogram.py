from __future__ import annotations

import hist
import numpy as np
import pytest

from lgdo import Array, Histogram, Scalar, lh5
from lgdo.lh5.exceptions import LH5DecodeError


def test_init_hist_regular():
    h = hist.Hist(
        hist.axis.Regular(bins=10, start=0, stop=1, name="x"),
        hist.axis.Regular(bins=10, start=0, stop=1, name="y"),
    )
    rng = np.random.default_rng()
    h.fill(rng.uniform(size=500), rng.uniform(size=500))
    h = Histogram(h, None)

    assert len(h.binning) == 2

    h = hist.Hist(hist.axis.Integer(start=0, stop=10))
    with pytest.raises(ValueError, match="only regular or variable axes"):
        h = Histogram(h)

    h = hist.Hist(hist.axis.Regular(bins=10, start=0, stop=1))
    with pytest.raises(ValueError, match="isdensity=True"):
        Histogram(h, isdensity=True)
    with pytest.raises(ValueError, match="custom binning"):
        Histogram(h, binning=(np.array([0, 1, 2]),))

    h.fill([-1, 0.8, 2])
    with pytest.raises(ValueError, match="flow bins"):
        Histogram(h)

    # assert that the hist data is not copied into the LGDO.
    h = hist.Hist(hist.axis.Regular(bins=10, start=0, stop=10))
    h.fill([1, 2, 3])
    hi = Histogram(h)
    assert np.sum(hi.weights.nda) == 3
    h.fill([1, 2, 3])
    assert np.sum(hi.weights.nda) == 6

    h = hist.Hist(
        hist.axis.Regular(bins=10, start=0, stop=10), storage=hist.storage.Mean()
    )
    h.fill([1, 2, 3], sample=[4, 4, 4])
    with pytest.raises(ValueError, match="simple numpy-backed storages"):
        hi = Histogram(h)


def test_init_hist_variable():
    h = hist.Hist(
        hist.axis.Variable((0, 0.5, 5), name="x"),
        hist.axis.Variable((0, 0.5, 5), name="y"),
    )
    rng = np.random.default_rng()
    h.fill(rng.uniform(size=500), rng.uniform(size=500))
    h = Histogram(h)

    assert len(h.binning) == 2


def test_init_np():
    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),))
    assert len(h.binning) == 1
    assert not h.isdensity

    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),), isdensity=True)
    assert h.isdensity

    with pytest.raises(ValueError, match="also pass binning"):
        h = Histogram(np.array([1, 1]), None)

    with pytest.raises(ValueError, match="dimensions do not match"):
        h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]), np.array([0, 1, 2])))

    with pytest.raises(ValueError, match="bin count does not match weight count"):
        h = Histogram(
            np.array([[1, 1], [1, 1]]), (np.array([0, 1, 2]), np.array([0, 1]))
        )

    h = Histogram(np.array([1, 1, 1]), (np.array([0, 1, 2.5, 3]),))


def test_datatype_name():
    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),))
    assert h.datatype_name() == "struct"
    assert h.form_datatype() == "struct{binning,weights,isdensity}"


def test_axes():
    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        (np.array([0, 1, 2]), np.array([2.1, 2.2, 2.3])),
        attrs={"units": "m"},
    )
    assert len(h.binning) == 2
    str(h)

    ax0 = h.binning[0]
    assert ax0.first == 0
    assert ax0.last == 2
    assert ax0.step == 1
    assert isinstance(ax0.nbins, int)
    assert len(ax0.edges) == 3
    assert str(ax0) == "first=0, last=2, step=1, closedleft=True"

    ax1 = h.binning[1]
    assert ax1.first == 2.1
    assert ax1.last == 2.3
    assert np.isclose(ax1.step, 0.1)
    assert isinstance(ax0.nbins, int)

    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        [(1, 3, 1), (4, 6, 1)],
    )
    ax0 = h.binning[0]
    str(h)

    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        [Histogram.Axis(None, 1, 3, 1), Histogram.Axis(None, 4, 6, 1, False)],
    )
    ax0 = h.binning[0]
    str(h)

    with pytest.raises(ValueError, match="invalid binning object"):
        h = Histogram(np.array([[1, 1], [1, 1]]), (range(2), range(2)))

    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        [Histogram.Axis(None, 1, 3, 1, True), Histogram.Axis(None, 4, 6, 1, False)],
    )

    with pytest.raises(ValueError, match="invalid binning object"):
        h = Histogram(
            np.array([[1, 1], [1, 1]]),
            [(1, 3, 1), Histogram.Axis(None, 4, 6, 1, False)],
        )

    h = Histogram(np.array([1, 1, 1]), (np.array([0, 1, 2.5, 3]),))
    with pytest.raises(TypeError, match="range"):
        x = h.binning[0].first
    with pytest.raises(TypeError, match="range"):
        x = h.binning[0].last
    with pytest.raises(TypeError, match="range"):
        x = h.binning[0].step  # noqa: F841
    assert h.binning[0].nbins == 3
    assert str(h.binning[0]) == "edges=[0.  1.  2.5 3. ], closedleft=True"

    with pytest.raises(ValueError, match="either from edges or from range"):
        Histogram.Axis(np.array([0, 1, 2.5, 3]), 0, 1, None)
    with pytest.raises(ValueError, match="all range parameters"):
        Histogram.Axis(None, 0, 1, None)


def test_ax_attributes():
    Histogram.Axis(
        np.array([0, 1, 2.5, 3]), None, None, None, binedge_attrs={"units": "m"}
    )

    with pytest.raises(ValueError, match="binedge_attrs"):
        Histogram.Axis(
            Array(np.array([0, 1, 2.5, 3])),
            None,
            None,
            None,
            binedge_attrs={"units": "m"},
        )
    with pytest.raises(ValueError, match=r"array<1>\{real\}"):
        Histogram.Axis(Array(np.array([[0, 1], [2.5, 3]])), None, None, None)

    ax = Histogram.Axis(
        np.array([0, 1, 2.5, 3]),
        None,
        None,
        None,
        binedge_attrs={"units": "m"},
    )
    assert (
        str(ax) == "edges=[0.  1.  2.5 3. ], closedleft=True with attrs={'units': 'm'}"
    )

    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        (np.array([0, 1, 2]), np.array([0, 1, 2])),
        binedge_attrs={"units": "m"},
    )
    assert str(h.binning[0]).endswith(", closedleft=True with attrs={'units': 'm'}")
    assert str(h.binning[1]).endswith(", closedleft=True with attrs={'units': 'm'}")
    assert h.binning[0].get_binedgeattrs() == {"units": "m"}

    with pytest.raises(ValueError):
        h = Histogram(
            np.array([[1, 1], [1, 1]]),
            [Histogram.Axis(None, 1, 3, 1, True), Histogram.Axis(None, 4, 6, 1, False)],
            binedge_attrs={"units": "m"},
        )


def test_view_as_hist():
    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),))
    hi = h.view_as("hist")
    assert isinstance(hi.axes[0], hist.axis.Regular)

    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),), isdensity=True)
    with pytest.raises(ValueError, match="cannot represent density"):
        h.view_as("hist")

    h = Histogram(
        np.array([[1, 1], [1, 1]]),
        [Histogram.Axis(None, 1, 3, 1, True), Histogram.Axis(None, 4, 6, 1, False)],
    )
    with pytest.raises(ValueError, match="cannot represent right-closed"):
        h.view_as("hist")

    h = Histogram(np.array([1, 1, 1]), (np.array([0, 1, 2.5, 3]),))
    hi = h.view_as("hist")
    assert isinstance(hi.axes[0], hist.axis.Variable)


def test_view_as_np():
    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),))
    assert h.binning[0].is_range
    assert h.binning[0].nbins == 2
    nda, axes = h.view_as("np")
    assert isinstance(nda, np.ndarray)
    assert len(axes) == 1
    assert np.array_equal(axes[0], np.array([0, 1, 2]))


def test_not_like_table():
    h = Histogram(np.array([1, 1]), (np.array([0, 1, 2]),))
    assert h.form_datatype() == "struct{binning,weights,isdensity}"
    with pytest.raises(TypeError):
        x = h.x  # noqa: F841
    with pytest.raises(TypeError):
        h["x"] = Scalar(1.0)
    with pytest.raises(TypeError):
        h.add_field("x", Scalar(1.0))
    with pytest.raises(TypeError):
        h.remove_field("binning")


def test_read_histogram_testdata(lgnd_test_data):
    file = lgnd_test_data.get_path("lh5/lgdo-histograms.lh5")

    h1 = lh5.read("test_histogram_range", file)
    assert isinstance(h1, Histogram)
    assert h1.binning[0].is_range

    h2 = lh5.read("test_histogram_variable", file)
    assert isinstance(h2, Histogram)
    assert not h2.binning[0].is_range

    h3 = lh5.read("test_histogram_range_w_attrs", file)
    assert isinstance(h3, Histogram)
    assert h3.binning[0].is_range
    assert h3.binning[0]["binedges"].getattrs() == {"units": "m"}


def test_read_histogram_multiple(lgnd_test_data):
    file = lgnd_test_data.get_path("lh5/lgdo-histograms.lh5")
    with pytest.raises(LH5DecodeError):
        lh5.read("test_histogram_range", [file, file])
