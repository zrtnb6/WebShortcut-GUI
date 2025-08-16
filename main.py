import sys
import os
import json
import base64
from datetime import datetime
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTextEdit, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QMenuBar, QMenu, QAction, QStatusBar, QPushButton,
    QDialog, QLineEdit, QFormLayout, QMessageBox, QFileDialog, QTabWidget,
    QListWidget, QListWidgetItem, QDialogButtonBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QTextCursor, QPalette, QColor
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from xml.etree import ElementTree as ET


class WebDAVConfigDialog(QDialog):
    """WebDAV配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WebDAV 配置")
        self.setGeometry(400, 400, 450, 250)

        layout = QFormLayout()

        self.url_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.remote_dir_input = QLineEdit()
        self.remote_dir_input.setPlaceholderText("默认上传到根目录") 

        layout.addRow("WebDAV地址:", self.url_input)
        layout.addRow("用户名:", self.username_input)
        layout.addRow("密码:", self.password_input)
        layout.addRow("远程目录:", self.remote_dir_input)

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addRow(btn_layout)
        self.setLayout(layout)

    def get_config(self):
        return {
            "url": self.url_input.text().strip(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip(),
            "remote_dir": self.remote_dir_input.text().strip()
        }

    def set_config(self, config):
        self.url_input.setText(config.get("url", ""))
        self.username_input.setText(config.get("username", ""))
        self.password_input.setText(config.get("password", ""))
        self.remote_dir_input.setText(config.get("remote_dir", ""))


class WebDAVFileDialog(QDialog):
    """WebDAV文件选择对话框"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("从WebDAV恢复备份")
        self.setGeometry(400, 400, 600, 400)
        self.config = config
        
        layout = QVBoxLayout()
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(QLabel("选择要恢复的文件:"))
        layout.addWidget(self.file_list)
        
        # 按钮布局
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self.load_files)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(button_box)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # 初始加载文件
        self.load_files()
    
    def load_files(self):
        """从WebDAV服务器加载文件列表"""
        self.file_list.clear()
        
        if not self.config.get("url"):
            QMessageBox.warning(self, "配置错误", "请先配置WebDAV服务器")
            return
            
        try:
            # 构建URL
            url = self.config["url"].strip('/')
            remote_dir = self.config.get("remote_dir", "").strip('/')
            if remote_dir:
                url = f"{url}/{remote_dir}"
            
            # 发送PROPFIND请求获取文件列表
            auth = (self.config["username"], self.config["password"])
            headers = {'Depth': '1'}
            response = requests.request('PROPFIND', url, auth=auth, headers=headers)
            
            if response.status_code != 207:  # 207 Multi-Status
                raise Exception(f"服务器返回错误: {response.status_code}")
                
            # 解析XML响应
            root = ET.fromstring(response.content)
            ns = {'d': 'DAV:'}
            
            for response in root.findall('d:response', ns):
                href = response.find('d:href', ns).text
                # 获取显示名称（去除路径）
                display_name = os.path.basename(href)
                
                # 过滤掉目录和空名称
                if display_name and not href.endswith('/'):
                    # 只显示Markdown文件
                    if display_name.lower().endswith('.md'):
                        self.file_list.addItem(display_name)
                        
        except Exception as e:
            QMessageBox.critical(self, "加载错误", f"无法从WebDAV加载文件列表:\n{str(e)}")
    
    def selected_file(self):
        """获取选中的文件名"""
        selected_items = self.file_list.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return None


