"""Проверяет native imports без записи макросов, хоткеев и видимого окна."""
import os
import sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
import pynput.keyboard
import pynput.mouse
import win32api
import win32con
import win32gui
from version import __version__

app = QtWidgets.QApplication([])
widget = QtWidgets.QWidget()
assert QtCore.qVersion()
assert __version__ == '0.3.0'
widget.close()
app.quit()
print('FROZEN_IMPORT_OK', __version__, sys.frozen, flush=True)
