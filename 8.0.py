import sys
import subprocess
import os

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

class TestOtomasyonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Appium Görsel Inspector & Raporlama Motoru (PRO)")
        self.geometry("1150x750")
        
        if getattr(sys, 'frozen', False): self.ana_dizin = os.path.dirname(sys.executable)
        else: self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
            
        self.db_yolu = os.path.join(self.ana_dizin, "test_merkezi.db")
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

        self.cihaz_cozunurlugunu_al()
        self.veritabanini_hazirla()

        # --- ARAYÜZ KURULUMU ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="INSPECTOR PRO", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.pack(pady=20, padx=10)

        self.btn_kayit_ekran = ctk.CTkButton(self.sidebar_frame, text="📸 Yeni Görsel Kayıt", command=self.goster_kayit)
        self.btn_kayit_ekran.pack(pady=10, padx=20)

        self.btn_liste_ekran = ctk.CTkButton(self.sidebar_frame, text="📂 Testleri Yönet", command=self.goster_liste)
        self.btn_liste_ekran.pack(pady=10, padx=20)

        self.btn_rapor_ekran = ctk.CTkButton(self.sidebar_frame, text="📊 Test Raporları", fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=self.goster_raporlar)
        self.btn_rapor_ekran.pack(pady=10, padx=20)

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
        lbl = ctk.CTkLabel(self.main_frame, text="XPath Tabanlı Appium Inspector'a Hoş Geldiniz!\n'Yeni Görsel Kayıt' sekmesiyle işlemlere başlayabilirsiniz.", font=("Arial", 16))
        lbl.pack(expand=True)

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
        
        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="▶️ INSPECTOR'I BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
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
        self.log_kutusu.insert("0.0", "Inspector Hazır. İşlemleriniz XML XPath olarak kaydedilecektir.\n")

    def ekran_yayini_dongusu(self):
        c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        temp_gorsel_yolu = os.path.join(self.hata_klasoru, "temp_canli_ekran.png")
        while self.kayit_aktif:
            try:
                subprocess.run([self.adb_yolu, "shell", "screencap", "-p", "/sdcard/temp_canli.png"], capture_output=True, creationflags=c_flags)
                subprocess.run([self.adb_yolu, "pull", "/sdcard/temp_canli.png", temp_gorsel_yolu], capture_output=True, creationflags=c_flags)
                if os.path.exists(temp_gorsel_yolu):
                    img = Image.open(temp_gorsel_yolu)
                    img_resized = img.resize((self.ui_w, self.ui_h))
                    ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(self.ui_w, self.ui_h))
                    self.after(0, lambda resim=ctk_img: self.lbl_ekran.configure(image=resim, text=""))
            except Exception: pass
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
        """Sonraki adımların kıyaslanması için aksiyon sonrası referans fotoğraf kaydeder."""
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

        if mesafe < 30: # TIKLAMA
            self.after(0, lambda: self.log_yaz("🔍 Obje taranıyor..."))
            def islem_yap():
                xpath = self.xpath_hedef_bul(gercek_x, gercek_y)
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(1.5) # Ekranın yüklenmesini bekle
                ref_isim = self.referans_ekran_al()
                
                # FORMAT: T;;;XPath;;;X;;;Y;;;RefImg
                self.gecici_dokunuslar.append(f"T;;;{xpath};;;{gercek_x};;;{gercek_y};;;{ref_isim}") 
                self.after(0, lambda: self.log_yaz(f"🎯 Tıkla (XPath): {xpath}"))
            threading.Thread(target=islem_yap).start()
            
        else: # KAYDIRMA
            fark_x = bitis_x - getattr(self, 'bas_x', 0)
            fark_y = bitis_y - getattr(self, 'bas_y', 0)
            yon = "down" if fark_y > 0 else "up"
            if abs(fark_x) > abs(fark_y): yon = "right" if fark_x > 0 else "left"
            
            def kaydir_yap():
                subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(gercek_bas_x), str(gercek_bas_y), str(gercek_x), str(gercek_y), "400"], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                # FORMAT: S;;;Yon;;;BasX;;;BasY;;;BitX;;;BitY;;;RefImg
                self.gecici_dokunuslar.append(f"S;;;{yon};;;{gercek_bas_x};;;{gercek_bas_y};;;{gercek_x};;;{gercek_y};;;{ref_isim}")
                self.after(0, lambda: self.log_yaz(f"👆 Kaydırma Eklendi: {yon}"))
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
            val = veri_girisi.get()
            if not val: return
            popup.destroy()
            def cihaza_yaz():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                time.sleep(1.5)
                ref_isim = self.referans_ekran_al()
                # FORMAT: M;;;XPath;;;X;;;Y;;;Deger;;;RefImg
                self.gecici_dokunuslar.append(f"M;;;{xpath};;;{gercek_x};;;{gercek_y};;;{val};;;{ref_isim}")
                self.after(0, lambda: self.log_yaz(f"✍️ XPath'e Metin Eklendi: '{val}'"))
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
                # FORMAT: K;;;XPath;;;X;;;Y;;;RefImg
                self.gecici_dokunuslar.append(f"K;;;{xpath};;;{gercek_x};;;{gercek_y};;;{ref_isim}")
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
        
        self.log_yaz(f"\n🚀 '{self.guncel_test_adi}' Inspector devrede!\nEkrana tıklayarak adımları kaydedebilirsiniz.")
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
            self.log_yaz("\n🎉 KAYIT TAMAMLANDI! Testleri Yönet sekmesinden dışa aktarabilirsiniz.\n")
        except Exception: pass

    def log_yaz(self, mesaj):
        self.log_kutusu.insert("end", mesaj + "\n")
        self.log_kutusu.see("end")

    # ==========================================
    #   2. YÖNETİM VE LOKAL OYNATMA (GÖRSEL KIYASLAMA)
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
        except Exception:
            return 0.0, check_yol

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
        
        # Sol Log Çerçevesi
        log_frame = ctk.CTkFrame(self.oynatma_penceresi, width=350)
        log_frame.pack(side="left", fill="y", padx=10, pady=10)
        btn_durdur = ctk.CTkButton(log_frame, text="🛑 ACİL DURDUR", fg_color="red", command=self.oynatmayi_durdur)
        btn_durdur.pack(pady=10)
        log_kutusu = ctk.CTkTextbox(log_frame, width=350, font=("Consolas", 12))
        log_kutusu.pack(fill="both", expand=True, padx=5, pady=5)
        log_kutusu.insert("end", f"🚀 {test_adi} başlatılıyor...\n\n")

        # Sağ Görüntü Çerçevesi
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
            basarili_adim = 0
            toplam_adim = len(dokunuslar)
            adim_raporlari = []
            dongu_iptal = False
            
            log_dosya_adi = f"log_{test_adi.replace(' ', '_')}_{int(time.time())}.txt"
            log_yolu = os.path.join(self.log_klasoru, log_dosya_adi)
            subprocess.run([self.adb_yolu, "logcat", "-c"], creationflags=c_flags)
            log_dosyasi = open(log_yolu, "w", encoding="utf-8")
            log_proc = subprocess.Popen([self.adb_yolu, "logcat", "-v", "threadtime"], stdout=log_dosyasi, creationflags=c_flags)

            for idx, nokta in enumerate(dokunuslar):
                if not self.playback_aktif:
                    self.after(0, lambda: log_kutusu.insert("end", "\n🛑 TEST KULLANICI TARAFINDAN İPTAL EDİLDİ!"))
                    dongu_iptal = True
                    break

                parts = nokta.split(";;;")
                islem = parts[0]
                ref_isim = parts[-1] 
                
                if islem == "T":
                    x, y = parts[2], parts[3]
                    self.after(0, lambda i=idx: log_kutusu.insert("end", f"[{i+1}] Tıklanıyor...\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                elif islem == "M":
                    x, y, val = parts[2], parts[3], parts[4]
                    self.after(0, lambda i=idx, v=val: log_kutusu.insert("end", f"[{i+1}] Yazılıyor: {v}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                elif islem == "S":
                    yon, b_x, b_y, s_x, s_y = parts[1], parts[2], parts[3], parts[4], parts[5]
                    self.after(0, lambda i=idx, y=yon: log_kutusu.insert("end", f"[{i+1}] Kaydırılıyor: {y}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(b_x), str(b_y), str(s_x), str(s_y), "400"], creationflags=c_flags)
                elif islem == "K":
                    x, y = parts[2], parts[3]
                    self.after(0, lambda i=idx: log_kutusu.insert("end", f"[{i+1}] Siliniyor...\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                    for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                
                time.sleep(1.5) # İşlem sonrası ekranın oturmasını bekle
                self.after(0, lambda i=idx: log_kutusu.insert("end", f"🔍 Kıyaslanıyor...\n"))
                
                # Cihazdan güncel check ekranını çek
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
                        adim_raporlari.append(f"✅ Adım {idx+1} - BAŞARILI (Benzerlik: %{skor_yuzde})")
                        self.after(0, lambda: log_kutusu.insert("end", f"✅ Benzerlik: %{skor_yuzde}\n"))
                    else:
                        foto_isim = f"hata_{test_adi.replace(' ', '_')}_Adim{idx+1}_{int(time.time())}.png"
                        foto_yol = os.path.join(self.hata_klasoru, foto_isim)
                        if os.path.exists(isaretli_yol): os.rename(isaretli_yol, foto_yol)
                        adim_raporlari.append(f"❌ Adım {idx+1} - BAŞARISIZ (Benzerlik: %{skor_yuzde}) | IMG:{foto_yol}")
                        self.after(0, lambda: log_kutusu.insert("end", "\n🛑 HATA TESPİT EDİLDİ! Test durduruluyor..."))
                        dongu_iptal = True
                        break
                else:
                    adim_raporlari.append(f"⚠️ Adım {idx+1} - REFERANS BULUNAMADI")
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

    # --- 3. STREAMLIT UYUMLU ŞABLONLA XPATH TABANLI EXPORT ---
    def testi_disa_aktar(self, t_id, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar, uygulama, yetkili, versiyon, tarih, telefon_modeli FROM case_bazli_testler WHERE id = ?", (t_id,))
            satir = cursor.fetchone()
            conn.close()
            if not satir or not satir[0]: return
            
            app_pkg = satir[1] if satir[1] else "com.example.app"
            yetkili = satir[2] if satir[2] else ""
            versiyon = satir[3] if satir[3] else ""
            tarih = satir[4] if satir[4] else ""
            telefon = satir[5] if satir[5] else ""
            
            fonk_ismi = f"{test_adi.replace(' ', '_')}_{t_id}"
            stream_cases = []
            case_obj = {"name": fonk_ismi, "steps": []}
            
            dokunuslar = [n for n in satir[0].split("|") if n]
            for idx, nokta in enumerate(dokunuslar):
                parts = nokta.split(";;;")
                islem = parts[0]
                
                step_obj = {"step_name": f"Adım {idx+1}", "action": "Tıkla", "xpath": "", "val": "", "count": 1, "direction": "Aşağı", "x": 0, "y": 0, "sys_key": "", "exact_match": False}
                
                if islem == "T":
                    step_obj["action"] = "Tıkla"
                    step_obj["xpath"] = parts[1]
                    step_obj["step_name"] = f"Tıkla: {parts[1].split('/')[-1][:15]}" if parts[1] else f"Adım {idx+1}"
                    if parts[1].startswith("//"): step_obj["exact_match"] = True
                elif islem == "M":
                    step_obj["action"] = "Metin Yaz"
                    step_obj["xpath"] = parts[1]
                    step_obj["val"] = parts[4]
                    step_obj["step_name"] = f"Yaz: '{parts[4]}'"
                    if parts[1].startswith("//"): step_obj["exact_match"] = True
                elif islem == "S":
                    step_obj["action"] = "Kaydır (Swipe)"
                    yon_tr = {"down": "Aşağı", "up": "Yukarı", "right": "Sağa", "left": "Sola"}.get(parts[1], "Aşağı")
                    step_obj["direction"] = yon_tr
                    step_obj["step_name"] = f"Kaydır: {yon_tr}"
                elif islem == "K":
                    step_obj["action"] = "Sistem Tuşu"
                    step_obj["sys_key"] = "Kutuyu Temizle"
                    step_obj["xpath"] = parts[1]
                    step_obj["step_name"] = "İçeriği Sil"
                    if parts[1].startswith("//"): step_obj["exact_match"] = True
                    
                case_obj["steps"].append(step_obj)
            stream_cases.append(case_obj)

            gen_code = f"""import time
import requests
import json
import re
import os
import threading
import logging
import sys
from datetime import datetime, timezone
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.action_builder import ActionBuilder
from selenium.webdriver.common.actions.pointer_input import PointerInput
from selenium.webdriver.common.actions import interaction
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

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

def akilli_element_bulucu(driver, locator, timeout=10):
    locator = str(locator).strip()
    if not locator: raise Exception("Hedef veri (XPath/ID) bos birakilmis!")
    wait = WebDriverWait(driver, timeout)
    try:
        if locator.startswith('//') or locator.startswith('(') or locator.startswith('hierarchy'):
            return wait.until(EC.presence_of_element_located((AppiumBy.XPATH, locator)))
        return wait.until(EC.presence_of_element_located((AppiumBy.ID, locator)))
    except Exception as e:
        print(f"\\n❌ HATA: Element bulunamadı!\\nBeklenen XPath: {{locator}}")
        driver.save_screenshot('hata_ekrani.png')
        print("📸 Hata anının ekran görüntüsü kaydedildi: hata_ekrani.png")
        sys.exit(1)

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

options = UiAutomator2Options()
"""
            gen_code += f"options.app_package = '{app_pkg}'\n"
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
                    
                    gen_code += f"        api_logger.log_message('Adım başlatılıyor: {s_name}...')\n"
                    finder = f"driver.find_element(by=AppiumBy.XPATH, value=r'''{xp}''')" if exact else f"akilli_element_bulucu(driver, r'''{xp}''')"
                    
                    if act == "Tıkla":
                        gen_code += f"        {finder}.click()\n        time.sleep(1)\n"
                    elif act == "Kaydır (Swipe)":
                        s_dir = {"Aşağı": "down", "Yukarı": "up", "Sağa": "right", "Sola": "left"}.get(step.get('direction','Aşağı'))
                        gen_code += f"        for _ in range({step.get('count',1)}):\n            ekran_kaydir(driver, '{s_dir}', {step.get('x',0)}, {step.get('y',0)})\n            time.sleep(0.5)\n"
                    elif act == "Metin Yaz":
                        safe_val = step.get("val", "").replace("'", "\\'")
                        gen_code += f"        kutu = {finder}\n        kutu.click(); time.sleep(0.5)\n        kutu.clear(); kutu.send_keys('{safe_val}'); time.sleep(1)\n"
                    elif act == "Sistem Tuşu":
                        if step.get("sys_key") == "Kutuyu Temizle":
                            gen_code += f"        kutu = {finder}\n        kutu.clear(); time.sleep(1)\n"
                        elif step.get("sys_key") == "Fiziksel Sil (Backspace)":
                            gen_code += f"        kutu = {finder}\n        kutu.click(); time.sleep(0.5)\n        driver.press_keycode(123)\n        for _ in range(25): driver.press_keycode(67)\n        time.sleep(1)\n"
                    
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
    #   4. RAPORLAMA VE ZIP ÇIKTISI
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
            rapor_icerik = "="*55 + "\n           OTOMASYON TEST SONUÇ RAPORU\n" + "="*55 + "\n\n"
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
    app = TestOtomasyonApp()
    app.mainloop()