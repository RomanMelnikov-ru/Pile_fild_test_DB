# dialogs/pasteable_table.py
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

class PasteableTableWidget(QTableWidget):
    """QTableWidget с поддержкой копирования/вставки таблицы из буфера обмена (Excel, Word)."""
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Paste):
            self.paste_from_clipboard()
        else:
            super().keyPressEvent(event)

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        rows = text.strip().split('\n')
        cur_row = self.currentRow()
        cur_col = self.currentColumn()

        if cur_row < 0:
            cur_row = 0
        if cur_col < 0:
            cur_col = 0

        for r_idx, row_text in enumerate(rows):
            target_row = cur_row + r_idx
            if target_row >= self.rowCount():
                self.insertRow(target_row)

            columns = row_text.split('\t')
            for c_idx, cell_value in enumerate(columns):
                target_col = cur_col + c_idx
                if target_col >= self.columnCount():
                    break
                val = cell_value.strip().replace(',', '.')
                self.setItem(target_row, target_col, QTableWidgetItem(val))