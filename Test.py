import os
import sys
import serial
import serial.tools.list_ports
from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import QMessageBox, QLabel #QMessageBox用来创建消息框
from PyQt5.QtCore import QTimer, QElapsedTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtGui import QTextCursor

from qt_material import apply_stylesheet

import cv2
import numpy as np

from pyzbar.pyzbar import decode
from cvtui import Ui_Dialog



def update_frame(self):
    if self.camera is not None and self.camera.isOpened():
        ret, frame = self.camera.read()
        if ret:
            original_frame = frame.copy()
            original_frame = cv2.cvtColor(original_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = original_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(original_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            scaled_image = qt_image.scaled(self.camera_label.width(), self.camera_label.height(), QtCore.Qt.KeepAspectRatio)
            self.camera_label.setPixmap(QPixmap.fromImage(scaled_image))

            if self.YesorNo:
                print("尝试识别物料标签中...")
                matched_frame = None
                matched_img = None
                for img in self.images:
                    current_matched_img, result = self.ORBMatcher(img, frame)
                    if result:
                        matched_frame = current_matched_img 
                        matched_img = img 
                        break 

                if matched_frame is not None:
                    print("成功识别到物料...")
                    self.progress_to(10)
                    result_frame = matched_frame
                    self.stop_recognition()

                    if (self.last_matched_img != None and self.last_matched_img != matched_img) or (self.last_matched_img == None):
                        if self.ser.isOpen():
                            try:
                                self.ser.write(b'1')
                                print("上位机命令下位机启动项目流程...")
                            except Exception as e:
                                QMessageBox.critical(self, "发送失败", f"无法发送数据: {str(e)}")
                            
                            self.last_matched_img = matched_img
                        else:
                            QMessageBox.warning(self, "串口未打开", "请先打开串口")

                else:
                    result_frame = frame

                result_frame = cv2.cvtColor(result_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = result_frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(result_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_image = qt_image.scaled(self.result_label.width(), self.result_label.height(), QtCore.Qt.KeepAspectRatio)
                self.result_label.setPixmap(QPixmap.fromImage(scaled_image))

def write(self, text):
    self.text_widget.moveCursor(QTextCursor.End) #移动光标到末尾
    self.text_widget.insertPlainText(text) #显示文本
    self.text_widget.moveCursor(QTextCursor.End) #再次移动光标到末尾
    self.text_widget.ensureCursorVisible() #设置光标可见，自动滚动
    QtWidgets.QApplication.processEvents() #保持快速响应