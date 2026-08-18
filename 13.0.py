import sys
import subprocess
import os
import io

# ==========================================
#   OTOMATİK KÜTÜPHANE YÜKLEYİCİ
# ==========================================
def bagimliliklari_kontrol_et_ve_yukle():
    gerekli_kutuphaneler = {
        "customtkinter": "customtkinter",
        "pynput": "pynput",
        "PIL": "pillow",
        "cv2": "opencv-python",
        "numpy": "numpy"
    }
    eksikler = []
    for modul_adi, pip_adi in gerekli_kutuphaneler.items():
        try:
            if modul_adi == "cv2": __import__("cv2")
            else: __import__(modul_adi)
        except ImportError:
            eksikler.append(pip_adi)
            
    if eksikler:
        print(f"\n[SİSTEM] Eksik kütüphaneler tespit edildi, otomatik yükleniyor: {eksikler}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *eksikler])
        print("[SİSTEM] Tüm kütüphaneler başarıyla yüklendi!\n")

bagimliliklari_kontrol_et_ve_yukle()

# ==========================================
#         GEREKLİ KÜTÜPHANELER
# ==========================================
import customtkinter as ctk
import threading
import time
import sqlite3
import json
import re
import math
import zipfile
import cv2
import numpy as np
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
from datetime import datetime
from pynput.keyboard import Listener, Key
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- YARDIMCI VERİ ERİŞİM FONKSİYONLARI (JSON MAPPING) ---
def parts_to_dict(parts, idx):
    islem = parts[0]
    step_obj = {
        "step_name": f"Adım {idx}", "action": "Tıkla", "xpath": "", "val": "",
        "count": 1, "direction": "Aşağı", "x": 0, "y": 0, "sys_key": "",
        "exact_match": False, "ref": ""
    }
    def safe_get(index, default): return parts[index] if len(parts) > index else default
    
    if islem == "C":
        step_obj["action"] = "Case"
        step_obj["val"] = safe_get(1, f"Case_{idx}")
    elif islem == "T":
        step_obj["action"] = "Tıkla"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, "")
        step_obj["step_name"] = safe_get(5, f"Tıkla: {step_obj['xpath'].split('/')[-1][:15]}" if step_obj['xpath'] else f"Adım {idx}")
        step_obj["exact_match"] = str(safe_get(6, "False")) == "True"
    elif islem == "M":
        step_obj["action"] = "Metin Yaz"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["val"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, ""), safe_get(5, "")
        step_obj["step_name"] = safe_get(6, f"Yaz: '{step_obj['val']}'")
        step_obj["exact_match"] = str(safe_get(7, "False")) == "True"
    elif islem == "S":
        step_obj["action"] = "Kaydır (Swipe)"
        yon = safe_get(1, "down")
        step_obj["direction"] = {"down": "Aşağı", "up": "Yukarı", "right": "Sağa", "left": "Sola"}.get(yon, yon)
        step_obj["x"], step_obj["y"] = int(safe_get(2, 0)), int(safe_get(3, 0)) 
        step_obj["ref"] = safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Kaydır: {step_obj['direction']}")
        step_obj["count"] = int(safe_get(8, 1))
    elif islem == "K":
        step_obj["action"] = "Sistem Tuşu"
        step_obj["sys_key"] = "Kutuyu Temizle"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, "")
        step_obj["step_name"] = safe_get(5, "İçeriği Sil")
        step_obj["exact_match"] = str(safe_get(6, "False")) == "True"
    elif islem == "SM":
        step_obj["action"] = "Güvenli Metin Yaz (Fiziksel)"
        step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["val"], step_obj["count"], step_obj["ref"] = safe_get(1, ""), int(safe_get(2, 0)), int(safe_get(3, 0)), safe_get(4, ""), int(safe_get(5, 10)), safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Güvenli Yaz: '{step_obj['val']}'")
        step_obj["exact_match"] = str(safe_get(8, "False")) == "True"
    elif islem == "SYS":
        step_obj["action"] = "Sistem Tuşu"
        step_obj["sys_key"], step_obj["xpath"], step_obj["x"], step_obj["y"], step_obj["count"], step_obj["ref"] = safe_get(1, "Geri"), safe_get(2, ""), int(safe_get(3, 0)), int(safe_get(4, 0)), int(safe_get(5, 1)), safe_get(6, "")
        step_obj["step_name"] = safe_get(7, f"Tuş: {step_obj['sys_key']}")
        step_obj["exact_match"] = str(safe_get(8, "False")) == "True"
    elif islem == "W":
        step_obj["action"] = "Bekle (Sleep)"
        step_obj["val"] = safe_get(1, "1")
        step_obj["step_name"] = safe_get(2, f"Bekle: {step_obj['val']} sn")
    elif islem == "B":
        step_obj["action"] = "Başlık / Yorum"
        step_obj["val"] = safe_get(1, "")
        step_obj["step_name"] = safe_get(2, f"--- {step_obj['val']} ---")
        
    return step_obj

def dict_to_parts(step_obj):
    act = step_obj["action"]
    sn = str(step_obj.get("step_name", "")).replace(";", "").replace("|", "")
    xp = str(step_obj.get("xpath", "")).replace(";", "").replace("|", "")
    x, y = str(step_obj.get("x", 0)), str(step_obj.get("y", 0))
    val = str(step_obj.get("val", "")).replace(";", "").replace("|", "")
    ref = str(step_obj.get("ref", ""))
    em = str(step_obj.get("exact_match", False))
    count = str(step_obj.get("count", 1))
    sysk = str(step_obj.get("sys_key", ""))
    
    if act == "Case": return ["C", val]
    elif act == "Tıkla": return ["T", xp, x, y, ref, sn, em]
    elif act == "Metin Yaz": return ["M", xp, x, y, val, ref, sn, em]
    elif act == "Kaydır (Swipe)":
        yon = {"Aşağı": "down", "Yukarı": "up", "Sağa": "right", "Sola": "left"}.get(step_obj.get("direction"), "down")
        return ["S", yon, x, y, x, y, ref, sn, count]
    elif act == "Sistem Tuşu":
        if sysk == "Kutuyu Temizle": return ["K", xp, x, y, ref, sn, em]
        else: return ["SYS", sysk, xp, x, y, count, ref, sn, em]
    elif act == "Güvenli Metin Yaz (Fiziksel)": return ["SM", xp, x, y, val, count, ref, sn, em]
    elif act == "Bekle (Sleep)": return ["W", val, sn]
    elif act == "Başlık / Yorum": return ["B", val, sn]
    return ["T", xp, x, y, ref, sn, em]

