from PySide6.QtWidgets import QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class BSICanvas(FigureCanvas):
    """Matplotlib placeholder chart – update later with real data."""

    def __init__(self, parent: QWidget | None = None) -> None:
        fig = Figure(figsize=(4, 3))
        super().__init__(fig)
        self.axes = fig.add_subplot(111)
        self._plot_dummy()

    def _plot_dummy(self) -> None:
        years = [0, 0.5, 1]
        bsi   = [5.3, 4.1, 9.6]
        self.axes.clear()
        self.axes.plot(years, bsi, marker="o")
        self.axes.set_xlabel("Time (Years)")
        self.axes.set_ylabel("Bone Scan Index (%)")
        self.draw()
