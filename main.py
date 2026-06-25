import os
import json
import time
import traceback
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.image import Image as KivyImage
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.utils import platform
from kivy.graphics import Color, RoundedRectangle

# ---------- THƯ VIỆN ẢNH ----------
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Pillow chưa được cài. Hãy chạy: pip install Pillow")

# ---------- CẤU HÌNH ----------
HISTORY_FILE = "print_history.json"

# MÀU SẮC TƯƠI SÁNG - XANH DA TRỜI CHỦ ĐẠO
COLOR_PRIMARY = (0.26, 0.65, 0.96, 1)      # #42A5F5
COLOR_PRIMARY_DARK = (0.12, 0.53, 0.90, 1) # #1E88E5
COLOR_SUCCESS = (0.40, 0.73, 0.42, 1)      # #66BB6A
COLOR_WARNING = (1.0, 0.65, 0.15, 1)       # #FFA726
COLOR_ERROR = (0.94, 0.33, 0.31, 1)        # #EF5350
COLOR_GRAY = (0.6, 0.6, 0.6, 1)
COLOR_LIGHT_GRAY = (0.96, 0.96, 0.96, 1)
COLOR_WHITE = (1, 1, 1, 1)
COLOR_BLACK = (0.1, 0.1, 0.1, 1)

# ---------- HÀM TIỆN ÍCH LỊCH SỬ ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(h):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Warning: cannot save history:", e)

def add_history_entry(order_id, customer, box_qty):
    h = load_history()
    h.append({
        "order_id": str(order_id),
        "customer": str(customer),
        "box_qty": int(box_qty),
        "timestamp": datetime.now().isoformat()
    })
    save_history(h)

def has_been_printed(order_id):
    h = load_history()
    return any(item.get("order_id") == str(order_id) for item in h)

# ---------- KIỂM TRA NỀN TẢNG ----------
def is_android():
    return platform == "android"

