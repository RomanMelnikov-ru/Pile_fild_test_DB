# graphics/plot_canvas.py
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class PlotCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = Figure(figsize=(5, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.clear_plot()

    def clear_plot(self):
        self.ax.clear()
        self.ax.set_title("График испытания сваи: S = f(N)")
        self.ax.set_xlabel("Нагрузка N, кН")
        self.ax.set_ylabel("Осадка S, мм")
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self.canvas.draw()

    def plot_curve(self, points: list, unload_points: list = None, pile_label: str = "Свая", fu_load: float = None,
                   fu_settlement: float = None):
        self.ax.clear()
        if not points:
            self.clear_plot()
            return

        loads = [p[0] for p in points]
        settlements = [p[1] for p in points]

        # 1. Ветвь нагружения
        self.ax.plot(loads, settlements, marker='o', markersize=5, color='#1f77b4', linewidth=2,
                     label=f"Нагружение ({pile_label})")

        # 2. Ветвь разгрузки (если задана)
        if unload_points and len(unload_points) > 0:
            un_loads = [p[0] for p in unload_points]
            un_settlements = [p[1] for p in unload_points]
            self.ax.plot(un_loads, un_settlements, marker='s', markersize=4, linestyle='--', color='#2ca02c',
                         linewidth=1.8, label="Разгрузка")

        # 3. Авторасчет недостающей координаты Fd
        if len(loads) >= 2:
            if (fu_settlement is not None and fu_settlement > 0) and (fu_load is None or fu_load <= 0):
                fu_load = float(np.interp(fu_settlement, settlements, loads))
            elif (fu_load is not None and fu_load > 0) and (fu_settlement is None or fu_settlement <= 0):
                fu_settlement = float(np.interp(fu_load, loads, settlements))

        # Отрисовка точки несущей способности Fd и проекций
        if fu_load is not None and fu_settlement is not None and fu_load > 0 and fu_settlement > 0:
            self.ax.plot(fu_load, fu_settlement, marker='*', markersize=14, color='red',
                         label=f"Fd = {fu_load:.1f} кН (S={fu_settlement:.1f} мм)")
            self.ax.plot([fu_load, fu_load], [0, fu_settlement], color='red', linestyle=':', linewidth=1.5)
            self.ax.plot([0, fu_load], [fu_settlement, fu_settlement], color='red', linestyle=':', linewidth=1.5)

        self.ax.set_title(f"Кривая нагрузка-осадка: {pile_label}")
        self.ax.set_xlabel("Нагрузка N, кН")
        self.ax.set_ylabel("Осадка S, мм")

        self.ax.set_ylim(bottom=0)
        self.ax.set_xlim(left=0)
        self.ax.invert_yaxis()  # Осадка растет вниз
        self.ax.grid(True, linestyle="--", alpha=0.6)
        self.ax.legend(loc='lower left')
        self.canvas.draw()