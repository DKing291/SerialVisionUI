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


def resource_path(relative_path): #获取资源文件的绝对路径
    if hasattr(sys, '_MEIPASS'):
        # 打包后，资源文件存储在临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        # 未打包时，资源文件存储在当前工作目录
        return os.path.join(os.path.abspath("."), relative_path)

#日志管理类
class OutputRedirector(object):
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, text):
        self.text_widget.moveCursor(QTextCursor.End) #移动光标到末尾
        self.text_widget.insertPlainText(text) #显示文本
        self.text_widget.moveCursor(QTextCursor.End) #再次移动光标到末尾
        self.text_widget.ensureCursorVisible() #设置光标可见，自动滚动
        QtWidgets.QApplication.processEvents() #保持快速响应

    def flush(self):
        pass #无需任何操作

class Pyqt5_Serial(QtWidgets.QWidget, Ui_Dialog):
    #程序初始化：
    def __init__(self):
        super(Pyqt5_Serial, self).__init__()
        self.setupUi(self)
        self.init() #初始化

        self.setWindowTitle("智能装配平台")
        self.setWindowIcon(QtGui.QIcon(resource_path('blue_circle.jpg')))

        #self.change_font_family("Source Han Sans")

        self.ser = serial.Serial()
        self.ser.baudrate = 9600
        self.port_check() #启动即检测串口和可用摄像头
        self.populate_camera_list() 

        self.load_image()

        #初始化识别算法变量
        self.last_matched_img = None  # 跟踪上一次匹配的图像
        self.images = []
        self.load_template_images()
        
        #摄像头部分
        self.camera = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame) 

        self.YesorNo = False 
        self.serial_timer = QTimer(self)
        self.serial_timer.timeout.connect(self.check_serial_data)  #设置的是每100毫秒检测一次串口信息

        
        self.count_4 = 0
        self.count_5 = 0
        self.count_6 = 0
        #计时器
        # self.recognition_timer = QElapsedTimer()
        # self.recognition_timeout = 5000#ms

        #日志
        sys.stdout = OutputRedirector(self.logtext)
        print("---------------------------------")
        print(" 欢 迎 使 用 智 能 装 配 平 台 ")
        print("---------------------------------")

        #进度条
        self.progressbar.setValue(0)
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        self.target_progress = 0
        self.current_progress = 0

        #二维码
        self.detected_codes=set()
        self.last_code=None
    

    
    #引用控件
    def init(self):
        # 串口检测按钮
        self.checkbutton.clicked.connect(self.port_check)

        # 打开串口按钮
        self.openbutton.clicked.connect(self.port_open)
        # 关闭串口按钮
        self.closebutton.clicked.connect(self.port_close)

        #启动按钮
        self.startbutton.clicked.connect(self.start)

        #电机归位
        self.reset_moto.clicked.connect(self.reset_moto_click)

        #启动电机
        self.start_moto.clicked.connect(self.start_moto_click)

        #打开1号气缸
        self.open1.clicked.connect(self.open1_click)

        #打开2号气缸
        self.open2.clicked.connect(self.open2_click)

        #打开3号气缸
        self.open3.clicked.connect(self.open3_click)

        #打开摄像头
        self.open_camera_button.clicked.connect(self.open_camera)

        #关闭摄像头
        self.close_camera_button.clicked.connect(self.close_camera)


    def populate_camera_list(self): #检查可能的摄像头设备
        self.select_Camera.clear()
        for i in range(3):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                self.select_Camera.addItem(f"Camera {i}")
                cap.release()

    def load_image(self):
        #科大logo
        pixmap = QPixmap(resource_path('logo.jpg'))
        # 调整图片大小以适应 label
        #pixmap = pixmap.scaled(self.image_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        # 让图片填充整个 label
        self.image_label.setScaledContents(True)
        
        #3D模型 12.23改
        self.model_label.setPixmap(QPixmap(resource_path('3Dmodel.jpg')))
        self.model_label.setScaledContents(True)

    #二维码识别
    def scan_QRcode(self, frame):
        barcodes = decode(frame)
        
        if barcodes:
            for barcode in barcodes:
                myData = barcode.data.decode('utf-8')
                
                if (myData != self.last_code) or (self.last_code is None):
                    print(f"识别到新的二维码: {myData}")
                    self.detected_codes.add(myData)
                    self.last_code = myData

                    # 图框
                    pts = np.array([barcode.polygon], np.int32)
                    pts = pts.reshape((-1,1,2))
                    cv2.polylines(frame, [pts], True, (0,255,0), 2)  # G
                    
                    # 二维码上方显示解码信息
                    x, y, w, h = barcode.rect
                    cv2.putText(frame, myData, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
                    return frame
        else:
            return None

    #进度条
    def progress_to(self, target):
        self.target_progress = target
        self.progress_timer.start(20)
    def update_progress(self):
        if self.current_progress < self.target_progress:
            self.current_progress += 1
            self.progressbar.setValue(self.current_progress)
        else:
            self.progress_timer.stop()


    # 检测可用串口
    def port_check(self):
        print("开始检测串口...")
        self.Com_Dict = {} #用于存储串口信息
        port_list = list(serial.tools.list_ports.comports()) #获取系统中可用的串口，转成list
        self.comboBox.clear() #清空串口下拉框
        for port in port_list: #遍历port_list中的每一个可用串口
            self.Com_Dict["%s" % port[0]] = "%s" % port[1] #将串口名称和串口信息转为字符串，并储存为字典的键值对
            self.comboBox.addItem(port[0]) #将串口名添加到comboBox 下拉框
        print("串口检测完毕...")
    
    
        # 打开串口
    
    def port_open(self):
        #打开串口前设置各种参数
        self.ser.port = self.comboBox.currentText() #选择的串口名称
        try:
            self.ser.open()
        except: #弹出一个错误消息对话框
            QMessageBox.critical(self, "串口错误", "此串口不能被打开！")
            return None

        if self.ser.isOpen():
            self.openbutton.setEnabled(False) #禁用掉“打开"按钮，防止重复打开
            self.closebutton.setEnabled(True) #启用关闭按钮
            print("串口打开成功...")
    

        # 关闭串口
    def port_close(self):
        try:
            self.ser.close()
        except:
            pass
        self.openbutton.setEnabled(True) #启用打开串口按钮
        self.closebutton.setEnabled(False) #禁用关闭串口按钮
        print("串口关闭成功...")

    
    def start(self):#启动按钮
        self.start_recognition() #开始图像识别检测
        print("智能装配平台启动...")

    
    def reset_moto_click(self):
        if self.ser.isOpen():
            try:
                self.ser.write(b'2')
                print("尝试执行电机归位...")
            except Exception as e:
                QMessageBox.critical(self, "执行失败", f"无法发送数据: {str(e)}")
        else:
            QMessageBox.warning(self, "串口未打开", "请先打开串口")

    def start_moto_click(self):
        if self.ser.isOpen():
            try:
                self.ser.write(b'3')
                print("尝试启动电机...")
            except Exception as e:
                QMessageBox.critical(self, "执行失败", f"无法发送数据: {str(e)}")
        else:
            QMessageBox.warning(self, "串口未打开", "请先打开串口")

    def open1_click(self):
            if self.ser.isOpen():
                try:
                    self.ser.write(b'4')
                    print("尝试启动1号气缸...")
                except Exception as e:
                    QMessageBox.critical(self, "启动失败", f"无法发送数据: {str(e)}")
            else:
                QMessageBox.warning(self, "串口未打开", "请先打开串口")

    def open2_click(self):
        if self.ser.isOpen():
            try:
                self.ser.write(b'5')
                print("尝试启动2号气缸...")
            except Exception as e:
                QMessageBox.critical(self, "启动失败", f"无法发送数据: {str(e)}")
        else:
            QMessageBox.warning(self, "串口未打开", "请先打开串口")

    def open3_click(self):
        if self.ser.isOpen():
            try:
                self.ser.write(b'6')
                print("尝试启动3号气缸...")
            except Exception as e:
                QMessageBox.critical(self, "启动失败", f"无法发送数据: {str(e)}")
        else:
            QMessageBox.warning(self, "串口未打开", "请先打开串口")
    
    def update_frame(self):
        if self.camera is not None and self.camera.isOpened():
            ret, frame = self.camera.read()
            if ret:
                original_frame = frame.copy()
                # 显示摄像头画面
                original_frame = cv2.cvtColor(original_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = original_frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(original_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                scaled_image = qt_image.scaled(self.camera_label.width(), self.camera_label.height(), QtCore.Qt.KeepAspectRatio)
                self.camera_label.setPixmap(QPixmap.fromImage(scaled_image))

                # #每30ms扫描二维码
                # QRcodeframe = self.scan_QRcode(frame)
                # if QRcodeframe is not None:
                #     # 显示处理后的图像
                #     QRcodeframe = cv2.cvtColor(QRcodeframe, cv2.COLOR_BGR2RGB)
                #     h, w, ch = QRcodeframe.shape
                #     bytes_per_line = ch * w
                #     qt_image = QImage(QRcodeframe.data, w, h, bytes_per_line, QImage.Format_RGB888)
                #     scaled_image = qt_image.scaled(self.QRcode_label.width(), self.QRcode_label.height(), QtCore.Qt.KeepAspectRatio)
                #     self.QRcode_label.setPixmap(QPixmap.fromImage(scaled_image))

                if self.YesorNo:
                    #执行图像识别
                    print("尝试识别物料标签中...")
                    matched_frame = None
                    matched_img = None
                    for img in self.images: #images模板
                        current_matched_img, result = self.ORBMatcher(img, frame) #frame是视频帧
                        if result:
                            matched_frame = current_matched_img #匹配结果
                            matched_img = img #匹配到的模板
                            break  # 成功匹配到就退出循环

                    # 显示算法识别结果
                    if matched_frame is not None: #匹配到了
                        print("成功识别到物料...")
                        self.progress_to(10)
                        result_frame = matched_frame
                        self.stop_recognition()  # 检测到就停止识别
                        #这里设置为一旦检测到了就停止计时，无论是否是之前检测到的

                        if (self.last_matched_img != None and self.last_matched_img != matched_img) or (self.last_matched_img == None):
                            #如果本次匹配到的和上次不同才会发送数据，避免串口通信阻塞，也就是实现了识别到只发送一次数据
                            if self.ser.isOpen():
                                try:
                                    self.ser.write(b'1') #启动整个流程
                                    print("上位机命令下位机启动项目流程...")
                                    #self.progress_to(100)
                                except Exception as e:
                                    QMessageBox.critical(self, "发送失败", f"无法发送数据: {str(e)}")
                                
                                self.last_matched_img = matched_img  # 更新上一次匹配到的模板
                            else:
                                QMessageBox.warning(self, "串口未打开", "请先打开串口")

                    else:  #如果没有匹配结果
                        result_frame = frame  # 将算法识别窗口设置为原始帧

                        
                        #没有匹配到结果就看是否超时。  isValid()的作用：判断是否正在计时中
                        # if self.recognition_timer.isValid() and self.recognition_timer.elapsed() > self.recognition_timeout:
                        #     if self.ser.isOpen():
                        #         try:
                        #             self.ser.write(b'4') #超时
                        #             print("无法检测到正确的物料，将回到开始位置...")
                        #             self.progressbar.setValue(0)
                        #         except Exception as e:
                        #             QMessageBox.critical(self, "发送失败", f"无法发送数据: {str(e)}")
                        #     self.stop_recognition()

                    
                    # 显示算法识别结果
                    result_frame = cv2.cvtColor(result_frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = result_frame.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(result_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                    scaled_image = qt_image.scaled(self.result_label.width(), self.result_label.height(), QtCore.Qt.KeepAspectRatio)
                    self.result_label.setPixmap(QPixmap.fromImage(scaled_image))
                #每30毫秒重复一次检测然后更新，对于人眼来说，这个更新频率足够快，看起来就像是实时的
    
    def open_camera(self):
        if self.camera is None:
            selected_camera = self.select_Camera.currentText()
            camera_index = int(selected_camera.split()[-1])
            self.camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)  # 使用DirectShow后端优化
            self.camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.camera.open(camera_index)

            if self.camera.isOpened():
                self.last_matched_img = None  # 在每次打开摄像头都设置默认值

                self.timer.start(30)  # 每30毫秒调用一次update_frame()
                self.serial_timer.start(100)  # 每100毫秒检测一次串口信息

                self.open_camera_button.setEnabled(False)
                self.close_camera_button.setEnabled(True)
                self.YesorNo = False  # 重置
                print(f"摄像头{camera_index}成功打开...")
            else:
                QMessageBox.warning(self, "错误", "无法打开摄像头！")

    def close_camera(self):
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
            self.camera = None
            self.camera_label.clear()  #清除显示的图像
            self.result_label.clear()  #清除匹配结果
            self.open_camera_button.setEnabled(True)
            self.close_camera_button.setEnabled(False)
            self.YesorNo = False  # 重置
            print("摄像头已关闭...")
            self.populate_camera_list() #重置摄像头列表


    def start_recognition(self):
        self.YesorNo = True
        #self.recognition_timer.start()
        #print("开始图像识别并计时")

    def stop_recognition(self):
        self.YesorNo = False
        #self.recognition_timer.invalidate()
        #print("停止图像识别和计时")

    def check_serial_data(self):
        if self.ser.isOpen():
            try:
                if self.ser.in_waiting:
                    received_data = self.ser.read(self.ser.in_waiting).decode()
                    if '2' in received_data:
                        print("收到反馈：电机已经归位")
                        self.progress_to(30)
                    if '3' in received_data:
                        print("收到反馈：电机已经到达翻转位置")
                        self.progress_to(40)
                    if '4' in received_data:
                        self.count_4 += 1
                        if(self.count_4 % 2==1):
                            print("收到反馈：1号电磁阀已经启动")
                            self.progress_to(50)
                        else:
                            print("收到反馈：1号电磁阀已经关闭")
                            self.progress_to(80)
                    if '5' in received_data:
                        self.count_5 += 1
                        if self.count_5 % 2 == 1:
                            print("收到反馈：2号电磁阀已经启动")
                            self.progress_to(60)
                        else:
                            print("收到反馈：2号电磁阀已经关闭")
                            self.progress_to(70)
                    if '6' in received_data:
                        self.count_6 += 1
                        if self.count_6 % 2 == 1:
                            print("收到反馈：3号电磁阀已经启动")
                        else:
                            print("收到反馈：3号电磁阀已经关闭")
                        self.progress_to(100)
            except Exception as e:
                print(f"串口数据读取错误: {str(e)}")
    
    #三个模板图像
    def load_template_images(self):
        self.images = [
            cv2.imread(resource_path("img_circle1.jpg")),
            cv2.imread(resource_path("img_circle2.jpg")),
            cv2.imread(resource_path("img_circle3.jpg"))
        ]


    def red_detect(self,contours_red):
        for  contours_reds in  contours_red:
            area=cv2.contourArea(contours_reds)
            if(area>1800):
                return True
        return False
    def blue_detect(self,contours_blue):
        for  contours_blues in  contours_blue:
            area=cv2.contourArea(contours_blues)
            if(area>1800):
                return True
        return False

    #ORB 设置为静态方法
    #@staticmethod
    def ORBMatcher(self,img1,img2):
        img_blur=cv2.GaussianBlur(img2, (9, 9), 2)
        
        img_mask=np.zeros((img2.shape[0],img2.shape[1],3),dtype=np.uint8)
        img_mask[150:390,180:425]=1
        img_camera1=cv2.multiply(img2,img_mask)
        #cv2.imshow("mask",img_camera1)
        #img_mask=np.array([img_blur.shape[0],img_blur.shape[1],3])
        #frame_hsv=cv2.cvtColor(img_blur,cv2.COLOR_BGR2HSV)
        
        frame_hsv=cv2.cvtColor(img_camera1,cv2.COLOR_BGR2HSV)

        lower_red1=np.array([0,50,50])
        lower_red2=np.array([170,50,50])
        lower_blue=np.array([100,50,50])
        higher_red1=np.array([10,255,255])
        higher_red2=np.array([180,255,255])
        higher_blue=np.array([125,255,255])

        mask_red1=cv2.inRange(frame_hsv,lower_red1,higher_red1)
        mask_red2=cv2.inRange(frame_hsv,lower_red2,higher_red2)
        mask_red=cv2.bitwise_or(mask_red1,mask_red2)
        mask_blue=cv2.inRange(frame_hsv,lower_blue,higher_blue)
        #frame_red=cv2.morphologyEx(mask_red,cv2.MORPH_OPEN,kernel)
        #frame_blue=cv2.morphologyEx(mask_blue,cv2.MORPH_OPEN,kernel)
        contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        #cv2.drawContours(frame, contours_red, -1, (0,0,255), 2)
        #cv2.drawContours(frame, contours_blue, -1, (255,0,0), 2)
        result_red=self.red_detect(contours_red)
        result_blue=self.blue_detect(contours_blue)
        edges=cv2.Canny(img_blur,50,150)
        
        # 使用霍夫圆变换检测圆 
        error = -1
        circles = cv2.HoughCircles(edges, cv2.HOUGH_GRADIENT, 1, 40, param1=20, param2=30, minRadius=100, maxRadius=125)
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                center = (i[0], i[1])  # 圆心
                radius = i[2]  # 半径
                #print(radius)
                error=0
                error=f"{abs(((radius-113.37)/113.37)*22.4):.2f}"
                
                # 绘制圆心
                if(result_red):
                    #cv2.circle(img2, center, 2, (0, 0, 255), 3)
                # 绘制圆轮廓
                    cv2.circle(img2, center, radius, (0, 0, 255), 3)
                    cv2.putText(img2,f"circle",(200,30),cv2.FONT_HERSHEY_PLAIN,3,(0,0,255),3)
                    #cv2.putText(img2,str("error:"+error+'mm'),(300,70),cv2.FONT_HERSHEY_PLAIN,3,(128,0,128),3)
                if(result_blue):
                # cv2.circle(img2, center, 2, (255, 0, 0), 3)
                # 绘制圆轮廓
                    cv2.circle(img2, center, radius, (255, 0, 0), 3)
                    cv2.putText(img2,f"circle",(200,35),cv2.FONT_HERSHEY_PLAIN,3,(255,0,0),3)
                    #cv2.putText(img2,str("error:"+error+'mm'),(300,70),cv2.FONT_HERSHEY_PLAIN,3,(128,0,128),3)
        

        ORB=cv2.ORB_create()
        keypoints1,des1=ORB.detectAndCompute(img1,None)
        keypoints2,des2=ORB.detectAndCompute(img2,None)
        ##近似近邻快速库(Fast Library for Approximate Nearest Neighbors，简称 FLANN），加速匹配过程
        FLANN_INDEX_LSH=6#局部敏感哈希
        index_params=dict(algorithm=FLANN_INDEX_LSH,table_number=6,key_size=12,multi_prove_level=1)#哈希表数量、哈希键大小、多探针级别数量
        search_params=dict(checks=50)
        flann=cv2.FlannBasedMatcher(index_params,search_params)
        matches=flann.knnMatch(des1,des2,k=2)
        points_good=[]
        for match in matches:
            if(len(match))==2:
                m,n=match
                if m.distance<0.75*n.distance:
                    points_good.append(m)
        MIN_MATCH_COUNT = 30 #保证鲁棒性，为RANSAC提供足够内点
        if len(points_good)>MIN_MATCH_COUNT:
            src_array=np.float32([keypoints1[m.queryIdx].pt for m in points_good]).reshape(-1,1,2)
            dst_array=np.float32([keypoints2[m.trainIdx].pt for m in points_good]).reshape(-1,1,2)
            M,mask=cv2.findHomography(src_array,dst_array,cv2.RANSAC,5.0)
            theta = -np.arctan2(M[0, 1], M[0, 0]) * 180 / np.pi
            matchesMask=mask.ravel().tolist()
            #h=img1.shape[0]
            #w=img1.shape[1]
            #array=np.float32([ [0,0],[0,h-1],[w-1,h-1],[w-1,0] ]).reshape(-1,1,2)
            #dst = np.array([[50, 50], [200, 50], [50, 200], [200, 200]], dtype=np.int32)
            #dst=cv2.perspectiveTransform(array,M)     #进行透视变换
            #img2=cv2.polylines(img2,[np.int32(dst)],True,(255, 0, 0),6,cv2.LINE_AA)
            draw_params = dict(matchColor = (0,255,0), # draw matches in green color
            singlePointColor = (0,0,255),
            matchesMask = matchesMask, # draw only inliers
            flags = 2)
            img3=cv2.drawMatches(img1,keypoints1,img2,keypoints2,points_good,None,**draw_params)
            if(result_red):
                cv2.putText(img3,f"color:red",(400,120),cv2.FONT_HERSHEY_PLAIN,3,(0,0,255),3)
                
                # # 绘制圆轮廓
                # cv2.circle(img3, center, radius, (0, 0, 255), 3)
                # cv2.putText(img3,f"circle",(200,30),cv2.FONT_HERSHEY_PLAIN,3,(0,0,255),3)

            if(result_blue):
                cv2.putText(img3,f"color:blue",(400,120),cv2.FONT_HERSHEY_PLAIN,3,(255,0,0),3)
                
                # #画圆
                # cv2.circle(img3, center, radius, (255, 0, 0), 3)
                # cv2.putText(img3,f"circle",(200,35),cv2.FONT_HERSHEY_PLAIN,3,(255,0,0),3)

            #角度和公差
            cv2.putText(img3,f"angle:{int(theta)}",(210,70),cv2.FONT_HERSHEY_PLAIN,3,(128,0,128),3)
            cv2.putText(img3,str("error:"+ str(error) +'mm'),(500,70),cv2.FONT_HERSHEY_PLAIN,3,(128,0,128),3)
            #cv2.imshow("display",img3)
            return img3,True
        else:
            return None,False
    #算法会尝试和三个模板进行匹配，直到找到一个匹配成功的模板
    #匹配成功之后，直接映射识别的结果
    #即使是上一次匹配到了，摄像头还会实时读取画面进行识别，并将最新的识别结果显示

    def closeEvent(self, event):
        if self.camera is not None: #释放摄像头资源
            self.camera.release()
        sys.stdout = sys.__stdout__  # 恢复标准输出
        event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    myshow = Pyqt5_Serial()

    apply_stylesheet(app, theme='dark_amber.xml')

    # 自定义进度条样式
    progress_bar_style = """
    QProgressBar {
        border: 1px solid grey;
        border-radius: 5px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: green;
        width: 10px;
        margin: 0.5px;
    }
    """

    # 实现应用
    myshow.progressbar.setStyleSheet(progress_bar_style)
    myshow.progressbar.setAlignment(QtCore.Qt.AlignCenter)
    myshow.progressbar.setFormat("%p%")
    myshow.progressbar.setTextVisible(True)

    # 增加对比
    myshow.progressbar.setPalette(QtGui.QPalette(QtGui.QColor("white")))

    myshow.show()
    sys.exit(app.exec_())