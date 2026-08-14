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
        "PIL": "pillow"
    }
    eksikler = []
    for modul_adi, pip_adi in gerekli_kutuphaneler.items():
        try:
            __import__(modul_adi)
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

        self.title("Appium Görsel Inspector & Kayıt Motoru (Gelişmiş)")
        self.geometry("1150x750")
        
        if getattr(sys, 'frozen', False):
            self.ana_dizin = os.path.dirname(sys.executable)
        else:
            self.ana_dizin = os.path.dirname(os.path.abspath(__file__))
            
        self.db_yolu = os.path.join(self.ana_dizin, "test_merkezi.db")
        self.adb_yolu = "adb" 
        
        self.hata_klasoru = os.path.join(self.ana_dizin, "hata_gorselleri")
        os.makedirs(self.hata_klasoru, exist_ok=True) 

        self.kayit_aktif = False
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
            versiyon TEXT, tarih TEXT, aksiyonlar TEXT)""")
        
        # Eğer eski tablo varsa yeni sütunları eklemeye çalış
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN versiyon TEXT")
        except sqlite3.OperationalError: pass
        try: cursor.execute("ALTER TABLE case_bazli_testler ADD COLUMN tarih TEXT")
        except sqlite3.OperationalError: pass
        
        conn.commit()
        conn.close()

    def aktif_uygulama_ve_versiyon_bul(self):
        pkg, ver = "", ""
        try:
            c_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            # Uygulama Paketini Bul
            res = subprocess.run([self.adb_yolu, "shell", "dumpsys", "window"], capture_output=True, text=True, creationflags=c_flags)
            match = re.search(r'mCurrentFocus=Window\{.*\s+([\w\.]+)/', res.stdout)
            if match:
                pkg = match.group(1)
                if pkg and pkg not in ["com.android.systemui", "com.android.launcher"]:
                    # Versiyonu Bul
                    res2 = subprocess.run([self.adb_yolu, "shell", "dumpsys", "package", pkg], capture_output=True, text=True, creationflags=c_flags)
                    v_match = re.search(r'versionName=(.*)', res2.stdout)
                    if v_match:
                        ver = v_match.group(1).strip()
        except: pass
        return pkg, ver

    def temizle(self):
        self.kayit_aktif = False
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
        
        # --- BİLGİ PANELİ ---
        info_frame = ctk.CTkFrame(self.main_frame, fg_color="#2c3e50")
        info_frame.pack(fill="x", padx=10, pady=(5,10))
        bilgi_metni = ("📌 NASIL KULLANILIR?\n"
                       "• Sol Tık: Tıklama yapar ve objenin XPath'ini otomatik kaydeder.\n"
                       "• Sürükle Bırak: Ekranı kaydırır (Swipe).\n"
                       "• Sağ Tık: O alana metin yazma veya içeriği temizleme menüsünü açar.")
        ctk.CTkLabel(info_frame, text=bilgi_metni, justify="left", font=("Arial", 13, "bold"), text_color="#f1c40f").pack(pady=10, padx=15, anchor="w")

        # --- FORM PANELİ ---
        form_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        form_frame.pack(fill="x", padx=10, pady=5)
        
        pkg, ver = self.aktif_uygulama_ve_versiyon_bul()
        aktif_kullanici = os.getlogin().capitalize() if hasattr(os, 'getlogin') else "Testçi"
        
        self.entry_ad = ctk.CTkEntry(form_frame, placeholder_text="Senaryo Adı (Örn: Login)", width=180)
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
        
        # --- BUTON PANELİ ---
        self.buton_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buton_frame.pack(pady=5)
        
        self.btn_baslat = ctk.CTkButton(self.buton_frame, text="▶️ INSPECTOR'I BAŞLAT", fg_color="green", hover_color="darkgreen", command=self.kaydi_tetikle)
        self.btn_baslat.grid(row=0, column=0, padx=5)
        self.btn_bitir = ctk.CTkButton(self.buton_frame, text="🛑 Kaydı Bitir (ESC)", fg_color="red", state="disabled", command=self.kaydi_bitir_islem)
        self.btn_bitir.grid(row=0, column=1, padx=5)

        # --- EKRAN VE LOG PANELİ ---
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
                # FORMAT: Islem;;;XPath;;;X;;;Y (X ve Y sadece OYNAT butonunda çalışsın diye saklanıyor, scriptte XPATH çıkacak)
                self.gecici_dokunuslar.append(f"T;;;{xpath};;;{gercek_x};;;{gercek_y}") 
                self.after(0, lambda: self.log_yaz(f"🎯 Tıkla (XPath): {xpath}"))
                
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
            threading.Thread(target=islem_yap).start()
            
        else: # KAYDIRMA
            fark_x = bitis_x - getattr(self, 'bas_x', 0)
            fark_y = bitis_y - getattr(self, 'bas_y', 0)
            yon = "down" if fark_y > 0 else "up"
            if abs(fark_x) > abs(fark_y): yon = "right" if fark_x > 0 else "left"
            
            # FORMAT: S;;;Yon;;;BasX;;;BasY;;;BitX;;;BitY
            self.gecici_dokunuslar.append(f"S;;;{yon};;;{gercek_bas_x};;;{gercek_bas_y};;;{gercek_x};;;{gercek_y}")
            self.after(0, lambda: self.log_yaz(f"👆 Kaydırma Eklendi: {yon}"))
            threading.Thread(target=lambda: subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(gercek_bas_x), str(gercek_bas_y), str(gercek_x), str(gercek_y), "400"], creationflags=c_flags)).start()

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
            # FORMAT: M;;;XPath;;;X;;;Y;;;Deger
            self.gecici_dokunuslar.append(f"M;;;{xpath};;;{gercek_x};;;{gercek_y};;;{val}")
            self.log_yaz(f"✍️ XPath'e Metin Eklendi: '{val}'")
            popup.destroy()
            
            def cihaza_yaz():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
            threading.Thread(target=cihaza_yaz).start()
            
        def sil():
            # FORMAT: K;;;XPath;;;X;;;Y
            self.gecici_dokunuslar.append(f"K;;;{xpath};;;{gercek_x};;;{gercek_y}")
            self.log_yaz(f"🧹 Silme İşlemi Eklendi")
            popup.destroy()
            
            def cihazdan_sil():
                subprocess.run([self.adb_yolu, "shell", "input", "tap", str(gercek_x), str(gercek_y)], creationflags=c_flags)
                time.sleep(0.5)
                subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
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
                              (ana_test_adi, yetkili, uygulama, versiyon, tarih, aksiyonlar) 
                              VALUES (?,?,?,?,?,?)""", 
                           (self.guncel_test_adi, self.guncel_yetkili, self.guncel_uygulama, self.guncel_versiyon, self.guncel_tarih, aksiyon_str))
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
    #   2. YÖNETİM, SİLME VE DIŞA AKTARIM
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
                
                # Butonlar
                ctk.CTkButton(satir, text="🗑️ Sil", width=60, fg_color="#c0392b", hover_color="#962d22", command=lambda i=t_id: self.testi_sil(i)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="✏️ Düzenle", width=80, fg_color="#F4A460", text_color="black", hover_color="#d68b49", command=lambda i=t_id, a=test_adi, y=yetk, u=uyg, v=ver: self.testi_duzenle_popup(i, a, y, u, v)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="▶️ Cihazda Oynat", width=120, fg_color="green", command=lambda i=t_id, a=test_adi: self.testi_oynat(i, a)).pack(side="right", padx=5, pady=10)
                ctk.CTkButton(satir, text="📤 Script Çıkar", width=130, fg_color="#2980b9", command=lambda i=t_id, a=test_adi: self.testi_disa_aktar(i, a)).pack(side="right", padx=5, pady=10)
        except Exception: pass

    def testi_sil(self, t_id):
        cevap = messagebox.askyesno("Onay", "Bu testi silmek istediğinize emin misiniz?")
        if cevap:
            conn = sqlite3.connect(self.db_yolu)
            conn.cursor().execute("DELETE FROM case_bazli_testler WHERE id = ?", (t_id,))
            conn.commit()
            conn.close()
            self.listeyi_guncelle()

    def testi_duzenle_popup(self, t_id, eski_ad, eski_yetkili, eski_uyg, eski_ver):
        popup = ctk.CTkToplevel(self)
        popup.title("Test Bilgilerini Düzenle")
        popup.geometry("350x350")
        popup.attributes("-topmost", True)
        
        yeni_ad_entry = ctk.CTkEntry(popup, width=250)
        yeni_ad_entry.insert(0, eski_ad)
        yeni_ad_entry.pack(pady=(20,10))
        
        yeni_yet_entry = ctk.CTkEntry(popup, width=250)
        yeni_yet_entry.insert(0, eski_yetkili if eski_yetkili else "")
        yeni_yet_entry.pack(pady=10)
        
        yeni_uyg_entry = ctk.CTkEntry(popup, width=250)
        yeni_uyg_entry.insert(0, eski_uyg if eski_uyg else "")
        yeni_uyg_entry.pack(pady=10)
        
        yeni_ver_entry = ctk.CTkEntry(popup, width=250)
        yeni_ver_entry.insert(0, eski_ver if eski_ver else "")
        yeni_ver_entry.pack(pady=10)
        
        def kaydet():
            conn = sqlite3.connect(self.db_yolu)
            conn.cursor().execute("UPDATE case_bazli_testler SET ana_test_adi=?, yetkili=?, uygulama=?, versiyon=? WHERE id=?", 
                                  (yeni_ad_entry.get(), yeni_yet_entry.get(), yeni_uyg_entry.get(), yeni_ver_entry.get(), t_id))
            conn.commit()
            conn.close()
            popup.destroy()
            self.listeyi_guncelle()
            
        ctk.CTkButton(popup, text="💾 Kaydet", fg_color="green", command=kaydet).pack(pady=10)

    # --- YENİLİK: CİHAZDA LOKAL OLARAK CANLI OYNATMA (PLAYBACK) ---
    def testi_oynat(self, t_id, test_adi):
        self.oynatma_penceresi = ctk.CTkToplevel(self)
        self.oynatma_penceresi.title(f"Test Yürütülüyor: {test_adi}")
        self.oynatma_penceresi.geometry("400x500")
        self.oynatma_penceresi.attributes("-topmost", True)
        
        log_kutusu = ctk.CTkTextbox(self.oynatma_penceresi, font=("Consolas", 12))
        log_kutusu.pack(fill="both", expand=True, padx=10, pady=10)
        log_kutusu.insert("end", f"🚀 {test_adi} cihazda çalıştırılıyor...\n\n")

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
            
            for idx, nokta in enumerate(dokunuslar):
                parts = nokta.split(";;;")
                islem = parts[0]
                
                if islem == "T":
                    # T;;;XPath;;;X;;;Y
                    xpath, x, y = parts[1], parts[2], parts[3]
                    self.after(0, lambda i=idx: log_kutusu.insert("end", f"[{i+1}] Tıklanıyor...\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(1)
                elif islem == "M":
                    # M;;;XPath;;;X;;;Y;;;Deger
                    xpath, x, y, val = parts[1], parts[2], parts[3], parts[4]
                    self.after(0, lambda i=idx, v=val: log_kutusu.insert("end", f"[{i+1}] Yazılıyor: {v}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "text", str(val)], creationflags=c_flags)
                    time.sleep(1)
                elif islem == "S":
                    # S;;;Yon;;;BasX;;;BasY;;;BitX;;;BitY
                    yon, b_x, b_y, s_x, s_y = parts[1], parts[2], parts[3], parts[4], parts[5]
                    self.after(0, lambda i=idx, y=yon: log_kutusu.insert("end", f"[{i+1}] Kaydırılıyor: {y}\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "swipe", str(b_x), str(b_y), str(s_x), str(s_y), "400"], creationflags=c_flags)
                    time.sleep(1)
                elif islem == "K":
                    # K;;;XPath;;;X;;;Y
                    xpath, x, y = parts[1], parts[2], parts[3]
                    self.after(0, lambda i=idx: log_kutusu.insert("end", f"[{i+1}] Siliniyor...\n"))
                    subprocess.run([self.adb_yolu, "shell", "input", "tap", str(x), str(y)], creationflags=c_flags)
                    time.sleep(0.5)
                    subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "123"], creationflags=c_flags)
                    for _ in range(25): subprocess.run([self.adb_yolu, "shell", "input", "keyevent", "67"], creationflags=c_flags)
                    time.sleep(1)
                    
            self.after(0, lambda: log_kutusu.insert("end", "\n🎉 TEST BİTTİ!"))

        threading.Thread(target=oynat_dongusu, daemon=True).start()

    # --- SIFIR KOORDİNAT - %100 XPATH TEMPLATE EXPORT ---
    def testi_disa_aktar(self, t_id, test_adi):
        try:
            conn = sqlite3.connect(self.db_yolu)
            cursor = conn.cursor()
            cursor.execute("SELECT aksiyonlar, uygulama FROM case_bazli_testler WHERE id = ?", (t_id,))
            satir = cursor.fetchone()
            conn.close()
            if not satir or not satir[0]: return
            
            app_pkg = satir[1] if satir[1] else "com.example.app"
            
            gen_code = "import time\nfrom appium import webdriver\nfrom appium.options.android import UiAutomator2Options\nfrom appium.webdriver.common.appiumby import AppiumBy\nfrom selenium.webdriver.support.ui import WebDriverWait\nfrom selenium.webdriver.support import expected_conditions as EC\n\n"
            
            gen_code += "def obje_bul(driver, xpath, timeout=10):\n    wait = WebDriverWait(driver, timeout)\n    return wait.until(EC.presence_of_element_located((AppiumBy.XPATH, xpath)))\n\n"
            
            gen_code += f"options = UiAutomator2Options()\noptions.app_package = '{app_pkg}'\noptions.no_reset = True\n"
            gen_code += "driver = webdriver.Remote('http://127.0.0.1:4723', options=options)\n\n"

            fonk_ismi = f"Test_{test_adi.replace(' ', '_')}_{t_id}"
            gen_code += f"def {fonk_ismi}():\n"
            
            dokunuslar = [n for n in satir[0].split("|") if n]
            for nokta in dokunuslar:
                parts = nokta.split(";;;")
                islem = parts[0]
                
                if islem == "T":
                    xpath = parts[1]
                    gen_code += f"    # Tıklama Adımı\n"
                    gen_code += f"    obje_bul(driver, r'''{xpath}''').click()\n    time.sleep(1)\n\n"
                elif islem == "M":
                    xpath, val = parts[1], parts[4]
                    gen_code += f"    # Metin Yazma Adımı\n"
                    gen_code += f"    kutu = obje_bul(driver, r'''{xpath}''')\n"
                    gen_code += f"    kutu.click()\n    kutu.clear()\n    kutu.send_keys('{val}')\n    time.sleep(1)\n\n"
                elif islem == "S":
                    yon = parts[1]
                    gen_code += f"    # Kaydırma İşlemi (Swipe {yon})\n"
                    gen_code += f"    driver.execute_script('mobile: scroll', {{'direction': '{yon}'}})\n    time.sleep(1)\n\n"
                elif islem == "K":
                    xpath = parts[1]
                    gen_code += f"    # İçerik Silme Adımı\n"
                    gen_code += f"    kutu = obje_bul(driver, r'''{xpath}''')\n"
                    gen_code += f"    kutu.click()\n    kutu.clear()\n    time.sleep(1)\n\n"

            gen_code += "try:\n" + f"    {fonk_ismi}()\n" + "finally:\n    driver.quit()\n"

            dosya_yolu = filedialog.asksaveasfilename(defaultextension=".py", initialfile=f"{fonk_ismi}_Appium.py", title="Appium Scripti Kaydet")
            if dosya_yolu:
                with open(dosya_yolu, "w", encoding="utf-8") as f: f.write(gen_code)
                messagebox.showinfo("Başarılı", f"Sıfır koordinatlı saf XPath Appium scripti üretildi!\nDosya: {dosya_yolu}")
        except Exception as e: messagebox.showerror("Hata", f"Dışa aktarma başarısız: {e}")

if __name__ == "__main__":
    app = TestOtomasyonApp()
    app.mainloop()