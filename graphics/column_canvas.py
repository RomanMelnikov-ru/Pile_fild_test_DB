# graphics/column_canvas.py
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsLineItem
from PyQt5.QtGui import QBrush, QColor, QPen, QFont, QPainter, QPolygonF
from PyQt5.QtCore import Qt, QPointF

SOIL_COLORS = {
    "Песок": QColor(255, 235, 150),
    "Супесь": QColor(255, 218, 185),
    "Суглинок": QColor(222, 184, 135),
    "Глина": QColor(188, 143, 143),
    "Торф": QColor(110, 75, 45),
    "Насыпной": QColor(211, 211, 211),
}

SAND_FRACTION_SHORT = {
    "Пылеватый": "пыл.",
    "Мелкий": "мелк.",
    "Средней крупности": "ср.кр.",
    "Крупный": "крупн.",
    "Гравелистый": "грав."
}

SAND_DENSITY_SHORT = {
    "Рыхлый": "рыхл.",
    "Средней плотности": "ср.пл.",
    "Плотный": "пл."
}


def format_layer_label(layer: dict) -> str:
    """Формирует подпись пласта: ИГЭ + вид + (IL для глинистых / крупность и плотность для песков)."""
    ige = layer.get('ige_code', '')
    soil = layer.get('soil_type', '')

    if soil in ["Супесь", "Суглинок", "Глина"]:
        il_val = layer.get('il')
        if il_val is not None:
            details = f"IL={il_val:.2f}" if isinstance(il_val, (int, float)) else f"IL={il_val}"
        elif layer.get('consistency'):
            details = layer['consistency']
        else:
            details = ""
        extra = f" {details}" if details else ""
        return f"{ige} ({soil}){extra}"

    elif soil == "Песок":
        frac = layer.get('sand_fraction') or ""
        dens = layer.get('sand_density') or ""

        frac_s = SAND_FRACTION_SHORT.get(frac, frac.lower())
        dens_s = SAND_DENSITY_SHORT.get(dens, dens.lower())

        parts = [p for p in [frac_s, dens_s] if p]
        desc = f" ({', '.join(parts)})" if parts else ""
        return f"{ige} {soil}{desc}"

    else:
        return f"{ige} ({soil})"


class ColumnCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.TextAntialiasing, True)
        self.scale_y = 35.0  # 35 px = 1 м глубины

    def render_column(self, z_collar: float, layers: list, gw_level: float = None, pile_data: dict = None):
        self.scene.clear()
        if not layers:
            return

        z_collar = z_collar if z_collar is not None else 0.0
        max_depth = max(l['depth_bottom'] for l in layers)

        p_type = pile_data.get('pile_type', 'Забивная') if pile_data else ''
        tip_h_meters = 0.4 if p_type in ['Забивная', 'Вдавливаемая', 'Вибропогружение', 'Винтовая'] else 0.0

        if pile_data:
            head_z = pile_data.get('head_z') if pile_data.get('head_z') is not None else z_collar
            pile_bottom_depth = (z_collar - head_z) + pile_data['length'] + tip_h_meters
            max_depth = max(max_depth, pile_bottom_depth + 1.5)

        col_x = 110.0
        col_w = 200.0
        pile_x = col_x + col_w + 35.0

        # Шкала глубин
        axis_x = 75.0
        self.scene.addLine(axis_x, 0, axis_x, max_depth * self.scale_y, QPen(Qt.black, 1.5))

        for d in range(int(max_depth) + 1):
            y_pos = d * self.scale_y
            self.scene.addLine(axis_x - 5, y_pos, axis_x, y_pos, QPen(Qt.black, 1))
            txt = self.scene.addText(f"{d}м", QFont("Arial", 8))
            txt.setPos(axis_x - 35, y_pos - 10)

            abs_z = z_collar - d
            z_txt = self.scene.addText(f"{abs_z:.1f}", QFont("Arial", 7))
            z_txt.setDefaultTextColor(Qt.darkGray)
            z_txt.setPos(axis_x - 70, y_pos - 9)

        # 1. Отрисовка слоев грунта с новыми подписями
        for layer in layers:
            y_top = layer['depth_top'] * self.scale_y
            height = (layer['depth_bottom'] - layer['depth_top']) * self.scale_y

            rect = QGraphicsRectItem(col_x, y_top, col_w, height)
            color = SOIL_COLORS.get(layer['soil_type'], QColor(240, 240, 240))
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(Qt.black, 1))
            self.scene.addItem(rect)

            label_str = format_layer_label(layer)
            txt_item = self.scene.addText(label_str, QFont("Arial", 8))
            txt_item.setPos(col_x + 5, y_top + 2)

        # 2. Уровень грунтовых вод (УГВ)
        if gw_level is not None and gw_level >= 0:
            gw_y = gw_level * self.scale_y
            gw_line = QGraphicsLineItem(col_x - 15, gw_y, col_x + col_w + 15, gw_y)
            gw_line.setPen(QPen(QColor(0, 102, 204), 2, Qt.DashDotLine))
            self.scene.addItem(gw_line)

            gw_sign = self.scene.addText(f"▼ УГВ: {gw_level:.2f} м", QFont("Arial", 8, QFont.Bold))
            gw_sign.setDefaultTextColor(QColor(0, 102, 204))
            gw_sign.setPos(col_x - 15, gw_y - 20)

        # 3. Свая
        if pile_data:
            head_z = pile_data.get('head_z') if pile_data.get('head_z') is not None else z_collar
            pile_head_depth = z_collar - head_z
            pile_y = pile_head_depth * self.scale_y

            pile_h = pile_data['length'] * self.scale_y
            pile_w = max(18.0, pile_data['diameter'] * 40.0)
            pile_center_x = pile_x + pile_w / 2.0

            # Расчетная граница длины L (куда проецируется пунктир)
            length_end_y = pile_y + pile_h

            pile_rect = QGraphicsRectItem(pile_x, pile_y, pile_w, pile_h)
            pile_rect.setBrush(QBrush(QColor(115, 125, 135)))
            pile_rect.setPen(QPen(Qt.darkBlue, 1.5))
            self.scene.addItem(pile_rect)

            if p_type == "Буронабивная":
                pass

            elif p_type in ["Забивная", "Вдавливаемая", "Вибропогружение"]:
                tip_h_px = tip_h_meters * self.scale_y
                poly = QPolygonF([
                    QPointF(pile_x, length_end_y),
                    QPointF(pile_x + pile_w, length_end_y),
                    QPointF(pile_center_x, length_end_y + tip_h_px)
                ])
                self.scene.addPolygon(poly, QPen(Qt.darkBlue, 1.5), QBrush(QColor(85, 95, 105)))

            elif p_type == "Винтовая":
                cone_h_px = tip_h_meters * self.scale_y
                poly = QPolygonF([
                    QPointF(pile_x, length_end_y),
                    QPointF(pile_x + pile_w, length_end_y),
                    QPointF(pile_center_x, length_end_y + cone_h_px)
                ])
                self.scene.addPolygon(poly, QPen(Qt.darkBlue, 1.5), QBrush(QColor(70, 80, 90)))

                blade_d = pile_data.get('blade_diameter') or (pile_data['diameter'] * 2.5)
                blade_w_px = max(pile_w + 14.0, blade_d * 40.0)
                blade_x1 = pile_center_x - blade_w_px / 2.0
                blade_x2 = pile_center_x + blade_w_px / 2.0
                blade_y = length_end_y - 2.0

                blade_poly = QPolygonF([
                    QPointF(blade_x1, blade_y - 4),
                    QPointF(blade_x2, blade_y + 4),
                    QPointF(blade_x2, blade_y + 8),
                    QPointF(blade_x1, blade_y)
                ])
                self.scene.addPolygon(blade_poly, QPen(Qt.darkRed, 1.5), QBrush(QColor(180, 40, 40)))

            # Пунктир проецируется строго от конца расчетной длины L
            guide_line = QGraphicsLineItem(col_x, length_end_y, pile_x + pile_w + 30, length_end_y)
            guide_line.setPen(QPen(Qt.red, 1.2, Qt.DashLine))
            self.scene.addItem(guide_line)

            extra_info = f"\nDлоп={pile_data['blade_diameter']}м" if (
                        p_type == "Винтовая" and pile_data.get('blade_diameter')) else ""
            label_text = f"{pile_data['pile_name']}\n{p_type}\nL={pile_data['length']}м, d={pile_data['diameter']}м{extra_info}"
            label = self.scene.addText(label_text, QFont("Arial", 8, QFont.Bold))
            label.setPos(pile_x + pile_w + 6, pile_y)

        self.setSceneRect(self.scene.itemsBoundingRect().adjusted(-20, -20, 40, 40))