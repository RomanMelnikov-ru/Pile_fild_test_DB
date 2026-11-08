# dialogs/sp24_dialog.py
"""
Диалог расчёта несущей способности свай по грунту.
СП 24.13330.2021 «Свайные фундаменты», аналитический метод (п. 7.2).

Вызывается из контекстного меню сваи в главном окне.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox,
    QSizePolicy, QScrollArea, QWidget, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from core.sp24_calculations import calc_sp24


# Поддерживаемые типы свай (без Винтовой)
SUPPORTED_PILE_TYPES = {"Забивная", "Вдавливаемая", "Вибропогружение", "Буронабивная"}


class SP24Dialog(QDialog):
    """
    Диалог расчёта несущей способности одиночной сваи по грунту,
    аналитический метод СП 24.13330.2021 п. 7.2.
    """

    def __init__(self, pile: dict, bh: dict, layers: list, parent=None):
        """
        :param pile:    Словарь данных испытания сваи (из db.get_pile_tests_by_borehole)
        :param bh:      Словарь скважины (borehole)
        :param layers:  Список слоёв скважины (из db.get_borehole_layers)
        :param parent:  Родительский виджет
        """
        super().__init__(parent)
        self.pile = pile
        self.bh = bh
        self.layers = layers

        self.setWindowTitle(
            f"Расчёт по СП 24.13330.2021 — {pile.get('pile_name', '')} "
            f"({pile.get('pile_type', '')})"
        )
        self.resize(1100, 780)

        self._build_ui()
        self._populate_inputs()

        # Выполним расчёт сразу при открытии
        self._run_calculation()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Заголовок
        title = QLabel(
            "<b>Расчёт несущей способности сваи по грунту</b><br>"
            "<small>Аналитический метод, п. 7.2 СП 24.13330.2021</small>"
        )
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # --- Параметры сваи (редактируемые) ---
        params_group = QGroupBox("Параметры сваи")
        params_form = QFormLayout(params_group)

        self.lbl_pile_type = QLabel()
        params_form.addRow("Способ погружения:", self.lbl_pile_type)

        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(0.5, 150.0)
        self.spin_length.setSuffix(" м")
        self.spin_length.setDecimals(2)
        params_form.addRow("Длина ствола L:", self.spin_length)

        self.spin_diam = QDoubleSpinBox()
        self.spin_diam.setRange(0.05, 5.0)
        self.spin_diam.setSingleStep(0.05)
        self.spin_diam.setSuffix(" м")
        self.spin_diam.setDecimals(3)
        params_form.addRow("Диаметр / сторона сечения d:", self.spin_diam)

        self.spin_head_z = QDoubleSpinBox()
        self.spin_head_z.setRange(-500.0, 5000.0)
        self.spin_head_z.setSuffix(" м")
        self.spin_head_z.setDecimals(2)
        params_form.addRow("Отметка оголовка Z:", self.spin_head_z)

        self.lbl_bh_z = QLabel()
        params_form.addRow("Отметка устья скважины:", self.lbl_bh_z)

        # Коэффициент надёжности γk
        self.spin_gamma_k = QDoubleSpinBox()
        self.spin_gamma_k.setRange(1.0, 2.0)
        self.spin_gamma_k.setSingleStep(0.05)
        self.spin_gamma_k.setValue(1.4)
        self.spin_gamma_k.setDecimals(2)
        self.spin_gamma_k.setToolTip(
            "Коэффициент надёжности γk по СП 24 п. 7.1.11.\n"
            "Для полевых испытаний: 1.2–1.25\n"
            "Аналитический метод без испытаний: 1.4–1.5"
        )
        params_form.addRow("Коэф. надёжности γk:", self.spin_gamma_k)

        root.addWidget(params_group)

        calc_btn = QPushButton("▶  Выполнить расчёт")
        calc_btn.setFixedHeight(36)
        calc_btn.setStyleSheet("font-weight: bold; font-size: 13px;")
        calc_btn.clicked.connect(self._run_calculation)
        root.addWidget(calc_btn)

        # --- Результаты ---
        results_group = QGroupBox("Результаты расчёта")
        results_layout = QVBoxLayout(results_group)

        # Итоговые значения
        summary_layout = QHBoxLayout()

        self.lbl_R_tip = self._make_result_label("R · A", "—", "кН")
        self.lbl_F_lat = self._make_result_label("u · Σfi·hi", "—", "кН")
        self.lbl_Fd = self._make_result_label("Fd (несущая)", "—", "кН", bold=True, color="#1a5276")
        self.lbl_Fd_design = self._make_result_label("Fd / γk (расч.)", "—", "кН", bold=True, color="#922b21")

        summary_layout.addWidget(self.lbl_R_tip)
        summary_layout.addWidget(self.lbl_F_lat)
        summary_layout.addWidget(self.lbl_Fd)
        summary_layout.addWidget(self.lbl_Fd_design)
        results_layout.addLayout(summary_layout)

        # Дополнительная информация
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color: #555; font-size: 11px;")
        results_layout.addWidget(self.lbl_info)

        # --- Таблица послойного расчёта ---
        tbl_label = QLabel("<b>Послойный расчёт бокового сопротивления (Таблица 7.3 СП 24):</b>")
        results_layout.addWidget(tbl_label)

        self.tbl_sublayers = QTableWidget(0, 8)
        self.tbl_sublayers.setHorizontalHeaderLabels([
            "ИГЭ", "Вид грунта", "IL / Фракция",
            "z кровли, м", "z подошвы, м",
            "hi, м", "fi, кПа", "fi·hi, кН/м"
        ])
        self.tbl_sublayers.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl_sublayers.horizontalHeader().setStretchLastSection(True)
        self.tbl_sublayers.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_sublayers.setAlternatingRowColors(True)
        self.tbl_sublayers.setMinimumHeight(220)
        results_layout.addWidget(self.tbl_sublayers)

        # --- Итоговая строка ---
        self.lbl_formula = QLabel()
        self.lbl_formula.setWordWrap(True)
        self.lbl_formula.setTextFormat(Qt.RichText)
        results_layout.addWidget(self.lbl_formula)

        # Предупреждения
        self.lbl_warnings = QLabel()
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet("color: #c0392b; font-weight: bold;")
        results_layout.addWidget(self.lbl_warnings)

        root.addWidget(results_group)

        # Кнопка закрыть
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        root.addWidget(close_btn)

    def _make_result_label(self, title: str, value: str, unit: str,
                           bold: bool = False, color: str = "#1a3c5e") -> QFrame:
        """Создаёт красивую карточку с заголовком и значением."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(
            f"QFrame {{ background: #eaf4fc; border-radius: 6px; border: 1px solid #aad4ee; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(lbl_title)

        lbl_val = QLabel(f"{value} {unit}")
        lbl_val.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16 if bold else 13)
        font.setBold(bold)
        lbl_val.setFont(font)
        lbl_val.setStyleSheet(f"color: {color};")
        layout.addWidget(lbl_val)

        # Сохраняем ссылку на label значения для обновления
        frame._value_label = lbl_val
        frame._unit = unit
        return frame

    def _update_result_label(self, frame: QFrame, value: str):
        frame._value_label.setText(f"{value} {frame._unit}")

    # ------------------------------------------------------------------
    # Заполнение начальных значений
    # ------------------------------------------------------------------

    def _populate_inputs(self):
        pile_type = self.pile.get('pile_type', '')
        self.lbl_pile_type.setText(f"<b>{pile_type}</b>")

        if pile_type not in SUPPORTED_PILE_TYPES:
            self.lbl_pile_type.setText(
                f"<b style='color:red'>{pile_type}</b> — этот тип не поддерживается расчётом по п. 7.2 СП 24"
            )

        self.spin_length.setValue(self.pile.get('length', 12.0) or 12.0)
        self.spin_diam.setValue(self.pile.get('diameter', 0.3) or 0.3)
        self.spin_head_z.setValue(self.pile.get('head_z', 100.0) or 100.0)

        bh_z = self.bh.get('z_collar') or 0.0
        self.lbl_bh_z.setText(f"<b>{bh_z:.2f} м</b>  (скважина {self.bh.get('name', '')})")

    # ------------------------------------------------------------------
    # Расчёт
    # ------------------------------------------------------------------

    def _run_calculation(self):
        pile_type = self.pile.get('pile_type', '')
        if pile_type not in SUPPORTED_PILE_TYPES:
            QMessageBox.warning(
                self, "Не поддерживается",
                f"Расчёт по п. 7.2 СП 24 для типа сваи «{pile_type}» не реализован.\n"
                "Поддерживаются: Забивная, Вдавливаемая, Вибропогружение, Буронабивная."
            )
            return

        length = self.spin_length.value()
        diameter = self.spin_diam.value()
        head_z = self.spin_head_z.value()
        gamma_k = self.spin_gamma_k.value()
        bh_z_collar = self.bh.get('z_collar') or 0.0

        result = calc_sp24(
            pile_type=pile_type,
            length=length,
            diameter=diameter,
            head_z=head_z,
            bh_z_collar=bh_z_collar,
            layers=self.layers
        )

        self._display_results(result, gamma_k)

    # ------------------------------------------------------------------
    # Отображение результатов
    # ------------------------------------------------------------------

    def _display_results(self, res: dict, gamma_k: float):
        Fd = res['Fd']
        Fd_design = round(Fd / gamma_k, 1) if gamma_k > 0 else Fd

        self._update_result_label(self.lbl_R_tip, f"{res['R_tip']:.1f}")
        self._update_result_label(self.lbl_F_lat, f"{res['F_lateral']:.1f}")
        self._update_result_label(self.lbl_Fd, f"{Fd:.1f}")
        self._update_result_label(self.lbl_Fd_design, f"{Fd_design:.1f}")

        gc, gcR, gcf = res['gammas']
        depth_tip = res['depth_tip']
        z_tip = res['z_tip']
        A = res['A']
        u = res['u']
        R_kPa = res.get('R_kPa', 0.0)
        tip = res.get('tip_layer')
        tip_desc = f"{tip['soil_type']} (ИГЭ {tip.get('ige_code', '')})" if tip else "—"

        self.lbl_info.setText(
            f"Глубина нижнего конца: <b>{depth_tip:.2f} м</b>  |  "
            f"Отметка острия: <b>{z_tip:.2f} м</b>  |  "
            f"Грунт под острием: <b>{tip_desc}</b>  |  "
            f"R = <b>{R_kPa:.1f} кПа</b>  |  "
            f"A = {A:.4f} м²  |  u = {u:.4f} м  |  "
            f"γc={gc}  γcR={gcR}  γcf={gcf}"
        )

        # --- Таблица подслоёв ---
        self.tbl_sublayers.setRowCount(0)
        sublayers = res.get('sublayers', [])
        total_fi_hi = 0.0

        for sub in sublayers:
            r = self.tbl_sublayers.rowCount()
            self.tbl_sublayers.insertRow(r)

            il_or_frac = ""
            if sub.get('il') is not None:
                il_or_frac = f"IL={sub['il']:.2f}"
                if sub.get('consistency'):
                    il_or_frac += f" ({sub['consistency']})"
            elif sub.get('sand_fraction'):
                il_or_frac = sub['sand_fraction']

            items = [
                sub.get('ige_code', ''),
                sub.get('soil_type', ''),
                il_or_frac,
                f"{sub['depth_top_sub']:.2f}",
                f"{sub['depth_bot_sub']:.2f}",
                f"{sub['h']:.2f}",
                f"{sub['fi']:.2f}",
                f"{sub['fi_hi']:.2f}",
            ]
            for c, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                self.tbl_sublayers.setItem(r, c, item)

            total_fi_hi += sub['fi_hi']

        # Итоговая строка Σ
        if sublayers:
            r = self.tbl_sublayers.rowCount()
            self.tbl_sublayers.insertRow(r)
            sigma_item = QTableWidgetItem("Σ")
            sigma_item.setTextAlignment(Qt.AlignCenter)
            font = QFont(); font.setBold(True)
            sigma_item.setFont(font)
            self.tbl_sublayers.setItem(r, 0, sigma_item)

            sum_item = QTableWidgetItem(f"{total_fi_hi:.2f}")
            sum_item.setTextAlignment(Qt.AlignCenter)
            sum_item.setFont(font)
            sum_item.setBackground(QColor("#d5f5e3"))
            self.tbl_sublayers.setItem(r, 7, sum_item)

            # Закрашиваем итоговую строку
            for c in range(self.tbl_sublayers.columnCount()):
                item = self.tbl_sublayers.item(r, c)
                if item:
                    item.setBackground(QColor("#d5f5e3"))

        # --- Формульная строка ---
        sum_fi_hi_u = round(u * total_fi_hi, 1)
        self.lbl_formula.setText(
            f"<b>Формула СП 24 п. 7.2:</b><br>"
            f"F<sub>d</sub> = γ<sub>c</sub> · (γ<sub>cR</sub> · R · A + u · Σγ<sub>cf</sub> · f<sub>i</sub> · h<sub>i</sub>)<br>"
            f"F<sub>d</sub> = {gc} · ({gcR} · {R_kPa:.1f} · {A:.4f} + {u:.4f} · {gcf} · {total_fi_hi:.2f})<br>"
            f"F<sub>d</sub> = {gc} · ({res['R_tip']:.1f} + {res['F_lateral']:.1f}) = <b>{Fd:.1f} кН</b><br>"
            f"Расчётная нагрузка: F<sub>d</sub> / γ<sub>k</sub> = {Fd:.1f} / {gamma_k:.2f} = <b>{Fd_design:.1f} кН</b>"
        )

        # --- Предупреждения ---
        warnings = res.get('warnings', [])
        if warnings:
            self.lbl_warnings.setText("Предупреждения:\n" + "\n".join(warnings))
        else:
            self.lbl_warnings.setText("")
