import sys
import subprocess
import os

# ==========================================
#   OTOMATİK KÜTÜPHANE YÜKLEYİCİ (BAŞLANGIÇ)
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
            if modul_adi == "cv2":
                __import__("cv2")
            else:
                __import__(modul_adi)
        except ImportError:
            eksikler.append(pip_adi)
            
    if eksikler:
        print(f"\n[SİSTEM] Eksik kütüphaneler tespit edildi, otomatik yükleniyor: {eksikler}")
        print("-" * 50)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *eksikler])
            print("-" * 50)
            print("[SİSTEM] Tüm kütüphaneler başarıyla yüklendi! Uygulama başlatılıyor...\n")
        except Exception as e:
            print(f"\n❌ Kütüphaneler yüklenirken kritik bir hata oluştu: {e}")
            input("Çıkmak için ENTER tuşuna basın...")
            sys.exit(1)

bagimliliklari_kontrol_et_ve_yukle()

# ==========================================
#         GEREKLİ KÜTÜPHANELER
# ==========================================
import customtkinter as ctk
import threading
import time
import sqlite3
import json
import zipfile
import cv2
import numpy as np
import re
import math
import io
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
from datetime import datetime
from pynput.keyboard import Listener, Key
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TestOtomasyonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Token Finansal Teknolojiler - Test Otomasyon Merkezi (Görsel Motorlu)")
        self.geometry("1050x700")
        
        # --- DOSYA VE KLASÖR YOLLARI ---
        if getattr(sys, 'frozen', False):
            self.ana_dizin = os.path.dirname(sys.executable)
        else:
            self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
            
        self.db_yolu = os.path.join(self.ana_dizin, "test_merkezi.db")
        
        # WinError 2 hatasını çözen ADB yolu güncellemesi
        self.adb_yolu = "adb" 
        # NOT: Eğer hala WinError 2 alırsanız, üstteki satırı silip alttaki gibi tam yolunu yazın:
        # self.adb_yolu = "C:\\Users\\Burak\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe"
        
        self.hata_klasoru = os.path.join(self.ana_dizin, "hata_gorselleri")
        os.makedirs(self.hata_klasoru, exist_ok=True) 

        self.log_klasoru = os.path.join(self.ana_dizin, "test_loglari")
        os.makedirs(self.log_klasoru, exist_ok=True)
        
        self.referans_klasoru = os.path.join(self.ana_dizin, "referans_gorseller")
        os.makedirs(self.referans_klasoru, exist_ok=True)

        # --- KAYIT MOTORU DEĞİŞKENLERİ ---
        self.kayit_aktif = False
        self.gecici_dokunuslar = []
        self.son_dokunus_zamani = 0 
        self.klavye_dinleyici = None
        self.adim_sayaci = 1
        
        # --- GÖRSEL ARAYÜZ BOYUTLARI ---
        self.ui_w = 320
        self.ui_h = 560
        
        # --- AKILLI ÇIKARIM MOTORU (GÖLGE HAFIZA) ---
        self.aktif_ekran_xml = ""
        
        # --- DONANIM VE EKRAN DEĞİŞKENLERİ ---
        self.ekran_genislik = 1080
        self.ekran_yukseklik = 1920

        self.cihaz_cozunurlugunu_al()
        self.veritabanini_hazirla()

        # --- GRID DÜZENİ ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- SOL PANEL (MENÜ) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="TEST PANELİ", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=10)

        self.btn_kayit_ekran = ctk.CTkButton(self.sidebar_frame, text="Yeni Görsel Kayıt", command=self.goster_kayit)
        self.btn_kayit_ekran.pack(pady=10, padx=20)

        self.btn_liste_ekran = ctk.CTkButton(self.sidebar_frame, text="Testleri Yönet & Çalıştır", command=self.goster_liste)
        self.btn_liste_ekran.pack(pady=10, padx=20)

        self.btn_rapor_ekran = ctk.CTkButton(self.sidebar_frame, text="📊 Test Raporları", fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=self.goster_raporlar)
        self.btn_rapor_ekran.pack(pady=10, padx=20)

        # --- SAĞ PANEL (İÇERİK) ---
        self.main_frame = ctk.CTkFrame(self, corner_radius=15)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.baslangic_ekrani()

    def cihaz_cozunurlugunu_al(self):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            sonuc = subprocess.run([self.adb_yolu, "shell", "wm", "size"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r"Override size:\s*(\d+)x(\d+)", sonuc.stdout)
            if not match: match = re.search(r"Physical size:\s*(\d+)x(\d+)", sonuc.stdout)
            if match:
                self.ekran_genislik = int(match.group(1))
                self.ekran_yukseklik = int(match.group(2))
        except Exception:
            pass

    def veritabanini_hazirla(self):
        conn = sqlite3.connect(self.db_yolu)
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS case_bazli_testler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, yetkili TEXT, uygulama TEXT, amac TEXT,
            case_adi TEXT, aksiyonlar TEXT, beklenen_xml TEXT)""")
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN telefon_modeli TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN notlar TEXT")
        except sqlite3.OperationalError: pass
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS test_sonuclari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ana_test_adi TEXT, tarih TEXT,
            toplam_adim INTEGER, basarili_adim INTEGER, genel_durum TEXT)""")
        try: cursor.execute("ALTER TABLE test_sonuclari ADD COLUMN detaylar TEXT")
        except sqlite3.OperationalError: pass 
        conn.commit()
        conn.close()

    def temizle(self):
        self.kayit_aktif = False
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def baslangic_ekrani(self):
        self.temizle()
        try: aktif_kullanici = os.getlogin().capitalize()
        except: aktif_kullanici = "Kullanıcı"
        lbl = ctk.CTkLabel(self.main_frame, text=f"Token Görsel Test Otomasyonuna Hoş Geldiniz, {aktif_kullanici}!\nSoldan 'Yeni Görsel Kayıt' seçerek başlayabilirsiniz.", font=("Arial", 16))
        lbl.pack(expand=True)

    def aktif_uygulamayi_bul(self):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            sonuc = subprocess.run([self.adb_yolu, "shell", "dumpsys", "window"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r'mCurrentFocus=Window\{.*\s+([\w\.]+)/', sonuc.stdout)
            if match: return match.group(1)
        except Exception: pass
        return ""

    # ==========================================
    #   1. YENİ GÖRSEL KAYIT MOTORU (CANLI)
    # ==========================================
    def goster_kayit(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📱 Görsel ve Canlı Senaryo Kaydı", font=("Arial", 18, "bold")).pack(pady=5)
        
        # FORM ALANI
        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=10, pady=5)
        
        self.entry_ad = ctk.CTkEntry(form_frame, placeholder_text="Senaryo Adı (Örn: Login)", width=150)
        self.entry_ad.grid(row=0, column=0, padx=5, pady=2)
        self.entry_yetkili = ctk.CTkEntry(form_frame, placeholder_text="Yetkili", width=120)
        self.entry_yetkili.grid(row=0, column=1, padx=5, pady=2)
        self.entry_uygulama = ctk.CTkEntry(form_frame, placeholder_text="Uygulama (Oto)", width=180)
        self.entry_uygulama.grid(row=0, column=2, padx=5, pady=2)
        self.entry_telefon = ctk.CTkEntry(form_frame, placeholder_text="Tel Modeli", width=120)
        self.entry_telefon.grid(row=0, column=3, padx=5, pady=2)
        
        # BUTONLAR
        self.buton_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buton_frame.pack(pady=5)
        
        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="▶️ KAYDI BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
        self.btn_baslat.grid(row=0, column=0, padx=5)
        self.lbl_oto_durum = ctk.CTkLabel(self.buton_frame, text="Kayıt Bekleniyor", fg_color="gray", text_color="white", corner_radius=5, width=150)
        self.lbl_oto_durum.grid(row=0, column=1, padx=5, ipadx=5, ipady=5)
        self.btn_bitir = ctk.CTkButton(self.buton_frame, text="🛑 Kaydı Bitir (ESC)", fg_color="red", state="disabled", command=self.kaydi_bitir_islem)
        self.btn_bitir.grid(row=0, column=2, padx=5)

        # GÖRSEL VE LOG ALANI
        content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.screen_frame = ctk.CTkFrame(content_frame, width=self.ui_w+20, fg_color="#1e1e1e")
        self.screen_frame.pack(side="left", fill="y", padx=10, pady=5)
        
        self.lbl_ekran = ctk.CTkLabel(self.screen_frame, text="Görüntü Bekleniyor...", width=self.ui_w, height=self.ui_h, fg_color="#000000")
        self.lbl_ekran.pack(pady=10, padx=10)
        
        # FARE BINDING'LERİ (CANLI ETKİLEŞİM)
        self.lbl_ekran.bind("<Button-1>", self.sol_tik_basildi)
        self.lbl_ekran.bind("<ButtonRelease-1>", self.sol_tik_birakildi)
        self.lbl_ekran.bind("<Button-2>", self.sag_tik_menusu)
        self.lbl_ekran.bind("<Button-3>", self.sag_tik_menusu)
        
        self.log_kutusu = ctk.CTkTextbox(content_frame, height=560)
        self.log_kutusu.pack(side="right", fill="both", expand=True, pady=10, padx=10)
        self.log_kutusu.insert("0.0", "Bilgileri girip kaydı başlatın. Cihaz ekranı yansıyacaktır.\n")

    def guncel_xml_cek(self):
        time.sleep(0.5) 
        while self.kayit_aktif:
            try:
                c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run([self.adb_yolu, "shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], capture_output=True, creationflags=c_flags)
                xml_data = subprocess.check_output([self.adb_yolu, "shell", "cat", "/sdcard/window_dump.xml"], creationflags=c_flags).decode('utf-8', errors='ignore')
                self.aktif_ekran_xml = xml_data
            except Exception: pass
            time.sleep(1.5)

    def ekran_yayini_dongusu(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        temp_gorsel_yolu = os.path.join(self.hata_klasoru, "temp_canli_ekran.png")
        
        while self.kayit_aktif:
            try:
                # 1. Cihazın içinde ekran görüntüsü al
                subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_canli.png"], capture_output=True, creationflags=c_flags)
                
                # 2. Görüntüyü bilgisayara çek
                subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_canli.png", temp_gorsel_yolu], capture_output=True, creationflags=c_flags)
                
                # 3. Görüntüyü oku ve CustomTkinter'a uygun hale getir
                if os.path.exists(temp_gorsel_yolu):
                    img = Image.open(temp_gorsel_yolu)
                    img_resized = img.resize((self.ui_w, self.ui_h))
                    ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(self.ui_w, self.ui_h))
                    
                    # KRİTİK: Arayüz güncellemesi mutlaka ana Thread (after) üzerinden yapılmalı
                    self.after(0, lambda resim=ctk_img: self.lbl_ekran.configure(image=resim, text=""))
                else:
                    self.after(0, lambda: self.log_yaz("⚠️ Görüntü telefondan çekilemedi. Bağlantıyı kontrol edin."))
                    
            except Exception as e: 
                self.after(0, lambda err=e: self.log_yaz(f"❌ Ekran döngüsü hatası: {err}"))
                
            time.sleep(0.5)

    def akilli_hedef_bul(self, gercek_x, gercek_y, is_swipe=False):
        if not self.aktif_ekran_xml: return "NONE", "", ""
        try:
            root = ET.fromstring(self.aktif_ekran_xml)
            en_kucuk_alan = float('inf')
            nihai_hedef = None
            TOLERANS = 50

            for elem in root.iter():
                bounds = elem.attrib.get('bounds')
                if bounds:
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        if (x1 - TOLERANS) <= gercek_x <= (x2 + TOLERANS) and (y1 - TOLERANS) <= gercek_y <= (y2 + TOLERANS):
                            alan = (x2 - x1) * (y2 - y1)
                            is_target = elem.attrib.get('scrollable') == 'true' if is_swipe else elem.attrib.get('clickable') == 'true'
                            if is_target and 0 < alan < en_kucuk_alan:
                                en_kucuk_alan = alan
                                nihai_hedef = elem.attrib
            
            if nihai_hedef:
                cls = nihai_hedef.get('class', '')
                text = nihai_hedef.get('text', '') or nihai_hedef.get('content-desc', '')
                
                if nihai_hedef.get('resource-id'): xpath = nihai_hedef.get('resource-id')
                elif nihai_hedef.get('text'): xpath = f"//*[@text='{nihai_hedef.get('text')}']"
                elif nihai_hedef.get('content-desc'): xpath = f"//*[@content-desc='{nihai_hedef.get('content-desc')}']"
                else: xpath = f"//{cls}[@bounds='{nihai_hedef.get('bounds')}']"
                
                return xpath.replace(";", ""), text.replace(";", ""), cls.replace(";", "")
        except Exception: pass
        return "NONE", "", ""

    # --- CANLI FARE ETKİLEŞİM KATMANI ---
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

        if mesafe < 30: # TIKLAMA (Tolerans 30'a çıkarıldı)
            xpath, text_val, cls_val = self.akilli_hedef_bul(gercek_x, gercek_y, is_swipe=False)
            ek_veri = f";;;{xpath};;;{text_val};;;{cls_val}"
            self.gecici_dokunuslar.append(f"T,{gercek_x},{gercek_y},0.5{ek_veri}")
            self.son_dokunus_zamani = time.time()
            self.after(0, lambda: self.log_yaz(f"🎯 Tıklama: ({gercek_x}, {gercek_y})"))
            threading.Thread(target=lambda: subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)).start()
        else: # KAYDIRMA
            fark_x = bitis_x - getattr(self, 'bas_x', 0)
            fark_y = bitis_y - getattr(self, 'bas_y', 0)
            yon = "Aşağı" if fark_y > 0 else "Yukarı"
            if abs(fark_x) > abs(fark_y): yon = "Sağa" if fark_x > 0 else "Sola"
            
            xpath, text_val, cls_val = self.akilli_hedef_bul(gercek_bas_x, gercek_bas_y, is_swipe=True)
            ek_veri = f";;;{xpath};;;{text_val};;;{cls_val}"
            self.gecici_dokunuslar.append(f"S,{gercek_bas_x},{gercek_bas_y},{gercek_x},{gercek_y},500,0.5{ek_veri}")
            self.son_dokunus_zamani = time.time()
            self.after(0, lambda: self.log_yaz(f"👆 Kaydırma: {yon}"))
            threading.Thread(target=lambda: subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(gercek_bas_x), str(gercek_bas_y), str(gercek_x), str(gercek_y), "500"], creationflags=c_flags)).start()

    def sag_tik_menusu(self, event):
        if not self.kayit_aktif: return
        gercek_x = int((event.x / self.ui_w) * self.ekran_genislik)
        gercek_y = int((event.y / self.ui_h) * self.ekran_yukseklik)
        
        xpath, text_val, cls_val = self.akilli_hedef_bul(gercek_x, gercek_y, is_swipe=False)
        ek_veri = f";;;{xpath};;;{text_val};;;{cls_val}"
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        
        popup = ctk.CTkToplevel(self)
        popup.title("Gelişmiş İşlemler")
        popup.geometry("300x200")
        popup.attributes("-topmost", True)
        
        veri_girisi = ctk.CTkEntry(popup, placeholder_text="Yazılacak metin...", width=200)
        veri_girisi.pack(pady=20)
        
        def yaz():
            val = veri_girisi.get()
            if not val: return
            self.gecici_dokunuslar.append(f"M,{gercek_x},{gercek_y},{val}{ek_veri}")
            self.son_dokunus_zamani = time.time()
            self.after(0, lambda: self.log_yaz(f"✍️ Metin Eklendi: '{val}'"))
            popup.destroy()
            
            def cihaza_yaz():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
            threading.Thread(target=cihaza_yaz).start()
            
        def sil():
            self.gecici_dokunuslar.append(f"K,{gercek_x},{gercek_y},Kutuyu Temizle{ek_veri}")
            self.son_dokunus_zamani = time.time()
            self.after(0, lambda: self.log_yaz(f"🧹 Silme İşlemi Eklendi"))
            popup.destroy()
            
            def cihazdan_sil():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                for _ in range(25):
                    subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
            threading.Thread(target=cihazdan_sil).start()
            
        ctk.CTkButton(popup, text="✍️ Metin Yaz", fg_color="green", command=yaz).pack(pady=5)
        ctk.CTkButton(popup, text="🧹 İçeriği Sil (Fiziksel)", fg_color="red", command=sil).pack(pady=5)

    def kaydi_tetikle(self):
        self.guncel_test_adi = self.entry_ad.get()
        self.guncel_yetkili = self.entry_yetkili.get()
        
        otomatik_paket = self.aktif_uygulamayi_bul()
        if otomatik_paket and otomatik_paket not in ["com.android.systemui", "com.android.launcher"]:
            self.guncel_uygulama = otomatik_paket
            self.entry_uygulama.delete(0, 'end')
            self.entry_uygulama.insert(0, otomatik_paket)
        else: self.guncel_uygulama = self.entry_uygulama.get()
        
        self.guncel_telefon = self.entry_telefon.get()
        self.guncel_notlar = ""
        self.guncel_amac = "Canlı Ekran Testi"

        if not self.guncel_test_adi:
            self.log_yaz("\n❌ Hata: Senaryo adı boş olamaz!")
            return

        self.cihaz_cozunurlugunu_al()
        self.btn_baslat.configure(state="disabled")
        self.lbl_oto_durum.configure(text="Canlı Yakalama Aktif", fg_color="#F4A460", text_color="black")
        self.btn_bitir.configure(state="normal")
        
        self.kayit_aktif = True
        self.gecici_dokunuslar = []
        self.son_dokunus_zamani = 0 
        self.adim_sayaci = 1
        self.aktif_ekran_xml = ""

        self.log_yaz(f"\n🚀 '{self.guncel_test_adi}' için kayıt başladı!")
        self.log_yaz("👉 Ekrana yansıyan görüntü üzerinden tıklayın veya sürükleyin.\n👉 Metin yazmak için SAĞ TIK kullanın.\n")

        threading.Thread(target=self.ekran_yayini_dongusu, daemon=True).start()
        threading.Thread(target=self.guncel_xml_cek, daemon=True).start()
        threading.Thread(target=self.otomatik_adim_izleyici, daemon=True).start()
        
        if self.klavye_dinleyici: self.klavye_dinleyici.stop()
        self.klavye_dinleyici = Listener(on_press=self.klavye_dinle)
        self.klavye_dinleyici.start()

    def klavye_dinle(self, key):
        if not self.kayit_aktif: return 
        if key == Key.esc: self.after(0, self.kaydi_bitir_islem)

    def otomatik_adim_izleyici(self):
        islem_yapiliyor = False
        while self.kayit_aktif:
            time.sleep(0.3)
            if not self.kayit_aktif: break
            
            if self.gecici_dokunuslar and self.son_dokunus_zamani > 0 and not islem_yapiliyor:
                gecen_sure = time.time() - self.son_dokunus_zamani
                if gecen_sure >= 1.5:
                    islem_yapiliyor = True
                    kopya = list(self.gecici_dokunuslar)
                    self.gecici_dokunuslar.clear()
                    
                    case_adi = f"Adim_{self.adim_sayaci}"
                    self.adim_sayaci += 1
                    
                    self.log_yaz(f"\n⏳ Otomatik Adım Yakalandı: '{case_adi}'. Çekiliyor...")
                    self.arka_planda_case_kaydet(case_adi, kopya)
                    islem_yapiliyor = False

    def arka_planda_case_kaydet(self, case_adi, dokunuslar):
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            zaman_ms = int(time.time() * 1000)
            cihaz_ref_yolu = f"/sdcard/ref_{zaman_ms}.png"
            ref_isim = f"ref_{self.guncel_test_adi.replace(' ', '_')}_{case_adi.replace(' ', '_')}_{zaman_ms}.png"
            ref_yol = os.path.join(self.referans_klasoru, ref_isim)
            
            subprocess.run([self.adb_yolu, "shell", "screencap", "-p", cihaz_ref_yolu], capture_output=True, creationflags=c_flags)
            subprocess.run([self.adb_yolu, "pull", cihaz_ref_yolu, ref_yol], capture_output=True, creationflags=c_flags)
            subprocess.run([self.adb_yolu, "shell", "rm", cihaz_ref_yolu], capture_output=True, creationflags=c_flags)
                
            aksiyon_str = "|".join(dokunuslar)
            
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO case_bazli_testler 
                           (ana_test_adi, yetkili, uygulama, amac, case_adi, aksiyonlar, beklenen_xml, telefon_modeli, notlar) 
                           VALUES (?,?,?,?,?,?,?,?,?)""", 
                         (self.guncel_test_adi, self.guncel_yetkili, self.guncel_uygulama, self.guncel_amac, case_adi, aksiyon_str, ref_isim, self.guncel_telefon, self.guncel_notlar))
            conn.commit()
            conn.close()
            self.after(0, lambda: self.log_yaz(f"✅ Adım '{case_adi}' OTO-KAYDEDİLDİ!"))
        except Exception as e:
            self.after(0, lambda: self.log_yaz(f"❌ Kayıt hatası: {e}"))

    def kaydi_bitir_islem(self):
        self.kayit_aktif = False
        if self.klavye_dinleyici:
            self.klavye_dinleyici.stop()
            self.klavye_dinleyici = None
            
        if self.gecici_dokunuslar:
            kopya = list(self.gecici_dokunuslar)
            self.gecici_dokunuslar.clear()
            self.arka_planda_case_kaydet(f"Adim_{self.adim_sayaci}", kopya)
            
        try:
            self.btn_baslat.configure(state="normal")
            self.lbl_oto_durum.configure(text="Kayıt Bitti", fg_color="gray", text_color="white")
            self.btn_bitir.configure(state="disabled")
            self.log_yaz("\n🎉 CANLI KAYIT TAMAMLANDI!\n")
        except Exception: pass

    def log_yaz(self, mesaj):
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")

    # ==========================================
    #   2. LİSTE YÖNETİMİ VE DIŞA AKTARIM
    # ==========================================
    def goster_liste(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="🚀 Kayıtlı Testleri Yönet", font=("Arial", 18, "bold")).pack(pady=10)
        
        ust_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        ust_frame.pack(pady=5, fill="x", padx=10)
        self.arama_entry = ctk.CTkEntry(ust_frame, placeholder_text="Ara...", width=400)
        self.arama_entry.pack(side="left", padx=10)
        self.arama_entry.bind("<KeyRelease>", self.listeyi_guncelle)

        self.test_listesi = ctk.CTkScrollableFrame(self.main_frame, width=800, height=400)
        self.test_listesi.pack(pady=10, padx=10, fill="both", expand=True)
        self.listeyi_guncelle()

    def listeyi_guncelle(self, event=None):
        for widget in self.test_listesi.winfo_children(): widget.destroy()
        if not os.path.exists(self.db_yolu): return
        arama = self.arama_entry.get().strip()
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ana_test_adi, uygulama, yetkili FROM case_bazli_testler WHERE ana_test_adi LIKE ?", (f'%{arama}%',))
            kayitlar = cursor.fetchall()
            conn.close()

            for test_adi, uyg, yetk in kayitlar:
                satir = ctk.CTkFrame(self.test_listesi, fg_color="#2b2b2b")
                satir.pack(fill="x", pady=5, padx=5)
                ctk.CTkLabel(satir, text=f"📂 {test_adi} | Uyg: {uyg} | {yetk}", font=("Arial", 13, "bold")).pack(side="left", padx=15, pady=10)
                ctk.CTkButton(satir, text="▶ Oynat", width=70, fg_color="green", command=lambda t=test_adi: self.testi_oynat(t)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="📤 IDE İçin Çıkar", width=120, fg_color="#2980b9", command=lambda t=test_adi: self.testi_disa_aktar(t)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def testi_disa_aktar(self, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT yetkili, uygulama, amac, case_adi, aksiyonlar, beklenen_xml FROM case_bazli_testler WHERE ana_test_adi = ? ORDER BY id ASC", (test_adi,))
            satirlar = cursor.fetchall()
            conn.close()
            if not satirlar: return
            
            stream_cases = []
            for s in satirlar:
                case_obj = {"name": s[3].replace(" ", "_"), "steps": []}
                dokunuslar = [n for n in s[4].split("|") if n]
                
                for idx, nokta in enumerate(dokunuslar):
                    parts = nokta.split(";;;")
                    ham_nokta = parts[0]
                    veriler = ham_nokta.split(",")
                    islem_turu = veriler[0]
                    
                    xpath = parts[1] if len(parts) > 1 else ""
                    text_val = parts[2] if len(parts) > 2 else ""
                    
                    step_name = f"Adım {idx+1}"
                    if text_val: step_name = f"İşlem: {text_val[:15]}"
                    
                    step_obj = {
                        "step_name": step_name,
                        "action": "Tıkla",
                        "xpath": xpath,
                        "val": "",
                        "count": 1,
                        "direction": "Aşağı",
                        "x": 0, "y": 0,
                        "sys_key": "",
                        "exact_match": True if xpath and xpath.startswith("//") else False
                    }
                    
                    if islem_turu == "T":
                        step_obj["action"] = "Tıkla"
                        step_obj["x"], step_obj["y"] = int(veriler[1]), int(veriler[2])
                    elif islem_turu == "S":
                        step_obj["action"] = "Kaydır (Swipe)"
                        x1, y1, x2, y2 = int(veriler[1]), int(veriler[2]), int(veriler[3]), int(veriler[4])
                        fark_x, fark_y = x2 - x1, y2 - y1
                        if abs(fark_y) > abs(fark_x): step_obj["direction"] = "Aşağı" if fark_y < 0 else "Yukarı"
                        else: step_obj["direction"] = "Sağa" if fark_x < 0 else "Sola"
                        step_obj["x"], step_obj["y"] = x1, y1
                    elif islem_turu == "M":
                        step_obj["action"] = "Metin Yaz"
                        step_obj["x"], step_obj["y"] = int(veriler[1]), int(veriler[2])
                        step_obj["val"] = ",".join(veriler[3:])
                        step_obj["step_name"] = f"Yaz: '{step_obj['val']}'"
                    elif islem_turu == "K":
                        step_obj["action"] = "Sistem Tuşu"
                        step_obj["x"], step_obj["y"] = int(veriler[1]), int(veriler[2])
                        step_obj["sys_key"] = veriler[3]
                        step_obj["step_name"] = "Silme İşlemi"
                            
                    case_obj["steps"].append(step_obj)
                stream_cases.append(case_obj)
            
            app_pkg = satirlar[0][1] if satirlar[0][1] else ""
            
            gen_code = "import time\nimport os\nfrom appium import webdriver\nfrom appium.options.android import UiAutomator2Options\nfrom appium.webdriver.common.appiumby import AppiumBy\nfrom selenium.webdriver.common.action_chains import ActionChains\nfrom selenium.webdriver.common.actions.action_builder import ActionBuilder\nfrom selenium.webdriver.common.actions.pointer_input import PointerInput\nfrom selenium.webdriver.common.actions import interaction\n\n"
            gen_code += "def akilli_element_bulucu(driver, locator):\n    if locator.startswith('//'): return driver.find_element(by=AppiumBy.XPATH, value=locator)\n    return driver.find_element(by=AppiumBy.ID, value=locator)\n\n"
            
            gen_code += "def ekran_kaydir(driver, yon, x, y):\n    size = driver.get_window_size()\n    merkez_x, merkez_y = (x, y) if x>0 else (int(size['width']/2), int(size['height']/2))\n    sx, sy, ex, ey = merkez_x, merkez_y, merkez_x, merkez_y\n    off_x, off_y = int(size['width']*0.25), int(size['height']*0.25)\n    if yon == 'down': sy += off_y; ey -= off_y\n    elif yon == 'up': sy -= off_y; ey += off_y\n    elif yon == 'right': sx -= off_x; ex += off_x\n    elif yon == 'left': sx += off_x; ex -= off_x\n    actions = ActionChains(driver)\n    actions.w3c_actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, 'touch'))\n    actions.w3c_actions.pointer_action.move_to_location(sx, sy).pointer_down().pause(0.1).move_to_location(ex, ey).pointer_up()\n    actions.perform()\n\n"
            
            gen_code += f"options = UiAutomator2Options()\noptions.app_package = '{app_pkg}'\noptions.no_reset = True\n"
            gen_code += "driver = webdriver.Remote('http://127.0.0.1:4723', options=options)\ndriver.implicitly_wait(10)\n\n"

            calls = []
            for case in stream_cases:
                c_name = case["name"]
                calls.append(f"    {c_name}()")
                gen_code += f"def {c_name}():\n"
                
                for step in case["steps"]:
                    act, xp, exact = step["action"], step.get('xpath', ''), step.get('exact_match', False)
                    finder = f"driver.find_element(by=AppiumBy.XPATH, value=r'''{xp}''')" if exact else f"akilli_element_bulucu(driver, r'''{xp}''')"
                    
                    if act == "Tıkla":
                        if xp and xp != "NONE": gen_code += f"    {finder}.click()\n    time.sleep(1)\n"
                        else: gen_code += f"    driver.tap([({step['x']}, {step['y']})])\n    time.sleep(1)\n"
                    elif act == "Kaydır (Swipe)":
                        s_dir = {"Aşağı": "down", "Yukarı": "up", "Sağa": "right", "Sola": "left"}.get(step.get('direction','Aşağı'))
                        gen_code += f"    ekran_kaydir(driver, '{s_dir}', {step.get('x',0)}, {step.get('y',0)})\n    time.sleep(0.5)\n"
                    elif act == "Metin Yaz":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        if xp and xp != "NONE":
                            gen_code += f"    k = {finder}\n    k.click(); time.sleep(0.5)\n    k.clear(); k.send_keys('{safe_val}'); time.sleep(1)\n"
                        else:
                            gen_code += f"    driver.tap([({step['x']}, {step['y']})]); time.sleep(0.5)\n    ActionChains(driver).send_keys('{safe_val}').perform()\n    time.sleep(1)\n"
                    elif act == "Sistem Tuşu":
                        if step.get("sys_key") == "Kutuyu Temizle":
                            if xp and xp != "NONE": gen_code += f"    k = {finder}\n    k.click(); time.sleep(0.5)\n"
                            else: gen_code += f"    driver.tap([({step['x']}, {step['y']})]); time.sleep(0.5)\n"
                            gen_code += "    driver.press_keycode(123)\n    for _ in range(25): driver.press_keycode(67)\n    time.sleep(1)\n"
                gen_code += "\n"

            gen_code += "try:\n" + ("\n".join(calls) if calls else "    pass") + "\nfinally:\n    driver.quit()\n"
            
            metadata_json = json.dumps({"platform": "Android", "app_pkg": app_pkg, "cases": stream_cases}, ensure_ascii=False)
            gen_code += f"\n# --- IDE_METADATA_START ---\n# {metadata_json}\n"

            dosya_yolu = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"{test_adi.replace(' ', '_')}_IDE.py", title="Görsel IDE İçin Aktar")
            if dosya_yolu:
                with open(dosya_yolu, "w", encoding="utf-8") as f: f.write(gen_code)
                messagebox.showinfo("Başarılı", f"Test IDE uyumlu aktarıldı!\nDosya: {dosya_yolu}")
        except Exception as e: messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

    # ==========================================
    #   3. OYNATMA VE CANLI GÖRSEL DASHBOARD
    # ==========================================
    def testi_oynat(self, test_adi):
        self.oynatma_penceresi = ctk.CTkToplevel(self)
        self.oynatma_penceresi.title(f"Test Yürütülüyor: {test_adi}")
        self.oynatma_penceresi.geometry("1100x650")
        
        self.log_frame = ctk.CTkFrame(self.oynatma_penceresi, width=350)
        self.log_frame.pack(side="left", fill="y", padx=10, pady=10)
        self.canli_log = ctk.CTkTextbox(self.log_frame, width=350, font=("Consolas", 12))
        self.canli_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.canli_log.insert("end", f"🚀 {test_adi} başlatılıyor...\n")
        
        threading.Thread(target=self.arka_planda_oynat, args=(test_adi,), daemon=True).start()

    def arka_planda_oynat(self, test_adi):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        def ekrana_yaz(mesaj):
            self.canli_log.insert("end", mesaj + "\n")
            self.canli_log.see("end")

        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT case_adi, aksiyonlar FROM case_bazli_testler WHERE ana_test_adi = ? ORDER BY id ASC", (test_adi,))
            cases = cursor.fetchall()
            conn.close()

            for c_adi, aksiyonlar in cases:
                dokunuslar = [n for n in aksiyonlar.split("|") if n]
                ekrana_yaz(f"⏳ '{c_adi}' uygulanıyor...")
                
                for nokta in dokunuslar:
                    ham_nokta = nokta.split(";;;")[0]
                    veriler = ham_nokta.split(",")
                    islem = veriler[0]

                    if islem == "T": 
                        subprocess.run([self.adb_yolu, "shell", "input", "tap", veriler[1], veriler[2]], creationflags=c_flags)
                        time.sleep(1)
                    elif islem == "S": 
                        subprocess.run([self.adb_yolu, "shell", "input", "swipe", veriler[1], veriler[2], veriler[3], veriler[4], veriler[5]], creationflags=c_flags)
                        time.sleep(1)
                    elif islem == "M":
                        subprocess.run([self.adb_yolu, "shell", "input", "tap", veriler[1], veriler[2]], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_yolu, "shell", "input", "text", ",".join(veriler[3:])], creationflags=c_flags)
                        time.sleep(1)
                    elif islem == "K":
                        subprocess.run([self.adb_yolu, "shell", "input", "tap", veriler[1], veriler[2]], creationflags=c_flags)
                        time.sleep(0.5)
                        subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                        for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                        time.sleep(1)

            ekrana_yaz(f"\n🎉 TÜM ADIMLAR BİTTİ!")
        except Exception as e: ekrana_yaz(f"\n❌ Hata: {str(e)}")

    def goster_raporlar(self):
        self.temizle()
        ctk.CTkLabel(self.main_frame, text="📊 Rapor Sistemi (Geliştiriliyor)", font=("Arial", 18, "bold")).pack(pady=10)

if __name__ == "__main__":
    app = TestOtomasyonApp()
    app.mainloop()