# ---------- MODULE CHO ANDROID ----------
if is_android():
    from jnius import autoclass
    import socket
    
    def request_android_permissions():
        try:
            from android.permissions import request_permissions, Permission
            permissions = [
                Permission.BLUETOOTH,
                Permission.BLUETOOTH_ADMIN,
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
                Permission.ACCESS_FINE_LOCATION
            ]
            request_permissions(permissions)
        except Exception as e:
            print("request_android_permissions error:", e)

    def find_paired_printers_pyjnius():
        try:
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            adapter = BluetoothAdapter.getDefaultAdapter()
            if adapter is None:
                return []
            paired = adapter.getBondedDevices()
            devices = []
            try:
                arr = paired.toArray()
                for dev in arr:
                    devices.append((dev.getName(), dev.getAddress()))
            except:
                it = paired.iterator()
                while it.hasNext():
                    dev = it.next()
                    devices.append((dev.getName(), dev.getAddress()))
            return devices
        except Exception as e:
            print("find_paired_printers_pyjnius error:", e)
            return []

    def print_via_bluetooth_pyjnius(mac_addr, payload_bytes):
        """
        Gửi dữ liệu qua Bluetooth với chunk nhỏ để tránh mất dữ liệu
        """
        try:
            UUID = autoclass('java.util.UUID')
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            adapter = BluetoothAdapter.getDefaultAdapter()
            device = adapter.getRemoteDevice(mac_addr)
            spp_uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
            
            sock = device.createRfcommSocketToServiceRecord(spp_uuid)
            
            if adapter.isDiscovering():
                adapter.cancelDiscovery()
            
            # Thử kết nối với retry
            max_retries = 3
            connected = False
            for attempt in range(max_retries):
                try:
                    print(f"Connect attempt {attempt+1}/{max_retries}...")
                    sock.connect()
                    connected = True
                    break
                except Exception as e:
                    print(f"Connect attempt {attempt+1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        sock = device.createRfcommSocketToServiceRecord(spp_uuid)
                        sock.setSoTimeout(15000)
            
            if not connected:
                return False, "Không thể kết nối sau 3 lần thử"
            
            out = sock.getOutputStream()
            
            # GỬI CHẬM, TỪNG CHUNK NHỎ
            chunk_size = 256
            total_sent = 0
            
            for i in range(0, len(payload_bytes), chunk_size):
                chunk = payload_bytes[i:i+chunk_size]
                out.write(chunk)
                out.flush()
                total_sent += len(chunk)
                print(f"Sent {total_sent}/{len(payload_bytes)} bytes")
                time.sleep(0.15)  # Chờ 150ms mỗi chunk
            
            # Chờ máy in xử lý
            time.sleep(2)
            
            out.close()
            sock.close()
            return True, None
            
        except Exception as e:
            print(f"Bluetooth print error: {e}")
            return False, str(e)

# ---------- HÀM TÌM FONT TRÊN HỆ THỐNG ----------
def find_system_font():
    """Tìm font có sẵn trên hệ thống"""
    if is_android():
        font_paths = [
            "/system/fonts/Roboto-Bold.ttf",
            "/system/fonts/DroidSans-Bold.ttf",
            "/system/fonts/NotoSans-Bold.ttf",
            "/system/fonts/Roboto-Regular.ttf",
            "/system/fonts/DroidSans.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return path
        return None
    
    if platform == "win":
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/timesbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return path
    
    if platform == "darwin":
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        for path in font_paths:
            if os.path.exists(path):
                return path
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    
    return None

# ---------- TẠO ẢNH NHÃN (NGANG, 120x75mm) ----------
def create_label_image(order_id, customer, box_index, box_total,
                       width_mm=120, height_mm=75, dpi=203):
    """
    Tạo ảnh nhãn ngang (120x75mm) với bố cục chuẩn
    """
    if not HAS_PIL:
        raise ImportError("Pillow chưa được cài đặt.")

    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)

    # Tạo ảnh trắng - QUAN TRỌNG: dùng mode '1' (đen trắng)
    img = Image.new('1', (width_px, height_px), 1)
    draw = ImageDraw.Draw(img)

    font_path = find_system_font()
    
    if font_path:
        try:
            font_order = ImageFont.truetype(font_path, size=int(height_px * 0.25))
            font_name = ImageFont.truetype(font_path, size=int(height_px * 0.18))
            font_box = ImageFont.truetype(font_path, size=int(height_px * 0.16))
        except:
            font_order = ImageFont.load_default()
            font_name = ImageFont.load_default()
            font_box = ImageFont.load_default()
    else:
        font_order = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_box = ImageFont.load_default()

    padding_x = int(width_px * 0.04)
    padding_y = int(height_px * 0.04)
    
    usable_height = height_px - padding_y * 2
    section_height = usable_height / 3
    
    # Dòng 1: Mã đơn (màu đen = 0)
    y1 = padding_y + int(section_height * 0.1)
    draw.text((padding_x, y1), order_id, fill=0, font=font_order)
    
    # Dòng 2: Tên khách
    y2 = padding_y + section_height + int(section_height * 0.1)
    draw.text((padding_x, y2), customer, fill=0, font=font_name)
    
    # Dòng 3: Box (căn phải)
    box_text = f"Box: #{box_index} / {box_total}"
    bbox = draw.textbbox((0,0), box_text, font=font_box)
    text_width = bbox[2] - bbox[0]
    x_pos = width_px - text_width - padding_x
    y3 = padding_y + section_height * 2 + int(section_height * 0.1)
    draw.text((x_pos, y3), box_text, fill=0, font=font_box)

    return img

def image_to_escpos_raster(img):
    """
    Chuyển ảnh PIL sang dữ liệu raster ESC/POS
    Định dạng: GS v 0 m xL xH yL yH [dữ liệu]
    """
    # Đảm bảo ảnh ở mode '1' (đen trắng)
    if img.mode != '1':
        img = img.convert('1')
    
    width, height = img.size
    
    # Tạo dữ liệu raster
    raster_data = bytearray()
    pixels = img.load()
    
    # Duyệt từng pixel theo hàng
    for y in range(height):
        byte = 0
        bit = 7
        for x in range(width):
            # Pixel đen = 0, pixel trắng = 1
            if pixels[x, y] == 0:
                byte |= (1 << bit)
            bit -= 1
            if bit < 0:
                raster_data.append(byte)
                byte = 0
                bit = 7
        if bit != 7:
            raster_data.append(byte)
    
    # Tạo lệnh ESC/POS
    xL = width & 0xFF
    xH = (width >> 8) & 0xFF
    yL = height & 0xFF
    yH = (height >> 8) & 0xFF
    
    cmd = bytes([0x1D, 0x76, 0x30, 0x00, xL, xH, yL, yH]) + bytes(raster_data)
    
    return cmd

def get_label_bytes(order_id, customer, box_index, box_total):
    """
    Tạo full lệnh ESC/POS để in label
    """
    # Tạo ảnh
    img = create_label_image(order_id, customer, box_index, box_total)
    
    # Chuyển sang raster
    raster_cmd = image_to_escpos_raster(img)
    
    # Tạo full payload với lệnh ESC/POS
    payload = b''
    payload += b'\x1b\x40'              # Reset máy in
    payload += b'\x1b\x61\x01'          # Căn giữa
    payload += raster_cmd               # Dữ liệu ảnh
    payload += b'\n' * 3                # Xuống dòng
    payload += b'\x1d\x56\x42\x00'      # Cắt giấy (GS V 42)
    
    return payload

# ---------- MÀN HÌNH PHỤ ----------
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        layout.add_widget(Label(text="CÀI ĐẶT", font_size=sp(24), bold=True,
                                size_hint_y=None, height=dp(50), color=COLOR_PRIMARY_DARK))
        layout.add_widget(Label(text="Chọn máy in mặc định, cổng, v.v...\n(Đang phát triển)",
                                font_size=sp(16), color=COLOR_GRAY))
        btn_back = Button(text="Về trang chủ", size_hint_y=None, height=dp(48),
                          background_color=COLOR_GRAY, color=COLOR_WHITE, font_size=sp(16))
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        self.add_widget(layout)

class PrinterManagerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
        layout.add_widget(Label(text="MÁY IN", font_size=sp(24), bold=True,
                                size_hint_y=None, height=dp(50), color=COLOR_PRIMARY_DARK))
        self.device_list = ScrollView()
        container = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        container.bind(minimum_height=container.setter('height'))
        if is_android():
            devices = find_paired_printers_pyjnius()
            if devices:
                for name, addr in devices:
                    lbl = Label(text=f"{name} - {addr}", font_size=sp(16),
                                size_hint_y=None, height=dp(40), color=COLOR_BLACK)
                    container.add_widget(lbl)
            else:
                container.add_widget(Label(text="Chưa có máy in Bluetooth nào được ghép nối",
                                          font_size=sp(16), color=COLOR_GRAY))
        else:
            container.add_widget(Label(text="(Chức năng này chỉ có trên Android)",
                                      font_size=sp(16), color=COLOR_GRAY))
        self.device_list.add_widget(container)
        layout.add_widget(self.device_list)
        btn_back = Button(text="Về trang chủ", size_hint_y=None, height=dp(48),
                          background_color=COLOR_GRAY, color=COLOR_WHITE, font_size=sp(16))
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        layout.add_widget(btn_back)
        self.add_widget(layout)

class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        root.add_widget(Label(text="LỊCH SỬ IN", font_size=sp(24), bold=True,
                              size_hint_y=None, height=dp(50), color=COLOR_PRIMARY_DARK))
        scroll = ScrollView()
        self.container = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.container.bind(minimum_height=self.container.setter('height'))
        scroll.add_widget(self.container)
        root.add_widget(scroll)
        btn_back = Button(text="Về trang chủ", size_hint_y=None, height=dp(48),
                          background_color=COLOR_GRAY, color=COLOR_WHITE, font_size=sp(16))
        btn_back.bind(on_release=lambda *_: setattr(self.manager, "current", "home"))
        root.add_widget(btn_back)
        self.add_widget(root)

    def on_enter(self, *args):
        self.refresh_history()

    def refresh_history(self):
        self.container.clear_widgets()
        data = load_history()
        counts = {}
        for it in data:
            oid = it.get("order_id")
            counts[oid] = counts.get(oid, 0) + 1
        for it in reversed(data):
            oid = it.get("order_id", "?")
            cust = it.get("customer", "?")
            box_qty = it.get("box_qty", 0)
            timestamp = it.get("timestamp", "")
            try:
                date_str = datetime.fromisoformat(timestamp).strftime("%d/%m/%Y %H:%M")
            except:
                date_str = timestamp[:16]
            is_duplicate = counts.get(oid, 0) > 1
            text_color = COLOR_ERROR if is_duplicate else COLOR_BLACK
            text = f"{oid}  |  {cust}  |  {box_qty} box  |  {date_str}"
            row = BoxLayout(size_hint_y=None, height=dp(40), padding=[dp(10),0,dp(10),0])
            lbl = Label(text=text, font_size=sp(16), color=text_color, halign='left', valign='middle')
            lbl.bind(size=lbl.setter('text_size'))
            row.add_widget(lbl)
            self.container.add_widget(row)

# ---------- MÀN HÌNH CHÍNH (HOME) ----------
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.clearcolor = COLOR_WHITE

        main_layout = BoxLayout(orientation='vertical')

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        content = BoxLayout(orientation='vertical', size_hint_y=None, padding=dp(12), spacing=dp(8))
        content.bind(minimum_height=content.setter('height'))

        # Ô nhập liệu
        self.so_input = TextInput(hint_text="SO Num", font_size=sp(18), multiline=False,
                                  size_hint_y=None, height=dp(44),
                                  background_color=(0.95,0.95,0.95,1),
                                  foreground_color=COLOR_BLACK, padding=[dp(10), dp(6)])
        content.add_widget(self.so_input)

        self.name_input = TextInput(hint_text="Name", font_size=sp(18), multiline=False,
                                    size_hint_y=None, height=dp(44),
                                    background_color=(0.95,0.95,0.95,1),
                                    foreground_color=COLOR_BLACK, padding=[dp(10), dp(6)])
        content.add_widget(self.name_input)

        self.box_input = TextInput(hint_text="Box", font_size=sp(18), multiline=False,
                                   input_filter='int', size_hint_y=None, height=dp(44),
                                   background_color=(0.95,0.95,0.95,1),
                                   foreground_color=COLOR_BLACK, padding=[dp(10), dp(6)])
        content.add_widget(self.box_input)

        # Nút IN TEM
        btn_print = Button(text="IN TEM", font_size=sp(20), bold=True,
                           size_hint_y=None, height=dp(50),
                           background_color=COLOR_SUCCESS, color=COLOR_WHITE)
        btn_print.bind(on_release=self.on_print)
        content.add_widget(btn_print)

        # Khu vực Preview
        preview_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(500), spacing=dp(4))
        preview_label = Label(text="Preview tem", font_size=sp(16), color=COLOR_GRAY,
                              size_hint_y=None, height=dp(24))
        preview_box.add_widget(preview_label)

        # Khung ảnh
        img_frame = BoxLayout(size_hint=(1, 0.85), padding=dp(4))
        with img_frame.canvas.before:
            Color(0.92, 0.92, 0.92, 1)
            self.img_bg = RoundedRectangle(pos=img_frame.pos, size=img_frame.size, radius=[6])
        img_frame.bind(pos=self._update_bg, size=self._update_bg)
        self.preview_image = KivyImage(size_hint=(1, 1), keep_ratio=True)
        img_frame.add_widget(self.preview_image)
        preview_box.add_widget(img_frame)

        # Điều hướng preview
        nav_box = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(12))
        self.prev_btn = Button(text="Trước", font_size=sp(14), size_hint_x=0.3,
                               background_color=COLOR_GRAY, color=COLOR_WHITE)
        self.prev_btn.bind(on_release=self.prev_page)
        self.page_label = Label(text="1/1", font_size=sp(14), size_hint_x=0.4,
                                color=COLOR_BLACK)
        self.next_btn = Button(text="Tiếp", font_size=sp(14), size_hint_x=0.3,
                               background_color=COLOR_GRAY, color=COLOR_WHITE)
        self.next_btn.bind(on_release=self.next_page)
        nav_box.add_widget(self.prev_btn)
        nav_box.add_widget(self.page_label)
        nav_box.add_widget(self.next_btn)
        preview_box.add_widget(nav_box)

        content.add_widget(preview_box)

        scroll.add_widget(content)
        main_layout.add_widget(scroll)

        # Thanh điều hướng dưới đáy (4 tab)
        nav_bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=0)
        tabs = ["Nhập liệu", "Lịch sử", "Máy in", "Cài đặt"]
        screen_map = {
            "Nhập liệu": "home",
            "Lịch sử": "history",
            "Máy in": "printer_manager",
            "Cài đặt": "settings"
        }
        for label in tabs:
            btn = Button(text=label, font_size=sp(14),
                         background_color=COLOR_LIGHT_GRAY, color=COLOR_BLACK,
                         halign='center', valign='middle')
            btn.bind(on_release=lambda x, sn=screen_map[label]: self.switch_tab(sn))
            nav_bottom.add_widget(btn)

        main_layout.add_widget(nav_bottom)
        self.add_widget(main_layout)

        # Biến preview
        self.current_order_id = ""
        self.current_customer = ""
        self.total_boxes = 0
        self.current_page = 0
        self.label_images = []

    def _update_bg(self, *args):
        self.img_bg.pos = self.preview_image.parent.pos
        self.img_bg.size = self.preview_image.parent.size

    def switch_tab(self, screen_name):
        if screen_name == "home":
            return
        else:
            self.manager.current = screen_name

    def on_print(self, *args):
        oid = self.so_input.text.strip()
        cust = self.name_input.text.strip()
        box = self.box_input.text.strip()
        if not oid or not cust or not box:
            Popup(title="Thiếu thông tin", content=Label(text="Vui lòng nhập đầy đủ!"),
                  size_hint=(.8,.4)).open()
            return
        try:
            box_n = int(box)
            if box_n <= 0: raise ValueError
        except:
            Popup(title="Lỗi", content=Label(text="Box phải là số nguyên dương"),
                  size_hint=(.8,.4)).open()
            return

        # Tạo ảnh preview
        self.current_order_id = oid
        self.current_customer = cust
        self.total_boxes = box_n
        self.current_page = 0
        self.label_images = []
        for i in range(box_n):
            try:
                img = create_label_image(oid, cust, i+1, box_n)
                self.label_images.append(img)
            except Exception as e:
                Popup(title="Lỗi tạo ảnh", content=Label(text=f"{e}"), size_hint=(.8,.4)).open()
                return
        self.update_preview()

        if has_been_printed(oid):
            popup = Popup(title="Cảnh báo", content=Label(text=f"Đơn {oid} đã in trước đó!"),
                          size_hint=(.8,.4))
            popup.open()

        self.show_print_popup(oid, cust, box_n)

    def show_print_popup(self, oid, cust, box_n):
        root = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(8))
        root.add_widget(Label(text=f"In {box_n} nhãn", font_size=sp(18), bold=True))

        if is_android():
            btn_bt = Button(text="In Bluetooth", size_hint_y=None, height=dp(44),
                            background_color=COLOR_PRIMARY, color=COLOR_WHITE, font_size=sp(16))
            btn_bt.bind(on_release=lambda x: self.do_print_bt(oid, cust, box_n, root))
            root.add_widget(btn_bt)
        else:
            btn_pc = Button(text="Lưu ảnh (mô phỏng)", size_hint_y=None, height=dp(44),
                            background_color=COLOR_SUCCESS, color=COLOR_WHITE, font_size=sp(16))
            btn_pc.bind(on_release=lambda x: self.simulate_print_pc(oid, cust, box_n))
            root.add_widget(btn_pc)

        btn_cancel = Button(text="Hủy", size_hint_y=None, height=dp(44),
                            background_color=COLOR_ERROR, color=COLOR_WHITE, font_size=sp(16))
        btn_cancel.bind(on_release=lambda x: popup.dismiss())
        root.add_widget(btn_cancel)

        popup = Popup(title="Chọn phương thức in", content=root, size_hint=(.9,.6))
        popup.open()

    def do_print_bt(self, oid, cust, box_n, popup_root):
        if not is_android():
            return
        devices = find_paired_printers_pyjnius()
        if not devices:
            Popup(title="Lỗi", content=Label(text="Không tìm thấy máy in Bluetooth"),
                  size_hint=(.8,.4)).open()
            return
        mac = devices[0][1]
        status_label = Label(text="Đang in...", font_size=sp(14), color=COLOR_PRIMARY)
        popup_root.add_widget(status_label)
        Clock.schedule_once(lambda dt: self._print_bt_thread(oid, cust, box_n, mac, status_label, popup_root), 0.1)

    def _print_bt_thread(self, oid, cust, box_n, mac, status_label, popup_root):
        try:
            for i in range(box_n):
                payload = get_label_bytes(oid, cust, i+1, box_n)
                ok, err = print_via_bluetooth_pyjnius(mac, payload)
                if not ok:
                    status_label.text = f"Lỗi: {err}"
                    status_label.color = COLOR_ERROR
                    return
                time.sleep(1)
            add_history_entry(oid, cust, box_n)
            status_label.text = f"In thành công {box_n} nhãn"
            status_label.color = COLOR_SUCCESS
            Clock.schedule_once(lambda dt: self.dismiss_popup(popup_root), 2)
        except Exception as e:
            status_label.text = f"Lỗi: {str(e)}"
            status_label.color = COLOR_ERROR

    def dismiss_popup(self, widget):
        parent = widget.parent
        while parent and not isinstance(parent, Popup):
            parent = parent.parent
        if parent:
            parent.dismiss()

    def simulate_print_pc(self, oid, cust, box_n):
        import subprocess
        import tempfile
        folder = tempfile.mkdtemp()
        files = []
        for i in range(box_n):
            img = create_label_image(oid, cust, i+1, box_n)
            path = os.path.join(folder, f"label_{i+1}.png")
            img.save(path)
            files.append(path)
        add_history_entry(oid, cust, box_n)
        if files:
            if platform == "win":
                os.startfile(files[0])
            elif platform == "darwin":
                subprocess.call(["open", files[0]])
            else:
                subprocess.call(["xdg-open", files[0]])
        Popup(title="Mô phỏng", content=Label(text=f"Đã lưu {box_n} ảnh tại {folder}"),
              size_hint=(.8,.4)).open()

    # ---------- Preview ----------
    def update_preview(self):
        if not self.label_images:
            self.preview_image.texture = None
            self.page_label.text = "0/0"
            return
        total = len(self.label_images)
        if self.current_page >= total:
            self.current_page = total - 1
        if self.current_page < 0:
            self.current_page = 0
        img = self.label_images[self.current_page]
        
        # Chuyển sang RGB để hiển thị
        if img.mode != 'RGB':
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img
            
        width, height = img.size
        data = img_rgb.tobytes()
        texture = Texture.create(size=(width, height), colorfmt='rgb')
        texture.blit_buffer(data, colorfmt='rgb', bufferfmt='ubyte')
        texture.flip_vertical()
        
        self.preview_image.texture = texture
        self.preview_image.keep_ratio = True
        self.preview_image.size_hint = (1, 1)
        
        self.page_label.text = f"{self.current_page+1}/{total}"

    def prev_page(self, *args):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_preview()

    def next_page(self, *args):
        if self.current_page < len(self.label_images)-1:
            self.current_page += 1
            self.update_preview()

    def on_enter(self):
        if self.label_images:
            self.update_preview()

# ---------- ỨNG DỤNG CHÍNH ----------
class OrderPrinterApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(HistoryScreen(name="history"))
        sm.add_widget(PrinterManagerScreen(name="printer_manager"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

if __name__ == "__main__":
    OrderPrinterApp().run()