class AppicTestStudyosu(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Appic - Test Otomasyon Stüdyosu")
        self.geometry("1150x750")
        
        if getattr(sys, 'frozen', False): self.ana_dizin = os.path.dirname(sys.executable)
        else: self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
            
        self.db_yolu = os.path.join(self.ana_dizin, "appic_test_merkezi.db")
        self.adb_yolu = "adb" 
        
        self.hata_klasoru = os.path.join(self.ana_dizin, "hata_gorselleri")
        os.makedirs(self.hata_klasoru, exist_ok=True) 

        self.log_klasoru = os.path.join(self.ana_dizin, "test_loglari")
        os.makedirs(self.log_klasoru, exist_ok=True)
        
        self.referans_klasoru = os.path.join(self.ana_dizin, "referans_gorseller")
        os.makedirs(self.referans_klasoru, exist_ok=True)

        self.kayit_aktif = False
        self.playback_aktif = False
        self.gecici_dokunuslar = []
        self.klavye_dinleyici = None
        
        self.ui_w = 360
        self.ui_h = 640
        
        self.aktif_ekran_xml = ""
        self.ekran_genislik = 1080
        self.ekran_yukseklik = 1920
        
        self.ide_aktif_adimlar = []
        self.ide_secili_test_id = None
        self.ide_secili_test_adi = ""

        self.cihaz_cozunurlugunu_al()
        self.veritabanini_hazirla()

        # --- ARAYÜZ KURULUMU ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="APPIC", font=ctk.CTkFont(size=24, weight="bold"), text_color="#3498db")
        self.logo_label.pack(pady=20, padx=10)

        self.btn_kayit_ekran = ctk.CTkButton(self.sidebar_frame, text="📸 Yeni Görsel Kayıt", command=self.goster_kayit)
        self.btn_kayit_ekran.pack(pady=10, padx=20)
        
        self.btn_ide_ekran = ctk.CTkButton(self.sidebar_frame, text="🧩 Görsel IDE (Düzenle)", fg_color="#8e44ad", hover_color="#732d91", command=self.goster_ide)
        self.btn_ide_ekran.pack(pady=10, padx=20)

        self.btn_liste_ekran = ctk.CTkButton(self.sidebar_frame, text="📂 Testleri Yönet", command=self.goster_liste)
        self.btn_liste_ekran.pack(pady=10, padx=20)

        self.btn_rapor_ekran = ctk.CTkButton(self.sidebar_frame, text="📊 Test Raporları", fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=self.goster_raporlar)
        self.btn_rapor_ekran.pack(pady=10, padx=20)

        self.btn_hakkinda = ctk.CTkButton(self.sidebar_frame, text="ℹ️ Hakkında", fg_color="#2c3e50", hover_color="#34495e", command=self.goster_hakkinda)
        self.btn_hakkinda.pack(side="bottom", pady=20, padx=20)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.baslangic_ekrani()

    def cihaz_cozunurlugunu_al(self):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            sonuc = subprocess.run([self.adb_yolu, "shell", "wm", "size"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r"size:\s*(\d+)x(\d+)", sonuc.stdout)
            if match:
                self.ekran_genislik = int(match.group(1))
                self.ekran_yukseklik = int(match.group(2))
        except Exception: pass

    def veritabanini_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS case_bazli_testler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, yetkili TEXT, uygulama TEXT, 
            versiyon TEXT, tarih TEXT, telefon_modeli TEXT, aksiyonlar TEXT)""")
        
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN versiyon TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN tarih TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN telefon_modeli TEXT")
        except sqlite3.OperationalError: pass
        
        cursor.execute("""CREATE TABLE IF NOT EXISTS test_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, tarih TEXT,
            toplam_adim INTEGER, basarili_adim INTEGER, genel_durum TEXT, detaylar TEXT)""")
            
        conn.commit()
        conn.close()

    def aktif_uygulama_ve_versiyon_bul(self):
        pkg, ver = "", ""
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            res = subprocess.run([self.adb_yolu, "shell", "dumpsys", "window"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r'mCurrentFocus=Window\{.*\s+([\w\.]+)/', res.stdout)
            if match:
                pkg = match.group(1)
                if pkg and pkg not in ["com.android.systemui", "com.android.launcher"]:
                    res2 = subprocess.run([self.adb_yolu, "shell", "dumpsys", "package", pkg], capture_output=True, text=True, creationflags=c_flags)
                    v_match = re.search(r'versionName=(.*)', res2.stdout)
                    if v_match: ver = v_match.group(1).strip()
        except: pass
        return pkg, ver

    def temizle(self):
        self.kayit_aktif = False
        self.playback_aktif = False
        for widget in self.main_frame.winfo_children(): widget.destroy()

    def baslangic_ekrani(self):
        self.temizle()
        lbl = ctk.CTkLabel(self.main_frame, text="Appic'e Hoş Geldiniz!\n\n1. 'Yeni Görsel Kayıt' ile test oluşturun.\n2. 'Görsel IDE' ile testlerinizi düzenleyin.\n3. 'Testleri Yönet' üzerinden cihazda kıyaslayın ve Script üretin.", font=("Arial", 16))
        lbl.pack(expand=True)

    def goster_hakkinda(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="ℹ️ Hakkında", font=("Arial", 22, "bold")).pack(pady=(40, 10))
        info_frame = ctk.CTkFrame(self.main_frame, fg_color="#2c3e50", corner_radius=15)
        info_frame.pack(pady=20, padx=50, fill="x")
        ctk.CTkLabel(info_frame, text="Appic Test Otomasyon Stüdyosu", font=("Arial", 18, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(info_frame, text="Sürüm 1.0", font=("Arial", 12)).pack(pady=0)
        kisi_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
        kisi_frame.pack(pady=(20, 20))
        ctk.CTkLabel(kisi_frame, text="Mahmut Burak Ceylan", font=("Arial", 16, "bold"), text_color="#f1c40f").pack(pady=5)
        ctk.CTkLabel(kisi_frame, text="Uygulamanın geliştirilmesi, teknik sorunlar ve hata bildirimleri\n(bug raporları) için doğrudan benimle iletişime geçebilirsiniz.", font=("Arial", 14), justify="center").pack(pady=5)

    # ==========================================
    #   1. CANLI INSPECTOR VE KAYIT
    # ==========================================
    def goster_kayit(self):
        self.temizle()
        info_frame = ctk.CTkFrame(self.main_frame, fg_color="#2c3e50")
        info_frame.pack(fill="x", padx=10, pady=(5,10))
        bilgi_metni = ("📌 NASIL KULLANILIR?\n"
                       "• Sol Tık: Tıklama yapar ve objenin XPath'ini otomatik kaydeder.\n"
                       "• Sürükle Bırak: Ekranı kaydırır (Swipe).\n"
                       "• Sağ Tık: O alana metin yazma veya içeriği temizleme menüsünü açar.")
        ctk.CTkLabel(info_frame, text=bilgi_metni, justify="left", font=("Arial", 13, "bold"), text_color="#f1c40f").pack(pady=10, padx=15, anchor="w")

        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=10, pady=5)
        
        pkg, ver = self.aktif_uygulama_ve_versiyon_bul()
        aktif_kullanici = os.getlogin().capitalize() if hasattr(os, 'getlogin') else "Testçi"
        
        self.entry_ad = ctk.CTkEntry(form_frame, placeholder_text="Senaryo Adı", width=180)
        self.entry_ad.grid(row=0, column=0, padx=5, pady=2)
        
        self.entry_yetkili = ctk.CTkEntry(form_frame, width=120)
        self.entry_yetkili.insert(0, aktif_kullanici)
        self.entry_yetkili.grid(row=0, column=1, padx=5, pady=2)
        
        self.entry_uygulama = ctk.CTkEntry(form_frame, width=180)
        self.entry_uygulama.insert(0, pkg if pkg else "Uygulama Paketi")
        self.entry_uygulama.grid(row=0, column=2, padx=5, pady=2)
        
        self.entry_versiyon = ctk.CTkEntry(form_frame, width=100)
        self.entry_versiyon.insert(0, ver if ver else "Versiyon")
        self.entry_versiyon.grid(row=0, column=3, padx=5, pady=2)

        self.entry_telefon = ctk.CTkEntry(form_frame, placeholder_text="Telefon Modeli", width=120)
        self.entry_telefon.grid(row=0, column=4, padx=5, pady=2)
        
        self.buton_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buton_frame.pack(pady=5)
        
        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="▶️ APPIC INSPECTOR BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
        self.btn_baslat.grid(row=0, column=0, padx=5)
        self.btn_bitir = ctk.CTkButton(self.buton_frame, text="🛑 Kaydı Bitir (ESC)", fg_color="red", state="disabled", command=self.kaydi_bitir_islem)
        self.btn_bitir.grid(row=0, column=1, padx=5)

        content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.screen_frame = ctk.CTkFrame(content_frame, width=self.ui_w+20, fg_color="#1e1e1e")
        self.screen_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        self.lbl_ekran = ctk.CTkLabel(self.screen_frame, text="Bağlantı Kuruluyor...", width=self.ui_w, height=self.ui_h, fg_color="#000000")
        self.lbl_ekran.pack(pady=10, padx=10)
        
        self.lbl_ekran.bind("<Button-1>", self.sol_tik_basildi)
        self.lbl_ekran.bind("<ButtonRelease-1>", self.sol_tik_birakildi)
        self.lbl_ekran.bind("<Button-2>", self.sag_tik_menusu)
        self.lbl_ekran.bind("<Button-3>", self.sag_tik_menusu)
        
        self.log_kutusu = ctk.CTkTextbox(content_frame, height=560)
        self.log_kutusu.pack(side="right", fill="both", expand=True, pady=10, padx=10)
        self.log_kutusu.insert("0.0", "Appic Hazır. İşlemleriniz XML XPath olarak kaydedilecektir.\n")

    def ekran_yayini_dongusu(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        temp_gorsel_yolu = os.path.join(self.hata_klasoru, "temp_canli_ekran.png")
        while self.kayit_aktif:
            try:
                subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_canli.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_canli.png", temp_gorsel_yolu], capture_output=True, creationflags=c_flags)
                if os.path.exists(temp_gorsel_yolu):
                    with open(temp_gorsel_yolu, "rb") as f:
                        img_data = f.read()
                    if img_data:
                        img = Image.open(io.BytesIO(img_data))
                        img_resized = img.resize((self.ui_w, self.ui_h))
                        ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(self.ui_w, self.ui_h))
                        self.after(0, lambda resim=ctk_img: self.lbl_ekran.configure(image=resim, text=""))
            except Exception as e:
                self.after(0, lambda err=e: self.log_yaz(f"⚠️ Ekran akış hatası: {err}"))
            time.sleep(0.3)

    def guncel_xml_tek_seferlik_cek(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            subprocess.run([self.adb_yolu, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], capture_output=True, creationflags=c_flags)
            xml_data = subprocess.check_output([self.adb_yolu, "shell", "cat", "/sdcard/window_dump.xml"], creationflags=c_flags).decode('utf-8', errors='ignore')
            self.aktif_ekran_xml = xml_data
        except Exception: pass

    def xpath_hedef_bul(self, gercek_x, gercek_y):
        self.guncel_xml_tek_seferlik_cek()
        if not self.aktif_ekran_xml: return "//android.view.View"
        try:
            root = ET.fromstring(self.aktif_ekran_xml)
            en_kucuk_alan = float('inf')
            nihai_hedef = None
            TOLERANS = 30
            for elem in root.iter():
                bounds = elem.attrib.get('bounds')
                if bounds:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        if (x1 - TOLERANS) <= gercek_x <= (x2 + TOLERANS) and (y1 - TOLERANS) <= gercek_y <= (y2 + TOLERANS):
                            alan = (x2 - x1) * (y2 - y1)
                            if 0 < alan < en_kucuk_alan:
                                en_kucuk_alan = alan
                                nihai_hedef = elem.attrib
            if nihai_hedef:
                if nihai_hedef.get('resource-id'): return f"//*[@resource-id='{nihai_hedef.get('resource-id')}']"
                elif nihai_hedef.get('text'): return f"//*[@text='{nihai_hedef.get('text')}']"
                elif nihai_hedef.get('content-desc'): return f"//*[@content-desc='{nihai_hedef.get('content-desc')}']"
                else: 
                    cls = nihai_hedef.get('class', 'android.view.View')
                    bnd = nihai_hedef.get('bounds')
                    return f"//{cls}[@bounds='{bnd}']"
        except Exception: pass
        return "//android.view.View"

    def referans_ekran_al(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        zaman_ms = int(time.time() * 1000)
        ref_isim = f"ref_{zaman_ms}.png"
        ref_yol = os.path.join(self.referans_klasoru, ref_isim)
        subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_ref.png"], capture_output=True, creationflags=c_flags)
        subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_ref.png", ref_yol], capture_output=True, creationflags=c_flags)
        return ref_isim

    def sol_tik_basildi(self, event):
        if not self.kayit_aktif: return
        self.bas_x = event.x
        self.bas_y = event.y

    def sol_tik_birakildi(self, event):
        if not self.kayit_aktif: return
        bitis_x = event.x
        bitis_y = event.y
        mesafe = math.hypot(bitis_x - getattr(self, 'bas_x', 0), bitis_y - getattr(self, 'bas_y', 0))
        
        gercek_x = int((bitis_x / self.ui_w) * self.ekran_genislik)
        gercek_y = int((bitis_y / self.ui_h) * self.ekran_yukseklik)
        gercek_bas_x = int((getattr(self, 'bas_x', 0) / self.ui_w) * self.ekran_genislik)
        gercek_bas_y = int((getattr(self, 'bas_y', 0) / self.ui_h) * self.ekran_yukseklik)
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        if mesafe < 30:
            self.after(0, lambda: self.log_yaz("🔍 Obje taranıyor..."))
            def islem_yap():
                xpath = self.xpath_hedef_bul(gercek_x, gercek_y)
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                # T;;;xpath;;;x;;;y;;;ref;;;step_name;;;exact_match
                sn = f"Tıkla: {xpath.split('/')[-1][:15]}" if xpath else "Adım"
                em = "True" if xpath.startswith("//") else "False"
                self.gecici_dokunuslar.append(f"T;;;{xpath};;;{gercek_x};;;{gercek_y};;;{ref_isim};;;{sn};;;{em}") 
                self.after(0, lambda: self.log_yaz(f"🎯 Tıkla (XPath): {xpath}"))
            threading.Thread(target=islem_yap).start()
        else:
            fark_x = bitis_x - getattr(self, 'bas_x', 0)
            fark_y = bitis_y - getattr(self, 'bas_y', 0)
            yon = "down" if fark_y > 0 else "up"
            if abs(fark_x) > abs(fark_y): yon = "right" if fark_x > 0 else "left"
            def kaydir_yap():
                subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(gercek_bas_x), str(gercek_bas_y), str(gercek_x), str(gercek_y), "400"], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                yon_tr = {"down": "Aşağı", "up": "Yukarı", "right": "Sağa", "left": "Sola"}.get(yon, "Aşağı")
                # S;;;yon;;;x;;;y;;;x;;;y;;;ref;;;step_name;;;count
                self.gecici_dokunuslar.append(f"S;;;{yon};;;{gercek_bas_x};;;{gercek_bas_y};;;{gercek_x};;;{gercek_y};;;{ref_isim};;;Kaydır: {yon_tr};;;1")
                self.after(0, lambda: self.log_yaz(f"👆 Kaydırma Eklendi: {yon_tr}"))
            threading.Thread(target=kaydir_yap).start()

    def sag_tik_menusu(self, event):
        if not self.kayit_aktif: return
        gercek_x = int((event.x / self.ui_w) * self.ekran_genislik)
        gercek_y = int((event.y / self.ui_h) * self.ekran_yukseklik)
        self.after(0, lambda: self.log_yaz("🔍 Metin kutusu taranıyor..."))
        def menuyu_hazirla():
            xpath = self.xpath_hedef_bul(gercek_x, gercek_y)
            self.after(0, lambda: self._popup_ac(gercek_x, gercek_y, xpath))
        threading.Thread(target=menuyu_hazirla).start()

    def _popup_ac(self, gercek_x, gercek_y, xpath):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        popup = ctk.CTkToplevel(self)
        popup.title("Kutu İşlemleri")
        popup.geometry("300x200")
        popup.attributes("-topmost", True)
        veri_girisi = ctk.CTkEntry(popup, placeholder_text="Yazılacak metin...", width=200)
        veri_girisi.pack(pady=20)
        
        def yaz():
            val = veri_girisi.get().replace(";", "").replace("|", "")
            if not val: return
            popup.destroy()
            def cihaza_yaz():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                em = "True" if xpath.startswith("//") else "False"
                # M;;;xpath;;;x;;;y;;;val;;;ref;;;step_name;;;exact_match
                self.gecici_dokunuslar.append(f"M;;;{xpath};;;{gercek_x};;;{gercek_y};;;{val};;;{ref_isim};;;Yaz: '{val}';;;{em}")
                self.after(0, lambda: self.log_yaz(f"✍️ Metin Eklendi: '{val}'"))
            threading.Thread(target=cihaza_yaz).start()
            
        def sil():
            popup.destroy()
            def cihazdan_sil():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                em = "True" if xpath.startswith("//") else "False"
                # K;;;xpath;;;x;;;y;;;ref;;;step_name;;;exact_match
                self.gecici_dokunuslar.append(f"K;;;{xpath};;;{gercek_x};;;{gercek_y};;;{ref_isim};;;İçeriği Sil;;;{em}")
                self.after(0, lambda: self.log_yaz(f"🧹 Silme İşlemi Eklendi"))
            threading.Thread(target=cihazdan_sil).start()

        ctk.CTkButton(popup, text="✍️ Metin Yaz", fg_color="green", command=yaz).pack(pady=5)
        ctk.CTkButton(popup, text="🧹 İçeriği Sil", fg_color="red", command=sil).pack(pady=5)

    def kaydi_tetikle(self):
        self.guncel_test_adi = self.entry_ad.get()
        if not self.guncel_test_adi:
            self.log_yaz("\n❌ Lütfen bir Senaryo Adı girin!")
            return

        self.guncel_yetkili = self.entry_yetkili.get()
        self.guncel_uygulama = self.entry_uygulama.get()
        self.guncel_versiyon = self.entry_versiyon.get()
        self.guncel_telefon = self.entry_telefon.get()
        self.guncel_tarih = datetime.now().strftime("%d-%m-%Y %H:%M")

        self.cihaz_cozunurlugunu_al()
        self.btn_baslat.configure(state="disabled")
        self.btn_bitir.configure(state="normal")
        
        self.kayit_aktif = True
        self.gecici_dokunuslar = []
        
        self.log_yaz(f"\n🚀 '{self.guncel_test_adi}' Appic Devrede!\nEkrana tıklayarak adımları kaydedebilirsiniz.")
        threading.Thread(target=self.ekran_yayini_dongusu, daemon=True).start()
        if self.klavye_dinleyici: self.klavye_dinleyici.stop()
        self.klavye_dinleyici = Listener(on_press=self.klavye_dinle)
        self.klavye_dinleyici.start()

    def klavye_dinle(self, key):
        if not self.kayit_aktif: return 
        if key == Key.esc: self.after(0, self.kaydi_bitir_islem)

    def kaydi_bitir_islem(self):
        self.kayit_aktif = False
        if self.klavye_dinleyici:
            self.klavye_dinleyici.stop()
            self.klavye_dinleyici = None
            
        if self.gecici_dokunuslar:
            kopya = list(self.gecici_dokunuslar)
            aksiyon_str = "|".join(kopya)
            
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO case_bazli_testler 
                              (ana_test_adi, yetkili, uygulama, versiyon, tarih, telefon_modeli, aksiyonlar) 
                              VALUES (?,?,?,?,?,?,?)""", 
                           (self.guncel_test_adi, self.guncel_yetkili, self.guncel_uygulama, self.guncel_versiyon, self.guncel_tarih, self.guncel_telefon, aksiyon_str))
            conn.commit()
            conn.close()
            
        try:
            self.btn_baslat.configure(state="normal")
            self.btn_bitir.configure(state="disabled")
            self.log_yaz("\n🎉 KAYIT TAMAMLANDI! Görsel IDE'den düzenleyebilir veya Yönet sekmesinden dışa aktarabilirsiniz.\n")
        except Exception: pass

    def log_yaz(self, mesaj):
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")

    # ==========================================
    #   2. GÖRSEL IDE (DÜZENLEYİCİ) KAPSAMLI
    # ==========================================
    def goster_ide(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="🧩 Görsel IDE (Test Düzenleyici)", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(fill="x", padx=10, pady=5)
        
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("SELECT id, ana_test_adi FROM case_bazli_testler ORDER BY id DESC")
        testler = cursor.fetchall()
        conn.close()
        
        self.test_sozlugu = {f"{t[1]} (ID:{t[0]})": t[0] for t in testler}
        test_isimleri = list(self.test_sozlugu.keys())
        
        if not test_isimleri:
            ctk.CTkLabel(ust_frame, text="Henüz kaydedilmiş bir test yok. Lütfen önce kayıt yapın.").pack()
            return

        self.ide_secili_test_id = None
        self.ide_aktif_adimlar = []
            
        self.combo_test = ctk.CTkComboBox(ust_frame, values=test_isimleri, width=250, command=self.ide_test_yukle)
        self.combo_test.pack(side="left", padx=10)
        
        ctk.CTkButton(ust_frame, text="➕ Yeni Case Ekle", width=120, fg_color="#8e44ad", hover_color="#732d91", command=self.ide_case_ekle_popup).pack(side="left", padx=5)
        ctk.CTkButton(ust_frame, text="➕ Blok Ekle", width=100, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=self.ide_blok_ekle_popup).pack(side="left", padx=5)
        
        ctk.CTkButton(ust_frame, text="📤 Kaydet & Dışa Aktar", fg_color="#2980b9", hover_color="#1f618d", command=self.ide_kaydet_ve_disa_aktar).pack(side="right", padx=5)
        ctk.CTkButton(ust_frame, text="💾 Sadece Kaydet", fg_color="green", hover_color="darkgreen", command=self.ide_kaydet).pack(side="right", padx=5)
        
        self.ide_liste_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.ide_liste_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.ide_test_yukle(test_isimleri[0])

    def ide_test_yukle(self, secim):
        test_id = self.test_sozlugu[secim]
        self.ide_secili_test_id = test_id
        self.ide_secili_test_adi = secim.split(" (ID:")[0]
        
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("SELECT aksiyonlar FROM case_bazli_testler WHERE id = ?", (test_id,))
        satir = cursor.fetchone()
        conn.close()
        
        self.ide_aktif_adimlar = []
        if satir and satir[0]:
            dokunuslar = [n for n in satir[0].split("|") if n]
            for idx, d in enumerate(dokunuslar):
                parts = d.split(";;;")
                self.ide_aktif_adimlar.append(parts_to_dict(parts, idx+1))
        self.ide_arayuzu_ciz()

    def ide_case_ekle_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Yeni Case Ekle")
        popup.geometry("300x150")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Case Adı:", font=("Arial", 12, "bold")).pack(pady=(15,5))
        entry_ad = ctk.CTkEntry(popup, width=200)
        entry_ad.pack(pady=5)
        
        def ekle():
            ad = entry_ad.get().replace(";", "").replace("|", "")
            if ad:
                self.ide_aktif_adimlar.append({"action": "Case", "val": ad})
                self.ide_arayuzu_ciz()
            popup.destroy()
            
        ctk.CTkButton(popup, text="Ekle", fg_color="green", command=ekle).pack(pady=10)

    def ide_blok_ekle_popup(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Yeni Blok Ekle")
        popup.geometry("400x500")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="İşlem Tipi:", font=("Arial", 12, "bold")).pack(pady=(10,0))
        combo_act = ctk.CTkComboBox(popup, values=["Tıkla", "Metin Yaz", "Güvenli Metin Yaz (Fiziksel)", "Kaydır (Swipe)", "Sistem Tuşu", "Bekle (Sleep)", "Başlık / Yorum"], width=300)
        combo_act.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Adım İsmi:", font=("Arial", 12)).pack()
        e_name = ctk.CTkEntry(popup, width=300)
        e_name.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Hedef XPath / Text Değeri:", font=("Arial", 12)).pack()
        e_xp = ctk.CTkEntry(popup, width=300)
        e_xp.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Değer / Yön / Saniye / Tuş:", font=("Arial", 12)).pack()
        e_val = ctk.CTkEntry(popup, width=300)
        e_val.pack(pady=5)
        
        ctk.CTkLabel(popup, text="Tekrar (Count):", font=("Arial", 12)).pack()
        e_count = ctk.CTkEntry(popup, width=100)
        e_count.insert(0, "1")
        e_count.pack(pady=5)
        
        chk_exact = ctk.CTkCheckBox(popup, text="Kesin Eşleşme (Exact Match)")
        chk_exact.pack(pady=10)
        
        def ekle():
            act = combo_act.get()
            step_obj = {
                "step_name": e_name.get().replace(";", ""),
                "action": act,
                "xpath": e_xp.get().replace(";", ""),
                "val": e_val.get().replace(";", ""),
                "count": int(e_count.get()) if e_count.get().isdigit() else 1,
                "direction": e_val.get() if act == "Kaydır (Swipe)" else "Aşağı",
                "sys_key": e_val.get() if act == "Sistem Tuşu" else "",
                "x": 0, "y": 0, "ref": "",
                "exact_match": chk_exact.get() == 1
            }
            if not step_obj["step_name"]: step_obj["step_name"] = act
            self.ide_aktif_adimlar.append(step_obj)
            self.ide_arayuzu_ciz()
            popup.destroy()
            
        ctk.CTkButton(popup, text="Ekle", fg_color="green", command=ekle).pack(pady=15)

    def ide_arayuzu_ciz(self):
        for widget in self.ide_liste_frame.winfo_children(): widget.destroy()
        if not self.ide_aktif_adimlar: return

        for idx, step in enumerate(self.ide_aktif_adimlar):
            act = step["action"]
            s_name = step.get("step_name", f"Adım {idx}")
            
            renk, ikon, detay = "#8A9BAC", "⚙️", ""
            
            if act == "Case":
                renk, ikon = "#FF6680", "⚙️ CASE:"
                s_name = f"{ikon} {step.get('val', '')}"
                
                satir = ctk.CTkFrame(self.ide_liste_frame, fg_color=renk, corner_radius=10)
                satir.pack(fill="x", pady=(15, 2), padx=5)
                ctk.CTkLabel(satir, text=s_name, font=("Arial", 16, "bold"), text_color="white").pack(side="left", padx=15, pady=10)
                ctk.CTkButton(satir, text="🗑️", width=40, fg_color="#c0392b", hover_color="#962d22", command=lambda i=idx: self.ide_adim_sil(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="✏️", width=40, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=lambda i=idx: self.ide_adim_duzenle(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="⬇️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_adim_tasi(i, 1), state="disabled" if idx == len(self.ide_aktif_adimlar)-1 else "normal").pack(side="right", padx=2, pady=10)
                ctk.CTkButton(satir, text="⬆️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_adim_tasi(i, -1), state="disabled" if idx == 0 else "normal").pack(side="right", padx=2, pady=10)
                continue
                
            elif act == "Tıkla": 
                renk, ikon = "#4C97FF", "👆"
                detay = f"[{step.get('xpath')[:20]}]" if step.get('xpath') else f"Koor({step.get('x')},{step.get('y')})"
            elif act == "Metin Yaz": 
                renk, ikon = "#59C059", "⌨️"
                detay = f"Yaz: '{step.get('val')}'"
            elif act == "Güvenli Metin Yaz (Fiziksel)": 
                renk, ikon = "#D35400", "🤖"
                detay = f"Güv. Yaz: '{step.get('val')}'"
            elif act == "Kaydır (Swipe)": 
                renk, ikon = "#FFBF00", "↔️"
                detay = f"Yön: {step.get('direction')}"
            elif act == "Bekle (Sleep)": 
                renk, ikon = "#9966FF", "⏳"
                detay = f"Süre: {step.get('val')}sn"
            elif act == "Başlık / Yorum": 
                renk, ikon = "#34495E", "📝"
                detay = step.get("val")
            elif act == "Sistem Tuşu": 
                if step.get("sys_key") == "Kutuyu Temizle": renk, ikon, detay = "#E74C3C", "🧹", "İçeriği Sil"
                elif step.get("sys_key") == "Fiziksel Sil (Backspace)": renk, ikon, detay = "#E74C3C", "🔙", "Fiziksel Sil"
                else: renk, ikon, detay = "#8A9BAC", "📱", f"Tuş: {step.get('sys_key')}"

            if step.get("exact_match"): detay += " 🔒 Kesin"

            satir = ctk.CTkFrame(self.ide_liste_frame, fg_color=renk, corner_radius=8)
            satir.pack(fill="x", pady=2, padx=20)
            
            ctk.CTkLabel(satir, text=f"{ikon} {s_name} | {detay}", font=("Arial", 14, "bold"), text_color="white").pack(side="left", padx=15, pady=10)
            ctk.CTkButton(satir, text="🗑️", width=40, fg_color="#c0392b", hover_color="#962d22", command=lambda i=idx: self.ide_adim_sil(i)).pack(side="right", padx=5, pady=10)
            ctk.CTkButton(satir, text="✏️ Düzenle", width=100, fg_color="#f39c12", text_color="black", hover_color="#d68b49", command=lambda i=idx: self.ide_adim_duzenle(i)).pack(side="right", padx=5, pady=10)
            ctk.CTkButton(satir, text="⬇️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_adim_tasi(i, 1), state="disabled" if idx == len(self.ide_aktif_adimlar)-1 else "normal").pack(side="right", padx=2, pady=10)
            ctk.CTkButton(satir, text="⬆️", width=40, fg_color="#34495e", command=lambda i=idx: self.ide_adim_tasi(i, -1), state="disabled" if idx == 0 else "normal").pack(side="right", padx=2, pady=10)

    def ide_adim_tasi(self, idx, yon):
        yeni_idx = idx + yon
        self.ide_aktif_adimlar[idx], self.ide_aktif_adimlar[yeni_idx] = self.ide_aktif_adimlar[yeni_idx], self.ide_aktif_adimlar[idx]
        self.ide_arayuzu_ciz()

    def ide_adim_sil(self, idx):
        self.ide_aktif_adimlar.pop(idx)
        self.ide_arayuzu_ciz()

    def ide_adim_duzenle(self, idx):
        step = self.ide_aktif_adimlar[idx]
        act = step["action"]
        
        popup = ctk.CTkToplevel(self)
        popup.title(f"Düzenle: {act}")
        popup.geometry("400x500")
        popup.attributes("-topmost", True)
        
        if act == "Case":
            ctk.CTkLabel(popup, text="Case Adı:").pack(pady=5)
            e_name = ctk.CTkEntry(popup, width=300)
            e_name.insert(0, step.get("val", ""))
            e_name.pack(pady=5)
            def kaydet():
                step["val"] = e_name.get()
                self.ide_aktif_adimlar[idx] = step
                popup.destroy()
                self.ide_arayuzu_ciz()
            ctk.CTkButton(popup, text="💾 Güncelle", fg_color="green", command=kaydet).pack(pady=20)
            return

        ctk.CTkLabel(popup, text="Adım Adı:").pack(pady=5)
        e_name = ctk.CTkEntry(popup, width=300)
        e_name.insert(0, step.get("step_name", ""))
        e_name.pack(pady=5)
        
        e_xp, e_val, e_count, chk_em = None, None, None, None
        
        if act in ["Tıkla", "Metin Yaz", "Güvenli Metin Yaz (Fiziksel)", "Sistem Tuşu"]:
            ctk.CTkLabel(popup, text="XPath / ID:").pack(pady=5)
            e_xp = ctk.CTkEntry(popup, width=300)
            e_xp.insert(0, step.get("xpath", ""))
            e_xp.pack(pady=5)
            
            chk_em = ctk.CTkCheckBox(popup, text="Kesin Eşleşme (Exact Match)")
            if step.get("exact_match"): chk_em.select()
            chk_em.pack(pady=5)
            
        if act in ["Metin Yaz", "Güvenli Metin Yaz (Fiziksel)", "Bekle (Sleep)", "Başlık / Yorum", "Kaydır (Swipe)", "Sistem Tuşu"]:
            l_text = "Değer / Saniye:"
            if act == "Kaydır (Swipe)": l_text = "Yön (Aşağı, Yukarı, Sağa, Sola):"
            elif act == "Sistem Tuşu": l_text = "Tuş (Geri, Ana Sayfa, Kutuyu Temizle):"
            
            ctk.CTkLabel(popup, text=l_text).pack(pady=5)
            e_val = ctk.CTkEntry(popup, width=300)
            v_ins = step.get("val", "")
            if act == "Kaydır (Swipe)": v_ins = step.get("direction", "Aşağı")
            elif act == "Sistem Tuşu": v_ins = step.get("sys_key", "")
            e_val.insert(0, v_ins)
            e_val.pack(pady=5)
            
        if act in ["Güvenli Metin Yaz (Fiziksel)", "Kaydır (Swipe)"] or (act == "Sistem Tuşu" and step.get("sys_key") == "Fiziksel Sil (Backspace)"):
            ctk.CTkLabel(popup, text="Tekrar Sayısı (Count):").pack(pady=5)
            e_count = ctk.CTkEntry(popup, width=100)
            e_count.insert(0, str(step.get("count", 1)))
            e_count.pack(pady=5)
            
        def kaydet():
            step["step_name"] = e_name.get().replace(";", "").replace("|", "")
            if e_xp: step["xpath"] = e_xp.get().replace(";", "")
            if e_val:
                v = e_val.get().replace(";", "")
                if act == "Kaydır (Swipe)": step["direction"] = v
                elif act == "Sistem Tuşu": step["sys_key"] = v
                else: step["val"] = v
            if e_count: step["count"] = int(e_count.get()) if e_count.get().isdigit() else 1
            if chk_em: step["exact_match"] = chk_em.get() == 1
            
            self.ide_aktif_adimlar[idx] = step
            popup.destroy()
            self.ide_arayuzu_ciz()
            
        ctk.CTkButton(popup, text="💾 Güncelle", fg_color="green", command=kaydet).pack(pady=20)

    def ide_kaydet(self, sessiz=False):
        if not self.ide_secili_test_id: return
        # Tüm Dict objelerini veritabanına özel ;;; stringlerine çeviriyoruz
        yeni_aksiyonlar = "|".join([";;;".join(dict_to_parts(s)) for s in self.ide_aktif_adimlar])
        conn = sqlite3.connect(self.db_yolu)
        conn.cursor().execute("UPDATE case_bazli_testler SET aksiyonlar = ? WHERE id = ?", (yeni_aksiyonlar, self.ide_secili_test_id))
        conn.commit()
        conn.close()
        if not sessiz: messagebox.showinfo("Başarılı", "Test senaryosu başarıyla güncellendi!")

    def ide_kaydet_ve_disa_aktar(self):
        if not self.ide_secili_test_id: return
        self.ide_kaydet(sessiz=True)
        self.testi_disa_aktar(self.ide_secili_test_id, self.ide_secili_test_adi)

    # ==========================================
    #   3. YÖNETİM VE LOKAL OYNATMA (GÖRSEL KIYASLAMA)
    # ==========================================
    def goster_liste(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📂 Kayıtlı Testleri Yönet", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)
        self.arama_entry = ctk.CTkEntry(ust_frame, placeholder_text="Test Adına Göre Ara...", width=400)
        self.arama_entry.pack(side="left", padx=10)
        self.arama_entry.bind("<KeyRelease>", self.listeyi_guncelle)

        self.test_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=450)
        self.test_listesi.pack(pady=10, padx=10, fill="both", expand=True)
        self.listeyi_guncelle()

    def listeyi_guncelle(self, event=None):
        for widget in self.test_listesi.winfo_children(): widget.destroy()
        if not os.path.exists(self.db_yolu): return
        arama = self.arama_entry.get().strip()
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT id, ana_test_adi, yetkili, uygulama, versiyon, tarih FROM case_bazli_testler WHERE ana_test_adi LIKE ? ORDER BY id DESC", (f'%{arama}%',))
            kayitlar = cursor.fetchall()
            conn.close()

            for t_id, test_adi, yetk, uyg, ver, tarih in kayitlar:
                satir = ctk.CTkFrame(self.test_listesi, fg_color="#2b2b2b")
                satir.pack(fill="x", pady=5, padx=5)
                
                bilgi_metni = f"📂 {test_adi}  |  👤 {yetk}  |  📱 {uyg} (v{ver})  |  🕒 {tarih}"
                ctk.CTkLabel(satir, text=bilgi_metni, font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                
                ctk.CTkButton(satir, text="🗑️ Sil", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda i=t_id: self.testi_sil(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="▶️ Cihazda Oynat & Kıyasla", width=160, fg_color="green", command=lambda i=t_id, a=test_adi: self.testi_oynat(i, a)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="📤 IDE Script Çıkar", width=140, fg_color="#2980b9", command=lambda i=t_id, a=test_adi: self.testi_disa_aktar(i, a)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def testi_sil(self, t_id):
        cevap = messagebox.askyesno("Onay", "Bu testi silmek istediğinize emin misiniz?")
        if cevap:
            conn = sqlite3.connect(self.db_yolu)
            conn.cursor().execute("DELETE FROM case_bazli_testler WHERE id = ?", (t_id,))
            conn.commit()
            conn.close()
            self.listeyi_guncelle()

    def oynatmayi_durdur(self):
        self.playback_aktif = False

    def goruntu_kiyasla_ve_isaretle(self, ref_yol, check_yol):
        try:
            img_ref_color = cv2.imdecode(np.fromfile(ref_yol, dtype=np.uint8), cv2.IMREAD_COLOR)
            img_check_color = cv2.imdecode(np.fromfile(check_yol, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img_ref_color is None or img_check_color is None: return 0.0, check_yol
            img1 = cv2.cvtColor(img_ref_color, cv2.COLOR_BGR2GRAY)
            img2 = cv2.cvtColor(img_check_color, cv2.COLOR_BGR2GRAY)
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
                img_check_color = cv2.resize(img_check_color, (img1.shape[1], img1.shape[0]))
            fark = cv2.absdiff(img1, img2)
            _, thresh = cv2.threshold(fark, 30, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                if cv2.contourArea(c) > 100: 
                    x, y, w, h = cv2.boundingRect(c)
                    cv2.rectangle(img_check_color, (x, y), (x+w, y+h), (0, 0, 255), 3) 
            farkli_piksel_sayisi = cv2.countNonZero(thresh)
            toplam_piksel = img1.shape[0] * img1.shape[1]
            benzerlik = 1.0 - (farkli_piksel_sayisi / toplam_piksel)
            fark_yol = os.path.join(self.hata_klasoru, "temp_diff.png")
            is_success, im_buf_arr = cv2.imencode(".png", img_check_color)
            if is_success: im_buf_arr.tofile(fark_yol)
            else: cv2.imwrite(fark_yol, img_check_color)
            return benzerlik, fark_yol
        except Exception: return 0.0, check_yol

    def ui_gorsel_guncelle(self, ref_yol, check_yol, skor_yuzde):
        try:
            img_ref = Image.open(ref_yol)
            img_check = Image.open(check_yol)
            oran = 480 / img_ref.height
            yeni_boyut = (int(img_ref.width * oran), 480)
            ctk_ref = ctk.CTkImage(light_image=img_ref, size=yeni_boyut)
            ctk_check = ctk.CTkImage(light_image=img_check, size=yeni_boyut)
            self.lbl_img_ref.configure(image=ctk_ref, text="")
            self.lbl_img_check.configure(image=ctk_check, text="")
            renk = "lightgreen" if skor_yuzde >= 85 else "#ff4d4d"
            self.lbl_benzerlik.configure(text=f"Analiz Edilen Benzerlik: %{skor_yuzde}", text_color=renk)
        except Exception: pass

    def testi_oynat(self, t_id, test_adi):
        self.playback_aktif = True
        self.oynatma_penceresi = ctk.CTkToplevel(self)
        self.oynatma_penceresi.title(f"Test Yürütülüyor: {test_adi}")
        self.oynatma_penceresi.geometry("1100x650")
        self.oynatma_penceresi.attributes("-topmost", True)
        
        log_frame = ctk.CTkFrame(self.oynatma_penceresi, width=350)
        log_frame.pack(side="left", fill="y", padx=10, pady=10)
        btn_durdur = ctk.CTkButton(log_frame, text="🛑 ACİL DURDUR", fg_color="red", command=self.oynatmayi_durdur)
        btn_durdur.pack(pady=10)
        log_kutusu = ctk.CTkTextbox(log_frame, width=350, font=("Consolas", 12))
        log_kutusu.pack(fill="both", expand=True, padx=5, pady=5)
        log_kutusu.insert("end", f"🚀 {test_adi} başlatılıyor...\n\n")

        img_frame = ctk.CTkFrame(self.oynatma_penceresi)
        img_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        title_frame = ctk.CTkFrame(img_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(title_frame, text="Beklenen (Referans)", font=("Arial", 14, "bold")).pack(side="left", expand=True)
        ctk.CTkLabel(title_frame, text="Anlık Cihaz (Hatalar İşaretli)", font=("Arial", 14, "bold")).pack(side="right", expand=True)
        
        images_container = ctk.CTkFrame(img_frame, fg_color="transparent")
        images_container.pack(fill="both", expand=True, pady=5)
        self.lbl_img_ref = ctk.CTkLabel(images_container, text="⏳ Test Bekleniyor...", width=300, height=480, fg_color="#2b2b2b")
        self.lbl_img_ref.pack(side="left", expand=True, padx=10)
        self.lbl_img_check = ctk.CTkLabel(images_container, text="⏳ Test Bekleniyor...", width=300, height=480, fg_color="#2b2b2b")
        self.lbl_img_check.pack(side="right", expand=True, padx=10)
        self.lbl_benzerlik = ctk.CTkLabel(img_frame, text="Benzerlik: Analiz Bekleniyor...", font=("Arial", 18, "bold"))
        self.lbl_benzerlik.pack(pady=10)

        def oynat_dongusu():
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar FROM case_bazli_testler WHERE id = ?", (t_id,))
            aksiyon_verisi = cursor.fetchone()
            conn.close()
            
            if not aksiyon_verisi or not aksiyon_verisi[0]:
                self.after(0, lambda: log_kutusu.insert("end", "⚠️ Kayıtlı adım bulunamadı."))
                return

            dokunuslar = [n for n in aksiyon_verisi[0].split("|") if n]
            
            gercek_adimlar = [d for d in dokunuslar if not d.startswith("C;;;") and not d.startswith("B;;;")]
            basarili_adim = 0
            toplam_adim = len(gercek_adimlar)
            adim_raporlari = []
            dongu_iptal = False
            
            log_dosya_adi = f"log_{test_adi.replace(' ', '_')}_{int(time.time())}.txt"
            log_yolu = os.path.join(self.log_klasoru, log_dosya_adi)
            subprocess.run([self.adb_yolu, "logcat", "-c"], creationflags=c_flags)
            log_dosyasi = open(log_yolu, "w", encoding="utf-8")
            log_proc = subprocess.Popen([self.adb_yolu, "logcat", "-v", "threadtime"], stdout=log_dosyasi, creationflags=c_flags)

            islem_index = 0
            for idx, nokta in enumerate(dokunuslar):
                if not self.playback_aktif:
                    self.after(0, lambda: log_kutusu.insert("end", "\n🛑 TEST KULLANICI TARAFINDAN İPTAL EDİLDİ!"))
                    dongu_iptal = True
                    break

                parts = nokta.split(";;;")
                step_obj = parts_to_dict(parts, idx+1)
                act = step_obj["action"]
                
                if act == "Case":
                    self.after(0, lambda p=step_obj["val"]: log_kutusu.insert("end", f"\n--- CASE: {p} ---\n"))
                    continue
                elif act == "Başlık / Yorum":
                    self.after(0, lambda p=step_obj["val"]: log_kutusu.insert("end", f"\n📝 {p}\n"))
                    continue
                    
                islem_index += 1
                ref_isim = step_obj.get("ref", "")
                
                if act == "Tıkla":
                    x, y = step_obj["x"], step_obj["y"]
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                elif act == "Metin Yaz":
                    x, y, val = step_obj["x"], step_obj["y"], step_obj["val"]
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                elif act == "Güvenli Metin Yaz (Fiziksel)":
                    x, y, val, count = step_obj["x"], step_obj["y"], step_obj["val"], step_obj["count"]
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                    for _ in range(count): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                elif act == "Kaydır (Swipe)":
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    for _ in range(step_obj.get("count", 1)):
                        # Lokal oynatmada 0,0 merkez ise ekranın ortasından kaydır varsayımı yapıyoruz.
                        b_x, b_y, s_x, s_y = self.ekran_genislik//2, self.ekran_yukseklik//2, self.ekran_genislik//2, self.ekran_yukseklik//2
                        off_x, off_y = self.ekran_genislik//4, self.ekran_yukseklik//4
                        yon = step_obj["direction"]
                        if yon == "Aşağı": b_y += off_y; s_y -= off_y
                        elif yon == "Yukarı": b_y -= off_y; s_y += off_y
                        elif yon == "Sağa": b_x -= off_x; s_x += off_x
                        elif yon == "Sola": b_x += off_x; s_x -= off_x
                        subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(b_x), str(b_y), str(s_x), str(s_y), "400"], creationflags=c_flags)
                        time.sleep(0.5)
                elif act == "Sistem Tuşu":
                    sysk = step_obj["sys_key"]
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    if sysk == "Geri": subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "4"], creationflags=c_flags)
                    elif sysk == "Ana Sayfa": subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "3"], creationflags=c_flags)
                    elif sysk == "Arka Plan": subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "187"], creationflags=c_flags)
                    elif sysk == "Klavyeyi Kapat": subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "111"], creationflags=c_flags)
                    elif sysk == "Kutuyu Temizle":
                        subprocess.run([self.adb_yolu, "shell", "input", "tap", str(step_obj["x"]), str(step_obj["y"])], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                        for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                    elif sysk == "Fiziksel Sil (Backspace)":
                        subprocess.run([self.adb_yolu, "shell", "input", "tap", str(step_obj["x"]), str(step_obj["y"])], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                        for _ in range(step_obj.get("count", 1)): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                elif act == "Bekle (Sleep)":
                    sure = float(step_obj["val"]) if step_obj["val"].replace(".","",1).isdigit() else 1
                    self.after(0, lambda i=islem_index, n=step_obj["step_name"]: log_kutusu.insert("end", f"[{i}] {n}\n"))
                    time.sleep(sure)
                    basarili_adim += 1
                    continue # Bekleme adımlarında OpenCV kıyaslaması yapılmaz
                
                time.sleep(1.5)
                
                # Eğer adımda ref görsel yoksa (IDE'den manuel eklenmişse) hata tespiti atlanır
                if not ref_isim:
                    basarili_adim += 1
                    adim_raporlari.append(f"✅ Adım {islem_index} - BAŞARILI (Görsel Kıyas Yok)")
                    self.after(0, lambda: log_kutusu.insert("end", f"✅ İşlem Tamamlandı.\n"))
                    continue

                self.after(0, lambda: log_kutusu.insert("end", f"🔍 Kıyaslanıyor...\n"))
                check_yol = os.path.join(self.hata_klasoru, f"temp_check_{int(time.time())}.png")
                subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_check.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_check.png", check_yol], capture_output=True, creationflags=c_flags)
                
                ref_yol = os.path.join(self.referans_klasoru, ref_isim)
                
                if os.path.exists(ref_yol) and os.path.exists(check_yol):
                    skor, isaretli_yol = self.goruntu_kiyasla_ve_isaretle(ref_yol, check_yol)
                    skor_yuzde = int(skor * 100)
                    self.after(0, lambda r=ref_yol, c=isaretli_yol, s=skor_yuzde: self.ui_gorsel_guncelle(r, c, s))
                    
                    if skor >= 0.85:
                        basarili_adim += 1
                        adim_raporlari.append(f"✅ Adım {islem_index} - BAŞARILI (Benzerlik: %{skor_yuzde})")
                        self.after(0, lambda s=skor_yuzde: log_kutusu.insert("end", f"✅ Benzerlik: %{s}\n"))
                    else:
                        foto_isim = f"hata_{test_adi.replace(' ', '_')}_Adim{islem_index}_{int(time.time())}.png"
                        foto_yol = os.path.join(self.hata_klasoru, foto_isim)
                        if os.path.exists(isaretli_yol): os.rename(isaretli_yol, foto_yol)
                        adim_raporlari.append(f"❌ Adım {islem_index} - BAŞARISIZ (Benzerlik: %{skor_yuzde}) | IMG:{foto_yol}")
                        self.after(0, lambda: log_kutusu.insert("end", "\n🛑 HATA TESPİT EDİLDİ! Test durduruluyor..."))
                        dongu_iptal = True
                        break
                else:
                    adim_raporlari.append(f"⚠️ Adım {islem_index} - REFERANS BULUNAMADI")
                    self.after(0, lambda: log_kutusu.insert("end", f"⚠️ Referans yok geçiliyor.\n"))

            log_proc.terminate()
            log_dosyasi.close()
            adim_raporlari.append(f"📄 LOG DOSYASI | LOG:{log_yolu}")
            
            genel_durum = "BAŞARILI" if basarili_adim == toplam_adim and not dongu_iptal else "BAŞARISIZ"
            tarih_saat = datetime.now().strftime("%d-%m-%Y %H:%M")
            detaylar_str = "\n".join(adim_raporlari)
            
            kayit_conn = sqlite3.connect(self.db_yolu)
            kayit_cursor = kayit_conn.cursor()
            kayit_cursor.execute("INSERT INTO test_sonuclari (ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar) VALUES (?,?,?,?,?,?)", 
                                 (test_adi, tarih_saat, toplam_adim, basarili_adim, genel_durum, detaylar_str))
            kayit_conn.commit()
            kayit_conn.close()
                    
            if not dongu_iptal: self.after(0, lambda: log_kutusu.insert("end", "\n🎉 TEST BİTTİ! Rapor kaydedildi."))
            self.playback_aktif = False

        threading.Thread(target=oynat_dongusu, daemon=True).start()

    # --- 4. STREAMLIT ŞABLONU İLE %100 UYUMLU SCRIPT ÇIKTISI ---
    def testi_disa_aktar(self, t_id, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar, uygulama, yetkili, versiyon, tarih, telefon_modeli FROM case_bazli_testler WHERE id = ?", (t_id,))
            satir = cursor.fetchone()
            conn.close()
            if not satir or not satir[0]: return
            
            app_pkg = satir[1] if satir[1] else ""
            yetkili = satir[2] if satir[2] else ""
            versiyon = satir[3] if satir[3] else ""
            tarih = satir[4] if satir[4] else ""
            telefon = satir[5] if satir[5] else ""
            
            fonk_ismi = f"{test_adi.replace(' ', '_')}"
            stream_cases = []
            current_case = None

            dokunuslar = [n for n in satir[0].split("|") if n]
            for idx, nokta in enumerate(dokunuslar):
                parts = nokta.split(";;;")
                step_obj = parts_to_dict(parts, idx+1)
                
                if step_obj["action"] == "Case":
                    if current_case: stream_cases.append(current_case)
                    case_safe_name = re.sub(r'\W|^(?=\d)', '_', step_obj["val"])
                    current_case = {"name": case_safe_name, "steps": []}
                    continue
                
                if not current_case:
                    current_case = {"name": fonk_ismi, "steps": []}
                
                current_case["steps"].append(step_obj)
                
            if current_case: stream_cases.append(current_case)

            gen_code = f"""import time
import requests
import json
import re
import os
import threading
import logging
from datetime import datetime, timezone
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction

logger = logging.getLogger(__name__)

# --- CLOUD API LOGGER ENTEGRASYONU (ASENKRON & SINGLETON) ---
_api_logger_instance = None

class APILogger:
    def __init__(self, run_id=None, agent_id=None):
        self.run_id = run_id or os.getenv("RUN_ID", "default_run")
        self.agent_id = agent_id or os.getenv("AGENT_ID", "qa_agent")
        
        base_url = os.getenv("PUBLIC_BASE_URL")
        self.base_url = f"{{base_url}}/api/v1" if base_url else None
        
        self.headers = {{
            "Content-Type": "application/json",
            "x-runner-shared-secret": os.getenv("RUNNER_SHARED_SECRET"),
        }}
        self.headers = {{k: v for k, v in self.headers.items() if v is not None}}
        
        self.seq = 0
        self.step = 0
        self.start_time = datetime.now()

    def _post_async(self, url, payload, headers):
        try:
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception as e:
            logger.error(f"Event gönderilemedi: {{e}}")

    def send_event(self, event_type, detail):
        self.step += 1
        self.seq += 1
        
        formatted_detail = f"[Adım {{self.step}}] {{detail}}" if detail and not detail.startswith("[Adım") else detail
        
        if not self.base_url: return False
            
        url = f"{{self.base_url}}/agents/runs/{{self.run_id}}/event"
        payload = {{
            "ok": True,
            "runEvent": {{
                "runId": self.run_id,
                "agentId": self.agent_id,
                "type": event_type,
                "payload": {{"detail": formatted_detail}},
                "is": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "seq": self.seq,
            }}
        }}
        
        threading.Thread(target=self._post_async, args=(url, payload, self.headers), daemon=True).start()
        print(f"[EVENT] {{event_type}}: {{formatted_detail}}")
        return True

    def log_step_passed(self, desc): self.send_event("step_passed", desc)
    def log_message(self, msg): self.send_event("log", msg)
    def log_test_app_launched(self, app): self.send_event("test_app_launched", f"{{app}} test app has started")

    def save_step_count_to_config(self):
        config_dir = "config"
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, f"step_count_{{self.run_id}}.json")
        
        duration = datetime.now() - self.start_time
        data = {{
            "total_steps": self.step,
            "duration_seconds": duration.total_seconds(),
            "run_id": self.run_id
        }}
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

def get_api_logger(run_id=None, agent_id=None):
    global _api_logger_instance
    if _api_logger_instance is None:
        _api_logger_instance = APILogger(run_id, agent_id)
    return _api_logger_instance

api_logger = get_api_logger()

def akilli_element_bulucu(driver, locator):
    locator = str(locator).strip()
    if not locator: raise Exception("Hedef veri (XPath/ID) bos birakilmis!")
    
    if locator.count("/") > 3 and "android.widget" in locator:
        son_dugum = locator.split("/")[-1]
        if ("@" in son_dugum) and (son_dugum.startswith("android.") or son_dugum.startswith("android.widget.")):
            locator = "//" + son_dugum

    if ("[@content-desc=" in locator or "[@text=" in locator) and ("'" in locator or '"' in locator):
        try:
            attr_part = locator.split("[@")[1].split("=")[0]
            val_part = locator.split("=")[1].split("]")[0].replace('"', '').replace("'", "")
            if len(val_part) > 12 or " " in val_part:
                kelimeler = re.findall(r'[\\wİıÖöÜüŞşÇçĞğ]+', val_part)
                if kelimeler:
                    secilen = sorted([k for k in kelimeler if len(k) >= 4], key=len, reverse=True)[0]
                    locator = f"//*[contains(@{{attr_part}}, '{{secilen}}')]"
        except: pass
    
    if locator.startswith("//") or locator.startswith("(") or locator.startswith("hierarchy"):
        return driver.find_element(by=AppiumBy.XPATH, value=locator)
    return driver.find_element(by=AppiumBy.ID, value=locator)

def ekran_kaydir(driver, yon, x=0, y=0):
    size = driver.get_window_size()
    merkez_x = x if x > 0 else int(size['width'] * 0.05) if yon in ['down', 'up'] else int(size['width'] / 2)
    merkez_y = y if y > 0 else int(size['height'] / 2) if yon in ['down', 'up'] else int(size['height'] * 0.1)
    
    start_x, start_y, end_x, end_y = merkez_x, merkez_y, merkez_x, merkez_y
    x_offset, y_offset = int(size['width'] * 0.25), int(size['height'] * 0.25)
    
    if yon == 'down': start_y += y_offset; end_y -= y_offset
    elif yon == 'up': start_y -= y_offset; end_y += y_offset
    elif yon == 'right': start_x -= x_offset; end_x += x_offset
    elif yon == 'left': start_x += x_offset; end_x -= x_offset

    try:
        actions = ActionChains(driver)
        actions.w3c_actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "touch"))
        actions.w3c_actions.pointer_action.move_to_location(start_x, start_y)
        actions.w3c_actions.pointer_action.pointer_down()
        actions.w3c_actions.pointer_action.pause(0.05) 
        actions.w3c_actions.pointer_action.move_to_location(end_x, end_y)
        actions.w3c_actions.pointer_action.pointer_up()
        actions.perform()
    except Exception as e: print(f"Kaydirma hatasi: {{e}}")

"""
            gen_code += "options = UiAutomator2Options()\n"
            if app_pkg: gen_code += f"options.app_package = '{app_pkg}'\n"
            gen_code += "options.no_reset = True\n"
            gen_code += "executor = os.getenv('COMMAND_EXECUTOR', 'http://127.0.0.1:4723')\n"
            gen_code += "driver = webdriver.Remote(executor, options=options)\n"
            gen_code += "driver.implicitly_wait(10)\n\n"

            calls = []
            for case in stream_cases:
                c_name = case["name"]
                calls.append(f"    {c_name}()")
                gen_code += f"def {c_name}():\n    try:\n        api_logger.log_message('--- {c_name.upper()} BAŞLADI ---')\n"
                
                for s_idx, step in enumerate(case["steps"]):
                    act = step["action"]
                    s_name = step.get("step_name", f"Adım {s_idx+1}").replace("'", "\\'")
                    xp = step.get('xpath', '')
                    exact = step.get('exact_match', False)
                    
                    if act == "Başlık / Yorum":
                        gen_code += f"\n        # --- {step.get('val', '')} ---\n"
                        gen_code += f"        api_logger.log_message('{step.get('val', '')}')\n"
                        continue
                        
                    gen_code += f"        api_logger.log_message('Adım başlatılıyor: {s_name}...')\n"
                    
                    def get_finder(xpath, exact_match):
                        if exact_match: return f"driver.find_element(by=AppiumBy.XPATH, value=r'''{xpath}''')"
                        return f"akilli_element_bulucu(driver, r'''{xpath}''')"
                    
                    if act == "Tıkla":
                        if step.get("x", 0) > 0 or step.get("y", 0) > 0:
                            gen_code += f"        driver.tap([({step['x']}, {step['y']})])\n        time.sleep(1)\n"
                        else:
                            gen_code += f"        {get_finder(xp, exact)}.click()\n        time.sleep(1)\n"
                    elif act == "Metin Yaz":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        gen_code += f"        kutu = {get_finder(xp, exact)}\n"
                        gen_code += f"        kutu.click(); time.sleep(0.5)\n" 
                        gen_code += f"        kutu.clear(); kutu.send_keys('{safe_val}'); time.sleep(1)\n"
                    elif act == "Güvenli Metin Yaz (Fiziksel)":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        d_count = step.get("count", 10)
                        gen_code += f"        kutu = {get_finder(xp, exact)}\n"
                        gen_code += f"        kutu.click(); time.sleep(0.5)\n"
                        gen_code += f"        driver.press_keycode(123) # İmleci sona al\n"
                        gen_code += f"        for _ in range({d_count}): driver.press_keycode(67) # SİL\n"
                        gen_code += f"        time.sleep(0.5)\n"
                        gen_code += f"        for rakam in '{safe_val}':\n"
                        gen_code += f"            driver.press_keycode(int(rakam) + 7)\n"
                        gen_code += f"            time.sleep(0.2)\n"
                        gen_code += f"        time.sleep(1)\n"
                    elif act == "Sistem Tuşu":
                        sk = step.get("sys_key", "")
                        if sk == "Klavyeyi Kapat": gen_code += "        try: driver.hide_keyboard()\n        except: pass\n"
                        elif sk == "Geri": gen_code += "        driver.press_keycode(4)\n"
                        elif sk == "Ana Sayfa": gen_code += "        driver.press_keycode(3)\n"
                        elif sk == "Kutuyu Temizle":
                            gen_code += f"        kutu = {get_finder(xp, exact)}\n"
                            gen_code += f"        kutu.clear(); time.sleep(1)\n"
                        elif sk == "Fiziksel Sil (Backspace)":
                            d_count = step.get("count", 10)
                            gen_code += f"        kutu = {get_finder(xp, exact)}\n"
                            gen_code += f"        kutu.click(); time.sleep(0.5)\n"
                            gen_code += f"        driver.press_keycode(123)\n"
                            gen_code += f"        for _ in range({d_count}): driver.press_keycode(67)\n        time.sleep(1)\n"
                    elif act == "Kaydır (Swipe)":
                        s_dir = {"Aşağı": "down", "Yukarı": "up", "Sağa": "right", "Sola": "left"}.get(step.get('direction','Aşağı'))
                        sx, sy = step.get('x', 0), step.get('y', 0)
                        gen_code += f"        for _ in range({step.get('count',1)}):\n            ekran_kaydir(driver, '{s_dir}', {sx}, {sy})\n            time.sleep(0.5)\n"
                    elif act == "Bekle (Sleep)":
                        gen_code += f"        time.sleep({step.get('val',1)})\n"
                        
                    gen_code += f"        api_logger.log_step_passed('{s_name}')\n"
                    
                gen_code += f"        api_logger.log_message('{c_name} Başarıyla Tamamlandı')\n"
                gen_code += "    except Exception as e:\n"
                gen_code += "        api_logger.log_message(f'HATA: {e}')\n"
                gen_code += "        raise Exception(f'Test Durduruldu! Beklenen element bulunamadı: {e}')\n\n"

            gen_code += "try:\n" + ("\n".join(calls) if calls else "    pass") + "\nfinally:\n    api_logger.save_step_count_to_config()\n    driver.quit()\n"

            metadata_dict = {"platform": "Android", "app_pkg": app_pkg, "app_act": "", "bundle_id": "", "cases": stream_cases}
            metadata_json = json.dumps(metadata_dict, ensure_ascii=False)
            gen_code += f"\n\n# --- IDE_METADATA_START ---\n# {metadata_json}\n"

            dosya_yolu = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"{fonk_ismi}_Appium.py", title="IDE Uyumlu Scripti Kaydet")
            if dosya_yolu:
                with open(dosya_yolu, "w", encoding="utf-8") as f: f.write(gen_code)
                messagebox.showinfo("Başarılı", f"Streamlit IDE uyumlu Appium scripti üretildi!\nDosya: {dosya_yolu}")
        except Exception as e: messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

    # ==========================================
    #   5. RAPORLAMA VE ZIP ÇIKTISI
    # ==========================================
    def goster_raporlar(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📊 Geçmiş Test Sonuç Raporları", font=("Arial", 18, "bold")).pack(pady=10)
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)
        self.arama_rapor_entry = ctk.CTkEntry(ust_frame, placeholder_text="Raporlarda Ara...", width=400)
        self.arama_rapor_entry.pack(side="left", padx=10)
        self.arama_rapor_entry.bind("<KeyRelease>", self.rapor_listeyi_guncelle)

        self.rapor_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=450)
        self.rapor_listesi.pack(pady=10, padx=10, fill="both", expand=True)
        self.rapor_listeyi_guncelle()

    def rapor_listeyi_guncelle(self, event=None):
        for widget in self.rapor_listesi.winfo_children(): widget.destroy()
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            arama_metni = self.arama_rapor_entry.get().strip() if hasattr(self, 'arama_rapor_entry') else ""
            cursor.execute("SELECT id, ana_test_adi, tarih, toplam_adim, basarili_adim, genel_durum, detaylar FROM test_sonuclari WHERE ana_test_adi LIKE ? ORDER BY id DESC", (f'%{arama_metni}%',))
            raporlar = cursor.fetchall()
            conn.close()

            for r_id, test_adi, tarih, toplam, basarili, durum, detaylar in raporlar:
                arka_plan = "darkgreen" if durum == "BAŞARILI" else "#962d22"
                satir = ctk.CTkFrame(self.rapor_listesi, fg_color=arka_plan, corner_radius=5)
                satir.pack(fill="x", pady=5, padx=5)

                bilgi_metni = f"🕒 {tarih}   |   📂 {test_adi}   |   Başarı: {basarili}/{toplam}"
                ctk.CTkLabel(satir, text=bilgi_metni, font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                
                ctk.CTkButton(satir, text="🗑️ Sil", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda idx=r_id: self.raporu_sil(idx)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="📤 ZIP İndir", width=100, fg_color="#2980b9", hover_color="#1f618d", command=lambda t=test_adi, dt=tarih, tp=toplam, b=basarili, dr=durum, d=detaylar: self.raporu_zip_paylas(t, dt, tp, b, dr, d)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="🔍 Detaylar", width=80, fg_color="#1f538d", hover_color="#14375e", command=lambda t=test_adi, dt=tarih, d=detaylar: self.detay_popup_ac(t, dt, d)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def raporu_sil(self, rapor_id):
        cevap = messagebox.askyesno("Onay", "Bu raporu ve hatalı ekran görüntülerini silmek istediğinize emin misiniz?")
        if not cevap: return
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT detaylar FROM test_sonuclari WHERE id = ?", (rapor_id,))
            kayit = cursor.fetchone()
            if kayit and kayit[0]:
                for satir in kayit[0].split("\n"):
                    if "| IMG:" in satir:
                        yol = satir.split("| IMG:")[1].strip()
                        if os.path.exists(yol): os.remove(yol)
                    elif "| LOG:" in satir:
                        yol = satir.split("| LOG:")[1].strip()
                        if os.path.exists(yol): os.remove(yol)
            cursor.execute("DELETE FROM test_sonuclari WHERE id = ?", (rapor_id,))
            conn.commit()
            conn.close()
            self.rapor_listeyi_guncelle()
        except Exception: pass

    def raporu_zip_paylas(self, test_adi, tarih, toplam, basarili, durum, detaylar):
        dosya_tarih = tarih.replace(":", "-").replace(" ", "_")
        zip_ismi = f"Rapor_{test_adi.replace(' ', '_')}_{dosya_tarih}.zip"
        zip_yolu = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP Dosyaları", "*.zip")], initialfile=zip_ismi)
        if not zip_yolu: return
        try:
            rapor_icerik = "="*55 + "\n           APPIC TEST SONUÇ RAPORU\n" + "="*55 + "\n\n"
            rapor_icerik += f"📌 Test Adı       : {test_adi}\n🕒 Çalışma Tarihi : {tarih}\n📊 Başarı Oranı   : {basarili} / {toplam} Adım Başarılı\n🎯 Genel Durum    : {durum}\n\n--- ADIM BAZLI DETAYLAR ---\n"
            eklenecek_dosyalar = []
            if detaylar:
                for satir in detaylar.split("\n"):
                    if "| IMG:" in satir:
                        metin, yol = satir.split("| IMG:")
                        rapor_icerik += metin.strip() + f" (Hata Görseli Zip İçinde: {os.path.basename(yol.strip())})\n"
                        if os.path.exists(yol.strip()): eklenecek_dosyalar.append(yol.strip())
                    elif "| LOG:" in satir:
                        metin, yol = satir.split("| LOG:")
                        rapor_icerik += metin.strip() + f" (Log Dosyası Zip İçinde: {os.path.basename(yol.strip())})\n"
                        if os.path.exists(yol.strip()): eklenecek_dosyalar.append(yol.strip())
                    else: rapor_icerik += satir + "\n"
            else: rapor_icerik += "Detay bulunamadı.\n"
            
            with zipfile.ZipFile(zip_yolu, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr(f"Rapor_Ozet_{dosya_tarih}.txt", rapor_icerik)
                for dosya in set(eklenecek_dosyalar): zipf.write(dosya, arcname=os.path.basename(dosya))
            messagebox.showinfo("Başarılı", f"Rapor ve dosyalar ZIP olarak paketlendi!\n{zip_yolu}")
        except Exception as e: messagebox.showerror("Hata", f"Paketleme hatası: {e}")

    def detay_popup_ac(self, test_adi, tarih, detaylar):
        popup = ctk.CTkToplevel(self)
        popup.title("Test Adım Detayları")
        popup.geometry("550x650") 
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text=f"📂 {test_adi}\n🕒 {tarih}", font=("Arial", 16, "bold")).pack(pady=10)
        scroll_alan = ctk.CTkScrollableFrame(popup, width=500, height=550)
        scroll_alan.pack(padx=10, pady=10, fill="both", expand=True)
        if detaylar:
            for satir in detaylar.split("\n"):
                if "| IMG:" in satir:
                    metin_kismi, foto_yolu = satir.split("| IMG:")
                    ctk.CTkLabel(scroll_alan, text=metin_kismi.strip(), font=("Arial", 14, "bold"), text_color="#ff4d4d").pack(pady=(15, 5), anchor="w", padx=10)
                    if os.path.exists(foto_yolu.strip()):
                        try:
                            orijinal_resim = Image.open(foto_yolu.strip())
                            oran = 300 / orijinal_resim.width
                            yeni_boyut = (300, int(orijinal_resim.height * oran))
                            ctk_img = ctk.CTkImage(light_image=orijinal_resim, dark_image=orijinal_resim, size=yeni_boyut)
                            ctk.CTkLabel(scroll_alan, image=ctk_img, text="").pack(pady=5, anchor="w", padx=30)
                        except Exception: pass
                elif "| LOG:" in satir:
                    metin_kismi, log_yolu = satir.split("| LOG:")
                    if os.path.exists(log_yolu.strip()): 
                        ctk.CTkButton(scroll_alan, text="📄 Cihaz Logunu (Logcat) Aç", fg_color="#8e44ad", command=lambda p=log_yolu.strip(): os.startfile(p)).pack(pady=(20, 10), padx=30, fill="x")
                else:
                    renk = "lightgreen" if "✅" in satir else "white"
                    ctk.CTkLabel(scroll_alan, text=satir.strip(), font=("Arial", 14, "bold"), text_color=renk).pack(pady=(15, 5), anchor="w", padx=10)

if __name__ == "__main__":
    app = AppicTestStudyosu()
    app.mainloop()