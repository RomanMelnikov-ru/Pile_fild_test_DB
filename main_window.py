# main_window.py
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QPushButton, QStatusBar, QMessageBox, QMenu)
from PyQt5.QtCore import Qt

from core.db import (init_db, add_project, update_project, get_all_projects, delete_project,
                     save_borehole, delete_borehole, get_boreholes_by_project,
                     get_borehole_layers, get_all_boreholes, save_pile_test,
                     delete_pile_test, get_pile_tests_by_borehole, get_borehole_by_id)
from graphics.column_canvas import ColumnCanvas
from graphics.plot_canvas import PlotCanvas
from dialogs.input_dialogs import ProjectDialog, BoreholeDialog, PileDialog, ProjectIgeManagerDialog
from dialogs.sp24_dialog import SP24Dialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Инженерно-геотехнический комплекс: Сваи и Скважины")
        self.resize(1350, 850)

        self.setup_ui()
        self.load_tree_data()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Иерархия объектов"])
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        left_layout.addWidget(self.tree)

        btn_row1 = QHBoxLayout()
        btn_proj = QPushButton("+ Объект")
        btn_proj.clicked.connect(self.on_add_project)
        btn_ige = QPushButton("📑 Реестр ИГЭ")
        btn_ige.clicked.connect(self.on_open_active_project_ige)
        btn_row1.addWidget(btn_proj)
        btn_row1.addWidget(btn_ige)

        btn_row2 = QHBoxLayout()
        btn_bh = QPushButton("+ Скважина")
        btn_bh.clicked.connect(self.on_add_borehole)
        btn_pile = QPushButton("+ Свая")
        btn_pile.clicked.connect(self.on_add_pile)
        btn_row2.addWidget(btn_bh)
        btn_row2.addWidget(btn_pile)

        left_layout.addLayout(btn_row1)
        left_layout.addLayout(btn_row2)

        self.column_view = ColumnCanvas()
        self.column_view.setMinimumWidth(380)

        self.plot_view = PlotCanvas()
        self.plot_view.setMinimumWidth(400)

        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.column_view)
        self.splitter.addWidget(self.plot_view)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 2)
        self.splitter.setSizes([260, 480, 560])

        main_layout.addWidget(self.splitter)
        self.setStatusBar(QStatusBar())

    def load_tree_data(self):
        self.tree.clear()
        projects = get_all_projects()

        if not projects:
            add_project("Площадка №1", "Основной объект")
            projects = get_all_projects()

        for p in projects:
            p_item = QTreeWidgetItem(self.tree, [f"🏢 {p['name']}"])
            p_item.setData(0, Qt.UserRole, {"type": "project", "data": p})

            boreholes = get_boreholes_by_project(p['id'])
            for bh in boreholes:
                bh_item = QTreeWidgetItem(p_item, [f"📍 Скважина: {bh['name']}"])
                bh_item.setData(0, Qt.UserRole, {"type": "borehole", "data": bh})

                piles = get_pile_tests_by_borehole(bh['id'])
                for pile in piles:
                    pile_item = QTreeWidgetItem(bh_item, [f"🔩 Свая: {pile['pile_name']}"])
                    pile_item.setData(0, Qt.UserRole, {"type": "pile", "data": pile, "bh_data": bh})

        self.tree.expandAll()

    def get_selected_project(self):
        curr = self.tree.currentItem()
        if not curr:
            projects = get_all_projects()
            return projects[0] if projects else None

        meta = curr.data(0, Qt.UserRole)
        if meta and meta['type'] == 'project':
            return meta['data']
        elif meta and meta['type'] == 'borehole':
            projects = get_all_projects()
            for p in projects:
                if p['id'] == meta['data']['project_id']:
                    return p
        elif meta and meta['type'] == 'pile':
            bh = meta['bh_data']
            projects = get_all_projects()
            for p in projects:
                if p['id'] == bh['project_id']:
                    return p
        projects = get_all_projects()
        return projects[0] if projects else None

    def on_open_active_project_ige(self):
        proj = self.get_selected_project()
        if not proj:
            QMessageBox.warning(self, "Внимание", "Сначала выберите или создайте объект!")
            return
        self.open_project_ige_manager(proj)

    def open_project_ige_manager(self, proj: dict):
        dlg = ProjectIgeManagerDialog(proj['id'], proj['name'], parent=self)
        dlg.exec_()

    def show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        meta = item.data(0, Qt.UserRole)
        menu = QMenu()

        if meta['type'] == 'project':
            ige_act = menu.addAction("📑 Открыть реестр ИГЭ объекта")
            edit_act = menu.addAction("Редактировать объект")
            del_act = menu.addAction("Удалить объект")
            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == ige_act:
                self.open_project_ige_manager(meta['data'])
            elif action == edit_act:
                self.edit_project(meta['data'])
            elif action == del_act:
                if QMessageBox.question(self, "Подтверждение",
                                        f"Удалить объект '{meta['data']['name']}' со всеми скважинами и сваями?") == QMessageBox.Yes:
                    delete_project(meta['data']['id'])
                    self.load_tree_data()

        elif meta['type'] == 'borehole':
            edit_act = menu.addAction("Редактировать скважину")
            del_act = menu.addAction("Удалить скважину")
            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == edit_act:
                self.edit_borehole(meta['data'])
            elif action == del_act:
                if QMessageBox.question(self, "Подтверждение",
                                        f"Удалить скважину '{meta['data']['name']}'?") == QMessageBox.Yes:
                    delete_borehole(meta['data']['id'])
                    self.load_tree_data()

        elif meta['type'] == 'pile':
            sp24_act = menu.addAction("📐 Расчёт по СП 24.13330.2021")
            menu.addSeparator()
            edit_act = menu.addAction("Редактировать сваю/испытание")
            del_act = menu.addAction("Удалить испытание сваи")
            action = menu.exec_(self.tree.mapToGlobal(pos))
            if action == sp24_act:
                self.open_sp24_dialog(meta['data'], meta['bh_data'])
            elif action == edit_act:
                self.edit_pile(meta['data'])
            elif action == del_act:
                if QMessageBox.question(self, "Подтверждение",
                                        f"Удалить сваю '{meta['data']['pile_name']}'?") == QMessageBox.Yes:
                    delete_pile_test(meta['data']['id'])
                    self.load_tree_data()

    def on_add_project(self):
        dlg = ProjectDialog(parent=self)
        if dlg.exec_() == ProjectDialog.Accepted:
            name, desc = dlg.get_data()
            if name:
                add_project(name, desc)
                self.load_tree_data()

    def edit_project(self, proj: dict):
        dlg = ProjectDialog(current_name=proj['name'], current_desc=proj.get('description', ''), parent=self)
        if dlg.exec_() == ProjectDialog.Accepted:
            name, desc = dlg.get_data()
            if name:
                update_project(proj['id'], name, desc)
                self.load_tree_data()

    def on_add_borehole(self):
        projects = get_all_projects()
        dlg = BoreholeDialog(projects, parent=self)
        if dlg.exec_() == BoreholeDialog.Accepted:
            d = dlg.get_data()
            save_borehole(d['project_id'], d['name'], d['x'], d['y'], d['z'], d['gw_level'], d['note'], d['layers'])
            self.load_tree_data()

    def edit_borehole(self, bh: dict):
        projects = get_all_projects()
        layers = get_borehole_layers(bh['id'])
        dlg = BoreholeDialog(projects, current_bh=bh, layers=layers, parent=self)
        if dlg.exec_() == BoreholeDialog.Accepted:
            d = dlg.get_data()
            save_borehole(d['project_id'], d['name'], d['x'], d['y'], d['z'], d['gw_level'], d['note'], d['layers'],
                          bh_id=bh['id'])
            self.load_tree_data()

    def on_add_pile(self):
        boreholes = get_all_boreholes()
        if not boreholes:
            QMessageBox.warning(self, "Ошибка", "Сначала создайте скважину!")
            return
        dlg = PileDialog(boreholes, parent=self)
        if dlg.exec_() == PileDialog.Accepted:
            d = dlg.get_data()
            save_pile_test(
                d['borehole_id'], d['pile_name'], d['pile_type'], d['length'], d['diameter'],
                d['head_z'], d['fu_load'], d['fu_settlement'], d['points'],
                x=d.get('x'), y=d.get('y'), same_coords_as_bh=d.get('same_coords_as_bh', True),
                unload_points=d.get('unload_points'),
                blade_diameter=d.get('blade_diameter'),
                leader_diam=d.get('leader_diam'),
                leader_depth=d.get('leader_depth'),
                blow_count=d.get('blow_count'),
                rest_days=d.get('rest_days')
            )
            self.load_tree_data()

    def edit_pile(self, pile: dict):
        boreholes = get_all_boreholes()
        dlg = PileDialog(boreholes, current_pile=pile, parent=self)
        if dlg.exec_() == PileDialog.Accepted:
            d = dlg.get_data()
            save_pile_test(
                d['borehole_id'], d['pile_name'], d['pile_type'], d['length'], d['diameter'],
                d['head_z'], d['fu_load'], d['fu_settlement'], d['points'],
                x=d.get('x'), y=d.get('y'), same_coords_as_bh=d.get('same_coords_as_bh', True),
                unload_points=d.get('unload_points'),
                blade_diameter=d.get('blade_diameter'),
                leader_diam=d.get('leader_diam'),
                leader_depth=d.get('leader_depth'),
                blow_count=d.get('blow_count'),
                rest_days=d.get('rest_days'),
                pile_id=pile['id']
            )
            self.load_tree_data()

    def open_sp24_dialog(self, pile: dict, bh: dict):
        """Открывает диалог расчёта несущей способности по СП 24.13330.2021."""
        pile_type = pile.get('pile_type', '')
        if pile_type == "Винтовая":
            QMessageBox.information(
                self, "Не поддерживается",
                "Расчёт по п. 7.2 СП 24 для винтовых свай не реализован.\n"
                "Поддерживаются: Забивная, Вдавливаемая, Вибропогружение, Буронабивная."
            )
            return

        bh_full = get_borehole_by_id(bh['id'])
        layers = get_borehole_layers(bh['id'])

        if not layers:
            QMessageBox.warning(
                self, "Нет данных",
                f"В скважине '{bh.get('name', '')}' нет слоёв грунта.\n"
                "Заполните напластования скважины перед расчётом."
            )
            return

        dlg = SP24Dialog(pile, bh_full, layers, parent=self)
        dlg.exec_()

    def on_tree_item_clicked(self, item, col):
        meta = item.data(0, Qt.UserRole)
        if not meta: return

        if meta['type'] == 'borehole':
            bh = meta['data']
            layers = get_borehole_layers(bh['id'])
            self.column_view.render_column(bh['z_collar'], layers, gw_level=bh.get('gw_level'), pile_data=None)
            self.plot_view.clear_plot()
            self.statusBar().showMessage(
                f"Скважина: {bh['name']} (X={bh.get('x')}, Y={bh.get('y')}, УГВ: {bh.get('gw_level', '-')}м)")

        elif meta['type'] == 'pile':
            pile = meta['data']
            bh = meta['bh_data']
            layers = get_borehole_layers(bh['id'])

            self.column_view.render_column(bh['z_collar'], layers, gw_level=bh.get('gw_level'), pile_data=pile)

            self.plot_view.plot_curve(
                pile['curve_data'],
                unload_points=pile.get('unload_curve_data'),
                pile_label=pile['pile_name'],
                fu_load=pile.get('fu_load'),
                fu_settlement=pile.get('fu_settlement')
            )

            tech_info = []
            if pile.get('x') is not None and pile.get('y') is not None:
                tech_info.append(f"X={pile['x']:.2f}, Y={pile['y']:.2f}")
            if pile.get('rest_days'): tech_info.append(f"отдых {pile['rest_days']} дн.")
            if pile.get('blow_count'): tech_info.append(f"{pile['blow_count']} ударов")
            if pile.get('leader_depth'): tech_info.append(f"лидер h={pile['leader_depth']}м")
            tech_str = f" [{', '.join(tech_info)}]" if tech_info else ""

            self.statusBar().showMessage(f"Испытание: {pile['pile_name']} (Fd={pile.get('fu_load', '-')} кН){tech_str}")


if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())