class MarkdownNotepad(QMainWindow):
    """Markdown记事本主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Markdown记事本")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 8px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
            }
        """)
        
        # 获取应用基础路径
        try:
            # 尝试从打包后的资源加载
            self.base_path = sys._MEIPASS
        except Exception:
            # 开发环境加载
            self.base_path = os.path.dirname(os.path.abspath(__file__))
        
        # 设置应用数据目录（用于存储配置和缓存）
        self.app_data_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "MarkdownNotepadData")
        os.makedirs(self.app_data_dir, exist_ok=True)
        
        # 设置缓存目录
        self.cache_dir = os.path.join(self.app_data_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 设置主窗口图标 - 修复打包后图标不显示的问题
        self.setup_icon()
        
        # 初始化变量
        self.current_file = None
        self.webdav_config = self.load_config()
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(30000)  # 30秒自动保存

        # 创建UI
        self.init_ui()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("就绪 | 未保存的更改")

    def setup_icon(self):
        """设置应用图标，确保在打包后也能正常工作"""
        # 可能的图标路径列表
        icon_paths = [
            # 1. 尝试从打包资源目录加载
            os.path.join(getattr(sys, '_MEIPASS', ''), "icons", "app_icon.png"),
            
            # 2. 尝试从可执行文件所在目录加载
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "app_icon.png"),
            
            # 3. 尝试从应用数据目录加载
            os.path.join(self.app_data_dir, "app_icon.png"),
            
            # 4. 尝试从源代码目录加载（开发环境）
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "app_icon.png")
        ]
        
        # 尝试所有可能的路径
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                print(f"使用图标: {icon_path}")
                return
        
        # 如果所有路径都失败，使用内置图标（作为base64字符串）
        print("未找到图标文件，使用内置图标")
        self.setWindowIcon(self.create_fallback_icon())
    
    def create_fallback_icon(self):
        """创建内置图标作为后备"""
        # 创建一个简单的图标作为后备
        from PyQt5.QtGui import QPixmap, QPainter, QColor, QBrush
        from PyQt5.QtCore import QSize
        
        # 创建一个简单的蓝色M图标
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.setBrush(QBrush(QColor(52, 152, 219)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 64, 64, 15, 15)
        
        # 绘制M字母
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")
        
        painter.end()
        
        return QIcon(pixmap)

    def init_ui(self):
        """初始化用户界面"""
        # 创建菜单栏
        self.create_menus()

        # 主布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        main_layout.addWidget(self.tab_widget)

        # 添加初始标签页
        self.add_new_tab()

        # 底部按钮
        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("保存")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                padding: 8px; 
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.save_btn.clicked.connect(self.save_file)

        self.webdav_backup_btn = QPushButton("备份到WebDAV")
        self.webdav_backup_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; 
                color: white; 
                padding: 8px; 
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
        """)
        self.webdav_backup_btn.clicked.connect(self.backup_to_webdav)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.webdav_backup_btn)

        main_layout.addLayout(btn_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def create_menus(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)

        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)

        save_as_action = QAction("另存为...", self)
        save_as_action.triggered.connect(self.save_file_as)

        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # WebDAV菜单
        webdav_menu = menubar.addMenu("WebDAV")

        config_action = QAction("配置...", self)
        config_action.triggered.connect(self.configure_webdav)

        backup_action = QAction("备份当前文件", self)
        backup_action.setShortcut("Ctrl+B")
        backup_action.triggered.connect(self.backup_to_webdav)

        restore_action = QAction("从备份恢复...", self)
        restore_action.triggered.connect(self.restore_from_webdav)

        webdav_menu.addAction(config_action)
        webdav_menu.addSeparator()
        webdav_menu.addAction(backup_action)
        webdav_menu.addAction(restore_action)

        # 查看菜单
        view_menu = menubar.addMenu("查看")

        self.preview_action = QAction("预览", self)
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(True)
        self.preview_action.setShortcut("Ctrl+P")
        self.preview_action.triggered.connect(self.toggle_preview)

        view_menu.addAction(self.preview_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)

        help_menu.addAction(about_action)

    def add_new_tab(self, title="新文档", content="", file_path=None):
        """添加新标签页"""
        # 确保title是字符串类型
        title = str(title)
        
        # 创建容器小部件
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)

        # 创建编辑区域
        editor = QTextEdit()
        editor.setFont(QFont("Consolas", 12))
        editor.setPlainText(content)
        editor.textChanged.connect(self.document_modified)
        
        # 保存编辑器样式表以便应用到预览窗口
        editor_style = editor.styleSheet()
        editor_style += " background-color: white;"  # 确保编辑器有白色背景

        # 创建预览区域
        preview = QTextEdit()
        preview.setFont(QFont("Segoe UI", 11))
        preview.setReadOnly(True)
        
        # 应用与编辑窗口相同的样式表
        preview.setStyleSheet(editor_style + " background-color: #f8f8f8;")

        # 添加组件到分割器
        splitter.addWidget(editor)
        splitter.addWidget(preview)
        splitter.setSizes([600, 400])
        
        layout.addWidget(splitter)
        container.setLayout(layout)

        # 添加标签页
        tab_index = self.tab_widget.addTab(container, title)
        self.tab_widget.setCurrentIndex(tab_index)

        # 存储对编辑器和预览的引用
        container.editor = editor
        container.preview = preview
        container.file_path = file_path  # 存储文件路径

        # 连接编辑器的修改事件
        editor.textChanged.connect(lambda: self.update_preview(preview, editor))

        # 初始更新预览
        self.update_preview(preview, editor)

        # 如果是当前标签页，设置当前文件路径
        if tab_index == self.tab_widget.currentIndex():
            self.current_file = file_path

        return container

    def close_tab(self, index):
        """关闭标签页"""
        if self.tab_widget.count() > 1:
            # 切换标签页前保存当前文件路径
            current_widget = self.tab_widget.currentWidget()
            if current_widget:
                self.current_file = current_widget.file_path
            
            # 关闭标签页
            self.tab_widget.removeTab(index)
            
            # 更新当前文件路径为新标签页的文件路径
            current_widget = self.tab_widget.currentWidget()
            if current_widget:
                self.current_file = current_widget.file_path
        else:
            QMessageBox.information(self, "无法关闭", "至少需要保留一个标签页")

    def get_current_tab_content(self):
        """获取当前标签页的内容部件"""
        current_widget = self.tab_widget.currentWidget()
        if current_widget:
            return current_widget.findChildren(QSplitter)[0]
        return None

    def get_current_container(self):
        """获取当前标签页的容器"""
        return self.tab_widget.currentWidget()

    def get_current_preview(self):
        """获取当前标签页的预览"""
        splitter = self.get_current_tab_content()
        if splitter and splitter.count() > 1:
            return splitter.widget(1)
        return None

    def document_modified(self):
        """文档修改时调用"""
        self.update_status("编辑中 | 未保存的更改")

    def update_preview(self, preview_widget, editor_widget):
        """更新预览窗格"""
        markdown_text = editor_widget.toPlainText()
        try:
            html = markdown.markdown(
                markdown_text,
                extensions=[
                    'extra',
                    'tables',
                    CodeHiliteExtension(),
                    'fenced_code'
                ]
            )
        except Exception as e:
            html = f"<p style='color:red'>Markdown解析错误: {str(e)}</p>"

        # 基本CSS样式
        css = """
        <style>
            body { font-family: 'Segoe UI', sans-serif; line-height: 1.6; }
            h1, h2, h3, h4, h5, h6 { color: #2c3e50; }
            pre { background-color: #f8f9fa; padding: 15px; border-radius: 4px; }
            code { background-color: #f8f9fa; padding: 2px 4px; border-radius: 4px; }
            blockquote { border-left: 4px solid #3498db; padding-left: 15px; color: #555; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            a { color: #2980b9; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
        """

        preview_widget.setHtml(f"<html><head>{css}</head><body>{html}</body></html>")

    def toggle_preview(self):
        """切换预览窗格可见性"""
        preview = self.get_current_preview()
        if preview:
            preview.setVisible(self.preview_action.isChecked())

    def save_file(self):
        """保存文件"""
        container = self.get_current_container()
        if not container:
            return

        editor = container.editor
        if not editor:
            return

        # 如果文件路径已设置，直接保存
        if container.file_path:
            self.save_to_file(container.file_path)
        else:
            # 如果没有文件路径，执行另存为
            self.save_file_as()

    def save_file_as(self):
        """文件另存为"""
        container = self.get_current_container()
        if not container:
            return

        editor = container.editor
        if not editor:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "", "Markdown文件 (*.md);;所有文件 (*)"
        )

        if file_path:
            if not file_path.endswith('.md'):
                file_path += '.md'
                
            if self.save_to_file(file_path):
                container.file_path = file_path
                self.update_tab_title(os.path.basename(file_path))
                self.current_file = file_path  # 更新当前文件路径

    def save_to_file(self, file_path):
        """保存内容到文件"""
        container = self.get_current_container()
        if not container or not container.editor:
            return False

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(container.editor.toPlainText())
            self.update_status(f"已保存: {file_path}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存错误", f"无法保存文件:\n{str(e)}")
            return False

    def open_file(self):
        """打开文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "Markdown文件 (*.md);;所有文件 (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 在新标签页中打开文件，并设置文件路径
                self.add_new_tab(os.path.basename(file_path), content, file_path)
                self.update_status(f"已打开: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "打开错误", f"无法打开文件:\n{str(e)}")

    def autosave(self):
        """自动保存功能"""
        container = self.get_current_container()
        if container and container.file_path:
            self.save_to_file(container.file_path)
            self.update_status(f"已自动保存: {container.file_path}")

    def update_tab_title(self, title):
        """更新当前标签页标题"""
        index = self.tab_widget.currentIndex()
        self.tab_widget.setTabText(index, title)

    def update_status(self, message):
        """更新状态栏"""
        now = datetime.now().strftime("%H:%M:%S")
        self.status_bar.showMessage(f"[{now}] {message}")

    def configure_webdav(self):
        """配置WebDAV"""
        dialog = WebDAVConfigDialog(self)
        dialog.set_config(self.webdav_config)

        if dialog.exec_() == QDialog.Accepted:
            self.webdav_config = dialog.get_config()
            self.save_config()
            self.update_status("WebDAV配置已更新")

    def backup_to_webdav(self):
        """备份到WebDAV"""
        if not self.webdav_config.get("url"):
            self.configure_webdav()
            if not self.webdav_config.get("url"):
                return

        container = self.get_current_container()
        if not container or not container.editor:
            return

        # 获取编辑器内容
        content = container.editor.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "内容为空", "当前文档内容为空，无法备份")
            return

        # 如果文件未保存，让用户选择保存位置
        if not container.file_path:
            self.save_file()  # 这会设置 container.file_path
            # 如果用户取消了保存对话框
            if not container.file_path:
                return

        # 获取文件名和扩展名
        filename = os.path.basename(container.file_path)
        name, ext = os.path.splitext(filename)
        
        # 生成时间戳 (格式: YYYYMMDDHHMMSS)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # 创建带时间戳的新文件名
        backup_filename = f"{name}_{timestamp}{ext}"

        # 构建远程路径
        remote_dir = self.webdav_config.get("remote_dir", "").strip('/')
        remote_path = f"{remote_dir}/{backup_filename}" if remote_dir else backup_filename

        # 上传文件
        try:
            url = self.webdav_config["url"].strip('/') + '/' + remote_path
            auth = (self.webdav_config["username"], self.webdav_config["password"])
            
            # 使用编辑器内容上传
            response = requests.put(url, data=content.encode('utf-8'), auth=auth)

            if response.status_code in [200, 201, 204]:
                self.update_status(f"文件已备份到WebDAV: {url}")
                QMessageBox.information(self, "备份成功", 
                    f"文件已成功备份到:\n{url}\n\n"
                    f"备份文件名: {backup_filename}")
            else:
                raise Exception(f"服务器响应: {response.status_code} - {response.reason}")
        except Exception as e:
            QMessageBox.critical(self, "备份失败", f"无法备份文件到WebDAV:\n{str(e)}")

    def restore_from_webdav(self):
        """从WebDAV恢复文件"""
        if not self.webdav_config.get("url"):
            self.configure_webdav()
            if not self.webdav_config.get("url"):
                return

        # 创建文件选择对话框
        dialog = WebDAVFileDialog(self.webdav_config, self)
        if dialog.exec_() == QDialog.Accepted:
            filename = dialog.selected_file()
            if filename:
                self.download_and_open_webdav_file(filename)

    def download_and_open_webdav_file(self, filename):
        """从WebDAV下载并打开文件"""
        try:
            # 构建URL
            url = self.webdav_config["url"].strip('/')
            remote_dir = self.webdav_config.get("remote_dir", "").strip('/')
            
            if remote_dir:
                full_url = f"{url}/{remote_dir}/{filename}"
            else:
                full_url = f"{url}/{filename}"
                
            auth = (self.webdav_config["username"], self.webdav_config["password"])
            
            # 发送GET请求
            response = requests.get(full_url, auth=auth)
            
            if response.status_code != 200:
                raise Exception(f"服务器响应: {response.status_code} - {response.reason}")
                
            # 获取文件内容
            content = response.text
            
            # 创建缓存文件路径
            cache_path = os.path.join(self.cache_dir, filename)
            
            # 保存到缓存目录
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 在新标签页中打开缓存文件
            self.add_new_tab(filename, content, cache_path)
            self.update_status(f"已恢复文件到缓存: {cache_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "恢复失败", f"无法从WebDAV恢复文件:\n{str(e)}")

    def show_about(self):
        """显示关于对话框"""
        about_text = f"""
        <h2>Markdown记事本</h2>
        <p>版本 1.0</p>
        <p>一款功能强大的Markdown笔记工具，支持实时预览和WebDAV备份。</p>
        <p>功能特点：</p>
        <ul>
            <li>Markdown语法支持</li>
            <li>实时预览功能</li>
            <li>多标签页编辑</li>
            <li>WebDAV云备份与恢复</li>
            <li>自动保存</li>
            <li>精美用户界面</li>
            <li>备份文件自动添加时间戳</li>
            <li>配置和缓存存储在应用数据目录</li>
            <li>从WebDAV恢复的文件自动保存到缓存目录</li>
        </ul>
        <p>应用数据目录: {self.app_data_dir}</p>
        <p>缓存目录: {self.cache_dir}</p>
        """
        QMessageBox.about(self, "关于", about_text)

    def load_config(self):
        """加载配置"""
        config_path = os.path.join(self.app_data_dir, "webdav_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置失败: {str(e)}")
                return self.get_default_config()
        return self.get_default_config()
    
    def get_default_config(self):
        """获取默认配置"""
        return {
            "url": "",
            "username": "",
            "password": "",
            "remote_dir": ""
        }

    def save_config(self):
        """保存配置"""
        config_path = os.path.join(self.app_data_dir, "webdav_config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.webdav_config, f, indent=4)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 创建调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.black)
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, Qt.black)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(52, 152, 219))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    # 设置全局滚动条样式（确保编辑器和预览窗口一致）
    app.setStyleSheet("""
        QScrollBar:vertical {
            border: none;
            background: #f0f0f0;
            width: 12px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #c0c0c0;
            min-height: 20px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical:hover {
            background: #a0a0a0;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QScrollBar:horizontal {
            border: none;
            background: #f0f0f0;
            height: 12px;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background: #c0c0c0;
            min-width: 20px;
            border-radius: 6px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #a0a0a0;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
    """)

    # 创建主窗口
    notepad = MarkdownNotepad()
    notepad.show()

    sys.exit(app.exec_())
