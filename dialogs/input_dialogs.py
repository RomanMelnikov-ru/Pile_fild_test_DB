# dialogs/input_dialogs.py
import numpy as np
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QDoubleSpinBox, QSpinBox, QTableWidgetItem,
                             QPushButton, QComboBox, QMessageBox, QLabel, QHeaderView,
                             QTabWidget, QWidget, QCheckBox)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from dialogs.pasteable_table import PasteableTableWidget
from core.geotech_standards import (SOIL_TYPES_REGISTRY, SAND_FRACTIONS, SAND_DENSITIES,
                                    CLAY_CONSISTENCIES, check_clay_type_by_ip,
                                    get_clay_consistency_by_il, get_sand_density_by_e)
from core.db import get_project_ige_registry, upsert_project_ige, get_connection


class ProjectDialog(QDialog):
    def __init__(self, current_name="", current_desc="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры объекта")
        self.resize(380, 150)
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(current_name)
        self.desc_edit = QLineEdit(current_desc)
        layout.addRow("Наименование объекта:", self.name_edit)
        layout.addRow("Описание / Шифр:", self.desc_edit)
        btn = QPushButton("Сохранить")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_data(self):
        return self.name_edit.text().strip(), self.desc_edit.text().strip()


class ProjectIgeManagerDialog(QDialog):
    """Окно предварительного создания и редактирования сводного реестра ИГЭ объекта по отчету ИГИ."""

    def __init__(self, project_id: int, project_name: str, parent=None):
        super().__init__(parent)
        self.project_id = project_id
        self.setWindowTitle(f"Реестр ИГЭ объекта: {project_name}")
        self.resize(1150, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Сводная таблица физико-механических свойств грунтов (ИГЭ) по отчету ИГИ:\n"
                                "Поддерживается вставка из Excel через Ctrl+V"))

        self.table = PasteableTableWidget(0, 13)
        self.headers = [
            "ИГЭ", "Вид грунта", "Крупность песка", "Плотн. сложения", "Консистенция",
            "Плотн. ρ", "Влажн. w", "IL", "IP", "Порист. e", "φ, град", "c, кПа", "E, МПа"
        ]
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Добавить ИГЭ")
        add_btn.clicked.connect(self.add_empty_row)
        del_btn = QPushButton("Удалить выбранный ИГЭ")
        del_btn.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        save_btn = QPushButton("Сохранить реестр ИГЭ")
        save_btn.clicked.connect(self.save_registry)
        layout.addWidget(save_btn)

        self.load_current_registry()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def add_row_with_data(self, d: dict = None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        d = d or {}

        self.table.setItem(r, 0, QTableWidgetItem(str(d.get('ige_code', f"ИГЭ-{r + 1}"))))

        type_combo = QComboBox()
        type_combo.addItems(SOIL_TYPES_REGISTRY)
        curr_soil = d.get('soil_type', "Песок")
        type_combo.setCurrentText(curr_soil)
        type_combo.currentTextChanged.connect(lambda text, row=r: self.on_soil_type_changed(row, text))
        self.table.setCellWidget(r, 1, type_combo)

        sand_combo = QComboBox()
        sand_combo.addItems(SAND_FRACTIONS)
        if d.get('sand_fraction'): sand_combo.setCurrentText(d['sand_fraction'])
        self.table.setCellWidget(r, 2, sand_combo)

        dens_combo = QComboBox()
        dens_combo.addItems(SAND_DENSITIES)
        if d.get('sand_density'): dens_combo.setCurrentText(d['sand_density'])
        self.table.setCellWidget(r, 3, dens_combo)

        cons_combo = QComboBox()
        cons_combo.addItems(CLAY_CONSISTENCIES)
        if d.get('consistency'): cons_combo.setCurrentText(d['consistency'])
        self.table.setCellWidget(r, 4, cons_combo)

        self.table.setItem(r, 5, QTableWidgetItem(str(d.get('density') or '1.95')))
        self.table.setItem(r, 6, QTableWidgetItem(str(d.get('moisture') or '0.18')))
        self.table.setItem(r, 7, QTableWidgetItem(str(d.get('il', '')) if d.get('il') is not None else ''))
        self.table.setItem(r, 8, QTableWidgetItem(str(d.get('ip', '')) if d.get('ip') is not None else ''))
        self.table.setItem(r, 9, QTableWidgetItem(str(d.get('e_ratio') or '0.65')))
        self.table.setItem(r, 10, QTableWidgetItem(str(d.get('friction_angle') or '30')))
        self.table.setItem(r, 11, QTableWidgetItem(str(d.get('cohesion') or '2')))
        self.table.setItem(r, 12, QTableWidgetItem(str(d.get('e_modulus') or '25')))

        self.on_soil_type_changed(r, curr_soil)

    def add_empty_row(self):
        self.add_row_with_data()

    def on_soil_type_changed(self, row, soil_type):
        sand_widget = self.table.cellWidget(row, 2)
        dens_widget = self.table.cellWidget(row, 3)
        cons_widget = self.table.cellWidget(row, 4)

        if soil_type == "Песок":
            if sand_widget: sand_widget.setEnabled(True)
            if dens_widget: dens_widget.setEnabled(True)
            if cons_widget: cons_widget.setEnabled(False)
            for c in [7, 8]:
                item = self.table.item(row, c)
                if item:
                    item.setText("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setBackground(QColor(235, 235, 235))
        elif soil_type in ["Супесь", "Суглинок", "Глина"]:
            if sand_widget: sand_widget.setEnabled(False)
            if dens_widget: dens_widget.setEnabled(False)
            if cons_widget: cons_widget.setEnabled(True)
            for c in [7, 8]:
                item = self.table.item(row, c)
                if item:
                    item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    item.setBackground(QColor(255, 255, 255))
        else:
            if sand_widget: sand_widget.setEnabled(False)
            if dens_widget: dens_widget.setEnabled(False)
            if cons_widget: cons_widget.setEnabled(False)
            for c in [7, 8]:
                item = self.table.item(row, c)
                if item:
                    item.setText("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setBackground(QColor(235, 235, 235))

    def load_current_registry(self):
        records = get_project_ige_registry(self.project_id)
        if records:
            for r in records:
                self.add_row_with_data(r)
        else:
            self.add_empty_row()

    def save_registry(self):
        def _to_float(item):
            if not item or not item.text(): return None
            try:
                return float(item.text().replace(',', '.'))
            except ValueError:
                return None

        with get_connection() as conn:
            conn.execute("DELETE FROM project_ige_registry WHERE project_id = ?", (self.project_id,))
            conn.commit()

        for r in range(self.table.rowCount()):
            ige_code = self.table.item(r, 0).text().strip() if self.table.item(r, 0) else ""
            if not ige_code: continue

            soil_combo = self.table.cellWidget(r, 1)
            sand_combo = self.table.cellWidget(r, 2)
            dens_combo = self.table.cellWidget(r, 3)
            cons_combo = self.table.cellWidget(r, 4)

            data = {
                "ige_code": ige_code,
                "soil_type": soil_combo.currentText() if soil_combo else "Песок",
                "sand_fraction": sand_combo.currentText() if sand_combo and sand_combo.isEnabled() else None,
                "sand_density": dens_combo.currentText() if dens_combo and dens_combo.isEnabled() else None,
                "consistency": cons_combo.currentText() if cons_combo and cons_combo.isEnabled() else None,
                "density": _to_float(self.table.item(r, 5)),
                "moisture": _to_float(self.table.item(r, 6)),
                "il": _to_float(self.table.item(r, 7)),
                "ip": _to_float(self.table.item(r, 8)),
                "e_ratio": _to_float(self.table.item(r, 9)),
                "friction_angle": _to_float(self.table.item(r, 10)),
                "cohesion": _to_float(self.table.item(r, 11)),
                "e_modulus": _to_float(self.table.item(r, 12))
            }
            upsert_project_ige(self.project_id, data)

        QMessageBox.information(self, "Успешно", "Реестр ИГЭ объекта сохранен!")
        self.accept()


class BoreholeDialog(QDialog):
    def __init__(self, projects: list, current_bh: dict = None, layers: list = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование скважины" if current_bh else "Добавление скважины")
        self.current_bh = current_bh
        self._is_updating_depths = False
        self.projects = projects

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.proj_combo = QComboBox()
        for p in projects:
            self.proj_combo.addItem(p['name'], p['id'])
        if current_bh:
            idx = self.proj_combo.findData(current_bh['project_id'])
            if idx >= 0: self.proj_combo.setCurrentIndex(idx)
        self.proj_combo.currentIndexChanged.connect(self.reload_ige_registry)

        self.name_edit = QLineEdit(current_bh['name'] if current_bh else "")
        self.x_spin = QDoubleSpinBox();
        self.x_spin.setRange(-1e7, 1e7);
        self.x_spin.setValue(current_bh['x'] or 0.0 if current_bh else 0.0)
        self.y_spin = QDoubleSpinBox();
        self.y_spin.setRange(-1e7, 1e7);
        self.y_spin.setValue(current_bh['y'] or 0.0 if current_bh else 0.0)
        self.z_spin = QDoubleSpinBox();
        self.z_spin.setRange(-500.0, 5000.0);
        self.z_spin.setValue(current_bh['z_collar'] or 100.0 if current_bh else 100.0)
        self.gw_spin = QDoubleSpinBox();
        self.gw_spin.setRange(-1.0, 500.0);
        self.gw_spin.setValue(current_bh['gw_level'] if current_bh and current_bh['gw_level'] is not None else -1.0)
        self.note_edit = QLineEdit(current_bh['note'] or "" if current_bh else "")

        coords_row = QHBoxLayout()
        coords_row.addWidget(QLabel("X:"));
        coords_row.addWidget(self.x_spin)
        coords_row.addWidget(QLabel("Y:"));
        coords_row.addWidget(self.y_spin)
        coords_row.addWidget(QLabel("Устье Z:"));
        coords_row.addWidget(self.z_spin)

        form.addRow("Объект (отчет ИГИ):", self.proj_combo)
        form.addRow("Номер скважины:", self.name_edit)
        form.addRow("Координаты:", coords_row)
        form.addRow("Глубина УГВ, м (-1 если нет):", self.gw_spin)
        form.addRow("Примечание:", self.note_edit)
        layout.addLayout(form)

        # Таблица напластований скважины
        self.table = PasteableTableWidget(0, 16)
        self.headers = [
            "ИГЭ", "Вид грунта", "Крупность песка", "Плотн. сложения", "Консистенция",
            "Кровля, м", "Мощность, м", "Подошва, м", "Плотн. ρ", "Влажн. w",
            "IL", "IP", "Порист. e", "φ, град", "c, кПа", "E, МПа"
        ]
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.on_cell_changed)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_row_btn = QPushButton("+ Добавить пласт")
        add_row_btn.clicked.connect(self.add_layer_row)

        dup_row_btn = QPushButton("📋 Дублировать пласт")
        dup_row_btn.clicked.connect(self.duplicate_layer_row)
        up_btn = QPushButton("▲ Вверх")
        up_btn.clicked.connect(self.move_layer_up)
        down_btn = QPushButton("▼ Вниз")
        down_btn.clicked.connect(self.move_layer_down)
        del_row_btn = QPushButton("Удалить пласт")
        del_row_btn.clicked.connect(self.delete_selected_row)

        btn_row.addWidget(add_row_btn)
        btn_row.addWidget(dup_row_btn)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addWidget(del_row_btn)
        layout.addLayout(btn_row)

        save_btn = QPushButton("Сохранить скважину")
        save_btn.clicked.connect(self.validate_and_accept)
        layout.addWidget(save_btn)

        self.reload_ige_registry()

        if layers:
            for l in layers:
                self.add_layer_row(l)
        elif not current_bh:
            self.add_layer_row()

    def showEvent(self, event):
        super().showEvent(event)
        self.showMaximized()

    def reload_ige_registry(self):
        proj_id = self.proj_combo.currentData()
        if proj_id:
            self.ige_registry = {r['ige_code']: r for r in get_project_ige_registry(proj_id)}
        else:
            self.ige_registry = {}

    def add_layer_row(self, data: dict = None):
        self._is_updating_depths = True
        r = self.table.rowCount()
        self.table.insertRow(r)

        prev_bottom = 0.0 if r == 0 else float(self.table.item(r - 1, 7).text().replace(',', '.'))
        d = data or {}

        top_val = d.get('depth_top', prev_bottom)
        bot_val = d.get('depth_bottom', top_val + 3.0)
        thick_val = round(bot_val - top_val, 2)

        # 0. ИГЭ (Выпадающий список с возможностью ручного ввода)
        ige_combo = QComboBox()
        ige_combo.setEditable(True)
        if self.ige_registry:
            ige_combo.addItems(list(self.ige_registry.keys()))
        curr_ige = d.get('ige_code', f"ИГЭ-{r + 1}")
        ige_combo.setCurrentText(str(curr_ige))
        ige_combo.currentTextChanged.connect(lambda text, row=r: self.on_ige_selected(row, text))
        self.table.setCellWidget(r, 0, ige_combo)

        # 1. Вид грунта
        type_combo = QComboBox()
        type_combo.addItems(SOIL_TYPES_REGISTRY)
        curr_soil = d.get('soil_type', "Песок")
        type_combo.setCurrentText(curr_soil)
        type_combo.currentTextChanged.connect(lambda text, row=r: self.on_soil_type_changed(row, text))
        self.table.setCellWidget(r, 1, type_combo)

        # 2. Крупность песка
        sand_combo = QComboBox()
        sand_combo.addItems(SAND_FRACTIONS)
        if d.get('sand_fraction'): sand_combo.setCurrentText(d['sand_fraction'])
        self.table.setCellWidget(r, 2, sand_combo)

        # 3. Плотность сложения
        dens_combo = QComboBox()
        dens_combo.addItems(SAND_DENSITIES)
        if d.get('sand_density'): dens_combo.setCurrentText(d['sand_density'])
        self.table.setCellWidget(r, 3, dens_combo)

        # 4. Консистенция
        cons_combo = QComboBox()
        cons_combo.addItems(CLAY_CONSISTENCIES)
        if d.get('consistency'): cons_combo.setCurrentText(d['consistency'])
        self.table.setCellWidget(r, 4, cons_combo)

        # 5. Кровля
        item_top = QTableWidgetItem(f"{top_val:.2f}")
        item_top.setFlags(item_top.flags() & ~Qt.ItemIsEditable)
        item_top.setBackground(QColor(245, 245, 245))
        self.table.setItem(r, 5, item_top)

        # 6. Мощность
        self.table.setItem(r, 6, QTableWidgetItem(f"{thick_val:.2f}"))

        # 7. Подошва
        self.table.setItem(r, 7, QTableWidgetItem(f"{bot_val:.2f}"))

        # 8-15. ФМХ
        self.table.setItem(r, 8, QTableWidgetItem(str(d.get('density') or '1.95')))
        self.table.setItem(r, 9, QTableWidgetItem(str(d.get('moisture') or '0.18')))
        self.table.setItem(r, 10, QTableWidgetItem(str(d.get('il', '')) if d.get('il') is not None else ''))
        self.table.setItem(r, 11, QTableWidgetItem(str(d.get('ip', '')) if d.get('ip') is not None else ''))
        self.table.setItem(r, 12, QTableWidgetItem(str(d.get('e_ratio') or '0.65')))
        self.table.setItem(r, 13, QTableWidgetItem(str(d.get('friction_angle') or '30')))
        self.table.setItem(r, 14, QTableWidgetItem(str(d.get('cohesion') or '2')))
        self.table.setItem(r, 15, QTableWidgetItem(str(d.get('e_modulus') or '25')))

        self.on_soil_type_changed(r, curr_soil)

        # Если этот ИГЭ есть в реестре объекта и создается новая строка, сразу подставляем свойства
        if not data and curr_ige in self.ige_registry:
            self.apply_ige_properties_to_row(r, self.ige_registry[curr_ige])

        self._is_updating_depths = False

    def on_ige_selected(self, row, ige_code):
        """Автоматическая подстановка свойств при выборе ИГЭ из реестра объекта."""
        ige_code = ige_code.strip()
        if ige_code in self.ige_registry:
            self.apply_ige_properties_to_row(row, self.ige_registry[ige_code])

    def apply_ige_properties_to_row(self, row, reg):
        self._is_updating_depths = True

        type_combo = self.table.cellWidget(row, 1)
        if type_combo: type_combo.setCurrentText(reg['soil_type'])

        sand_combo = self.table.cellWidget(row, 2)
        if sand_combo and reg.get('sand_fraction'): sand_combo.setCurrentText(reg['sand_fraction'])

        dens_combo = self.table.cellWidget(row, 3)
        if dens_combo and reg.get('sand_density'): dens_combo.setCurrentText(reg['sand_density'])

        cons_combo = self.table.cellWidget(row, 4)
        if cons_combo and reg.get('consistency'): cons_combo.setCurrentText(reg['consistency'])

        if reg.get('density'): self.table.item(row, 8).setText(str(reg['density']))
        if reg.get('moisture'): self.table.item(row, 9).setText(str(reg['moisture']))
        if reg.get('il') is not None: self.table.item(row, 10).setText(str(reg['il']))
        if reg.get('ip') is not None: self.table.item(row, 11).setText(str(reg['ip']))
        if reg.get('e_ratio'): self.table.item(row, 12).setText(str(reg['e_ratio']))
        if reg.get('friction_angle'): self.table.item(row, 13).setText(str(reg['friction_angle']))
        if reg.get('cohesion'): self.table.item(row, 14).setText(str(reg['cohesion']))
        if reg.get('e_modulus'): self.table.item(row, 15).setText(str(reg['e_modulus']))

        self.on_soil_type_changed(row, reg['soil_type'])
        self._is_updating_depths = False

    def on_soil_type_changed(self, row, soil_type):
        sand_widget = self.table.cellWidget(row, 2)
        dens_widget = self.table.cellWidget(row, 3)
        cons_widget = self.table.cellWidget(row, 4)

        if soil_type == "Песок":
            if sand_widget: sand_widget.setEnabled(True)
            if dens_widget: dens_widget.setEnabled(True)
            if cons_widget: cons_widget.setEnabled(False)
            for c in [10, 11]:
                item = self.table.item(row, c)
                if item:
                    item.setText("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setBackground(QColor(235, 235, 235))
        elif soil_type in ["Супесь", "Суглинок", "Глина"]:
            if sand_widget: sand_widget.setEnabled(False)
            if dens_widget: dens_widget.setEnabled(False)
            if cons_widget: cons_widget.setEnabled(True)
            for c in [10, 11]:
                item = self.table.item(row, c)
                if item:
                    item.setFlags(item.flags() | Qt.ItemIsEnabled)
                    item.setBackground(QColor(255, 255, 255))
        else:
            if sand_widget: sand_widget.setEnabled(False)
            if dens_widget: dens_widget.setEnabled(False)
            if cons_widget: cons_widget.setEnabled(False)
            for c in [10, 11]:
                item = self.table.item(row, c)
                if item:
                    item.setText("")
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setBackground(QColor(235, 235, 235))

    def on_cell_changed(self, item):
        if self._is_updating_depths: return
        col = item.column()
        row = item.row()

        # Мощность
        if col == 6:
            try:
                thick = float(item.text().replace(',', '.'))
                top = float(self.table.item(row, 5).text().replace(',', '.'))
                bot = top + thick
                self._is_updating_depths = True
                self.table.item(row, 7).setText(f"{bot:.2f}")
                self._recalculate_all_depths(start_row=row + 1)
                self._is_updating_depths = False
            except ValueError:
                pass

        # Подошва
        elif col == 7:
            try:
                bot = float(item.text().replace(',', '.'))
                top = float(self.table.item(row, 5).text().replace(',', '.'))
                thick = max(0.01, bot - top)
                self._is_updating_depths = True
                self.table.item(row, 6).setText(f"{thick:.2f}")
                self._recalculate_all_depths(start_row=row + 1)
                self._is_updating_depths = False
            except ValueError:
                pass

    def _recalculate_all_depths(self, start_row=0):
        for r in range(start_row, self.table.rowCount()):
            prev_bot = 0.0 if r == 0 else float(self.table.item(r - 1, 7).text().replace(',', '.'))
            thick = float(self.table.item(r, 6).text().replace(',', '.'))
            bot = prev_bot + thick
            self.table.item(r, 5).setText(f"{prev_bot:.2f}")
            self.table.item(r, 7).setText(f"{bot:.2f}")

    def duplicate_layer_row(self):
        curr_row = self.table.currentRow()
        if curr_row < 0: return
        data = self._get_row_data(curr_row)
        prev_bot = float(self.table.item(self.table.rowCount() - 1, 7).text().replace(',', '.'))
        thick = data['depth_bottom'] - data['depth_top']
        data['depth_top'] = prev_bot
        data['depth_bottom'] = prev_bot + thick
        self.add_layer_row(data)

    def delete_selected_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._is_updating_depths = True
            self._recalculate_all_depths(start_row=0)
            self._is_updating_depths = False

    def move_layer_up(self):
        row = self.table.currentRow()
        if row <= 0: return
        self._swap_rows(row, row - 1)
        self.table.setCurrentCell(row - 1, self.table.currentColumn())

    def move_layer_down(self):
        row = self.table.currentRow()
        if row < 0 or row >= self.table.rowCount() - 1: return
        self._swap_rows(row, row + 1)
        self.table.setCurrentCell(row + 1, self.table.currentColumn())

    def _swap_rows(self, r1, r2):
        d1 = self._get_row_data(r1)
        d2 = self._get_row_data(r2)
        self.table.removeRow(max(r1, r2))
        self.table.removeRow(min(r1, r2))
        self.add_layer_row(d2)
        self.add_layer_row(d1)
        self._is_updating_depths = True
        self._recalculate_all_depths(start_row=0)
        self._is_updating_depths = False

    def _get_row_data(self, r):
        def _to_float(item):
            if not item or not item.text(): return None
            try:
                return float(item.text().replace(',', '.'))
            except ValueError:
                return None

        ige_widget = self.table.cellWidget(r, 0)
        ige_code = ige_widget.currentText().strip() if isinstance(ige_widget, QComboBox) else (
            self.table.item(r, 0).text() if self.table.item(r, 0) else "")

        soil_combo = self.table.cellWidget(r, 1)
        sand_combo = self.table.cellWidget(r, 2)
        dens_combo = self.table.cellWidget(r, 3)
        cons_combo = self.table.cellWidget(r, 4)

        return {
            "ige_code": ige_code,
            "soil_type": soil_combo.currentText() if soil_combo else "Песок",
            "sand_fraction": sand_combo.currentText() if sand_combo and sand_combo.isEnabled() else None,
            "sand_density": dens_combo.currentText() if dens_combo and dens_combo.isEnabled() else None,
            "consistency": cons_combo.currentText() if cons_combo and cons_combo.isEnabled() else None,
            "depth_top": _to_float(self.table.item(r, 5)) or 0.0,
            "depth_bottom": _to_float(self.table.item(r, 7)) or 0.0,
            "density": _to_float(self.table.item(r, 8)),
            "moisture": _to_float(self.table.item(r, 9)),
            "il": _to_float(self.table.item(r, 10)),
            "ip": _to_float(self.table.item(r, 11)),
            "e_ratio": _to_float(self.table.item(r, 12)),
            "friction_angle": _to_float(self.table.item(r, 13)),
            "cohesion": _to_float(self.table.item(r, 14)),
            "e_modulus": _to_float(self.table.item(r, 15)),
            "note": ""
        }

    def validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите номер скважины!")
            return
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Ошибка", "Добавьте хотя бы один пласт!")
            return

        warnings = []
        for r in range(self.table.rowCount()):
            d = self._get_row_data(r)
            ige = d['ige_code']

            if d['soil_type'] in ["Супесь", "Суглинок", "Глина"]:
                if d['ip'] is not None:
                    gost_type = check_clay_type_by_ip(d['ip'])
                    if gost_type and gost_type != d['soil_type']:
                        warnings.append(
                            f"• {ige}: Выбран вид '{d['soil_type']}', но по числу пластичности IP={d['ip']} это '{gost_type}' (ГОСТ 25100).")
                if d['il'] is not None and d['consistency']:
                    gost_cons = get_clay_consistency_by_il(d['soil_type'], d['il'])
                    if gost_cons and gost_cons != d['consistency']:
                        warnings.append(
                            f"• {ige}: По IL={d['il']} консистенция должна быть '{gost_cons}', а выбрана '{d['consistency']}'.")

            if d['soil_type'] == "Песок" and d['e_ratio'] is not None and d['sand_fraction']:
                gost_dens = get_sand_density_by_e(d['sand_fraction'], d['e_ratio'])
                if gost_dens and d['sand_density'] and gost_dens != d['sand_density']:
                    warnings.append(
                        f"• {ige}: Для фракции '{d['sand_fraction']}' при e={d['e_ratio']} плотность по ГОСТ '{gost_dens}', а указана '{d['sand_density']}'.")

        if warnings:
            msg = "Обнаружены несоответствия классификации ГОСТ 25100:\n\n" + "\n".join(
                warnings) + "\n\nСохранить все равно?"
            if QMessageBox.question(self, "Проверка ГОСТ", msg, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return

        self.accept()

    def get_data(self):
        layers = [self._get_row_data(r) for r in range(self.table.rowCount())]
        gw = self.gw_spin.value()
        return {
            "project_id": self.proj_combo.currentData(),
            "name": self.name_edit.text().strip(),
            "x": self.x_spin.value(),
            "y": self.y_spin.value(),
            "z": self.z_spin.value(),
            "gw_level": gw if gw >= 0 else None,
            "note": self.note_edit.text().strip(),
            "layers": layers
        }


class PileDialog(QDialog):
    def __init__(self, boreholes: list, current_pile: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование сваи" if current_pile else "Добавление сваи")
        self.resize(650, 780)
        self.boreholes = {bh['id']: bh for bh in boreholes}
        self.current_pile = current_pile

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.bh_combo = QComboBox()
        for bh_id, bh in self.boreholes.items():
            proj_name = bh.get('project_name', f"Объект {bh['project_id']}")
            self.bh_combo.addItem(f"[{proj_name}] {bh['name']}", bh_id)

        self.name_edit = QLineEdit(current_pile['pile_name'] if current_pile else "Свая-1")

        # Координаты сваи
        self.same_coords_chk = QCheckBox("Принять координаты по скважине")
        self.x_spin = QDoubleSpinBox();
        self.x_spin.setRange(-1e7, 1e7)
        self.y_spin = QDoubleSpinBox();
        self.y_spin.setRange(-1e7, 1e7)

        coords_box = QHBoxLayout()
        coords_box.addWidget(QLabel("X:"));
        coords_box.addWidget(self.x_spin)
        coords_box.addWidget(QLabel("Y:"));
        coords_box.addWidget(self.y_spin)
        coords_box.addWidget(self.same_coords_chk)

        self.same_coords_chk.toggled.connect(self.on_same_coords_toggled)
        self.bh_combo.currentIndexChanged.connect(self.on_bh_selection_changed)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Забивная", "Вдавливаемая", "Вибропогружение", "Буронабивная", "Винтовая"])
        if current_pile: self.type_combo.setCurrentText(current_pile['pile_type'])
        self.type_combo.currentTextChanged.connect(self.on_pile_type_changed)

        self.len_spin = QDoubleSpinBox();
        self.len_spin.setRange(1.0, 150.0);
        self.len_spin.setValue(current_pile['length'] if current_pile else 12.0)
        self.diam_spin = QDoubleSpinBox();
        self.diam_spin.setRange(0.05, 5.0);
        self.diam_spin.setSingleStep(0.05);
        self.diam_spin.setValue(current_pile['diameter'] if current_pile else 0.30)

        self.blade_spin = QDoubleSpinBox();
        self.blade_spin.setRange(0.1, 5.0);
        self.blade_spin.setSingleStep(0.05)
        self.blade_spin.setValue(current_pile.get('blade_diameter') or 0.80 if current_pile else 0.80)

        self.leader_diam_spin = QDoubleSpinBox();
        self.leader_diam_spin.setRange(0.0, 5.0);
        self.leader_diam_spin.setSingleStep(0.05)
        self.leader_diam_spin.setValue(current_pile.get('leader_diam') or 0.0 if current_pile else 0.0)

        self.leader_depth_spin = QDoubleSpinBox();
        self.leader_depth_spin.setRange(0.0, 150.0)
        self.leader_depth_spin.setValue(current_pile.get('leader_depth') or 0.0 if current_pile else 0.0)

        self.blow_count_spin = QSpinBox();
        self.blow_count_spin.setRange(0, 100000)
        self.blow_count_spin.setValue(current_pile.get('blow_count') or 0 if current_pile else 0)

        self.rest_days_spin = QSpinBox();
        self.rest_days_spin.setRange(0, 365)
        self.rest_days_spin.setValue(current_pile.get('rest_days') or 6 if current_pile else 6)

        leader_row = QHBoxLayout()
        leader_row.addWidget(QLabel("d (м):"));
        leader_row.addWidget(self.leader_diam_spin)
        leader_row.addWidget(QLabel("h (м):"));
        leader_row.addWidget(self.leader_depth_spin)

        drive_row = QHBoxLayout()
        drive_row.addWidget(QLabel("Ударов:"));
        drive_row.addWidget(self.blow_count_spin)
        drive_row.addWidget(QLabel("Отдых (дней):"));
        drive_row.addWidget(self.rest_days_spin)

        self.head_z_spin = QDoubleSpinBox();
        self.head_z_spin.setRange(-500.0, 5000.0);
        self.head_z_spin.setValue(current_pile['head_z'] or 100.0 if current_pile else 100.0)

        self.fu_load_spin = QDoubleSpinBox();
        self.fu_load_spin.setRange(0, 100000);
        self.fu_load_spin.setValue(current_pile.get('fu_load') or 0.0 if current_pile else 0.0)
        self.fu_s_spin = QDoubleSpinBox();
        self.fu_s_spin.setRange(0, 1000);
        self.fu_s_spin.setValue(current_pile.get('fu_settlement') or 0.0 if current_pile else 0.0)

        self.fu_load_spin.valueChanged.connect(self.on_fu_load_changed)
        self.fu_s_spin.valueChanged.connect(self.on_fu_s_changed)

        fu_row = QHBoxLayout()
        fu_row.addWidget(QLabel("Fd (кН):"));
        fu_row.addWidget(self.fu_load_spin)
        fu_row.addWidget(QLabel("Осадка при Fd (мм):"));
        fu_row.addWidget(self.fu_s_spin)

        form.addRow("Привязка к скважине:", self.bh_combo)
        form.addRow("Марка/Номер сваи:", self.name_edit)
        form.addRow("Положение сваи:", coords_box)
        form.addRow("Способ погружения:", self.type_combo)
        form.addRow("Длина ствола (L), м:", self.len_spin)
        form.addRow("Диаметр/Сечение, м:", self.diam_spin)
        form.addRow("Диаметр лопасти (для винтовой), м:", self.blade_spin)
        form.addRow("Лидерная скважина:", leader_row)
        form.addRow("Забивка и отдых:", drive_row)
        form.addRow("Отметка оголовка, м:", self.head_z_spin)
        form.addRow("Несущая способность Fd:", fu_row)
        layout.addLayout(form)

        self.tabs = QTabWidget()

        load_tab = QWidget()
        load_layout = QVBoxLayout(load_tab)
        self.table_load = PasteableTableWidget(0, 2)
        self.table_load.setHorizontalHeaderLabels(["Нагрузка N, кН", "Осадка S, мм"])
        self.table_load.horizontalHeader().setStretchLastSection(True)
        load_layout.addWidget(self.table_load)

        btn_load_row = QHBoxLayout()
        add_load_btn = QPushButton("+ Ступень нагружения")
        add_load_btn.clicked.connect(lambda: self.add_point_row(self.table_load, 0, 0))
        del_load_btn = QPushButton("Удалить ступень")
        del_load_btn.clicked.connect(lambda: self.table_load.removeRow(self.table_load.currentRow()))
        btn_load_row.addWidget(add_load_btn);
        btn_load_row.addWidget(del_load_btn)
        load_layout.addLayout(btn_load_row)
        self.tabs.addTab(load_tab, "📈 Ветвь нагружения")

        unload_tab = QWidget()
        unload_layout = QVBoxLayout(unload_tab)
        self.table_unload = PasteableTableWidget(0, 2)
        self.table_unload.setHorizontalHeaderLabels(["Нагрузка N, кН", "Осадка S, мм"])
        self.table_unload.horizontalHeader().setStretchLastSection(True)
        unload_layout.addWidget(self.table_unload)

        btn_unload_row = QHBoxLayout()
        add_unload_btn = QPushButton("+ Ступень разгрузки")
        add_unload_btn.clicked.connect(lambda: self.add_point_row(self.table_unload, 0, 0))
        del_unload_btn = QPushButton("Удалить ступень")
        del_unload_btn.clicked.connect(lambda: self.table_unload.removeRow(self.table_unload.currentRow()))
        btn_unload_row.addWidget(add_unload_btn);
        btn_unload_row.addWidget(del_unload_btn)
        unload_layout.addLayout(btn_unload_row)
        self.tabs.addTab(unload_tab, "📉 Ветвь разгрузки")

        layout.addWidget(self.tabs)

        save_btn = QPushButton("Сохранить сваю")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

        if current_pile:
            idx = self.bh_combo.findData(current_pile['borehole_id'])
            if idx >= 0: self.bh_combo.setCurrentIndex(idx)
            is_same = bool(current_pile.get('same_coords_as_bh', 1))
            self.same_coords_chk.setChecked(is_same)
            if not is_same:
                self.x_spin.setValue(current_pile.get('x') or 0.0)
                self.y_spin.setValue(current_pile.get('y') or 0.0)
        else:
            self.same_coords_chk.setChecked(True)

        self.on_same_coords_toggled(self.same_coords_chk.isChecked())
        self.on_pile_type_changed(self.type_combo.currentText())

        if current_pile and current_pile.get('curve_data'):
            for pt in current_pile['curve_data']:
                self.add_point_row(self.table_load, pt[0], pt[1])
        elif not current_pile:
            for pt in [[0, 0], [200, 2.0], [400, 4.0], [600, 16.0], [800, 40.0]]:
                self.add_point_row(self.table_load, pt[0], pt[1])

        if current_pile and current_pile.get('unload_curve_data'):
            for pt in current_pile['unload_curve_data']:
                self.add_point_row(self.table_unload, pt[0], pt[1])

    def on_same_coords_toggled(self, is_checked):
        self.x_spin.setEnabled(not is_checked)
        self.y_spin.setEnabled(not is_checked)
        if is_checked:
            self.sync_coords_from_bh()

    def on_bh_selection_changed(self):
        if self.same_coords_chk.isChecked():
            self.sync_coords_from_bh()

    def sync_coords_from_bh(self):
        bh_id = self.bh_combo.currentData()
        if bh_id and bh_id in self.boreholes:
            bh = self.boreholes[bh_id]
            self.x_spin.setValue(bh.get('x') or 0.0)
            self.y_spin.setValue(bh.get('y') or 0.0)

    def on_pile_type_changed(self, p_type):
        is_screw = (p_type == "Винтовая")
        is_driven_like = (p_type in ["Забивная", "Вдавливаемая", "Вибропогружение"])
        is_hammer_driven = (p_type == "Забивная")

        self.blade_spin.setEnabled(is_screw)
        self.leader_diam_spin.setEnabled(is_driven_like)
        self.leader_depth_spin.setEnabled(is_driven_like)
        self.rest_days_spin.setEnabled(is_driven_like)
        self.blow_count_spin.setEnabled(is_hammer_driven)

    def add_point_row(self, table, load=0.0, s=0.0):
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(str(load)))
        table.setItem(r, 1, QTableWidgetItem(str(s)))

    def _get_table_points(self, table):
        pts = []
        for r in range(table.rowCount()):
            try:
                load = float(table.item(r, 0).text().replace(',', '.'))
                s = float(table.item(r, 1).text().replace(',', '.'))
                pts.append((load, s))
            except (ValueError, AttributeError):
                continue
        return pts

    def on_fu_load_changed(self, load_val):
        if load_val <= 0: return
        pts = sorted(self._get_table_points(self.table_load), key=lambda x: x[0])
        if len(pts) >= 2:
            loads = [p[0] for p in pts]
            settlements = [p[1] for p in pts]
            if min(loads) <= load_val <= max(loads):
                calc_s = float(np.interp(load_val, loads, settlements))
                self.fu_s_spin.blockSignals(True)
                self.fu_s_spin.setValue(round(calc_s, 2))
                self.fu_s_spin.blockSignals(False)

    def on_fu_s_changed(self, s_val):
        if s_val <= 0: return
        pts = sorted(self._get_table_points(self.table_load), key=lambda x: x[0])
        if len(pts) >= 2:
            settlements = [p[1] for p in pts]
            loads = [p[0] for p in pts]
            if min(settlements) <= s_val <= max(settlements):
                calc_load = float(np.interp(s_val, settlements, loads))
                self.fu_load_spin.blockSignals(True)
                self.fu_load_spin.setValue(round(calc_load, 1))
                self.fu_load_spin.blockSignals(False)

    def get_data(self):
        load_pts = [[p[0], p[1]] for p in self._get_table_points(self.table_load)]
        unload_pts = [[p[0], p[1]] for p in self._get_table_points(self.table_unload)]

        fu_l = self.fu_load_spin.value()
        fu_s = self.fu_s_spin.value()

        if len(load_pts) >= 2:
            sorted_pts = sorted(load_pts, key=lambda x: x[0])
            loads = [p[0] for p in sorted_pts]
            settlements = [p[1] for p in sorted_pts]
            if fu_s > 0 and fu_l == 0:
                fu_l = float(np.interp(fu_s, settlements, loads))
            elif fu_l > 0 and fu_s == 0:
                fu_s = float(np.interp(fu_l, loads, settlements))

        p_type = self.type_combo.currentText()
        is_screw = (p_type == "Винтовая")
        is_driven_like = (p_type in ["Забивная", "Вдавливаемая", "Вибропогружение"])

        return {
            "borehole_id": self.bh_combo.currentData(),
            "pile_name": self.name_edit.text().strip(),
            "pile_type": p_type,
            "length": self.len_spin.value(),
            "diameter": self.diam_spin.value(),
            "x": self.x_spin.value(),
            "y": self.y_spin.value(),
            "same_coords_as_bh": self.same_coords_chk.isChecked(),
            "blade_diameter": self.blade_spin.value() if is_screw else None,
            "leader_diam": self.leader_diam_spin.value() if is_driven_like else None,
            "leader_depth": self.leader_depth_spin.value() if is_driven_like else None,
            "blow_count": self.blow_count_spin.value() if p_type == "Забивная" else None,
            "rest_days": self.rest_days_spin.value() if is_driven_like else None,
            "head_z": self.head_z_spin.value(),
            "fu_load": fu_l if fu_l > 0 else None,
            "fu_settlement": fu_s if fu_s > 0 else None,
            "points": load_pts,
            "unload_points": unload_pts
        }